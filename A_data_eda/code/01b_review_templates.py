"""01b_review_templates.py — 수작업 판정 양식 생성 (담당 A)

입력  shared/data/raw/candidates.csv
출력  shared/data/raw/review_A.csv, review_B.csv

추출된 후보(sampled=1) 중 각자 담당(A 또는 B)과 공동 판정(AB) 제품을 담는다.
공동 판정 행을 위에 둔다. 기존 후보와 참고 칸이 그대로라면 새 후보만 뒤에 추가한다.
이미 작성된 판정은 유지하며, 작성된 파일의 기존 후보나 참고 칸이 달라졌으면 실행을 중단한다.
Excel에서 한글이 깨지지 않도록 UTF-8(BOM)으로 저장한다. 읽을 때는 encoding="utf-8-sig".
실행: python A_data_eda/code/01b_review_templates.py
"""
from pathlib import Path
from urllib.parse import quote

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "shared/data/raw"

# 협업 명세서의 판정 컬럼 + 실행 기준 확정안의 claim_text
REVIEW_COLS = ["candidate_id", "reviewer", "protein_claim", "claim_text", "evidence_url", "checked_at",
               "proposed_series_id", "series_reason", "inclusion_status", "exclusion_reason", "notes"]
# 판정에 참고할 정보(판정 결과가 아님)
CONTEXT_COLS = ["assigned_to", "food_group", "screen_stratum", "product_name", "manufacturer", "rep_food_name",
                "yogurt_style", "ingredient_check", "has_plant_protein", "auto_series_key", "search_url"]
FILLED = REVIEW_COLS[2:]


def build(cand, reviewer):
    rows = cand[(cand["sampled"] == "1") & cand["assigned_to"].isin([reviewer, "AB"])].copy()
    rows["search_url"] = "https://search.naver.com/search.naver?query=" + rows["product_name"].map(quote)
    rows["calib"] = rows["assigned_to"].ne("AB")          # 공동 판정 먼저
    rows = rows.sort_values(["calib", "food_group", "screen_stratum", "auto_series_key", "candidate_id"])
    for c in REVIEW_COLS[1:]:
        rows[c] = ""
    rows["reviewer"] = reviewer
    return rows[REVIEW_COLS + CONTEXT_COLS]


def main():
    cand = pd.read_csv(RAW / "candidates.csv", dtype=str, keep_default_na=False)
    outputs = {}
    for reviewer in ["A", "B"]:
        path = RAW / f"review_{reviewer}.csv"
        out = build(cand, reviewer)
        if path.exists():
            old = pd.read_csv(path, dtype=str, encoding="utf-8-sig", keep_default_na=False)
            if (old[FILLED] != "").any().any():
                current = out.set_index("candidate_id", verify_integrity=True)
                saved = old.set_index("candidate_id", verify_integrity=True)
                if (not saved.index.isin(current.index).all()
                        or not saved[CONTEXT_COLS].equals(current.loc[saved.index, CONTEXT_COLS])):
                    raise SystemExit(f"{path.name}: 작성된 양식의 기존 후보 또는 참고 칸이 달라졌습니다.")
                added = out[~out["candidate_id"].isin(saved.index)]
                if added.empty:
                    print(f"{path.name}: 새 후보가 없어 기존 양식을 유지합니다.")
                    continue
                out = pd.concat([old, added], ignore_index=True)
        outputs[path] = out

    for path, out in outputs.items():
        out.to_csv(path, index=False, encoding="utf-8-sig")
        n_ab = (out["assigned_to"] == "AB").sum()
        print(f"{path.name}: {len(out)}행 (공동 {n_ab}, 단독 {len(out) - n_ab})")
        print(out.groupby(["food_group", "screen_stratum"]).size().to_string())


if __name__ == "__main__":
    main()
