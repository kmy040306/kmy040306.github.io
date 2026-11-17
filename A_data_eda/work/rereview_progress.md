# 판정 재검토 진행 상황 (A, 2026-11-17, 작업 중)

기준: `decisions.md` ③ 확정 기준(포장·공식 근거만 인정, 부족하면 빈칸+hold).
결과는 `rereview_progress.tsv`(review_A.csv 칸 순서: candidate_id, protein_claim, claim_text, evidence_url, inclusion_status, exclusion_reason, notes). 아직 review_A.csv에 반영 안 함.

## 반영할 때 규칙
- `inclusion_status=KEEP` → 기존 include/exclude 유지(C00287~289 프로바: C00287 include, 나머지 duplicate 유지), claim·근거만 갱신
- 판정 날짜 `checked_at`=2026-11-17, notes 앞에 `[포장]`/`[공식]`
- 새 요거트 시리즈 ID: Delight C02701~03=S0090, 요밀 C02859=S0091, 에이클래스 시그니처 C02935=S0092, 유얼거트 C03215=S0093, 그릭데이 C02393=S0094, 풀무원다논 그릭 허니 C03337=S0089(기존 라인)
- 이전 판정에서 바뀌는 행: 1→hold(오늘의 요거트 프로틴 7개, C02494, C02121, C00299, C02193), 0→hold(C00525, C01495, C02756), hold→확정(C00067=0, C02618=1, C02619 duplicate)

## 남은 일
1. 기존 보류 중 아직 안 본 행은 그대로 hold 유지(재검토에서도 못 찾음): C00225 C00045 C00253 C00273 C00318 C00327 C00077 C01418 C02156 C02116 C02511 C02531 C02597 C02791 C02885 C02887 C02888 C02971 C03230
2. 공식몰 근거였던 1 판정(셀렉스·랩노쉬·뉴케어·닥터유 등)은 notes에 `[공식]`만 붙이면 됨
3. tsv를 review_A.csv에 반영 → 02~06 재실행 → 결과 확인 → PR
4. 결과: 요거트 고단백 집단이 줄어듦(새 Delight·에이클래스·메치니코프·요하트로 일부 보충) — B에게 공유
