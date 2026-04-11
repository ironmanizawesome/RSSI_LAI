# CLAUDE.md — WSN4Crop 프로젝트 (글로벌)

## 이 문서의 역할
버전 무관 공통 규칙. 데이터셋 명세, 코딩 규칙, 금지 목록만 포함한다.
분석 방향과 세션별 지침은 각 버전의 CLAUDE_vN.md를 참조.

---

## 데이터셋 기본 정보

- 장소: 독일 Braunschweig JKI 실험 포장
- 기간: 2016-04-13 ~ 2016-06-28 (약 77일)
- 작물: 겨울밀 (Triticum aestivum L.)
- 측정 주기: 2분 간격
- LAI: 투과율 기반 추정값 (GT 아님, reference)
- 원본 경로: `data_set_Braunschweig-2016/` (절대 수정 금지, 모든 버전이 공유)

### 폴더별 역할
| 폴더 | 센서 ID | 환경 |
|------|---------|------|
| 60_gateway/ | 0x9 | GW + LAI 계산 기준 |
| 61_cluster_1/ | 0x1, 0x2, 0x5, 0x6 | 가뭄 스트레스 |
| 63_cluster_3/ | 0x10, 0x11 | 캐노피 상부 기준 |
| 64_cluster_2/ | 0x3, 0x4, 0x7, 0x8 | 정상 관수 |

### 주요 링크 (Bauer 2020 Table 1 기준)
| 링크 | 거리 | 유형 | CAT |
|------|------|------|-----|
| A↔GW (0x1↔0x9) | 23m | ground-above | 2 |
| B↔GW (0x2↔0x9) | 22.5m | ground-above | 2 |
| D↔GW (0x6↔0x9) | 22m | ground-above | 2 |
| G↔GW (0x3↔0x9) | 65m | ground-above | 3 |
| H↔GW (0x4↔0x9) | 65m | ground-above | 3 |
| A↔B (0x1↔0x2) | 0.3m | ground-ground | 1 |
| A↔D (0x1↔0x6) | 1.2m | ground-ground | 1 |
| B↔D (0x2↔0x6) | 1.2m | ground-ground | 1 |

### 링크 유형별 분석 원칙
- **ground-above**: 신호가 캐노피를 통과 → LAI 차폐 효과 해석 가능. 분석 대상.
- **ground-ground**: 신호가 캐노피를 통과하지 않음 → LAI 차폐 효과로 해석 불가. 분석 제외.

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
  datetime timestamp 0xA, src_id SN ground_light ref_light LAI

음수 LAI (컬럼 7개, ref와 LAI가 붙어있음):
  datetime timestamp 0xA, src_id SN ground_light ref_light-LAI
  예: 1.96-0.68 → ref_light=1.96, LAI=-0.68
```

---

## hex 변환 규칙

⚠️ 아래 규칙은 CC2420 데이터시트, SHT11 데이터시트, Bauer 2020 Eq.1에 기반하나,
**v2 세션 1에서 실제 데이터와 대조 검증 필수**. 검증 방법:
- RSSI 범위가 -100 ~ 0 dBm 이내인지
- 온도 범위가 현실적인지 (0~60°C)
- 습도 범위가 0~100% 이내인지
- 논문 Fig.7의 RSSI/온도 값 범위와 대략 일치하는지

```python
# RSSI: CC2420 signed byte → dBm (데이터시트: RSSI_VAL/2 - 45)
def hex_to_rssi(h):
    v = int(h, 16)
    if v > 127: v -= 256
    return v / 2 - 45

# 온도: SHT11 (데이터시트: -39.6 + 0.01 * SOt)
def hex_to_temp(h):
    return -39.6 + 0.01 * int(h, 16)

# 상대습도: SHT11 (데이터시트: -4 + 0.0405*SOrh - 2.8e-6*SOrh²)
def hex_to_rh(h):
    r = int(h, 16)
    return -4 + 0.0405 * r - 2.8e-6 * r**2

# 절대습도: Bauer 2020 Eq.1 (Magnus 공식)
def rh_to_ah(temp_c, rh_pct):
    import numpy as np
    e = 6.112 * np.exp(17.67 * temp_c / (temp_c + 243.5))
    return 216.7 * (e * rh_pct / 100) / (273.15 + temp_c)
```

---

## 코딩 규칙

- 언어: Python 3
- 라이브러리: pandas, numpy, matplotlib, scipy, statsmodels
- 모든 경로: `Path(__file__).parent.parent` 기준 상대경로
- 원본 데이터: `data_set_Braunschweig-2016/` 읽기 전용
- 파일 읽기: `open(f, 'rb')` 후 `decode('ascii', errors='ignore')`
- 코드 스타일: black 포맷
- 응답 언어: 한국어

---

## 금지 목록

### 표현
- ❌ "정확히 추정하였다" / "대체할 수 있다"
- ❌ p > 0.05 결과를 유의미하다고 해석
- ❌ 다중비교 보정 없이 여러 검정을 단정적으로 해석
- ✅ "경향성을 확인하였다" / "가능성을 탐색하였다"

### 분석
- ❌ ground-ground 링크를 LAI 차폐 효과 분석에 사용
- ❌ 원본 데이터 수정
- ❌ proxy를 GT처럼 서술
- ❌ n 수 명시 없이 상관계수 보고

---

## 폴더 구조

```
RSSI_LAI/
├── CLAUDE.md                    ← 이 파일 (글로벌)
├── workflow.txt                 ← 세션 간 맥락 전달
├── .claude/
│   └── settings.json
├── data_set_Braunschweig-2016/  ← 원본 (공유, 수정 금지)
├── v1/                          ← 기존 분석 (아카이브)
│   ├── CLAUDE_v1.md
│   ├── scripts/
│   ├── data/
│   └── figures/
└── v2/                          ← 현재 분석
    ├── CLAUDE_v2.md             ← v2 전용 지침
    ├── START_PROMPT.md          ← 세션별 프롬프트
    ├── scripts/
    ├── data/
    └── figures/
```

---

## 참고 논문

| 연도 | 저자 | 핵심 역할 |
|------|------|----------|
| 2016 | Bauer, Siegmann, Jarmer, Aschenbruck | WSN 기반 LAI 추정 가능성 |
| 2019 | Bauer, Jarmer, Schittenhelm, Siegmann, Aschenbruck | LAI 시계열 필터링·처리 |
| 2020 | Bauer, Aschenbruck | RSSI ~ T + AH + LAI 다중회귀 프레임 |
