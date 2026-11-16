# 판정 양식 작성 가이드 (review_A.csv / review_B.csv)

양식은 `python A_data_eda/code/01b_review_templates.py`로 만든다. 재실행하면 기존 후보와 참고 칸이 동일한 경우에만 새 후보를 뒤에 추가하며 작성된 판정은 유지한다. 작성된 양식의 기존 후보 또는 참고 칸이 달라지면 실행을 중단한다. Excel로 열어도 되며 저장할 때 **CSV UTF-8** 형식을 유지한다.

## 작업 순서

1. 표본 확대 및 아래 근거 기준을 A·B가 합의한 뒤, 위쪽 `assigned_to = AB` 14행을 상대방 답안을 보지 않고 각자 판정한다.
2. 두 사람 결과를 비교해 다른 항목은 기준을 맞추고 `decisions.md`에 기록한다.
3. 나머지 자기 담당 행을 판정한다.

## 칸별 작성법

| 칸 | 값 | 설명 |
|---|---|---|
| `protein_claim` | `1` / `0` / 빈칸 | 1 = 포장·제조사 공식 설명에서 고단백·프로틴·단백질 ○g 등을 제품 특징으로 강조. 0 = 포장이나 제조사 공식 설명을 충분히 확인했고 강조 없음. 빈칸 = 확인 불가(미상). 공식 제품명과 토핑은 아래 기준 적용 |
| `claim_text` | 문구 | 근거가 된 표시 문구 그대로. 예: `단백질 20g`, `고단백`. 0이면 비워도 됨 |
| `evidence_url` | URL | 확인한 제조사 페이지·공식몰·상품 상세 페이지. `search_url`(검색 결과)은 근거 URL로 쓰지 않는다 |
| `checked_at` | `YYYY-MM-DD` | 확인한 날짜 |
| `proposed_series_id` | 예: `S0001` | 같은 라인에서 맛만 다른 제품은 같은 ID. ID에 영양값·집단을 넣지 않는다. A·B가 겹치지 않게 A는 `S0001~S0499`, B는 `S0500~S0999`를 쓰고 A가 최종 통합 |
| `series_reason` | 짧은 문장 | 예: `같은 브랜드 라인, 맛만 다름`, `저당 라인이라 분리` |
| `inclusion_status` | `include` / `exclude` / `hold` | hold = 다시 함께 볼 것 |
| `exclusion_reason` | 아래 코드 | exclude·hold일 때 |
| `notes` | 자유 | 원재료·배합 연도 불일치 등 |

- 제품명에 단백질·고단백·프로틴·protein이 들어간 경우, 포장이나 제조사 공식 페이지에서 제품 본체 또는 전체의 정식 명칭으로 확인하면 `1`을 준다. DB 이름·검색 결과·판매자 제목이나 영양정보 표만으로는 판정 근거가 부족하다.
- 토핑에만 단백질이 강조되고 본체·전체 강조를 확인하지 못하면 `protein_claim`을 비우고 `hold`로 둔다. 판매 페이지에 강조 문구가 없고 포장·공식 설명 확인도 불충분한 경우에도 같은 방식으로 기록한다.
- 근거 부족으로 보류하면 발견한 근거 URL과 확인일을 가능한 범위에서 적고, `exclusion_reason`과 `notes`에 사유를 기록한다. 제품은 찾았지만 표시 판단이 어려운 경우 코드는 `other`를 쓴다.

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

## 시리즈 ID 통합 (판정이 끝난 뒤)

A(`S0001~`)와 B(`S0500~`)가 같은 제품 라인에 서로 다른 ID를 줄 수 있다. 통합은 자동으로 하지 않는다.

1. `python A_data_eda/code/02_clean.py`를 실행하면 `shared/results/series_merge_suggestions.csv`에 자동 시리즈 키가 같은데 ID가 다른 경우가 나온다. 이 목록은 후보일 뿐이다(예: 같은 이름이라도 41g 라인, 무가당·가당 라인은 의도적으로 분리).
2. 같은 라인으로 판단되면 `shared/docs/series_id_map.csv`에 한 줄 추가한다: `from_series_id,to_series_id,reason,decided_by,decided_at`. 최종 ID로 바로 적고 연쇄(A→B→C)는 쓰지 않는다.
3. 다시 실행하면 `products.csv`의 `series_id`가 통합되고, 원래 제안 ID는 `proposed_series_id`에 남는다. 통합 내역은 `cleaning_log.csv`(`series_merged`)에 기록된다.
4. 통합 후 한 시리즈 안에 집단·식품군·단위가 섞이면 `clean_checks.csv`에 fail이 남고 종료 코드 1로 끝난다. 이 상태로 v001을 확정하지 않는다.
