"""05_food_comparison.py — 단백질 20g을 얻을 때 함께 먹게 되는 성분 비교 (담당 A)

효율 상위 고단백 시리즈와 닭가슴살·달걀·두부를 '단백질 20g당' 같은 조건에서 비교한다.
  성분 / 단백질 × 20          : 단백질 20g을 얻을 때 함께 먹는 열량·당류·나트륨·포화지방
  기준량 / 단백질 × 20         : 단백질 20g에 필요한 양 (바·요거트·일반 식품 g, 음료 mL)
상위 25%는 식품군별 고단백 시리즈 안에서 효율 75백분위 이상(경계 동률 포함)이다 (decisions.md ⑬).
같은 데이터로 고른 상위 집단이므로 탐색적 사례 비교로만 해석한다. 단백질 20g당 열량은
효율의 역수(2000 / 효율)이므로 효율과 별개의 발견으로 해석하지 않는다.

입력  shared/data/processed/products.csv, series_statistics.csv
      shared/data/raw/raw_foods_rda.csv (닭가슴살·달걀), processed_foods_mfds.csv (두부)
출력  shared/data/processed/reference_foods.csv
      shared/results/food_comparison.csv
      shared/figures/food_comparison.png
실행: python A_data_eda/code/05_food_comparison.py   (03_build_metrics.py 다음)
"""
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

matplotlib.use("Agg")
ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "shared/data/raw"
PROCESSED = ROOT / "shared/data/processed"
RESULTS = ROOT / "shared/results"
FIGURES = ROOT / "shared/figures"
PROTEIN_TARGET = 20

# 사전 선택 기준을 만족하는 항목 (selection_rules.md 5절)
REFERENCES = [
    ("R01", "닭가슴살", "RDA_RAW", "raw_foods_rda.csv", "닭고기_가슴(껍질 제거)_삶은것", "껍질 제거, 삶음, 무첨가"),
    ("R02", "달걀", "RDA_RAW", "raw_foods_rda.csv", "달걀_삶은것", "전란, 삶음, 무첨가"),
    ("R03", "두부", "MFDS_PROC", "processed_foods_mfds.csv", "두부", "일반 두부, 양념·기름 무첨가 (농촌진흥청 성분표 행)"),
]
SRC_COLS = {"단백질(g)": "protein_g", "에너지(kcal)": "energy_kcal", "당류(g)": "sugar_g",
            "나트륨(mg)": "sodium_mg", "포화지방산(g)": "sat_fat_g"}
METRICS = {  # 결과 metric : (제품 컬럼, 단위, 그림 제목)
    "energy": ("energy_kcal", "kcal", "열량"),
    "sugar": ("sugar_g", "g", "당류"),
    "sodium": ("sodium_mg", "mg", "나트륨"),
    "sat_fat": ("sat_fat_g", "g", "포화지방"),
}
GROUPS = {"bar": "바", "yogurt": "요거트", "dairy_drink": "유제품 음료"}
SCOPES = {"top25_high": "효율 상위 25%", "all_high": "고단백 전체"}
COLORS = {"top25_high": "#2a78d6", "all_high": "#9fc3ee", "reference": "#eb6834"}
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"

plt.rcParams.update({
    "font.family": ["Malgun Gothic", "NanumGothic", "sans-serif"], "axes.unicode_minus": False,
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "axes.edgecolor": GRID,
    "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED, "axes.titlecolor": INK,
    "font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
})


def build_references():
    rows = []
    for rid, name, source_id, file, food_name, prep in REFERENCES:
        src = pd.read_csv(RAW / file, dtype=str, encoding="utf-8-sig")
        hit = src[src["식품명"].str.strip() == food_name]
        if "출처명" in hit and len(hit) > 1:                      # 두부: 성분표 행만
            hit = hit[hit["출처명"].str.contains("농촌진흥청")]
        if len(hit) != 1:
            print(f"{name}: 적합 항목 {len(hit)}개 — 비교 보류")
            continue
        h = hit.iloc[0]
        row = {"reference_id": rid, "food_name": name, "source_id": source_id,
               "source_food_code": h["식품코드"], "source_food_name": food_name, "preparation": prep,
               "basis_amount": 100, "basis_unit": "g", "source_year": h["데이터기준일자"][:4]}
        row.update({col: float(h[raw]) for raw, col in SRC_COLS.items()})
        rows.append(row)
    return pd.DataFrame(rows)


def per_20g(df, amount_col="basis_amount"):
    """제품(또는 식품)별 단백질 20g당 값. 단백질이 0·결측이면 계산하지 않는다."""
    out = pd.DataFrame(index=df.index)
    protein = df["protein_g"].where(df["protein_g"] > 0)
    for metric, (col, _, _) in METRICS.items():
        out[metric] = df[col] / protein * PROTEIN_TARGET
    out["amount"] = df[amount_col] / protein * PROTEIN_TARGET
    return out


