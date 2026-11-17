"""06_pool_protein.py — 보조 분석: 후보 전체에서 단백질 함량과 다른 성분의 관계 (담당 A)

광고 기준 주분석은 수작업 판정 표본만 쓰지만, 이 분석은 판정 없이 규칙을 통과한 후보 전체를 쓴다.
단백질 수준은 식약처 영양성분 강조표시 기준(1일 기준치 55g)으로 나눈다.
  바·요거트  100g당  5.5g 이상 '급원',  11g 이상 '고'
  유제품 음료 100mL당 2.75g 이상 '급원', 5.5g 이상 '고'
100kcal당 기준은 단백질 효율과 같은 값이라 쓰지 않는다 (shared/docs/decisions.md ⑭).

입력  shared/data/raw/candidates.csv, processed_foods_mfds.csv
      shared/data/processed/products.csv            (광고 기준 교차표용)
출력  shared/data/processed/pool_series.csv         자동 시리즈 키별 평균 + 단백질 수준
      shared/results/pool_spearman.csv              식품군별 단백질 함량과 다른 성분의 순위상관 (기술 통계)
      shared/results/claim_vs_legal.csv             광고 강조 여부 × 법적 '고' 충족 교차표
      shared/figures/pool_protein_levels.png        단백질 수준별 당류·나트륨·포화지방·열량 분포
실행: python A_data_eda/code/06_pool_protein.py
"""
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd

matplotlib.use("Agg")
ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "shared/data/raw"
PROCESSED = ROOT / "shared/data/processed"
RESULTS = ROOT / "shared/results"
FIGURES = ROOT / "shared/figures"

DAILY_PROTEIN = 55
SHARE = {"bar": 1.0, "yogurt": 1.0, "dairy_drink": 0.5}   # 100mL 기준은 100g 기준의 절반
LEVELS = ["기준 미만", "급원(10%+)", "고(20%+)"]
GROUPS = {"bar": ("바", "100g"), "yogurt": ("요거트", "100g"), "dairy_drink": ("유제품 음료", "100mL")}
COLS = {"단백질(g)": "protein_g", "에너지(kcal)": "energy_kcal", "당류(g)": "sugar_g",
        "나트륨(mg)": "sodium_mg", "포화지방산(g)": "sat_fat_g"}
OTHERS = {"sugar_g": ("당류", "g"), "sodium_mg": ("나트륨", "mg"),
          "sat_fat_g": ("포화지방", "g"), "energy_kcal": ("열량", "kcal")}
LEVEL_COLORS = ["#c3c2b7", "#7fb3ea", "#2a78d6"]           # 한 색상(파랑)의 밝기 단계
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"

plt.rcParams.update({
    "font.family": ["Malgun Gothic", "NanumGothic", "sans-serif"], "axes.unicode_minus": False,
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "axes.edgecolor": GRID,
    "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED, "axes.titlecolor": INK,
    "font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
})


def thresholds(group):
    base = DAILY_PROTEIN * SHARE[group]
    return 0.10 * base, 0.20 * base


def protein_level(row):
    low, high = thresholds(row["food_group"])
    if pd.isna(row["protein_g"]):
        return None
    return LEVELS[2] if row["protein_g"] >= high else LEVELS[1] if row["protein_g"] >= low else LEVELS[0]


def load_pool():
    cand = pd.read_csv(RAW / "candidates.csv", dtype=str, keep_default_na=False)
    cand = cand[cand["cafe_drink"] != "1"]  # 라떼·밀크티·커피 유형은 범위 밖 (decisions ②)
    src = pd.read_csv(RAW / "processed_foods_mfds.csv", dtype=str, encoding="utf-8-sig",
                      usecols=["식품코드", *COLS])
    pool = cand.merge(src, left_on="source_food_code", right_on="식품코드", how="left", validate="many_to_one")
    for raw, col in COLS.items():
        pool[col] = pd.to_numeric(pool[raw], errors="coerce")
    energy = pool["energy_kcal"].where(pool["energy_kcal"] > 0)
    pool["protein_efficiency"] = pool["protein_g"] / energy * 100
    return pool


