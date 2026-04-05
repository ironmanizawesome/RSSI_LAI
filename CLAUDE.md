# CLAUDE.md — WSN4Crop RSSI/LAI 분석 프로젝트

## 프로젝트 한 줄 요약
RSSI 처리 방식(Raw / 이동평균 / 변화량 / 변동성 / 환경보정)에 따라
광량 기반 LAI 시계열과의 관계성이 어떻게 달라지는지 비교·분석한다.

---

## 절대 놓치면 안 되는 해석 원칙

- 이 프로젝트는 "RSSI로 LAI를 정확히 예측"하는 게 아니다.
- 핵심은 **저비용 생육 모니터링의 경향성 해석 가능성** 탐색이다.
- 모든 코드 주석, 출력 메시지, 분석 결과 해석에서 아래 표현을 따른다.
  - ✅ "경향성을 반영할 수 있음을 확인하였다"
  - ✅ "가능성을 탐색하였다"
  - ❌ "정확히 추정하였다" / "대체할 수 있다"

---

## 프로젝트 구조

```
RSSI_LAI/
├── CLAUDE.md
├── workflow.txt                ← 전체 작업 기록 (사람이 읽는 문서)
├── .claude/
│   └── settings.json          ← hooks 설정
├── data_set_Braunschweig-2016/ ← 원본 데이터 (절대 수정 금지)
│   ├── 60_gateway/
│   ├── 61_cluster_1/
│   ├── 63_cluster_3/
│   └── 64_cluster_2/
├── data/                       ← 스크립트 실행 결과 저장
│   ├── lai_raw.csv             (235,106행)
│   ├── lai_daily.csv           (72일치)
│   ├── rssi_raw.csv            (558,690행)
│   └── rssi_daily.csv          (1,752행, 63링크)
├── figures/                    ← 시각화 PNG
│   ├── fig1_lai_timeseries.png
│   ├── fig2_rssi_features.png
│   ├── fig3_env_correction.png
│   ├── fig4_scatter.png
│   └── fig5_lag_analysis.png
└── scripts/                    ← 분석 코드
    ├── parse_lai.py            (Step 1~2)
    ├── parse_rssi.py           (Step 3)
    ├── feature_engineering.py  (Step 4)
    └── visualize.py            (Step 5~6)
```

모든 스크립트 경로 기준: **`Path(__file__).parent.parent`** (= RSSI_LAI/)

---

## 데이터셋 구조

### 배치 정보
- 장소: 독일 Braunschweig JKI 실험 포장
- 기간: 2016-04-13 ~ 2016-06-28 (약 77일)
- 측정 주기: 2분 간격

### 폴더별 역할
| 폴더 | 센서 ID | 환경 |
|------|---------|------|
| 60_gateway/ | 0x9 | GW + LAI 계산 기준 |
| 61_cluster_1/ | 0x1, 0x2, 0x5, 0x6 | 가뭄 스트레스 |
| 63_cluster_3/ | 0x10, 0x11 | 캐노피 상부 기준 (LAI 계산) |
| 64_cluster_2/ | 0x3, 0x4, 0x7, 0x8 | 정상 관수 |

### 주요 링크 (README 기준)
| 링크 | 거리 | 유형 | 품질 | 분석 가용 일수 |
|------|------|------|------|--------------|
| A↔GW (0x1↔0x9) | 23m | ground-above | medium | **3일** (분석 불가) |
| G↔GW (0x3↔0x9) | 65m | ground-above | low | **25일** (주 분석 대상) |
| A↔B (0x1↔0x2) | 0.3m | ground-ground | high | 73일 (물리적 해석 불가) |

### 링크 유형별 분석 가능 여부
- **ground-above**: 신호가 캐노피를 통과 → LAI 차폐 효과 해석 가능. 분석 대상.
- **ground-ground**: 신호가 캐노피를 통과하지 않음 → LAI와의 관계를 차폐 효과로
  해석 불가. 통계 수치가 좋게 나와도 분석 대상에서 제외.

