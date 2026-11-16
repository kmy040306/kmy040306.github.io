"""01_collect.py — 후보 목록 생성과 층화 추출 (담당 A)

입력  shared/data/raw/processed_foods_mfds.csv      주자료(가공식품)
      shared/data/raw/raw_materials_report.csv.gz    품목제조보고 원재료(음료 유제품 기반 확인)
출력  shared/data/raw/candidates.csv                 규칙을 통과한 전체 후보 + 추출 여부·담당
      shared/results/prescreen_flow.csv              식품군별 단계별 행 수(표본 흐름표)

규칙의 근거는 shared/docs/selection_rules.md. 영양값은 중복 판정에만 쓰고
집단·추출에는 쓰지 않는다. 실행: python A_data_eda/code/01_collect.py
"""
from pathlib import Path
import re

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "shared/data/raw"
RESULTS = ROOT / "shared/results"
SEED = 42
MAX_SERIES = 30          # 식품군 × 선별층당 기본 최대 시리즈
MAX_GREEK_SERIES = 50    # 요거트 선별층 2의 보충 추출 후 최대 시리즈
MAX_FLAVORS = 3          # 시리즈당 최대 제품(맛)
SOURCE_ID = "MFDS_PROC"
NUTRIENTS = ["에너지(kcal)", "단백질(g)", "당류(g)", "나트륨(mg)", "포화지방산(g)"]

PROTEIN_WORDS = r"프로틴|단백질|고단백|protein"

# ---------- 식품군 규칙 ----------
BAR_REPS = {"시리얼바/에너지바/영양바", "일반과자", "초콜릿과자", "견과류 가공품", "견과류",
            "기타 농산가공품", "기타가공품", "시리얼", "두류가공품"}
BAR_NAME = (r"(?:프로틴|단백질|에너지|시리얼|그래놀라|견과|너츠|넛츠|뮤즐리|곡물|영양|오트|현미)\s*바(?![가-힣])"
            r"|(?<![가-힣])바(?=\s|\(|$)|\bbar\b")
BAR_SHAPE_EXCL = r"쿠키|웨이퍼|분말|파우더|아이스|바게트|바이트|볼$"
CANDY_BRANDS = r"스니커즈|트윅스|킷캣|킷켓|밀키웨이|자유시간|핫브레이크|마스바|바운티|크런키"
BAR_GRAIN_WORDS = PROTEIN_WORDS + r"|시리얼|그래놀라|견과|너츠|넛츠|곡물|오트|현미|에너지|영양|뮤즐리"

YOGURT_REPS = {"발효유", "농후발효유"}          # 크림발효유(사워크림) 제외
YOGURT_DRINK = r"드링크|드링킹|마시는|drink|쿠르트|짜먹는|사워크림"
GREEK = r"그릭|그리스|greek|아이슬란딕|스키르|skyr"

DAIRY_REPS = {"우유", "우유(멸균)", "가공우유", "가공우유(멸균)", "강화우유", "유당분해우유", "유함유가공품"}
LIQUID_EXCL = (r"두유|아몬드|오트|귀리|옥수수|식물성|비건|커피|라떼|콜드브루|탄산|스파클링|차$|티$|주스|에이드"
               r"|워터|water|이온")
DAIRY_ING = r"우유|원유|분유|유단백|카제인|유청|산양유|유크림|농축유|연유|우유단백"
PLANT_ING = r"대두단백|분리대두|완두단백|쌀단백|두류가공품|아몬드|귀리|오트"
LIQUID_NAME_SCREEN = r"우유|밀크|milk|유청|" + PROTEIN_WORDS

FLAVORS = ("초코|초콜릿|딸기|바닐라|바나나|플레인|블루베리|쿠키앤크림|커피|피넛버터|피넛|땅콩|카라멜|캬라멜|"
           "말차|녹차|흑임자|고구마|오리지널|복숭아|망고|사과|애플|베리|요거트|치즈|솔티드|크림|"
           "아몬드|코코넛|레몬|자몽|포도|체리|밀크티|타로|곡물|흑당|헤이즐넛|모카|민트|시나몬|저당|무가당|라이트")


def has(series, pattern):
    return series.str.contains(pattern, case=False, regex=True, na=False)


def norm_maker(s):
    s = re.sub(r"\(주\)|㈜|주식회사|\(유\)|유한회사|농업회사법인|영농조합법인", "", str(s))
    s = re.sub(r"\S*(공장|센터|CentralKitchen.*|Central Kitchen.*)$", "", s.strip())
    return re.sub(r"[\s\-_.,]", "", s).lower()