def top25_series(stats):
    """식품군별 고단백 시리즈 중 효율 75백분위 이상(경계 동률 포함)."""
    high = stats[stats["protein_claim"] == 1]
    cut = high.groupby("food_group")["efficiency_mean"].transform(lambda s: s.quantile(0.75))
    return set(high.loc[high["efficiency_mean"] >= cut, "series_id"])


def compare(products, stats, refs):
    p = products[products["protein_claim"] == 1].copy()
    p = p.join(per_20g(p))
    top = top25_series(stats)
    version = products["data_version"].iloc[0]
    rows = []
    for scope, mask in [("top25_high", p["series_id"].isin(top)), ("all_high", pd.Series(True, index=p.index))]:
        # 제품별 값 → 시리즈 평균 → 식품군 평균 (시리즈마다 같은 가중치)
        s = p[mask].groupby(["food_group", "series_id", "basis_unit"])[[*METRICS, "amount"]].mean().reset_index()
        for (g, unit), d in s.groupby(["food_group", "basis_unit"]):
            for metric in [*METRICS, "amount"]:
                rows.append({"entity_id": f"{g}:{scope}", "entity_type": "product_group", "food_group": g,
                             "selection_scope": scope, "n_series": len(d), "metric": metric,
                             "value_per_20g_protein": d[metric].mean(),
                             "unit": unit if metric == "amount" else METRICS[metric][1], "data_version": version})
    r = refs.join(per_20g(refs))
    for _, ref in r.iterrows():
        for metric in [*METRICS, "amount"]:
            rows.append({"entity_id": ref["reference_id"], "entity_type": "reference", "food_group": ref["food_name"],
                         "selection_scope": "reference", "n_series": np.nan, "metric": metric,
                         "value_per_20g_protein": ref[metric],
                         "unit": "g" if metric == "amount" else METRICS[metric][1], "data_version": version})
    return pd.DataFrame(rows)


def plot(table):
    entities = []
    for g, gname in GROUPS.items():
        for scope, sname in SCOPES.items():
            hit = table[(table["food_group"] == g) & (table["selection_scope"] == scope)]
            if len(hit):
                entities.append((g, scope, f"{gname} · {sname} ({int(hit['n_series'].iloc[0])}개 시리즈)"))
    for name in table.loc[table["entity_type"] == "reference", "food_group"].unique():
        entities.append((name, "reference", name))

    panels = [*METRICS, "amount"]
    fig, axes = plt.subplots(1, len(panels), figsize=(13, 0.42 * len(entities) + 1.4), sharey=True)
    y = np.arange(len(entities))[::-1]
    for ax, metric in zip(axes, panels):
        vals, units = [], []
        for g, scope, _ in entities:
            hit = table[(table["food_group"] == g) & (table["selection_scope"] == scope) & (table["metric"] == metric)]
            vals.append(hit["value_per_20g_protein"].iloc[0] if len(hit) else np.nan)
            units.append(hit["unit"].iloc[0] if len(hit) else "")
        colors = [COLORS[scope] for _, scope, _ in entities]
        ax.barh(y, vals, height=0.62, color=colors)
        for yi, v, u in zip(y, vals, units):
            if not np.isnan(v):
                label = f"{v:,.0f}{u}" if metric == "amount" else f"{v:,.1f}"
                ax.text(v, yi, f" {label}", va="center", color=INK, fontsize=7.5)
        title = "필요한 양 (g 또는 mL)" if metric == "amount" else f"{METRICS[metric][2]} ({METRICS[metric][1]})"
        ax.set_title(title, loc="left", fontsize=10)
        ax.set_xlim(0, np.nanmax(vals) * 1.35)
        ax.grid(axis="x", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        ax.tick_params(axis="x", labelsize=7.5)
    axes[0].set_yticks(y, [label for _, _, label in entities])
    fig.suptitle("단백질 20g을 얻을 때 함께 먹는 성분과 필요한 양 (탐색적 사례 비교)", x=0.01, ha="left", color=INK)
    handles = [plt.Rectangle((0, 0), 1, 1, color=COLORS[k]) for k in COLORS]
    fig.legend(handles, ["고단백 · 효율 상위 25%", "고단백 전체", "일반 단백질 식품"], frameon=False,
               loc="upper right", ncol=3)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    return fig


def main():
    products = pd.read_csv(PROCESSED / "products.csv", dtype={"series_id": str, "source_food_code": str})
    stats = pd.read_csv(PROCESSED / "series_statistics.csv", dtype={"series_id": str})
    refs = build_references()
    refs.to_csv(PROCESSED / "reference_foods.csv", index=False, encoding="utf-8")

    table = compare(products, stats, refs)
    table.to_csv(RESULTS / "food_comparison.csv", index=False, encoding="utf-8")
    fig = plot(table)
    fig.savefig(FIGURES / "food_comparison.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    wide = table.pivot_table(index=["food_group", "selection_scope"], columns="metric",
                             values="value_per_20g_protein").round(1)
    print(f"data_version={products['data_version'].iloc[0]}  (단백질 {PROTEIN_TARGET}g당)")
    print(wide[["amount", "energy", "sugar", "sodium", "sat_fat"]].to_string())


if __name__ == "__main__":
    main()
