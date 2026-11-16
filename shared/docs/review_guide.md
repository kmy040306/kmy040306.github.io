# 판정 양식 작성 가이드 (review_A.csv / review_B.csv)

양식은 `python A_data_eda/code/01b_review_templates.py`로 만든다. 판정이 한 칸이라도 기록되면 다시 실행해도 덮어쓰지 않는다. Excel로 열어도 되며 저장할 때 **CSV UTF-8** 형식을 유지한다.

## 작업 순서

1. 위쪽 `assigned_to = AB` 14행을 **상대방과 상의하지 않고** 각자 판정한다.
2. 두 사람 결과를 비교해 다른 항목은 기준을 맞추고 `decisions.md`에 기록한다.
3. 나머지 자기 담당 행을 판정한다.

## 칸별 작성법

| 칸 | 값 | 설명 |
|---|---|---|
| `protein_claim` | `1` / `0` / 빈칸 | 1 = 포장·제조사 공식 설명에서 고단백·프로틴·단백질 ○g 등을 제품 특징으로 강조. 0 = 확인했으나 강조 없음. 빈칸 = 확인 불가(미상). **제품명이나 영양정보 표 수치만으로 1을 주지 않는다.** 미상을 0으로 바꾸지 않는다 |
| `claim_text` | 문구 | 근거가 된 표시 문구 그대로. 예: `단백질 20g`, `고단백`. 0이면 비워도 됨 |
| `evidence_url` | URL | 확인한 제조사 페이지·공식몰·상품 상세 페이지. `search_url`(검색 결과)은 근거 URL로 쓰지 않는다 |
| `checked_at` | `YYYY-MM-DD` | 확인한 날짜 |
| `proposed_series_id` | 예: `S0001` | 같은 라인에서 맛만 다른 제품은 같은 ID. ID에 영양값·집단을 넣지 않는다. A·B가 겹치지 않게 A는 `S0001~S0499`, B는 `S0500~S0999`를 쓰고 A가 최종 통합 |
| `series_reason` | 짧은 문장 | 예: `같은 브랜드 라인, 맛만 다름`, `저당 라인이라 분리` |
| `inclusion_status` | `include` / `exclude` / `hold` | hold = 다시 함께 볼 것 |
| `exclusion_reason` | 아래 코드 | exclude·hold일 때 |
| `notes` | 자유 | 원재료·배합 연도 불일치 등 |

## 제외 코드 (`exclusion_reason`)

| 코드 | 의미 |
|---|---|
| `out_of_scope_form` | 형태가 범위 밖 (캔디바, 쿠키, 마시는·짜먹는 요거트, 분말, 워터류) |
| `non_dairy` | 음료가 유제품 기반이 아님 (식물성 단백질 위주 등) |
| `medical_food` | 환자용·특수의료 목적 제품 |
| `discontinued_or_not_found` | 제품 정보를 찾을 수 없음 |
| `formula_mismatch` | 영양 DB와 현재 포장의 배합·연도가 다름 |
| `duplicate` | 다른 후보와 같은 제품 (용량만 다름 등). notes에 대상 candidate_id |
| `other` | 기타. notes에 설명 |

## 참고 칸 (수정하지 않음)

`assigned_to`, `food_group`, `screen_stratum`(0 = 키워드 없음, 1 = 이름에 단백질 키워드, 2 = 요거트 그릭류), `product_name`, `manufacturer`(위탁 생산 공장일 수 있음, 브랜드 아님), `rep_food_name`, `yogurt_style`, `ingredient_check`, `has_plant_protein`(1이면 유제품 기반인지 특히 확인), `auto_series_key`(자동 제안), `search_url`(네이버 검색 바로가기).

판정은 단백질·열량·효율 값을 보고 정하지 않는다. 판정이 끝날 때까지 영양값을 열어보지 않는다.
