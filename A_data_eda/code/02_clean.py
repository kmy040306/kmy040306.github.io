"""02_clean.py — 판정 결과를 합쳐 정제된 제품 표를 만든다 (담당 A)

입력  shared/data/raw/candidates.csv                후보 목록 (01_collect.py)
      shared/data/raw/review_A.csv, review_B.csv    수작업 판정 (B 파일은 없거나 비어 있어도 됨)
      shared/data/raw/processed_foods_mfds.csv      주자료 영양성분
      shared/docs/series_id_map.csv                 시리즈 ID 통합 결정 (A·B가 같은 라인에 다른 ID를 준 경우)
출력  shared/data/processed/products.csv            한 행 = 분석에 포함된 개별 제품
      shared/results/exclusions.csv                 추출된 후보 중 포함되지 않은 제품과 사유
      shared/results/review_conflicts.csv           공동 판정(AB)에서 A·B가 다르게 판정한 항목
      shared/results/cleaning_log.csv               정제 중 생긴 일: 숫자 변환 실패, 원자료 미결합, 0값, ID 통합
      shared/results/clean_checks.csv               자체 점검 항목별 통과·실패 (실패가 있으면 종료 코드 1)
      shared/results/series_merge_suggestions.csv   자동 시리즈 키가 같은데 ID가 다른 시리즈 — 통합 검토용

규칙 (shared/docs/selection_rules.md, decisions.md)
- 공동 판정(AB) 후보는 A·B 판정이 모두 있고 서로 같을 때만 확정한다.
- protein_claim이 빈칸(미상)이면 포함 판정이어도 주분석에서 제외한다.
- 영양값은 원자료 그대로 쓰고 실제 0은 유지한다. 숫자가 아닌 값은 결측으로 두고 로그에 남긴다.
- 단백질 효율 = 단백질 / 열량 × 100 (g/100kcal). 열량이 0·결측이면 계산하지 않는다.
- 시리즈 ID: 판정자가 제안한 ID(proposed_series_id)에 series_id_map.csv를 적용해 최종 series_id를 만든다.
  통합은 자동으로 하지 않고, 통합 후보만 series_merge_suggestions.csv로 제안한다.
실행: python A_data_eda/code/02_clean.py
"""
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "shared/data/raw"
PROCESSED = ROOT / "shared/data/processed"
RESULTS = ROOT / "shared/results"
SERIES_MAP = ROOT / "shared/docs/series_id_map.csv"
MAP_COLS = ["from_series_id", "to_series_id", "reason", "decided_by", "decided_at"]
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
        log.append({"event": "parse_error", "candidate_id": c, "column": col, "value": raw,
                    "detail": "숫자가 아닌 값 → 결측 처리"})
    return v


def load_series_map():
    """시리즈 ID 통합표를 읽고 검증한다. 파일이 없으면 빈 표."""
    if not SERIES_MAP.exists():
        return pd.DataFrame(columns=MAP_COLS)
    m = read_csv(SERIES_MAP)
    if m["from_series_id"].duplicated().any():
        raise ValueError("series_id_map.csv: 같은 from_series_id가 두 번 있습니다.")
    if m["to_series_id"].isin(m["from_series_id"]).any():
        raise ValueError("series_id_map.csv: 통합 대상이 다시 다른 ID로 통합됩니다(연쇄). 최종 ID로 바로 적어 주세요.")
    return m


def apply_series_map(decided, series_map, log):
    mapping = dict(zip(series_map["from_series_id"], series_map["to_series_id"]))
    for sid in sorted(set(mapping) - set(decided["proposed_series_id"])):
        log.append({"event": "series_map_unused", "candidate_id": "", "column": "series_id", "value": sid,
                    "detail": "통합표에 있지만 판정 결과에 없는 ID"})
    decided = decided.copy()
    decided["series_id"] = decided["proposed_series_id"].map(lambda s: mapping.get(s, s))
    changed = decided[decided["series_id"] != decided["proposed_series_id"]]
    for _, r in changed.iterrows():
        log.append({"event": "series_merged", "candidate_id": r["candidate_id"], "column": "series_id",
                    "value": f"{r['proposed_series_id']} -> {r['series_id']}", "detail": "series_id_map.csv"})
    return decided


def build_products(cand, decided, source, log):
    inc = decided[(decided["inclusion_status"] == "include") & decided["protein_claim"].isin(["0", "1"])]
    p = inc.merge(cand, on="candidate_id", how="left", suffixes=("", "_cand"))
    p = p.merge(source, left_on="source_food_code", right_on="식품코드", how="left", validate="many_to_one",
                indicator=True)
    for cid in p.loc[p["_merge"] != "both", "candidate_id"]:
        log.append({"event": "missing_source", "candidate_id": cid, "column": "source_food_code", "value": "",
                    "detail": "원자료에서 식품코드를 찾지 못함"})

    for raw_col, col in NUTRIENTS.items():
        p[col] = to_number(p[raw_col].fillna(""), log, p["candidate_id"], col)
        for cid in p.loc[p[col] == 0, "candidate_id"]:
            log.append({"event": "zero_value", "candidate_id": cid, "column": col, "value": "0",
                        "detail": "표시값 0을 실제 0으로 유지"})

    p["original_basis_amount"] = 100
    p["original_basis_unit"] = p["영양성분함량기준량"].str.replace("ml", "mL")
    p["basis_amount"] = 100
    p["basis_unit"] = p["original_basis_unit"].map(UNIT)
    energy = p["energy_kcal"].where(p["energy_kcal"] > 0)
    p["protein_efficiency"] = p["protein_g"] / energy * 100

    p = p.sort_values(["food_group", "series_id", "candidate_id"]).reset_index(drop=True)
    p["product_id"] = [f"P{i:06d}" for i in range(1, len(p) + 1)]
    p["protein_claim"] = p["protein_claim"].astype(int)
    p["data_version"] = DATA_VERSION
    cols = ["product_id", "candidate_id", "series_id", "proposed_series_id", "product_name", "brand",
            "manufacturer", "food_group",
            "protein_claim", "yogurt_style", "source_id", "source_food_code", "basis_amount", "basis_unit",
            "original_basis_amount", "original_basis_unit", *NUTRIENTS.values(), "protein_efficiency",
            "reviewer", "auto_series_key", "data_version"]
    return p[cols]


