"""
세션 1 - Step 2: lai_raw.csv 필터링 → v2/data/lai_daily.csv
필터: 10~14시, 0 < LAI <= 8, 일별 median 집계
"""

from pathlib import Path

import pandas as pd

V2_ROOT = Path(__file__).parent.parent
DATA_DIR = V2_ROOT / "data"

lai_raw = pd.read_csv(DATA_DIR / "lai_raw.csv", parse_dates=["datetime"])

lai_filtered = lai_raw[
    (lai_raw["datetime"].dt.hour >= 10)
    & (lai_raw["datetime"].dt.hour < 14)
    & (lai_raw["LAI"] > 0)
    & (lai_raw["LAI"] <= 8)
].copy()

lai_filtered["date"] = lai_filtered["datetime"].dt.date

lai_daily = (
    lai_filtered.groupby("date")["LAI"]
    .agg(lai_median="median", lai_mean="mean", lai_std="std", count="count")
    .reset_index()
)
lai_daily["date"] = pd.to_datetime(lai_daily["date"])
lai_daily = lai_daily.sort_values("date").reset_index(drop=True)
lai_daily.to_csv(DATA_DIR / "lai_daily.csv", index=False)

print(f"lai_daily.csv: {len(lai_daily)}일치")
print(
    f"날짜 범위: {lai_daily['date'].min().date()} ~ {lai_daily['date'].max().date()}"
)
print(
    f"LAI median 범위: {lai_daily['lai_median'].min():.3f} ~ {lai_daily['lai_median'].max():.3f}"
)
print(f"LAI median 평균: {lai_daily['lai_median'].mean():.3f}")

# 생육 경향 간단 확인
peak_date = lai_daily.loc[lai_daily["lai_median"].idxmax(), "date"]
print(f"\nLAI 피크 날짜: {peak_date.date()} (median={lai_daily['lai_median'].max():.3f})")

print("\n[일별 LAI median (전체)]")
print(lai_daily[["date", "lai_median", "count"]].to_string(index=False))