def series_key(name):
    """맛·괄호 표기를 지운 제품 라인 이름. 수작업 확정 전의 제안값.
    제조사명은 위탁 생산 공장마다 달라 같은 라인을 쪼개므로 키에 넣지 않는다."""
    s = re.sub(r"\(.*?\)|\[.*?\]", " ", str(name)).lower()
    s = re.sub(r"(?:" + FLAVORS + r")\s*(?:맛|향)?", " ", s)
    s = re.sub(r"\d+\s*(g|ml|입|개)\b", " ", s)
    s = re.sub(r"[^0-9a-z가-힣]", "", s)
    return s or str(name)


def load_main():
    df = pd.read_csv(RAW / "processed_foods_mfds.csv", dtype=str, encoding="utf-8-sig")
    df["식품명"] = df["식품명"].str.replace("﻿", "", regex=False).str.strip()
    return df


def load_ingredients():
    cols = ["PRDLST_REPORT_NO", "RAWMTRL_NM", "CHNG_DT"]
    g = pd.read_csv(RAW / "raw_materials_report.csv.gz", dtype=str, encoding="utf-8-sig", usecols=cols)
    g = g.sort_values("CHNG_DT").drop_duplicates("PRDLST_REPORT_NO", keep="last")
    return g.set_index("PRDLST_REPORT_NO")["RAWMTRL_NM"]


def select_groups(df, ingredients, flow):
    name, rep, base = df["식품명"], df["대표식품명"], df["영양성분함량기준량"]
    out = []

    # bar
    m = (rep.isin(BAR_REPS) & has(name, BAR_NAME)) | (rep == "시리얼바/에너지바/영양바")
    flow.append(("bar", "1_category_and_name", m.sum()))
    m &= base.eq("100g")
    flow.append(("bar", "2_basis_100g", m.sum()))
    candy = has(name, CANDY_BRANDS) | (rep.isin({"초콜릿과자", "초콜릿"}) & ~has(name, BAR_GRAIN_WORDS))
    m &= ~candy & ~has(name, BAR_SHAPE_EXCL)
    flow.append(("bar", "3_exclude_candy_and_shape", m.sum()))
    out.append(df[m].assign(food_group="bar", yogurt_style="", ingredient_check="", has_plant_protein=""))

    # yogurt
    m = rep.isin(YOGURT_REPS)
    flow.append(("yogurt", "1_category", m.sum()))
    m &= base.eq("100g")
    flow.append(("yogurt", "2_basis_100g", m.sum()))
    m &= ~has(name, YOGURT_DRINK)
    flow.append(("yogurt", "3_exclude_drinkable", m.sum()))
    y = df[m].assign(food_group="yogurt", ingredient_check="", has_plant_protein="")
    y["yogurt_style"] = np.where(has(y["식품명"], GREEK), "greek", "regular")
    out.append(y)

    # dairy_drink: 우유류 코드 + 유제품 원료가 확인되는 액상음료
    dairy = rep.isin(DAIRY_REPS)
    liquid = rep.eq("액상음료") & ~has(name, LIQUID_EXCL)
    flow.append(("dairy_drink", "1_category", (dairy | liquid).sum()))
    keep_base = base.eq("100ml")
    flow.append(("dairy_drink", "2_basis_100ml", ((dairy | liquid) & keep_base).sum()))
    d = df[dairy & keep_base].assign(ingredient_check="dairy_code", has_plant_protein="")
    lq = df[liquid & keep_base].copy()
    ing = lq["품목제조보고번호"].map(ingredients)
    lq["has_plant_protein"] = np.where(has(ing, PLANT_ING), "1", "0")
    matched_dairy = ing.notna() & has(ing, DAIRY_ING)
    unmatched_screen = ing.isna() & has(lq["식품명"], LIQUID_NAME_SCREEN)
    lq["ingredient_check"] = np.where(matched_dairy, "dairy_ingredient", "unmatched_name_screen")
    lq.loc[unmatched_screen, "has_plant_protein"] = ""
    lq = lq[matched_dairy | unmatched_screen]
    dd = pd.concat([d, lq]).assign(food_group="dairy_drink", yogurt_style="")
    flow.append(("dairy_drink", "3_dairy_base_check", len(dd)))
    out.append(dd)
    return pd.concat(out, ignore_index=True)


def drop_duplicates(c, flow):
    """같은 제품명+제조사: 영양값이 같으면 최신 1행, 다르면 모두 남기고 표시."""
    c["maker_norm"] = c["제조사명"].map(norm_maker)
    c = c.sort_values("데이터기준일자")
    c = c.drop_duplicates(["food_group", "식품명", "maker_norm"] + NUTRIENTS, keep="last")
    c["dup_conflict"] = c.duplicated(["food_group", "식품명", "maker_norm"], keep=False).map({True: "1", False: ""})
    for g, n in c.groupby("food_group").size().items():
        flow.append((g, "4_after_dedup", n))
    return c


