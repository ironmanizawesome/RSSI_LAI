"""
세션 3: RSSI 특징량 5가지 생성 + LAI/환경변수 병합 → v2/data/features_merged.csv
주 분석 링크: A↔GW (1↔9, 23m, CAT2), B↔GW (2↔9, 22.5m, CAT2), D↔GW (6↔9, 22m, CAT2)
  → GW(sensor_9) 관점, 전 기간 72일 가용
특징량: rssi_raw, rssi_ma7, rssi_delta, rssi_std7, rssi_residual
"""

from pathlib import Path

import numpy as np
import pandas as pd

V2_ROOT = Path(__file__).parent.parent
DATA_DIR = V2_ROOT / "data"

TARGET_LINKS = {
    (1, 9): "A_GW",
    (2, 9): "B_GW",
    (6, 9): "D_GW",
}


def rh_to_ah(temp_c: pd.Series, rh_pct: pd.Series) -> pd.Series:
    e = 6.112 * np.exp(17.67 * temp_c / (temp_c + 243.5))
    return 216.7 * (e * rh_pct / 100) / (273.15 + temp_c)


# ── 데이터 로드 ────────────────────────────────────────────────────────────────
rssi = pd.read_csv(DATA_DIR / "rssi_raw.csv", parse_dates=["datetime"])
lai_daily = pd.read_csv(DATA_DIR / "lai_daily.csv", parse_dates=["date"])
env_daily = pd.read_csv(DATA_DIR / "env_daily.csv", parse_dates=["date"])

# 주 분석 링크 필터 (G↔GW, H↔GW)
rssi["link_key"] = rssi.apply(
    lambda r: tuple(sorted([r["link_from"], r["link_to"]])), axis=1
)
rssi = rssi[rssi["link_key"].isin(TARGET_LINKS.keys())].copy()
rssi["link"] = rssi["link_key"].map(TARGET_LINKS)
rssi["date"] = pd.to_datetime(rssi["datetime"].dt.date)
rssi["hour"] = rssi["datetime"].dt.hour
rssi["ah"] = rh_to_ah(rssi["temp_c"], rssi["rh_pct"])

print(f"주 분석 링크 레코드: {len(rssi):,}행")
for lk in ["A_GW", "B_GW", "D_GW"]:
    n = (rssi["link"] == lk).sum()
    print(f"  {lk}: {n:,}건")

# ── 야간 OLS 잔차 계산 (방식 B) ───────────────────────────────────────────────
# 야간(22~06시): 식생 영향 최소 → 환경-RSSI 관계를 LAI 오염 없이 학습
# ⚠️ 전체 기간 OLS 금지 (계절 공변동으로 LAI 신호 흡수)
night_mask = (rssi["hour"] >= 22) | (rssi["hour"] < 6)

residual_parts = []
for lk in ["A_GW", "B_GW", "D_GW"]:
    sub = rssi[rssi["link"] == lk].copy()
    night = sub[night_mask[sub.index]]

    X_night = np.column_stack(
        [np.ones(len(night)), night[["temp_c", "ah"]].values]
    )
    y_night = night["rssi_dbm"].values

    try:
        if len(night) >= 10:
            coef, _, _, _ = np.linalg.lstsq(X_night, y_night, rcond=None)
            print(f"\n[{lk}] 야간 OLS: n={len(night)}, "
                  f"β0={coef[0]:.2f}, βT={coef[1]:.3f}, βAH={coef[2]:.3f}")
        else:
            X_all = np.column_stack(
                [np.ones(len(sub)), sub[["temp_c", "ah"]].values]
            )
            coef, _, _, _ = np.linalg.lstsq(X_all, sub["rssi_dbm"].values, rcond=None)
            print(f"\n[{lk}] 야간 데이터 부족({len(night)}건), 전체 기간 fallback 사용")

        X_all = np.column_stack(
            [np.ones(len(sub)), sub[["temp_c", "ah"]].values]
        )
        y_pred = X_all @ coef
    except Exception as exc:
        print(f"[{lk}] OLS 실패: {exc}")
        y_pred = np.full(len(sub), np.nan)

    sub = sub.copy()
    sub["rssi_residual_raw"] = sub["rssi_dbm"].values - y_pred
    residual_parts.append(sub[["datetime", "link", "rssi_residual_raw"]])

