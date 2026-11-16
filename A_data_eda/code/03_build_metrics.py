"""03_build_metrics.py — 제품 표로 시리즈 단위 표 2종을 만든다 (담당 A)

입력  shared/data/processed/products.csv
출력  shared/data/processed/series_statistics.csv   통계용: 지표별 유효 제품의 평균과 개수
      shared/data/processed/series_ml.csv           ML용: 당류·나트륨·포화지방이 모두 있는 제품만의 평균

- 효율 평균은 제품별 효율의 평균이며 '평균 단백질 / 평균 열량'이 아니다.
- 지표마다 결측 제품이 다를 수 있으므로 지표별 유효 제품 수(n_*)를 함께 저장한다.
- 유효 제품이 없는 지표는 평균을 빈칸, n을 0으로 둔다.
- 저장할 때 반올림하지 않는다.
실행: python A_data_eda/code/03_build_metrics.py   (02_clean.py 다음)
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "shared/data/processed"

KEYS = ["series_id", "food_group", "protein_claim", "basis_unit"]
STAT_METRICS = {                  # 결과 이름 : 제품 컬럼
    "efficiency": "protein_efficiency",
    "sugar": "sugar_g",
    "sodium": "sodium_mg",
    "sat_fat": "sat_fat_g",
    "energy": "energy_kcal",
    "protein": "protein_g",
}
ML_INPUTS = {"sugar": "sugar_g", "sodium": "sodium_mg", "sat_fat": "sat_fat_g"}


def series_statistics(p):
    g = p.groupby(KEYS, sort=True)
    out = g.size().rename("n_products_total").to_frame()
    for name, col in STAT_METRICS.items():
        out[f"{name}_mean"] = g[col].mean()          # mean()은 결측을 건너뛴다
        out[f"n_{name}"] = g[col].count()
    out["data_version"] = p["data_version"].iloc[0]
    return out.reset_index()


def series_ml(p):
    complete = p.dropna(subset=list(ML_INPUTS.values()))
    g = complete.groupby(KEYS, sort=True)
    out = g[list(ML_INPUTS.values())].mean()
    out.columns = [f"{name}_mean" for name in ML_INPUTS]
    out["n_complete_products"] = g.size()
    out["data_version"] = p["data_version"].iloc[0]
    return out.reset_index()


def main():
    p = pd.read_csv(PROCESSED / "products.csv", dtype={"series_id": str, "source_food_code": str})
    stats = series_statistics(p)
    ml = series_ml(p)
    stats.to_csv(PROCESSED / "series_statistics.csv", index=False, encoding="utf-8")
    ml.to_csv(PROCESSED / "series_ml.csv", index=False, encoding="utf-8")

    print(f"제품 {len(p)} → 통계용 시리즈 {len(stats)}, ML용 시리즈 {len(ml)}")
    n = stats.groupby(["food_group", "protein_claim"])["n_efficiency"].apply(lambda s: (s > 0).sum())
    table = n.unstack(fill_value=0).rename(columns={0: "n_regular", 1: "n_high"})
    table["inference_ok(>=10)"] = (table.min(axis=1) >= 10)
    print("\n효율 계산 가능 시리즈 수:")
    print(table)
    missing = {f"n_{k}": int((stats[f"n_{k}"] < stats["n_products_total"]).sum()) for k in STAT_METRICS}
    print("\n결측 제품이 있는 시리즈 수:", missing)


if __name__ == "__main__":
    main()
