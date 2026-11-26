# 데이터 인수인계 — v001 (2026-11-17, A → B)

A·B 판정을 통합해 확정한 첫 분석용 데이터. 통계·ML은 이 버전으로 실행한다. 이후 판정이 바뀌면 v002로 올리고 이 문서를 새로 쓴다.

## 기준 상태

- main 기준: PR #18 머지 후(`5e71314`) + 이 PR의 버전 표기 변경
- 판정 기준: `decisions.md` ③(포장·제조사 공식 페이지 근거만 인정), 라떼·커피 유형은 추출 후 제외(②, 2026-11-17)
- 공동 판정 14행 A·B 불일치 0건 (`shared/results/review_conflicts.csv` 비어 있음)
- 시리즈 통합 4건 (`shared/docs/series_id_map.csv`)
- `02_clean.py` 자체 점검 10개 전부 pass, B `00_validate_statistics.py` 통과
- 시리즈 평균 재계산 검수: `products.csv`에서 다시 계산한 6개 평균과 `series_statistics.csv` 최대 차이 7e-15

## 표본

| 식품군 | 집단 | 제품 | 시리즈 |
|---|---|---|---|
| 바 | 일반(0) | 14 | 13 |
| 바 | 강조(1) | 25 | 18 |
| 유제품 음료 | 일반(0) | 12 | 11 |
| 유제품 음료 | 강조(1) | 24 | 16 |
| 요거트 | 일반(0) | 29 | 24 |
| 요거트 | 강조(1) | 14 | 10 |
| **합계** | | **118** | **92** |

세 식품군 모두 양 집단 10시리즈 이상 → 추론 분석 대상. 요거트 강조는 10개로 기준선에 딱 걸려 있으므로 결과 해석 때 표본 크기를 함께 밝힌다.

추출 276행 중 포함 118행. 제외·보류 158행(`shared/results/exclusions.csv`):

| 상태 | 사유 | 행 |
|---|---|---|
| 제외 | out_of_scope_form (마시는 요거트·라떼류 등) | 14 |
| 제외 | duplicate | 13 |
| 제외 | non_dairy | 4 |
| 보류 | other (근거 부족·토핑만 강조 등) | 99 |
| 보류 | discontinued_or_not_found | 24 |
| 보류 | 기타 | 4 |

보류는 강조 여부를 확정하지 못한 제품이라 분석에서 빠진다(미상을 일반으로 바꾸지 않음). 한계로 보고한다.

## 파일 (git에 저장된 내용 기준 SHA-256)

| 파일 | 행 | SHA-256 |
|---|---|---|
| `shared/data/raw/candidates.csv` | 3,431 | `613d4c319d0d2cfa6f93f3034d4c89694c19ee31333dde4e839f4196625dd49d` |
| `shared/data/raw/review_A.csv` | 146 | `e2f1b56192b11fd5c2d890b451a37943a60d2fde3474874cf2c6d23347ed2c07` |
| `shared/data/raw/review_B.csv` | 144 | `2a0fdc914653a4444c48319f8d62659ea67b31e340398227659180e5778d2d91` |
| `shared/docs/series_id_map.csv` | 4 | `9d464acea308c8e44746b4173ee699fa5684e0b04a9772c8258c43fc378bef3b` |
| `shared/data/processed/products.csv` | 118 | `c1daf2db79c6218b7b8fbf91a006734e376261a321454a9195fc0cfd64f47dff` |
| `shared/data/processed/series_statistics.csv` | 92 | `4674d1a5ac6bd2a38cf1ffd5cce398674b42f58c58b46de089fb5e020790b0d9` |
| `shared/data/processed/series_ml.csv` | 92 | `c10226888e5976798e560533fa8278e933d46a0bde4cfed1c1a8fda783b2b4eb` |

`review_A.csv`는 2026-11-26 보류 3행의 사유 코드만 채워 해시가 바뀌었다(분석 데이터 변화 없음).

확인: `git show HEAD:<파일> | sha256sum` (Windows 작업 사본은 줄바꿈 변환 때문에 값이 다를 수 있음)

원본 공공데이터 3개 파일의 SHA-256은 `shared/docs/sources.csv`의 비고 칸에 있다.

## 재현

```bash
python A_data_eda/code/02_clean.py
python A_data_eda/code/03_build_metrics.py
python B_statistics_ml/code/00_validate_statistics.py
```

## 다음

- B: `01_tests.py` → `02_interaction.py` → `03_ml.py`를 v001로 실행
- A: 설명문(03·04) 수치를 v001로 갱신, 튜토리얼 통합
