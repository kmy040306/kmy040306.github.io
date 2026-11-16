"""04_eda.py — 탐색적 분석: 표본 수, 효율·영양성분 분포 (담당 A)

입력  shared/data/processed/products.csv, series_statistics.csv
      shared/results/prescreen_flow.csv, exclusions.csv
출력  shared/figures/eda_series_counts.png      식품군·집단별 시리즈 수와 10개 기준선
      shared/figures/eda_efficiency.png         시리즈 평균 단백질 효율 분포
      shared/figures/eda_nutrients.png          당류·나트륨·포화지방·열량 분포 (식품군 × 지표)
      shared/results/eda_summary.csv            식품군·집단별 시리즈 수, 중앙값, 0값 개수

그림의 점 하나 = 시리즈 하나(맛별 제품 평균). 검정이 아닌 분포 확인용이다.
실행: python A_data_eda/code/04_eda.py   (03_build_metrics.py 다음)
"""
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

matplotlib.use("Agg")
ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "shared/data/processed"
RESULTS = ROOT / "shared/results"
FIGURES = ROOT / "shared/figures"
SEED = 42

GROUPS = {"bar": "바", "yogurt": "요거트", "dairy_drink": "유제품 음료"}
CLAIMS = {0: "일반", 1: "고단백 강조"}
COLORS = {0: "#2a78d6", 1: "#eb6834"}          # 범주 1·2번 슬롯 (파랑, 주황)
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
METRICS = {  # 시리즈 표 컬럼 : (제목, 단위 앞부분)
    "sugar_mean": ("당류", "g"),
    "sodium_mean": ("나트륨", "mg"),
    "sat_fat_mean": ("포화지방", "g"),
    "energy_mean": ("열량", "kcal"),
}
MIN_SERIES = 10

plt.rcParams.update({
    "font.family": ["Malgun Gothic", "NanumGothic", "sans-serif"],
    "axes.unicode_minus": False, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.titlecolor": INK, "axes.titlesize": 11, "font.size": 9,
    "axes.spines.top": False, "axes.spines.right": False,
})


def unit_of(df, group):
    return "100mL" if df.loc[df["food_group"] == group, "basis_unit"].iloc[0] == "mL" else "100g"


def strip(ax, df, col, rng):
    """집단별 점(시리즈) + 중앙값 막대. x는 집단, 점은 가로로 조금 흩뜨린다."""
    for claim, x in [(0, 0), (1, 1)]:
        y = df.loc[df["protein_claim"] == claim, col].dropna().to_numpy()
        if len(y) == 0:
            continue
        jitter = rng.uniform(-0.15, 0.15, len(y))
        ax.scatter(x + jitter, y, s=28, color=COLORS[claim], alpha=0.85,
                   edgecolor=SURFACE, linewidth=1.5, zorder=3)
        ax.hlines(np.median(y), x - 0.28, x + 0.28, color=INK, linewidth=2, zorder=4)
        ax.text(x + 0.32, np.median(y), f"{np.median(y):.1f}", va="center", color=INK, fontsize=8)
    ax.set_xticks([0, 1], [f"{CLAIMS[c]}\n(n={(df['protein_claim'] == c).sum()})" for c in (0, 1)])
    ax.set_xlim(-0.6, 1.8)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def plot_counts(stats):
    n = stats[stats["n_efficiency"] > 0].groupby(["food_group", "protein_claim"]).size()
    fig, ax = plt.subplots(figsize=(7, 3.2))
    labels = list(GROUPS)
    x = np.arange(len(labels))
    for claim, dx in [(0, -0.18), (1, 0.18)]:
        vals = [n.get((g, claim), 0) for g in labels]
        bars = ax.bar(x + dx, vals, width=0.34, color=COLORS[claim], label=CLAIMS[claim])
        ax.bar_label(bars, padding=2, color=INK, fontsize=8)
    ax.axhline(MIN_SERIES, color=MUTED, linestyle="--", linewidth=1, label=f"추론 분석 기준 ({MIN_SERIES})")
    ax.set_xticks(x, [GROUPS[g] for g in labels])
    ax.set_ylabel("효율 계산 가능 시리즈 수")
    ax.set_title("식품군·집단별 시리즈 수", loc="left")
    ax.set_ylim(0, max(n.max(), MIN_SERIES) * 1.25)
    ax.legend(frameon=False, loc="upper right", ncol=3)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    return fig


def plot_efficiency(stats, rng):
    fig, axes = plt.subplots(1, 3, figsize=(9, 3.4), sharey=True)
    for ax, g in zip(axes, GROUPS):
        strip(ax, stats[stats["food_group"] == g], "efficiency_mean", rng)
        ax.set_title(GROUPS[g], loc="left")
    axes[0].set_ylabel("단백질 효율 (g / 100kcal)")
    fig.suptitle("시리즈 평균 단백질 효율 — 점 하나가 시리즈, 가로선은 중앙값", x=0.01, ha="left", color=INK)
    fig.tight_layout()
    return fig


def plot_nutrients(stats, rng):
    fig, axes = plt.subplots(len(METRICS), 3, figsize=(9, 2.6 * len(METRICS)))
    for j, g in enumerate(GROUPS):
        d = stats[stats["food_group"] == g]
        unit = unit_of(stats, g)
        for i, (col, (name, u)) in enumerate(METRICS.items()):
            ax = axes[i, j]
            strip(ax, d, col, rng)
            ax.set_title(f"{GROUPS[g]} · {name}", loc="left", fontsize=10)
            ax.set_ylabel(f"{u} / {unit}")
    fig.suptitle("영양성분 분포 (식품군마다 기준 단위가 다르므로 세로축을 공유하지 않음)",
                 x=0.01, ha="left", color=INK)
    fig.tight_layout()
    return fig


def summary_table(stats, products):
    rows = []
    for (g, c), d in stats.groupby(["food_group", "protein_claim"]):
        p = products[(products["food_group"] == g) & (products["protein_claim"] == c)]
        row = {"food_group": g, "protein_claim": c, "n_series": len(d), "n_products": len(p),
               "basis_unit": d["basis_unit"].iloc[0]}
        for col in ["efficiency_mean", *METRICS]:
            row[f"median_{col}"] = d[col].median()
        for col in ["sugar_g", "sodium_mg", "sat_fat_g"]:
            row[f"zero_{col}"] = int((p[col] == 0).sum())
        rows.append(row)
    return pd.DataFrame(rows)


def main():
    stats = pd.read_csv(PROCESSED / "series_statistics.csv", dtype={"series_id": str})
    products = pd.read_csv(PROCESSED / "products.csv", dtype={"series_id": str})
    rng = np.random.default_rng(SEED)
    FIGURES.mkdir(parents=True, exist_ok=True)

    for name, fig in [("eda_series_counts", plot_counts(stats)),
                      ("eda_efficiency", plot_efficiency(stats, rng)),
                      ("eda_nutrients", plot_nutrients(stats, rng))]:
        fig.savefig(FIGURES / f"{name}.png", dpi=150, bbox_inches="tight")
        plt.close(fig)

    table = summary_table(stats, products)
    table.to_csv(RESULTS / "eda_summary.csv", index=False, encoding="utf-8")
    print(f"data_version={stats['data_version'].iloc[0]}")
    print(table[["food_group", "protein_claim", "n_series", "n_products",
                 "median_efficiency_mean", "zero_sugar_g", "zero_sat_fat_g"]].to_string(index=False))
    print(f"그림 저장: {FIGURES}")


if __name__ == "__main__":
    main()