residual_df = pd.concat(residual_parts, ignore_index=True)
rssi = rssi.merge(residual_df, on=["datetime", "link"], how="left")

# ── 링크별 일별 집계 ──────────────────────────────────────────────────────────
daily_parts = []
for lk in ["A_GW", "B_GW", "D_GW"]:
    sub = rssi[rssi["link"] == lk].sort_values("datetime").copy()
    daily = (
        sub.groupby("date")
        .agg(
            rssi_raw=("rssi_dbm", "mean"),
            rssi_residual=("rssi_residual_raw", "mean"),
        )
        .reset_index()
        .sort_values("date")
        .reset_index(drop=True)
    )
    daily["rssi_ma7"] = daily["rssi_raw"].rolling(7, min_periods=3).mean()
    daily["rssi_delta"] = daily["rssi_raw"].diff()
    daily["rssi_std7"] = daily["rssi_raw"].rolling(7, min_periods=3).std()
    daily["link"] = lk
    daily_parts.append(daily)

rssi_daily_all = pd.concat(daily_parts, ignore_index=True)

# ── 두 링크 일별 평균 (G_H_mean) ─────────────────────────────────────────────
feat_cols = ["rssi_raw", "rssi_ma7", "rssi_delta", "rssi_std7", "rssi_residual"]
rssi_mean = (
    rssi_daily_all.groupby("date")[feat_cols]
    .mean()
    .reset_index()
)

# ── LAI 병합 ─────────────────────────────────────────────────────────────────
merged = rssi_mean.merge(
    lai_daily[["date", "lai_median", "lai_std", "count"]],
    on="date",
    how="outer",
)

# ── 환경변수 병합 (ABD_mean) ──────────────────────────────────────────────────
env_mean = env_daily[env_daily["link"] == "ABD_mean"][
    ["date", "temp_mean", "rh_mean", "ah_mean"]
]
merged = merged.merge(env_mean, on="date", how="left")
merged = merged.sort_values("date").reset_index(drop=True)

# 컬럼 순서 정리
col_order = [
    "date", "lai_median", "lai_std", "count",
    "rssi_raw", "rssi_ma7", "rssi_delta", "rssi_std7", "rssi_residual",
    "temp_mean", "rh_mean", "ah_mean",
]
merged = merged[col_order]
merged.to_csv(DATA_DIR / "features_merged.csv", index=False)

# ── 결측값 비율 ───────────────────────────────────────────────────────────────
print("\n[컬럼별 결측값 비율]")
for col in col_order[1:]:
    miss = merged[col].isna().mean() * 100
    print(f"  {col:20s}: {miss:.1f}%")

# 분석 가능 행 수 (모든 컬럼 non-null)
analysis_cols = ["lai_median", "rssi_raw", "rssi_ma7", "rssi_delta",
                 "rssi_std7", "rssi_residual", "temp_mean", "rh_mean", "ah_mean"]
complete = merged.dropna(subset=analysis_cols)
print(f"\nfeatures_merged.csv: 전체 {len(merged)}행")
print(f"분석 가능 행 수 (모든 컬럼 non-null): {len(complete)}행")
print(f"날짜 범위: {merged['date'].min().date()} ~ {merged['date'].max().date()}")

print("\n[분석 가능 행 샘플 (상위 10행)]")
print(complete[["date", "lai_median", "rssi_raw", "rssi_residual", "temp_mean", "ah_mean"]]
      .head(10).to_string(index=False))