def check_products(p, log):
    """A의 자체 점검 (협업 명세서 04). 항목마다 pass/fail과 근거를 남긴다."""
    checks = []

    def add(name, failed, detail=""):
        checks.append({"check": name, "status": "fail" if failed else "pass", "detail": detail})

    add("product_id 중복 없음", p["product_id"].duplicated().any())
    dup = p["candidate_id"].duplicated()
    add("candidate_id 중복 없음", dup.any(), ", ".join(p.loc[dup, "candidate_id"]))
    add("series_id 빈칸 없음", p["series_id"].str.strip().eq("").any())
    for col in ["food_group", "protein_claim", "basis_unit"]:
        n = p.groupby("series_id")[col].nunique()
        add(f"시리즈 안에서 {col} 일치", (n > 1).any(), ", ".join(n[n > 1].index))
    no_unit = p["basis_unit"].isna()
    add("기준 단위가 g 또는 mL", no_unit.any(), ", ".join(p.loc[no_unit, "candidate_id"]))
    neg = (p[list(NUTRIENTS.values())] < 0).any(axis=1)
    add("음수 영양값 없음", neg.any(), ", ".join(p.loc[neg, "candidate_id"]))
    missing = [r["candidate_id"] for r in log if r["event"] == "missing_source"]
    add("모든 제품이 원자료와 결합", bool(missing), ", ".join(missing))
    no_eff = p["protein_efficiency"].isna()
    add("효율 계산 가능 (정보)", False, f"계산 불가 {int(no_eff.sum())}개 " + ", ".join(p.loc[no_eff, "candidate_id"]))
    return pd.DataFrame(checks).assign(data_version=DATA_VERSION)


def merge_suggestions(p):
    """자동 시리즈 키가 같은데 최종 ID가 다른 경우. 맛 표기 차이로 같은 라인일 수 있어 사람이 확인한다."""
    rows = []
    for (fg, key), d in p.groupby(["food_group", "auto_series_key"]):
        ids = sorted(d["series_id"].unique())
        if len(ids) > 1:
            rows.append({"food_group": fg, "auto_series_key": key, "series_ids": "|".join(ids),
                         "reviewers": "|".join(sorted(d["reviewer"].unique())),
                         "product_names": " / ".join(d["product_name"])})
    return pd.DataFrame(rows, columns=["food_group", "auto_series_key", "series_ids", "reviewers", "product_names"])


def main():
    cand = read_csv(RAW / "candidates.csv")
    source = read_csv(RAW / "processed_foods_mfds.csv")[["식품코드", "영양성분함량기준량", *NUTRIENTS]]
    log = []
    decided, conflicts = resolve(load_reviews())
    decided = apply_series_map(decided, load_series_map(), log)

    products = build_products(cand, decided, source, log)
    checks = check_products(products, log)
    suggestions = merge_suggestions(products)

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
    log_cols = ["event", "candidate_id", "column", "value", "detail"]
    pd.DataFrame(log, columns=log_cols).assign(data_version=DATA_VERSION).to_csv(
        RESULTS / "cleaning_log.csv", index=False, encoding="utf-8")
    checks.to_csv(RESULTS / "clean_checks.csv", index=False, encoding="utf-8")
    suggestions.to_csv(RESULTS / "series_merge_suggestions.csv", index=False, encoding="utf-8")

    print(f"추출 후보 {len(sampled)} → 포함 제품 {len(products)}  (data_version={DATA_VERSION})")
    print(status.groupby(["food_group", "inclusion_status"]).size().unstack(fill_value=0))
    print("\n포함 제품의 시리즈 수 (0=일반, 1=고단백):")
    print(products.groupby(["food_group", "protein_claim"])["series_id"].nunique().unstack(fill_value=0))
    events = pd.Series([r["event"] for r in log], dtype=str).value_counts().to_dict()
    print(f"\n공동 판정 불일치 {len(conflicts)}건, 정제 로그 {events}")
    print(f"시리즈 통합 후보 {len(suggestions)}건 → shared/results/series_merge_suggestions.csv")
    print("\n자체 점검:")
    print(checks[["check", "status", "detail"]].to_string(index=False))
    if (checks["status"] == "fail").any():
        print("\n점검 실패 항목이 있습니다. 결과 파일은 저장했지만 v001로 확정하지 마세요.")
        sys.exit(1)


if __name__ == "__main__":
    main()
