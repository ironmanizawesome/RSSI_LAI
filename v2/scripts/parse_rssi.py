"""
세션 2 - Step 1: sensor_1~8 + sensor_9(GW) RSSI 파싱 → v2/data/rssi_raw.csv
출력 컬럼: datetime, sensor_id, link_from, link_to, rssi_dbm, lqi, temp_c, rh_pct
이상값 필터: RSSI -100~0 dBm, 온도 0~60°C, 습도 0~100%
sensor_9 추가 이유: GW 관점에서 CAT2 링크(A/B/D↔GW, 22~23m) 전 기간(72일) 가용
"""

from pathlib import Path

import pandas as pd

V2_ROOT = Path(__file__).parent.parent
DATA_SET = V2_ROOT.parent / "data_set_Braunschweig-2016"
OUT_DIR = V2_ROOT / "data"
OUT_DIR.mkdir(exist_ok=True)

# 네트워크 전체 센서 ID (오름차순 고정)
ALL_SENSORS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]

SENSOR_DIRS = {
    1: DATA_SET / "61_cluster_1",
    2: DATA_SET / "61_cluster_1",
    5: DATA_SET / "61_cluster_1",
    6: DATA_SET / "61_cluster_1",
    3: DATA_SET / "64_cluster_2",
    4: DATA_SET / "64_cluster_2",
    7: DATA_SET / "64_cluster_2",
    8: DATA_SET / "64_cluster_2",
    9: DATA_SET / "60_gateway",   # GW 추가: CAT2 링크(A/B/D↔GW) 72일 가용
}


# ── hex 변환 ──────────────────────────────────────────────────────────────────
def hex_to_rssi(h: str) -> float:
    v = int(h, 16)
    if v > 127:
        v -= 256
    return v / 2 - 45


def hex_to_temp(h: str) -> float:
    return -39.6 + 0.01 * int(h, 16)


def hex_to_rh(h: str) -> float:
    r = int(h, 16)
    return -4 + 0.0405 * r - 2.8e-6 * r**2


# ── 라인 파싱 ─────────────────────────────────────────────────────────────────
def parse_line(line: str, sensor_id: int):
    tokens = line.strip().split()
    if len(tokens) < 4 or "BOOT" in line:
        return []

    dt_str = tokens[0]
    data_part = tokens[3]

    parts = data_part.split("-")
    if len(parts) < 3:
        return []

    th_part = parts[1].split(",")
    if len(th_part) < 2:
        return []
    try:
        temp_c = hex_to_temp(th_part[0])
        rh_pct = hex_to_rh(th_part[1])
    except (ValueError, ZeroDivisionError):
        return []

    rssi_str = "-".join(parts[2:])
    triplets = rssi_str.split(";")

    other_sensors = [s for s in ALL_SENSORS if s != sensor_id]

    try:
        dt = pd.to_datetime(dt_str, format="%Y-%m-%d_%H:%M:%S")
    except Exception:
        return []

    results = []
    for idx, triplet in enumerate(triplets):
        if idx >= len(other_sensors):
            break
        abc = triplet.strip().split(":")
        if len(abc) != 2:
            continue
        bc = abc[1].split("/")
        if len(bc) != 2:
            continue
        b_hex, c_hex = bc[0], bc[1]
        try:
            b_val = int(b_hex, 16)
            c_val = int(c_hex, 16)
        except ValueError:
            continue
        if b_val == 0 and c_val == 0:
            continue

        try:
            rssi_dbm = hex_to_rssi(b_hex)
            lqi = c_val
        except ValueError:
            continue

        results.append(
            {
                "datetime": dt,
                "sensor_id": sensor_id,
                "link_from": other_sensors[idx],
                "link_to": sensor_id,
                "rssi_dbm": rssi_dbm,
                "lqi": lqi,
                "temp_c": temp_c,
                "rh_pct": rh_pct,
            }
        )
    return results


# ── 파일 수집 ─────────────────────────────────────────────────────────────────
records = []
for sid, base_dir in sorted(SENSOR_DIRS.items()):
    files = sorted(base_dir.glob(f"**/sensor_{sid}.dat"))
    print(f"sensor_{sid}: {len(files)}개 파일")
    for fpath in files:
        raw = fpath.open("rb").read().decode("ascii", errors="ignore")
        for line in raw.splitlines():
            if not line.strip():
                continue
            records.extend(parse_line(line, sid))

rssi_raw = pd.DataFrame(records)
rssi_raw = rssi_raw.sort_values("datetime").reset_index(drop=True)

print(f"\n[필터 전] {len(rssi_raw):,}행")
print(
    f"RSSI: {rssi_raw['rssi_dbm'].min():.1f} ~ {rssi_raw['rssi_dbm'].max():.1f} dBm"
)
print(f"온도: {rssi_raw['temp_c'].min():.1f} ~ {rssi_raw['temp_c'].max():.1f} °C")
print(f"습도: {rssi_raw['rh_pct'].min():.1f} ~ {rssi_raw['rh_pct'].max():.1f} %")

# 이상값 필터
before = len(rssi_raw)
rssi_raw = rssi_raw[
    (rssi_raw["rssi_dbm"] >= -100)
    & (rssi_raw["rssi_dbm"] <= 0)
    & (rssi_raw["temp_c"] >= 0)
    & (rssi_raw["temp_c"] <= 60)
    & (rssi_raw["rh_pct"] >= 0)
    & (rssi_raw["rh_pct"] <= 100)
].reset_index(drop=True)

print(f"\n[필터 후] {len(rssi_raw):,}행 (제거: {before - len(rssi_raw):,}행)")
print(
    f"RSSI: {rssi_raw['rssi_dbm'].min():.1f} ~ {rssi_raw['rssi_dbm'].max():.1f} dBm"
    f"  mean={rssi_raw['rssi_dbm'].mean():.1f}  median={rssi_raw['rssi_dbm'].median():.1f}"
)
print(
    f"온도: {rssi_raw['temp_c'].min():.1f} ~ {rssi_raw['temp_c'].max():.1f} °C"
    f"  mean={rssi_raw['temp_c'].mean():.1f}"
)
print(
    f"습도: {rssi_raw['rh_pct'].min():.1f} ~ {rssi_raw['rh_pct'].max():.1f} %"
    f"  mean={rssi_raw['rh_pct'].mean():.1f}"
)

rssi_raw.to_csv(OUT_DIR / "rssi_raw.csv", index=False)
print(f"\nrssi_raw.csv 저장 완료")
