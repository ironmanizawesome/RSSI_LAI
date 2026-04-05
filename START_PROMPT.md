# Claude Code 시작 프롬프트

세션 시작 시 아래 내용을 순서대로 붙여넣는다.

---

## 세션 1: 환경 확인 + LAI 파싱

```
CLAUDE.md를 먼저 읽어줘.

읽은 뒤 아래 순서로 진행해줘:

1. black 설치 여부 확인, 없으면 설치
2. data_set_Braunschweig-2016/ 폴더 존재 여부 확인
3. CLAUDE.md의 Step 1~2에 따라 LAI 파싱 스크립트를 scripts/parse_lai.py로 작성하고 실행
4. 실행 후 data/lai_raw.csv, data/lai_daily.csv 생성 확인
5. lai_daily.csv의 일별 LAI median 값이 생육 경향성과 맞는지 간단히 보고

주의: 모든 경로는 Path(__file__).parent.parent 기준 상대경로로 작성
```

---

## 세션 2: RSSI 파싱 + 특징량 생성

```
CLAUDE.md를 읽어줘.

Step 3~4에 따라 진행해줘:

1. scripts/parse_rssi.py 작성 및 실행
   - 실행 후 RSSI 값 범위가 -100 ~ 0 dBm 사이인지 검증
   - 이상값 있으면 보고하고 필터 기준 같이 결정

2. scripts/feature_engineering.py 작성 및 실행
   - 5가지 처리 방식 특징량 생성
   - lai_daily.csv와 병합 확인
   - 각 처리 방식 결측값 비율 출력
```

---

## 세션 3: 시각화 + 상관관계 분석

```
CLAUDE.md를 읽어줘.

Step 5~6에 따라 진행해줘:

1. scripts/visualize.py 작성 및 실행
   - Figure 2의 대표 링크: A↔GW (sensor_id=1, link_from=9)
   - 생성된 Figure 4개 순서대로 보여줘

2. 처리 방식별 Pearson r, Spearman r 계산
   - 링크: A↔GW, G↔GW 각각
   - 결과를 표로 출력

결과 해석 시: "경향성 반영 가능성" 수준으로 표현할 것
```