def stratified_sample(c):
    rng = np.random.default_rng(SEED)
    c["auto_series_key"] = c["식품명"].map(series_key)
    # 선별층: 1 = 이름에 단백질 키워드, 2 = (요거트만) 키워드 없이 그릭류, 0 = 나머지. 시리즈 안 최댓값 사용
    # 우선순위 점수(단백질 2 > 그릭 1 > 없음 0)를 시리즈 안에서 최댓값으로 정한 뒤 층 번호로 바꾼다
    priority = np.where(has(c["식품명"], PROTEIN_WORDS), 2,
                        np.where((c["food_group"] == "yogurt") & has(c["식품명"], GREEK), 1, 0))
    best = pd.Series(priority, index=c.index).groupby([c["food_group"], c["auto_series_key"]]).transform("max")
    c["screen_stratum"] = best.map({2: 1, 1: 2, 0: 0})
    c = c.sort_values(["food_group", "auto_series_key", "식품명", "식품코드"]).reset_index(drop=True)
    c["candidate_id"] = [f"C{i:05d}" for i in range(1, len(c) + 1)]
    c["series_rank"], c["sampled"] = np.nan, 0

    strata = c.groupby(["food_group", "screen_stratum"], sort=True)
    for _, part in strata:
        sample_series(c, part, rng, MAX_SERIES)

    # 기존 추출을 모두 끝낸 뒤 보충해 기존 표본·담당·공동 판정이 바뀌지 않게 한다.
    remaining_greek = c[(c["food_group"] == "yogurt")
                        & (c["screen_stratum"] == 2) & c["series_rank"].isna()]
    sample_series(c, remaining_greek, rng, MAX_GREEK_SERIES - MAX_SERIES, start_rank=MAX_SERIES + 1)
    return c


def sample_series(c, part, rng, limit, start_rank=1):
    keys = np.array(sorted(part["auto_series_key"].unique()))
    order = rng.permutation(len(keys))[:limit]
    for rank, key in enumerate(keys[order], start=start_rank):
        idx = part.index[part["auto_series_key"] == key]
        c.loc[idx, "series_rank"] = rank
        pick = rng.permutation(len(idx))[:MAX_FLAVORS]
        c.loc[idx[pick], "sampled"] = 1


def assign_reviewers(c):
    """시리즈 단위로 A/B 교대 배정. 각 식품군×선별층 1·2순위 시리즈의 첫 제품은 공동 판정(AB)."""
    c["assigned_to"] = ""
    s = c[c["sampled"] == 1]
    for _, part in s.groupby(["food_group", "screen_stratum"]):
        for rank, idx in part.groupby("series_rank").groups.items():
            c.loc[idx, "assigned_to"] = "A" if int(rank) % 2 else "B"
            if rank <= 2:
                c.loc[idx[0], "assigned_to"] = "AB"
    return c


def main():
    flow = []
    df = load_main()
    cand = select_groups(df, load_ingredients(), flow)
    cand = drop_duplicates(cand, flow)
    cand = assign_reviewers(stratified_sample(cand))
    for (g, s), n in cand[cand["sampled"] == 1].groupby(["food_group", "screen_stratum"])["auto_series_key"].nunique().items():
        flow.append((g, f"5_sampled_series_stratum{s}", n))

    out = cand.rename(columns={"식품명": "product_name", "제조사명": "manufacturer", "식품코드": "source_food_code",
                               "품목제조보고번호": "report_no", "대표식품명": "rep_food_name",
                               "영양성분함량기준량": "basis_unit"})
    out["brand"], out["source_id"] = "", SOURCE_ID
    out["basis_unit"] = out["basis_unit"].str.replace("ml", "mL")
    cols = ["candidate_id", "product_name", "brand", "manufacturer", "food_group", "source_id", "source_food_code",
            "assigned_to", "report_no", "rep_food_name", "basis_unit", "yogurt_style", "ingredient_check",
            "has_plant_protein", "dup_conflict", "auto_series_key", "screen_stratum", "series_rank", "sampled"]
    out[cols].to_csv(RAW / "candidates.csv", index=False, encoding="utf-8")
    RESULTS.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(flow, columns=["food_group", "step", "n_rows"]).to_csv(RESULTS / "prescreen_flow.csv", index=False)

    print(pd.DataFrame(flow, columns=["food_group", "step", "n"]).to_string(index=False))
    print(out[out["sampled"] == 1].groupby(["food_group", "screen_stratum", "assigned_to"]).size().unstack(fill_value=0))


if __name__ == "__main__":
    main()