---

## 파일 포맷 명세

### sensor_N.dat (RSSI/온도/습도)
```
2016-05-15_03:05:23 1463274323 0x1 12;[light×25]-[temp_hex],[hum_hex]-[RSSI_array]

RSSI_array: A:B/C 반복 (;로 구분)
  A = SN 차이 (0이면 수신 없음)
  B = RSSI (hex, signed byte)
  C = LQI (hex)
  위치 인덱스 → 송신 센서 ID (sensor 0x1 기준: 0=0x1, 1=0x2, ...)
```

### sensor_base_N.dat (LAI 포함)
```
양수 LAI (컬럼 8개):
  2016-05-15_03:05:19 timestamp 0xA, src_id SN ground_light ref_light LAI

음수 LAI (컬럼 7개, ref와 LAI가 붙어있음):
  2016-05-15_02:51:19 timestamp 0xA, src_id SN ground_light ref_light-LAI
  예: 1.96-0.68 → ref_light=1.96, LAI=-0.68
```

---

## hex 변환 규칙

```python
# RSSI: CC2420 signed byte → dBm
def hex_to_rssi(h):
    v = int(h, 16)
    if v > 127: v -= 256
    return v / 2 - 45

# 온도: SHT11
def hex_to_temp(h):
    return -39.6 + 0.01 * int(h, 16)

# 상대습도: SHT11
def hex_to_rh(h):
    r = int(h, 16)
    return -4 + 0.0405 * r - 2.8e-6 * r**2

# 절대습도 (온도 + RH 결합)
def rh_to_ah(temp_c, rh_pct):
    import numpy as np
    e = 6.112 * np.exp(17.67 * temp_c / (temp_c + 243.5))
    return 216.7 * (e * rh_pct / 100) / (273.15 + temp_c)
```

---

## 분석 작업 순서

### Step 1. LAI 파싱 → `data/lai_raw.csv`
- 대상: sensor_base_9, sensor_base_10, sensor_base_11
- 파싱 이슈: 음수 LAI는 `ref-LAI` 형태로 붙어있음 (위 명세 참고)
- null 바이트 포함 손상 라인 제거 필요 (`errors='ignore'`)
- 출력 컬럼: datetime, sensor_id, ground_light, ref_light, LAI

### Step 2. LAI 필터링 → `data/lai_daily.csv`
- 필터 조건: 시간 10~14시, 0 < LAI ≤ 8
- 집계: 일별 median
- 출력 컬럼: date, lai_median, lai_mean, lai_std, count

### Step 3. RSSI 파싱 → `data/rssi_raw.csv`
- 대상: sensor_1~8 (cluster_1, cluster_2)
- B=0, C=0인 triplet은 수신 없음 → 스킵
- 출력 컬럼: datetime, sensor_id, link_from, link_to, rssi_dbm, lqi, temp_c, rh_pct
- 이상값 필터: RSSI -100~0 dBm, 온도 0~60°C, 습도 0~100% (5건 제거)

### Step 4. 특징량 생성 → `data/rssi_daily.csv`
RSSI 처리 방식 5가지 (링크별로 계산):
1. `rssi_raw`: 일별 mean
2. `rssi_ma7`: 7일 rolling mean (min_periods=3)
3. `rssi_delta`: 전일 대비 diff
4. `rssi_std7`: 7일 rolling std (min_periods=3)
5. `rssi_residual`: **야간(22~06시) 데이터로 OLS 적합** → 전체 데이터에 적용한 잔차

   ⚠️ rssi_residual 주의사항:
   전체 기간 OLS를 쓰면 계절적 공변동(온도↑ = 습도↑ = LAI↑ 동시 발생)으로
   회귀 모델이 LAI 신호까지 흡수함. 반드시 야간 기반 OLS 사용.
   (근거: Bauer & Aschenbruck 2020)

