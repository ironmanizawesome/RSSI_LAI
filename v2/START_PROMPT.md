# START_PROMPT.md — v2 세션별 프롬프트

---

## 세션 1: 환경 확인 + LAI 파싱

```
CLAUDE.md(글로벌)와 v2/CLAUDE_v2.md를 읽어줘.

아래 순서로 진행:

1. 의존성 확인 (black, statsmodels, pandas, numpy, matplotlib, scipy)
   없으면 설치
2. data_set_Braunschweig-2016/ 폴더 존재 확인
3. v2/scripts/parse_lai.py 작성 및 실행
   - 대상: sensor_base_9, sensor_base_10, sensor_base_11
   - 음수 LAI 파싱 (글로벌 CLAUDE.md 파일 포맷 명세 참고)
   - null 바이트 손상 라인 제거
   - 출력: v2/data/lai_raw.csv
4. v2/scripts/filter_lai.py 작성 및 실행
   - 필터: 시간 10~14시, 0 < LAI ≤ 8
   - 집계: 일별 median
   - 출력: v2/data/lai_daily.csv
5. 검증
   - LAI median 범위가 0~8 이내인지
   - 일수가 60일 이상인지
   - 시계열이 생육 경향(증가→피크→감소)과 맞는지 간단히 보고

완료 후 workflow.txt에 기록:

## 세션 1 완료
- 생성 파일: [목록]
- 주요 수치: lai_raw 행 수, lai_daily 일수, LAI 범위(min~max)
- 발견된 이슈: [있으면 기록, 없으면 "없음"]
- 다음 세션 필요: lai_daily.csv 존재 확인
```

---

## 세션 2: RSSI 파싱 + 환경변수 추출

```
CLAUDE.md(글로벌)와 v2/CLAUDE_v2.md를 읽고, workflow.txt 세션 1 확인.

아래 순서로 진행:

1. v2/scripts/parse_rssi.py 작성 및 실행
   - 대상: sensor_1~8 (cluster_1, cluster_2)
   - hex 변환 규칙은 글로벌 CLAUDE.md 참조
   - B=0, C=0 → 수신 없음, 스킵
   - 출력: v2/data/rssi_raw.csv
     (datetime, sensor_id, link_from, link_to, rssi_dbm, lqi, temp_c, rh_pct)
   - 이상값 필터: RSSI -100~0, 온도 0~60, 습도 0~100

2. hex 변환 검증
   - RSSI 분포 출력 (min, max, mean, median)
   - 온도 분포 출력 → Bauer 2020 Fig.7과 대략 일치하는지 (10~40°C 범위)
   - 범위 벗어나면 변환 공식 재검토 후 이슈로 기록

3. 링크 탐색
   - 전체 링크 목록 출력 (link_from → link_to, 유형, 가용 일수)
   - ground-above 링크만 필터
   - 가용 일수 기준 정렬
   - Bauer 2020처럼 여러 링크 평균이 가능한지 검토
   - 주 분석 대상 링크(또는 링크 조합) 선정 + 이유 기록

4. v2/scripts/extract_env.py 작성 및 실행
   - 주 분석 링크 대상, 일별 환경변수 집계
   - AH 계산 포함 (글로벌 CLAUDE.md rh_to_ah)
   - 출력: v2/data/env_daily.csv (date, link, temp_mean, rh_mean, ah_mean)

완료 후 workflow.txt에 기록:

## 세션 2 완료
- 생성 파일: [목록]
- 주요 수치: rssi_raw 행 수, 전체 링크 수, ground-above 링크별 가용 일수
- hex 검증 결과: 정상 / 이상 (상세)
- 주 분석 링크: [선정 결과 + 이유]
- 발견된 이슈: [있으면 기록]
- 다음 세션 필요: rssi_raw.csv, env_daily.csv 존재 확인
```

---

## 세션 3: 특징량 생성

```
CLAUDE.md(글로벌)와 v2/CLAUDE_v2.md를 읽고, workflow.txt 세션 1~2 확인.

아래 순서로 진행:

1. v2/scripts/feature_engineering.py 작성 및 실행
   주 분석 링크 대상, RSSI 특징량 5가지 (링크별·일별):
   - rssi_raw: 일별 mean
   - rssi_ma7: 7일 rolling mean (min_periods=3)
   - rssi_delta: 전일 대비 diff
   - rssi_std7: 7일 rolling std (min_periods=3)
   - rssi_residual: 야간(22~06시) OLS → 전체 적용 잔차
     ⚠️ 전체 기간 OLS 금지 (CLAUDE_v2.md 방식 B 참조)

2. lai_daily.csv, env_daily.csv와 date 기준 병합
   - 출력: v2/data/features_merged.csv
   - 컬럼: date, lai_median, rssi_raw, rssi_ma7, rssi_delta, rssi_std7,
           rssi_residual, temp_mean, rh_mean, ah_mean
   - 각 컬럼 결측값 비율 출력
   - 분석 가능 행 수(모든 컬럼 non-null) 출력

완료 후 workflow.txt에 기록:

## 세션 3 완료
- 생성 파일: [목록]
- 주요 수치: features_merged 행 수, 분석 가능 행 수, 결측값 비율
- 발견된 이슈: [있으면 기록]
- 다음 세션 필요: features_merged.csv 존재 확인
```

