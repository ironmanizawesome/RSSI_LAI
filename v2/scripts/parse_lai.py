"""
세션 1 - Step 1: sensor_base_9/10/11 파싱 → v2/data/lai_raw.csv
"""

import re
from pathlib import Path

import pandas as pd

V2_ROOT = Path(__file__).parent.parent          # RSSI_LAI/v2/
DATA_SET = V2_ROOT.parent / "data_set_Braunschweig-2016"
OUT_DIR = V2_ROOT / "data"
OUT_DIR.mkdir(exist_ok=True)

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
        ground = float(tokens[5])
    except ValueError:
        return None

    rest = tokens[6:]
    if len(rest) == 1:
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


records = []
for sid in [9, 10, 11]:
    base_dir = SENSOR_BASE_DIRS[sid]
    pattern = f"sensor_base_{sid}.dat"
    files = sorted(base_dir.glob(f"**/{pattern}"))
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
    f"\nlai_raw.csv: {len(lai_raw):,}행"
    f", LAI 범위 {lai_raw['LAI'].min():.3f} ~ {lai_raw['LAI'].max():.3f}"
)
print(f"기간: {lai_raw['datetime'].min()} ~ {lai_raw['datetime'].max()}")
