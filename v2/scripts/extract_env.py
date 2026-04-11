"""
세션 2 - Step 2: 주 분석 링크 대상 일별 환경변수 집계 → v2/data/env_daily.csv
주 분석 링크: A↔GW (1↔9, 23m, CAT2), B↔GW (2↔9, 22.5m, CAT2), D↔GW (6↔9, 22m, CAT2)
  → GW(sensor_9) 관점에서 전 기간(72일) 가용
출력 컬럼: date, link, temp_mean, rh_mean, ah_mean
"""

from pathlib import Path

import numpy as np
import pandas as pd

V2_ROOT = Path(__file__).parent.parent
DATA_DIR = V2_ROOT / "data"

# ground-above CAT2 링크 (GW 관점, 72일 가용)
TARGET_LINKS = {
    (1, 9): "A_GW",
    (2, 9): "B_GW",
    (6, 9): "D_GW",
}


def rh_to_ah(temp_c: pd.Series, rh_pct: pd.Series) -> pd.Series:
    """절대습도 계산 (Bauer 2020 Eq.1, Magnus 공식)"""
    e = 6.112 * np.exp(17.67 * temp_c / (temp_c + 243.5))
    return 216.7 * (e * rh_pct / 100) / (273.15 + temp_c)


df = pd.read_csv(DATA_DIR / "rssi_raw.csv", parse_dates=["datetime"])
df["date"] = df["datetime"].dt.date
df["link_key"] = df.apply(
    lambda r: tuple(sorted([r["link_from"], r["link_to"]])), axis=1
)

records = []
for (s1, s2), link_name in TARGET_LINKS.items():
    key = tuple(sorted([s1, s2]))
    sub = df[df["link_key"] == key].copy()

    if sub.empty:
        print(f"[경고] {link_name} ({s1}↔{s2}): 데이터 없음")
        continue

    sub["ah"] = rh_to_ah(sub["temp_c"], sub["rh_pct"])

    daily = (
        sub.groupby("date")
        .agg(
            temp_mean=("temp_c", "mean"),
            rh_mean=("rh_pct", "mean"),
            ah_mean=("ah", "mean"),
            n_records=("rssi_dbm", "count"),
        )
        .reset_index()
    )
    daily["link"] = link_name
    daily["date"] = pd.to_datetime(daily["date"])

    print(
        f"{link_name} ({s1}↔{s2}): {len(daily)}일"
        f"  T={daily['temp_mean'].mean():.1f}°C"
        f"  RH={daily['rh_mean'].mean():.1f}%"
        f"  AH={daily['ah_mean'].mean():.2f} g/m³"
    )
    records.append(daily)

env_daily = pd.concat(records, ignore_index=True)
env_daily = env_daily.sort_values(["link", "date"]).reset_index(drop=True)

# 세 링크 평균
combined = (
    env_daily.groupby("date")[["temp_mean", "rh_mean", "ah_mean"]]
    .mean()
    .reset_index()
)
combined["link"] = "ABD_mean"
env_daily = pd.concat([env_daily, combined], ignore_index=True)

env_daily.to_csv(DATA_DIR / "env_daily.csv", index=False)
print(f"\nenv_daily.csv 저장: {len(env_daily)}행 ({env_daily['link'].nunique()}가지 링크)")
print(f"링크 종류: {env_daily['link'].unique().tolist()}")
print(f"날짜 범위: {env_daily['date'].min().date()} ~ {env_daily['date'].max().date()}")
