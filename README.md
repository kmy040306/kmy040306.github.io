# 고단백 제품은 효율적인 단백질 공급원인가?

팀원 A: 이름 입력 / 팀원 B: 이름 입력

AI and Data Analysis Practice 2인 프로젝트의 초기 작업 공간입니다. 아직 데이터 수집·분석 결과가 없습니다.

## 역할과 저장 위치

| 담당 | 코드 | 작업 노트북 | 설명 |
|---|---|---|---|
| A: 데이터·EDA·일반 식품 비교 | `A_data_eda/code/` | `A_data_eda/notebooks/` | `A_data_eda/explanations/` |
| B: 통계검정·머신러닝 | `B_statistics_ml/code/` | `B_statistics_ml/notebooks/` | `B_statistics_ml/explanations/` |
| 공동: 선정 규칙·출처·결론 | `shared/` | `final/tutorial.ipynb` | `shared/docs/` |

제품 표시·시리즈 수작업 확인은 두 사람이 반씩 분담하고, 처음 10개 후보는 교차 검토합니다. A가 정제한 데이터를 B가 검토한 후 분석용 버전을 확정합니다.

## 과목의 제출 요구

- 사용자명.github.io 저장소와 공개 GitHub Pages URL 한 개.
- Markdown 설명과 Python 코드가 함께 있는 독립적인 튜토리얼.
- 데이터 수집·정제·관리 → EDA → 가설검정 → 머신러닝 → 통찰과 한계.
- 본문 최소 1,500 words, 의미 있는 Python 코드 최소 150줄. 2인 팀은 기대 수준이 높아지지만 정확히 두 배라는 규정은 없음.
- 제목 아래 모든 팀원의 이름, 참고자료, 시각화, 재현 가능한 코드.
- 명세서상 마감: 12월 21일 월요일 오후 4시. 실제 수업 공지도 확인.

## 협업 순서

1. 공동 예비 조사와 선정 규칙 확정.
2. 후보 확인을 반씩 분담.
3. A가 정제·지표·EDA, B가 교차 검토.
4. A가 일반 식품 비교, B가 검정·ML 수행.
5. 각자 explanations에 방법과 해석 작성 후 상대방 검토.
6. final/tutorial.ipynb에 내용을 순서대로 통합하고 커널 재시작 후 전체 실행.
7. `python scripts/export_site.py`로 HTML을 생성하고 결과를 확인한 뒤 커밋.

## 실행 환경

Python 3.11 이상 권장. `python -m pip install -r requirements.txt`로 분석 도구를 설치합니다. 실제 분석 시작 시 검증된 버전을 고정하세요.

## GitHub Pages 설정

저장소 이름: `kmy040306.github.io` (이미 존재하면 기존 내용을 먼저 확인)

Settings → Pages → Deploy from a branch → main → /(root) → Save.
배포 후 예상 URL: https://kmy040306.github.io/ (생성·배포 완료 여부는 별도 확인 필요)

현재 index.html은 별도로 작성한 초기 안내 페이지이며, 최종 과제 분량을 충족한 결과물이 아닙니다.
