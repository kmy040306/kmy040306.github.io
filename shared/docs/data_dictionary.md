# 분석 데이터 계약

| 파일 | 행 단위 | 필수 정보 |
|---|---|---|
| products.csv | 개별 제품 | product_id, series_id, food_group, protein_claim, 기준량·단위, 단백질·열량·당류·나트륨·포화지방, 출처 |
| series_statistics.csv | 시리즈 | 식품군·집단, 제품별 지표의 평균, 지표별 유효 제품 수 |
| series_ml.csv | 시리즈 | 식품군·집단, 핵심 입력 3개 완전 관측 제품의 당류·나트륨·포화지방 평균, 제품 수 |
| exclusions.csv | 제외 후보 | 제품 ID, 제외 사유, 판정 근거 |

결측값을 실제 0으로 바꾸지 않습니다. 제품별 효율은 단백질 / 열량 × 100입니다. 단백질 20g 지표는 성분 / 단백질 × 20입니다. 분모가 0 또는 결측이면 계산하지 않습니다.

## 정제 기록 (02_clean.py)

| 파일 | 행 단위 | 내용 |
|---|---|---|
| shared/results/cleaning_log.csv | 사건 | `event`(parse_error, missing_source, zero_value, series_merged, series_map_unused), candidate_id, column, value, detail |
| shared/results/clean_checks.csv | 점검 항목 | check, status(pass/fail), detail. fail이 하나라도 있으면 v001 확정 금지 |
| shared/results/series_merge_suggestions.csv | 통합 후보 | 자동 시리즈 키가 같은데 최종 ID가 다른 시리즈 |
| shared/docs/series_id_map.csv | 통합 결정 | from_series_id → to_series_id, 이유, 결정자, 날짜 |

`products.csv`에는 최종 `series_id` 외에 판정자가 처음 제안한 `proposed_series_id`와 자동 키 `auto_series_key`를 함께 둔다.