---

## 세션 4: 세 가지 보정 방식 비교 분석

```
CLAUDE.md(글로벌)와 v2/CLAUDE_v2.md를 읽고, workflow.txt 세션 1~3 확인.

이 세션이 v2의 핵심. CLAUDE_v2.md의 "비교할 세 가지 방식" 섹션을 반드시 숙지.

v2/scripts/analysis_comparison.py 작성 및 실행:

### 방식 A: 보정 없음
- 각 RSSI 특징량(raw, ma7, delta, std7) vs lai_median
- Pearson r, p-value 계산

### 방식 B: OLS 잔차
- rssi_residual vs lai_median
- Pearson r, p-value 계산

### 방식 C: 다중회귀 공변량
- 모델: lai_median ~ rssi_X + temp_mean + ah_mean
  (rssi_X = raw, ma7 각각)
- statsmodels OLS 사용
- 출력: R², adj R², 각 계수(β) + p-value, 전체 F-test p-value
- VIF 계산 (statsmodels.stats.outliers_influence.variance_inflation_factor)
  → 10 초과 시 경고, 해석에 주의 문구 추가

### 비교표 출력
아래 형식으로 콘솔 + CSV 저장 (v2/data/comparison_results.csv):

| 방식 | RSSI 입력 | 지표 | 값 | p-value | n |
|------|----------|------|-----|---------|---|

### 해석
- CLAUDE_v2.md "결과 해석 가이드" 기준으로 1단락 해석 작성
- 모든 수치에 n 명시
- p > 0.05면 "유의미하지 않음" 반드시 명시

완료 후 workflow.txt에 기록:

## 세션 4 완료
- 생성 파일: [목록]
- 핵심 비교표: (표 붙여넣기)
- 방식 C R²: [값]
- VIF 이상 여부: [정상/경고]
- 해석 요약: (1~2문장)
- 발견된 이슈: [있으면 기록]
- 다음 세션 필요: comparison_results.csv 존재 확인
```

---

## 세션 5: 시각화

```
CLAUDE.md(글로벌)와 v2/CLAUDE_v2.md를 읽고, workflow.txt 세션 1~4 확인.

v2/scripts/visualize.py 작성 및 실행:

### Figure 1: LAI 시계열
- 일별 median + std 범위 음영
- 저장: v2/figures/fig1_lai_timeseries.png

### Figure 2: RSSI 특징량 시계열
- 주 분석 링크 기준
- 4개 subplot (raw / ma7 / delta / std7)
- 각 subplot에 LAI를 secondary y-axis로 겹침
- 저장: v2/figures/fig2_rssi_features.png

### Figure 3: 보정 방식 비교 (핵심 Figure)
- 3개 subplot 가로 배치:
  (a) 방식 A: rssi_raw vs LAI 산점도 + Pearson r, p
  (b) 방식 B: rssi_residual vs LAI 산점도 + Pearson r, p
  (c) 방식 C: 다중회귀 예측 LAI vs 실제 LAI 산점도 + R², p
- 저장: v2/figures/fig3_comparison.png

### Figure 4: 방식 C 시계열 비교
- 다중회귀 예측 LAI vs 실제 LAI 시계열 겹침
- R², nRMSE, p-value 텍스트 표기
- Bauer 2020 Fig.14 스타일 참고
- 저장: v2/figures/fig4_multiregression.png

공통:
- x축 날짜: 전체 기간
- 영문 라벨
- dpi=150
- 배경 음영: 생육 급증 구간 (workflow.txt에서 확인 또는 LAI 기울기 기반 자동 판단)

완료 후 workflow.txt에 기록:

## 세션 5 완료
- 생성 파일: [Figure 목록]
- 각 Figure 핵심 관찰 1줄
- 전체 분석 결론 (3줄 이내)
- 남은 작업: [있으면 기록, 없으면 "분석 완료"]
```

---

## 세션 간 규칙

1. **세션 시작**: CLAUDE.md(글로벌) + v2/CLAUDE_v2.md + workflow.txt 읽기
2. **세션 종료**: workflow.txt에 정해진 형식으로 기록
3. **에러 발생**: workflow.txt에 에러 기록 → 수정 시도 → 3회 실패 시 중단, 이슈로 기록
4. **파일 의존**: 이전 세션 출력 파일 존재 여부 먼저 확인, 없으면 알림
5. **경로 규칙**: 스크립트 내 모든 경로는 `Path(__file__).parent.parent` (= v2/) 기준,
   원본 데이터는 `Path(__file__).parent.parent.parent / "data_set_Braunschweig-2016"` 참조