lai_daily.csv와 date 기준 병합 포함.

### Step 5. 시각화 → `figures/`
- Figure 1: LAI 시계열 (median + std 범위 음영)
- Figure 2: RSSI 처리 방식별 4개 subplot, 대표 링크: **G↔GW (9_to_3)**
- Figure 3: 환경보정 전/후 RSSI vs LAI 비교 (G↔GW 기준)
- Figure 4: 처리 방식별 LAI 산점도 + Pearson r 표시
- Figure 5: Lag 분석 (G↔GW, rssi_raw / rssi_ma7, lag -7~+7일)

공통 조건:
- x축: 날짜 전체 기간
- 생육 급증 구간 (2016-04-27 ~ 2016-05-20) 배경 음영 강조
- 영문 라벨, dpi=150, figures/ 폴더에 PNG 저장

### Step 6. 상관관계 분석
- Pearson r, Spearman r 모두 계산
- 처리 방식 × 링크 조합별 결과 테이블 출력
- p-value 함께 표시
- 주 분석 링크: G↔GW (9_to_3, 25일치)
- A↔GW (9_to_1, 3일치)는 참고용으로만 출력

### Step 7. Lag 분석 (보조적 탐색)
- 대상: G↔GW (9_to_3) — A↔GW는 3일치로 분석 불가
- 처리 방식: rssi_raw, rssi_ma7
- lag 범위: -7일 ~ +7일 (양수 = RSSI가 LAI보다 앞서 변화)
- 결과가 유의미하지 않으면 "표본 부족으로 해석 불가"로 결론
- 유의미한 결과도 반드시 n 수 명시

---

## 코딩 규칙

- 언어: Python 3
- 라이브러리: pandas, numpy, matplotlib, scipy
- **모든 경로**: `Path(__file__).parent.parent` 기준 상대경로 사용
- **원본 데이터**: `data_set_Braunschweig-2016/` 읽기 전용, 수정 금지
- **파일 읽기**: `open(f, 'rb')` 후 `decode('ascii', errors='ignore')` 사용
- 코드 스타일: black 포맷 적용
- 응답 언어: 한국어

---

## 분석 결과 요약 (세션 1~3 완료)

### LAI
- lai_daily.csv: 72일치, median 범위 0.015 ~ 6.315, 평균 2.103
- 생육 급증 구간(4-27~5-20)에서 4~6 수준 출현 확인

### RSSI 상관관계 — G↔GW (9_to_3, n=25)
| Feature | Pearson r | p | Spearman r | p |
|---------|----------|---|-----------|---|
| rssi_raw | -0.114 | 0.586 | -0.147 | 0.483 |
| rssi_ma7 | -0.158 | 0.472 | -0.154 | 0.483 |
| rssi_delta | +0.108 | 0.614 | +0.210 | 0.324 |
| rssi_std7 | -0.164 | 0.454 | -0.165 | 0.452 |
| rssi_residual | +0.104 | 0.619 | -0.005 | 0.980 |

→ 모든 처리 방식 p > 0.05. 표본 부족(25일)이 주요 원인.

### Lag 분석 — rssi_ma7 / G↔GW
- lag=-4일: r=-0.613, p=0.002, n=22 (유일하게 p<0.05)
- 해석: "rssi_ma7은 LAI 변화에 4일 지연 반응하는 경향이 있을 가능성"
- 주의: n=22, 단일 링크 → 반드시 한계 명시 필요

---

## 참고 논문

| 연도 | 역할 |
|------|------|
| Bauer et al. 2016 | WSN 기반 LAI 추정 가능성 — 정당성 근거 |
| Bauer et al. 2019 | LAI 시계열 필터링·처리 — 처리 방법 참고 |
| Bauer & Aschenbruck 2020 | RSSI ~ T + AH + LAI 회귀 — 환경 보정 프레임 근거 |
