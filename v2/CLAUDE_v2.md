# CLAUDE_v2.md — 환경변수 보정 방식 비교 분석

## 상위 문서
글로벌 규칙은 `../../CLAUDE.md` 참조. 이 문서는 v2 분석 방향만 다룬다.

---

## 연구 질문
같은 데이터에서 환경변수(T, AH) 보정 방식을 다르게 했을 때,
RSSI와 LAI 간 관계가 어떻게 달라지는가?

## 비교할 세 가지 방식

### 방식 A: 보정 없음
- raw RSSI vs LAI 단순 상관 (Pearson r)
- RSSI 특징량별(raw, ma7, delta, std7) 각각 실행
- 의미: 환경변수를 전혀 고려하지 않았을 때의 기준선(baseline)

### 방식 B: OLS 잔차 (2단계 분리)
- 1단계: 야간(22~06시) 데이터로 `RSSI ~ T + AH` OLS 적합
  → 식물 영향이 없는 시간대에서 환경-RSSI 관계 학습
- 2단계: 전체 시간대에서 (실제 RSSI − 예측 RSSI) = 잔차
  → 잔차 vs LAI 상관 분석
- 의미: 환경 효과를 "사전 제거"한 후 남은 신호가 LAI와 관련 있는가

⚠️ 주의: 전체 기간 OLS 금지. 계절적 공변동(T↑ = AH↑ = LAI↑)으로
회귀 모델이 LAI 신호까지 흡수함. 반드시 야간 기반 OLS 사용.

### 방식 C: 다중회귀 공변량 (Bauer 2020 Eq.5 재현)
- 모델: `LAI ~ RSSI + T + AH` (statsmodels OLS)
- T와 AH를 공변량으로 동시 투입 → RSSI의 부분 효과(partial effect) 추출
- RSSI 특징량별(raw, ma7 등)로 각각 실행
- 출력: R², adjusted R², 각 계수 p-value, F-test p-value
- 다중공선성 확인: VIF 계산, 10 초과 시 경고
- 의미: 환경 효과를 "동시 통제"하면서 RSSI-LAI 관계를 보는 방식

---

## v1과의 차이

| 항목 | v1 | v2 |
|------|-----|-----|
| 연구 축 | RSSI 처리 방식 비교 | 환경변수 보정 방식 비교 |
| 환경보정 | OLS 잔차만 사용 | A/B/C 세 방식 체계 비교 |
| 다중회귀 | 미구현 | 구현 (방식 C) |
| 링크 선택 | G↔GW 단일 링크 | 가용 링크 전체 탐색 후 선정 |

---

## 링크 선택 전략

v1에서는 G↔GW(25일)만 사용하여 표본 부족 문제가 있었다.
v2에서는:
1. 세션 2에서 모든 ground-above 링크의 가용 일수를 먼저 파악
2. Bauer 2020처럼 여러 링크의 평균을 사용할 수 있는지 검토
3. 가용 일수가 가장 많은 링크 또는 링크 조합을 주 분석 대상으로 선정

---

## 기대하는 결과 구조

최종 비교표:
| 방식 | RSSI 입력 | 지표 | 값 | p-value | n |
|------|----------|------|-----|---------|---|
| A | rssi_raw | Pearson r | ? | ? | ? |
| A | rssi_ma7 | Pearson r | ? | ? | ? |
| B | rssi_residual | Pearson r | ? | ? | ? |
| C | rssi_raw+T+AH | R² | ? | ? | ? |
| C | rssi_ma7+T+AH | R² | ? | ? | ? |

이 표가 논문/포스터의 핵심 결과물이 된다.

---

## 결과 해석 가이드

- 방식 A < B < C 순으로 관계가 개선되면:
  → "환경변수를 고려할수록 RSSI-LAI 관계가 명확해진다" 주장 가능
- 방식 B와 C가 비슷하면:
  → "사전 제거든 동시 투입이든 환경 보정 자체가 중요하다"
- 방식 C에서도 유의미하지 않으면:
  → "표본 부족 또는 단일 링크의 한계"로 정직하게 서술
- 어떤 경우든 "가능성 탐색" 수준으로 표현

---

## v2 폴더 구조

```
v2/
├── CLAUDE_v2.md        ← 이 파일
├── START_PROMPT.md     ← 세션별 프롬프트
├── scripts/
│   ├── parse_lai.py
│   ├── filter_lai.py
│   ├── parse_rssi.py
│   ├── extract_env.py
│   ├── feature_engineering.py
│   ├── analysis_comparison.py
│   └── visualize.py
├── data/
│   ├── lai_raw.csv
│   ├── lai_daily.csv
│   ├── rssi_raw.csv
│   ├── env_daily.csv
│   └── features_merged.csv
└── figures/
    ├── fig1_lai_timeseries.png
    ├── fig2_rssi_features.png
    ├── fig3_comparison.png
    └── fig4_multiregression.png
```
