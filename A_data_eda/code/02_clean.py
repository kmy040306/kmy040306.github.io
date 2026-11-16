"""02_clean.py — 판정 결과를 합쳐 정제된 제품 표를 만든다 (담당 A)

입력  shared/data/raw/candidates.csv                후보 목록 (01_collect.py)
      shared/data/raw/review_A.csv, review_B.csv    수작업 판정 (B 파일은 없거나 비어 있어도 됨)
      shared/data/raw/processed_foods_mfds.csv      주자료 영양성분
출력  shared/data/processed/products.csv            한 행 = 분석에 포함된 개별 제품
      shared/results/exclusions.csv                 추출된 후보 중 포함되지 않은 제품과 사유
      shared/results/review_conflicts.csv           공동 판정(AB)에서 A·B가 다르게 판정한 항목

규칙 (shared/docs/selection_rules.md, decisions.md)
- 공동 판정(AB) 후보는 A·B 판정이 모두 있고 서로 같을 때만 확정한다.
- protein_claim이 빈칸(미상)이면 포함 판정이어도 주분석에서 제외한다.
- 영양값은 원자료 그대로 쓰고 실제 0은 유지한다. 숫자가 아닌 값은 결측으로 두고 로그에 남긴다.
- 단백질 효율 = 단백질 / 열량 × 100 (g/100kcal). 열량이 0·결측이면 계산하지 않는다.
실행: python A_data_eda/code/02_clean.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "shared/data/raw"
PROCESSED = ROOT / "shared/data/processed"
RESULTS = ROOT / "shared/results"
DATA_VERSION = "v000-draft"          # A·B 판정과 B 검수가 끝나면 v001로 올린다

DECISION_COLS = ["protein_claim", "claim_text", "evidence_url", "checked_at", "proposed_series_id",
                 "series_reason", "inclusion_status", "exclusion_reason", "notes"]
NUTRIENTS = {                                     # 원자료 컬럼 -> 계약 컬럼
    "단백질(g)": "protein_g",
    "에너지(kcal)": "energy_kcal",
    "당류(g)": "sugar_g",
    "나트륨(mg)": "sodium_mg",
    "포화지방산(g)": "sat_fat_g",
}
UNIT = {"100g": "g", "100mL": "mL"}


def read_csv(path):
    return pd.read_csv(path, dtype=str, encoding="utf-8-sig", keep_default_na=False)


def load_reviews():
    """판정 파일을 읽어 판정이 적힌 행만 남긴다. 파일이 없으면 빈 표."""
    frames = []
    for reviewer in ["A", "B"]:
        path = RAW / f"review_{reviewer}.csv"
        if not path.exists():
            continue
        r = read_csv(path)
        r = r[r["inclusion_status"].str.strip() != ""]
        frames.append(r[["candidate_id", "reviewer", "assigned_to"] + DECISION_COLS])
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def resolve(reviews):
    """후보별 최종 판정. 단독 담당은 그대로, 공동(AB)은 두 판정이 일치할 때만 확정."""
    final, conflicts = [], []
    key = ["protein_claim", "inclusion_status", "proposed_series_id"]
    for cid, g in reviews.groupby("candidate_id"):
        if g["assigned_to"].iloc[0] != "AB":
            final.append(g.iloc[0])
            continue
        if g["reviewer"].nunique() < 2:
            row = g.iloc[0].copy()
            row["inclusion_status"], row["exclusion_reason"] = "hold", "awaiting_second_review"
            final.append(row)
            continue
        a, b = g[g["reviewer"] == "A"].iloc[0], g[g["reviewer"] == "B"].iloc[0]
        # 시리즈 ID는 A·B 번호 범위가 달라 비교하지 않는다
        if (a[key[:2]] == b[key[:2]]).all():
            final.append(a)
        else:
            conflicts.append({"candidate_id": cid, **{f"A_{k}": a[k] for k in key}, **{f"B_{k}": b[k] for k in key}})
            row = a.copy()
            row["inclusion_status"], row["exclusion_reason"] = "hold", "review_conflict"
            final.append(row)
    return pd.DataFrame(final), pd.DataFrame(conflicts)


def to_number(s, log, cid, col):
    v = pd.to_numeric(s, errors="coerce")
    bad = v.isna() & s.str.strip().ne("")
    for c, raw in zip(cid[bad], s[bad]):
        log.append({"candidate_id": c, "column": col, "raw_value": raw})
    return v


def build_products(cand, decided, source):
    inc = decided[(decided["inclusion_status"] == "include") & decided["protein_claim"].isin(["0", "1"])]
    p = inc.merge(cand, on="candidate_id", how="left", suffixes=("", "_cand"))
    p = p.merge(source, left_on="source_food_code", right_on="식품코드", how="left", validate="many_to_one")

    log = []
    for raw_col, col in NUTRIENTS.items():
        p[col] = to_number(p[raw_col], log, p["candidate_id"], col)

    p["original_basis_amount"] = 100
    p["original_basis_unit"] = p["영양성분함량기준량"].str.replace("ml", "mL")
    p["basis_amount"] = 100
    p["basis_unit"] = p["original_basis_unit"].map(UNIT)
    energy = p["energy_kcal"].where(p["energy_kcal"] > 0)
    p["protein_efficiency"] = p["protein_g"] / energy * 100

    p = p.sort_values(["food_group", "proposed_series_id", "candidate_id"]).reset_index(drop=True)
    p["product_id"] = [f"P{i:06d}" for i in range(1, len(p) + 1)]
    p["protein_claim"] = p["protein_claim"].astype(int)
    p["data_version"] = DATA_VERSION
    p = p.rename(columns={"proposed_series_id": "series_id"})
    cols = ["product_id", "candidate_id", "series_id", "product_name", "brand", "manufacturer", "food_group",
            "protein_claim", "yogurt_style", "source_id", "source_food_code", "basis_amount", "basis_unit",
            "original_basis_amount", "original_basis_unit", *NUTRIENTS.values(), "protein_efficiency",
            "reviewer", "data_version"]
    return p[cols], pd.DataFrame(log)


def check_products(p):
    """A의 자체 점검: ID 중복, 시리즈 안 집단·식품군·단위 일치, 음수 값."""
    problems = []
    if p["product_id"].duplicated().any():
        problems.append("product_id 중복")
    for col in ["food_group", "protein_claim", "basis_unit"]:
        n = p.groupby("series_id")[col].nunique()
        if (n > 1).any():
            problems.append(f"시리즈 안에서 {col}이 다름: {n[n > 1].index.tolist()}")
    if p["basis_unit"].isna().any():
        problems.append("기준 단위가 100g/100mL가 아닌 행")
    neg = (p[list(NUTRIENTS.values())] < 0).any(axis=1)
    if neg.any():
        problems.append(f"음수 영양값: {p.loc[neg, 'candidate_id'].tolist()}")
    return problems


def main():
    cand = read_csv(RAW / "candidates.csv")
    source = read_csv(RAW / "processed_foods_mfds.csv")[["식품코드", "영양성분함량기준량", *NUTRIENTS]]
    decided, conflicts = resolve(load_reviews())

    products, parse_log = build_products(cand, decided, source)
    problems = check_products(products)

    sampled = cand[cand["sampled"] == "1"][["candidate_id", "food_group"]]
    status = sampled.merge(decided, on="candidate_id", how="left")
    status["inclusion_status"] = status["inclusion_status"].fillna("not_reviewed")
    unknown = (status["inclusion_status"] == "include") & ~status["protein_claim"].isin(["0", "1"])
    status.loc[unknown, ["inclusion_status", "exclusion_reason"]] = ["exclude", "claim_unknown"]
    ex = status[status["inclusion_status"] != "include"].assign(stage="review")
    ex = ex.rename(columns={"exclusion_reason": "reason_code", "notes": "detail", "checked_at": "decided_at"})
    ex["reason_code"] = ex["reason_code"].replace("", "unspecified").fillna(ex["inclusion_status"])

    PROCESSED.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    products.to_csv(PROCESSED / "products.csv", index=False, encoding="utf-8")
    ex[["candidate_id", "food_group", "stage", "inclusion_status", "reason_code", "detail", "reviewer",
        "decided_at"]].to_csv(RESULTS / "exclusions.csv", index=False, encoding="utf-8")
    conflicts.to_csv(RESULTS / "review_conflicts.csv", index=False, encoding="utf-8")

    print(f"추출 후보 {len(sampled)} → 포함 제품 {len(products)}  (data_version={DATA_VERSION})")
    print(status.groupby(["food_group", "inclusion_status"]).size().unstack(fill_value=0))
    print("\n포함 제품의 시리즈 수 (0=일반, 1=고단백):")
    print(products.groupby(["food_group", "protein_claim"])["series_id"].nunique().unstack(fill_value=0))
    print(f"\n공동 판정 불일치 {len(conflicts)}건, 숫자 변환 실패 {len(parse_log)}건")
    print("자체 점검:", "통과" if not problems else problems)


if __name__ == "__main__":
    main()