def to_series(pool):
    """자동 시리즈 키별 제품 평균. 맛이 많은 라인이 결과를 지배하지 않도록 한다."""
    value_cols = [*COLS.values(), "protein_efficiency"]
    s = pool.groupby(["food_group", "auto_series_key"])[value_cols].mean()
    s["n_products"] = pool.groupby(["food_group", "auto_series_key"]).size()
    s = s.reset_index()
    s["protein_level"] = s.apply(protein_level, axis=1)
    return s


def spearman_table(s):
    rows = []
    for g, d in s.groupby("food_group"):
        for col, (name, _) in OTHERS.items():
            pair = d[["protein_g", col]].dropna()
            rows.append({"food_group": g, "metric": name, "n_series": len(pair),
                         "spearman_rho": pair["protein_g"].corr(pair[col], method="spearman")})
    return pd.DataFrame(rows)


def claim_vs_legal():
    p = pd.read_csv(PROCESSED / "products.csv", dtype={"series_id": str})
    p["legal_high"] = p.apply(lambda r: r["protein_g"] >= thresholds(r["food_group"])[1], axis=1)
    table = p.groupby(["food_group", "protein_claim", "legal_high"]).size().unstack(fill_value=0)
    table.columns = ["legal_high_no" if not c else "legal_high_yes" for c in table.columns]
    table["data_version"] = p["data_version"].iloc[0]
    return table.reset_index()


def plot_levels(s):
    fig, axes = plt.subplots(len(OTHERS), 3, figsize=(9, 2.5 * len(OTHERS)))
    for j, (g, (gname, unit)) in enumerate(GROUPS.items()):
        d = s[s["food_group"] == g]
        counts = d["protein_level"].value_counts()
        for i, (col, (name, u)) in enumerate(OTHERS.items()):
            ax = axes[i, j]
            data = [d.loc[d["protein_level"] == lv, col].dropna() for lv in LEVELS]
            box = ax.boxplot(data, widths=0.55, patch_artist=True, showfliers=False,
                             medianprops={"color": INK, "linewidth": 1.5},
                             whiskerprops={"color": MUTED}, capprops={"color": MUTED})
            for patch, color in zip(box["boxes"], LEVEL_COLORS):
                patch.set(facecolor=color, edgecolor=SURFACE, linewidth=1.5)
            ax.set_xticks(range(1, 4), [f"{lv}\n(n={counts.get(lv, 0)})" for lv in LEVELS], fontsize=7.5)
            ax.set_title(f"{gname} · {name}", loc="left", fontsize=10)
            ax.set_ylabel(f"{u} / {unit}")
            ax.grid(axis="y", color=GRID, linewidth=0.8)
            ax.set_axisbelow(True)
    fig.suptitle("법적 단백질 강조 기준별 다른 성분 분포 (후보 전체, 자동 시리즈 평균, 이상치 표시 생략)",
                 x=0.01, ha="left", color=INK)
    fig.tight_layout()
    return fig


def main():
    pool = load_pool()
    series = to_series(pool)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    series.to_csv(PROCESSED / "pool_series.csv", index=False, encoding="utf-8")

    rho = spearman_table(series)
    rho.to_csv(RESULTS / "pool_spearman.csv", index=False, encoding="utf-8")
    cross = claim_vs_legal()
    cross.to_csv(RESULTS / "claim_vs_legal.csv", index=False, encoding="utf-8")

    fig = plot_levels(series)
    fig.savefig(FIGURES / "pool_protein_levels.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    print(f"후보 제품 {len(pool)} → 자동 시리즈 {len(series)}")
    print(pd.crosstab(series["food_group"], series["protein_level"])[LEVELS])
    print("\n단백질 함량과의 순위상관 (기술 통계, 검정 아님):")
    print(rho.pivot(index="food_group", columns="metric", values="spearman_rho").round(2))
    print("\n광고 강조 × 법적 '고' 충족 (판정 표본):")
    print(cross.to_string(index=False))


if __name__ == "__main__":
    main()
