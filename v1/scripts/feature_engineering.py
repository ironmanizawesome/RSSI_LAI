"""
Step 4: RSSI 특징량 5가지 생성 → data/rssi_daily.csv
필터: -100 <= RSSI <= 0 dBm, 0 <= temp <= 60°C, 0 <= rh <= 100%
"""

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).parent.parent
OUT_DIR = ROOT / "data"

# ── 데이터 로드 ───────────────────────────────────────────────────────────────
rssi = pd.read_csv(OUT_DIR / "rssi_raw.csv", parse_dates=["datetime"])
lai_daily = pd.read_csv(OUT_DIR / "lai_daily.csv", parse_dates=["date"])

# ── 이상값 필터 ───────────────────────────────────────────────────────────────
before = len(rssi)
rssi = rssi[
    (rssi["rssi_dbm"] >= -100)
    & (rssi["rssi_dbm"] <= 0)
    & (rssi["temp_c"] >= 0)
    & (rssi["temp_c"] <= 60)
    & (rssi["rh_pct"] >= 0)
    & (rssi["rh_pct"] <= 100)
].copy()
print(f"필터 후: {before:,} → {len(rssi):,}행 ({before - len(rssi)}건 제거)")


# ── 절대습도 계산 ─────────────────────────────────────────────────────────────
def rh_to_ah(temp_c, rh_pct):
    e = 6.112 * np.exp(17.67 * temp_c / (temp_c + 243.5))
    return 216.7 * (e * rh_pct / 100) / (273.15 + temp_c)


rssi["ah"] = rh_to_ah(rssi["temp_c"], rssi["rh_pct"])
rssi["date"] = rssi["datetime"].dt.date
rssi["date"] = pd.to_datetime(rssi["date"])

# ── 링크 식별자 ───────────────────────────────────────────────────────────────
rssi["link"] = rssi["link_from"].astype(str) + "_to_" + rssi["link_to"].astype(str)

links = rssi["link"].unique()
print(f"링크 수: {len(links)}")

# ── 환경보정 잔차 계산 (야간 데이터로 모델 적합 → 전체 데이터에 적용) ────────────
# 야간(22~06시): 캐노피 존재해도 식생 효과 최소 → 환경 계수를 LAI 오염 없이 추정
rssi["hour"] = rssi["datetime"].dt.hour
night_mask = (rssi["hour"] >= 22) | (rssi["hour"] < 6)

residual_records = []
night_n_list = []
for lk in links:
    sub = rssi[rssi["link"] == lk].copy()
    night = sub[night_mask[sub.index]]

    X_night = np.column_stack([np.ones(len(night)), night[["temp_c", "ah"]].values])
    y_night = night["rssi_dbm"].values

    # 야간 데이터로 환경 모델 적합
    try:
        if len(night) >= 10:
            slope, _, _, _ = np.linalg.lstsq(X_night, y_night, rcond=None)
        else:
            # 야간 데이터 부족 시 전체 데이터로 fallback
            X_all = np.column_stack([np.ones(len(sub)), sub[["temp_c", "ah"]].values])
            slope, _, _, _ = np.linalg.lstsq(X_all, sub["rssi_dbm"].values, rcond=None)

        # 전체 데이터에 계수 적용
        X_all = np.column_stack([np.ones(len(sub)), sub[["temp_c", "ah"]].values])
        y_pred = X_all @ slope
    except Exception:
        y_pred = np.full(len(sub), np.nan)

    sub = sub.copy()
    sub["rssi_residual_raw"] = sub["rssi_dbm"].values - y_pred
    night_n_list.append((lk, len(night)))
    residual_records.append(sub[["datetime", "link", "rssi_residual_raw"]])

print(f"\n야간 기반 환경 모델 적합 완료")
print(
    f"  야간 데이터 10건 미만(fallback) 링크 수: {sum(1 for _, n in night_n_list if n < 10)}"
)

residual_df = pd.concat(residual_records, ignore_index=True)
rssi = rssi.merge(residual_df, on=["datetime", "link"], how="left")

# ── 일별 집계 ─────────────────────────────────────────────────────────────────
daily_records = []
for lk in links:
    sub = rssi[rssi["link"] == lk].sort_values("datetime").copy()
    daily = (
        sub.groupby("date")
        .agg(
            rssi_raw=("rssi_dbm", "mean"),
            rssi_residual=("rssi_residual_raw", "mean"),
        )
        .reset_index()
    )

    # 7일 rolling (min_periods=3)
    daily = daily.sort_values("date").reset_index(drop=True)
    daily["rssi_ma7"] = daily["rssi_raw"].rolling(7, min_periods=3).mean()
    daily["rssi_delta"] = daily["rssi_raw"].diff()
    daily["rssi_std7"] = daily["rssi_raw"].rolling(7, min_periods=3).std()

    daily["link"] = lk
    daily_records.append(daily)

rssi_daily = pd.concat(daily_records, ignore_index=True)

# ── LAI 병합 ─────────────────────────────────────────────────────────────────
rssi_daily = rssi_daily.merge(
    lai_daily[["date", "lai_median", "lai_mean", "lai_std"]],
    on="date",
    how="left",
)

rssi_daily = rssi_daily.sort_values(["link", "date"]).reset_index(drop=True)
rssi_daily.to_csv(OUT_DIR / "rssi_daily.csv", index=False)

# ── 결측값 비율 ───────────────────────────────────────────────────────────────
feat_cols = ["rssi_raw", "rssi_ma7", "rssi_delta", "rssi_std7", "rssi_residual"]
print("\n[처리 방식별 결측값 비율 (LAI 있는 날짜 기준)]")
has_lai = rssi_daily[rssi_daily["lai_median"].notna()]
for col in feat_cols:
    miss = has_lai[col].isna().mean() * 100
    print(f"  {col:20s}: {miss:.1f}%")

print(f"\nrssi_daily.csv: {len(rssi_daily):,}행, {rssi_daily['link'].nunique()}개 링크")
print(
    f"날짜 범위: {rssi_daily['date'].min().date()} ~ {rssi_daily['date'].max().date()}"
)

# ── 주요 링크 확인 ─────────────────────────────────────────────────────────────
print("\n[주요 링크 일별 RSSI 샘플 - A<->GW (9_to_1)]")
agw = rssi_daily[rssi_daily["link"] == "9_to_1"][
    ["date", "rssi_raw", "rssi_ma7", "rssi_residual", "lai_median"]
]
print(agw.dropna(subset=["rssi_raw"]).head(10).to_string(index=False))
