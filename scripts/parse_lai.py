"""
Step 1~2: sensor_base_9/10/11 파싱 → lai_raw.csv, lai_daily.csv
"""

import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent.parent
DATA_SET = ROOT / "data_set_Braunschweig-2016"
OUT_DIR = ROOT / "data"
OUT_DIR.mkdir(exist_ok=True)

# sensor_base 파일 위치
SENSOR_BASE_DIRS = {
    9: DATA_SET / "60_gateway",
    10: DATA_SET / "63_cluster_3",
    11: DATA_SET / "63_cluster_3",
}


def parse_line(line: str):
    """
    양수 LAI (8토큰):
      datetime timestamp 0xA, src_id SN ground ref LAI
    음수 LAI (7토큰, ref-LAI 붙음):
      datetime timestamp 0xA, src_id SN ground ref-LAI
    """
    tokens = line.strip().split()
    if len(tokens) < 7:
        return None

    dt_str = tokens[0]
    src_id = tokens[3].rstrip(",")
    try:
        sn = int(tokens[4])
        ground = float(tokens[5])
    except ValueError:
        return None

    # ref 와 LAI — 붙어있을 수 있음
    rest = tokens[6:]
    if len(rest) == 1:
        # ref-LAI 형태 (음수 LAI)
        m = re.match(r"^(-?\d+\.?\d*)(-\d+\.?\d*)$", rest[0])
        if not m:
            return None
        ref = float(m.group(1))
        lai = float(m.group(2))
    elif len(rest) >= 2:
        try:
            ref = float(rest[0])
            lai = float(rest[1])
        except ValueError:
            return None
    else:
        return None

    try:
        dt = pd.to_datetime(dt_str, format="%Y-%m-%d_%H:%M:%S")
    except Exception:
        return None

    return {
        "datetime": dt,
        "sensor_id": src_id,
        "ground_light": ground,
        "ref_light": ref,
        "LAI": lai,
    }


def collect_files(sensor_id: int):
    base_dir = SENSOR_BASE_DIRS[sensor_id]
    pattern = f"sensor_base_{sensor_id}.dat"
    files = sorted(base_dir.glob(f"**/{pattern}"))
    return files


# ── Step 1: 파싱 ─────────────────────────────────────────────────────────────
records = []
for sid in [9, 10, 11]:
    files = collect_files(sid)
    print(f"sensor_base_{sid}: {len(files)}개 파일")
    for fpath in files:
        raw = fpath.open("rb").read().decode("ascii", errors="ignore")
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            row = parse_line(line)
            if row:
                row["sensor_id"] = sid
                records.append(row)

lai_raw = pd.DataFrame(records)
lai_raw = lai_raw.sort_values("datetime").reset_index(drop=True)
lai_raw.to_csv(OUT_DIR / "lai_raw.csv", index=False)
print(
    f"\nlai_raw.csv: {len(lai_raw):,}행, LAI 범위 {lai_raw['LAI'].min():.2f} ~ {lai_raw['LAI'].max():.2f}"
)

# ── Step 2: 필터링 → 일별 집계 ───────────────────────────────────────────────
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
lai_daily.to_csv(OUT_DIR / "lai_daily.csv", index=False)

print(
    f"lai_daily.csv: {len(lai_daily)}일치, 날짜 범위 {lai_daily['date'].min().date()} ~ {lai_daily['date'].max().date()}"
)
print("\n[일별 LAI median 샘플]")
print(lai_daily[["date", "lai_median", "count"]].to_string(index=False))
