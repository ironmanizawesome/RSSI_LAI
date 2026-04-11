"""
Step 3: sensor_1~8 RSSI 파싱 → data/rssi_raw.csv
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent.parent
DATA_SET = ROOT / "data_set_Braunschweig-2016"
OUT_DIR = ROOT / "data"
OUT_DIR.mkdir(exist_ok=True)

# 네트워크 전체 센서 ID (오름차순 고정)
ALL_SENSORS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]

# 파싱 대상: cluster_1, cluster_2
SENSOR_DIRS = {
    1: DATA_SET / "61_cluster_1",
    2: DATA_SET / "61_cluster_1",
    5: DATA_SET / "61_cluster_1",
    6: DATA_SET / "61_cluster_1",
    3: DATA_SET / "64_cluster_2",
    4: DATA_SET / "64_cluster_2",
    7: DATA_SET / "64_cluster_2",
    8: DATA_SET / "64_cluster_2",
}


# ── hex 변환 ─────────────────────────────────────────────────────────────────
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
    """
    형식: datetime timestamp 0xN SN;[light×25]-[temp_hex],[hum_hex]-[RSSI_array]
    RSSI_array: A:B/C 를 ;로 구분, B=0이고 C=0이면 수신 없음 → 스킵
    반환: list of dict (triplet 하나당 하나)
    """
    tokens = line.strip().split()
    if len(tokens) < 4 or "BOOT" in line:
        return []

    dt_str = tokens[0]
    # 데이터 부분 (SN;light-temp,hum-rssi)
    data_part = tokens[3]

    parts = data_part.split("-")
    if len(parts) < 3:
        return []

    # temp, hum
    th_part = parts[1].split(",")
    if len(th_part) < 2:
        return []
    try:
        temp_c = hex_to_temp(th_part[0])
        rh_pct = hex_to_rh(th_part[1])
    except (ValueError, ZeroDivisionError):
        return []

    # RSSI 배열 (세 번째 '-' 이후 전부)
    rssi_str = "-".join(parts[2:])
    triplets = rssi_str.split(";")

    # 자신을 제외한 센서 순서 목록
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
        # B=0 AND C=0 → 수신 없음
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

# ── 검증 ─────────────────────────────────────────────────────────────────────
print(f"\nrssi_raw: {len(rssi_raw):,}행")
print(
    f"RSSI 범위: {rssi_raw['rssi_dbm'].min():.1f} ~ {rssi_raw['rssi_dbm'].max():.1f} dBm"
)

out_of_range = rssi_raw[(rssi_raw["rssi_dbm"] < -100) | (rssi_raw["rssi_dbm"] > 0)]
print(f"이상값(-100 ~ 0 dBm 초과): {len(out_of_range)}행")
if len(out_of_range) > 0:
    print(out_of_range["rssi_dbm"].describe())

print(f"온도 범위: {rssi_raw['temp_c'].min():.1f} ~ {rssi_raw['temp_c'].max():.1f} °C")
print(f"습도 범위: {rssi_raw['rh_pct'].min():.1f} ~ {rssi_raw['rh_pct'].max():.1f} %")

# A↔GW 링크 (sensor_id=1, link_from=9) 확인
agw = rssi_raw[(rssi_raw["sensor_id"] == 1) & (rssi_raw["link_from"] == 9)]
print(f"\n[A↔GW 링크] {len(agw)}건, RSSI: {agw['rssi_dbm'].mean():.1f} dBm (mean)")
ggw = rssi_raw[(rssi_raw["sensor_id"] == 3) & (rssi_raw["link_from"] == 9)]
print(f"[G↔GW 링크] {len(ggw)}건, RSSI: {ggw['rssi_dbm'].mean():.1f} dBm (mean)")

rssi_raw.to_csv(OUT_DIR / "rssi_raw.csv", index=False)
print(f"\nrssi_raw.csv 저장 완료")
