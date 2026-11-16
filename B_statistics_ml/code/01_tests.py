#이 코드가 하는 일
#A가 만든 시리즈 단위 데이터를 이용
#같은 식품군 안에서 단백질 강조 제품과 일반 제품을 비교

from pathlib import Path
import runpy

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests


ROOT = Path(__file__).resolve().parents[2]
RESULT_DIR = ROOT / "shared/results"

ALPHA = 0.05
N_BOOT = 5000
SEED = 42

# 결과표의 지표 이름: 입력 데이터의 컬럼 이름
METRICS = {
    "efficiency": "efficiency_mean",
    "sugar": "sugar_mean",
    "sodium": "sodium_mean",
    "sat_fat": "sat_fat_mean",
    "energy": "energy_mean",
}


def welch_test(high, regular):
    """평균 차이의 Welch 양측 검정과 개별 95% 신뢰구간."""
    if min(len(high), len(regular)) < 2:
        return np.nan, np.nan, np.nan, "insufficient_data"

    difference = high.mean() - regular.mean()

    # 두 표본 평균의 분산 추정값
    a = high.var(ddof=1) / len(high)
    b = regular.var(ddof=1) / len(regular)

    if a + b <= 0:
        return np.nan, np.nan, np.nan, "zero_variance"

    standard_error = np.sqrt(a + b)

    # Welch–Satterthwaite 자유도
    degrees_of_freedom = (a + b) ** 2 / (
        a**2 / (len(high) - 1)
        + b**2 / (len(regular) - 1)
    )

    t_value = difference / standard_error
    p_value = 2 * stats.t.sf(
        abs(t_value), df=degrees_of_freedom
    )
    critical_value = stats.t.ppf(
        1 - ALPHA / 2, df=degrees_of_freedom
    )

    margin = critical_value * standard_error
    return (
        p_value,
        difference - margin,
        difference + margin,
        "ok",
    )


def bootstrap_interval(high, regular, rng):
    """집단별로 시리즈를 복원추출해 평균 차이 구간을 계산한다."""
    if min(len(high), len(regular)) < 2:
        return np.nan, np.nan, "insufficient_data"

    differences = np.empty(N_BOOT)

    for i in range(N_BOOT):
        high_sample = rng.choice(
            high, size=len(high), replace=True
        )
        regular_sample = rng.choice(
            regular, size=len(regular), replace=True
        )
        differences[i] = (
            high_sample.mean() - regular_sample.mean()
        )

    low, high_bound = np.quantile(
        differences, [ALPHA / 2, 1 - ALPHA / 2]
    )
    status = (
        "degenerate_interval"
        if np.all(differences == differences[0])
        else "ok"
    )
    return low, high_bound, status


def main():
    # 숫자로 시작하는 파일명도 불러올 수 있도록 runpy를 사용한다.
    validator_path = Path(__file__).with_name(
        "00_validate_statistics.py"
    )
    validator = runpy.run_path(str(validator_path))
    data, sample_summary = validator["validate_statistics"]()

    print("식품군별 효율 계산 가능 시리즈 수:")
    print(sample_summary.to_string())

    groups = sample_summary.index[
        sample_summary["eligible_for_inference"]
    ].tolist()

    if not groups:
        raise ValueError(
            "양 집단 각각 10시리즈 기준을 충족하는 식품군이 없습니다. "
            "추론 분석을 보류합니다. 기존 결과 파일은 갱신하지 않습니다."
        )

    version = data["data_version"].iloc[0]
    test_rows = []
    bootstrap_rows = []

    # 비교마다 별도의 난수 흐름을 사용한다.
    streams = iter(
        np.random.SeedSequence(SEED).spawn(
            len(groups) * len(METRICS)
        )
    )

    for group in groups:
        group_data = data.loc[data["food_group"].eq(group)]

        for metric, column in METRICS.items():
            high = (
                group_data.loc[
                    group_data["protein_claim"].eq(1), column
                ]
                .dropna()
                .to_numpy(dtype=float)
            )
            regular = (
                group_data.loc[
                    group_data["protein_claim"].eq(0), column
                ]
                .dropna()
                .to_numpy(dtype=float)
            )

            mean_high = high.mean() if len(high) else np.nan
            mean_regular = regular.mean() if len(regular) else np.nan

            common = {
                "data_version": version,
                "food_group": group,
                "metric": metric,
                "n_high": len(high),
                "n_regular": len(regular),
                "mean_high": mean_high,
                "mean_regular": mean_regular,
                "difference": mean_high - mean_regular,
            }

            p_raw, ci_low, ci_high, status = welch_test(
                high, regular
            )
            test_rows.append({
                **common,
                "ci_low": ci_low,
                "ci_high": ci_high,
                "p_raw": p_raw,
                "test_status": status,
                "ci_method": "welch_individual_95pct",
            })

            rng = np.random.default_rng(next(streams))
            boot_low, boot_high, boot_status = bootstrap_interval(
                high, regular, rng
            )
            bootstrap_rows.append({
                **common,
                "ci_low": boot_low,
                "ci_high": boot_high,
                "n_boot": N_BOOT,
                "seed": SEED,
                "bootstrap_status": boot_status,
                "ci_method": "percentile_individual_95pct",
            })

    tests = pd.DataFrame(test_rows)
    bootstrap = pd.DataFrame(bootstrap_rows)

    # 全 식품군 × 5개 지표를 하나의 묶음으로 Holm 보정한다.
    # 미실시 검정의 원 p값은 결측으로 두고 보정 계산에만 1을 쓴다.
    correction_input = tests["p_raw"].fillna(1.0).to_numpy()
    _, adjusted_p, _, _ = multipletests(
        correction_input,
        alpha=ALPHA,
        method="holm",
    )

    tests["p_holm"] = adjusted_p
    tests["reject_holm"] = (
        tests["test_status"].eq("ok")
        & tests["p_holm"].lt(ALPHA)
    )
    tests["planned_test_count"] = len(tests)
    tests["holm_missing_policy"] = "use_1_for_correction_only"

    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    tests.to_csv(
        RESULT_DIR / "hypothesis_tests.csv",
        index=False,
        encoding="utf-8-sig",
    )
    bootstrap.to_csv(
        RESULT_DIR / "bootstrap_intervals.csv",
        index=False,
        encoding="utf-8-sig",
    )

    print(f"\n데이터 버전: {version}")
    print(f"추론 분석 식품군: {', '.join(groups)}")
    print(f"계획 검정 수: {len(tests)}")
    print(
        tests[
            [
                "food_group",
                "metric",
                "difference",
                "p_holm",
                "test_status",
            ]
        ].to_string(index=False)
    )
    print(f"\n결과 저장 완료: {RESULT_DIR}")


if __name__ == "__main__":
    main()



#     python - <<'PY'
# import runpy
# import numpy as np
# from scipy import stats

# module = runpy.run_path("B_statistics_ml/code/01_tests.py")

# high = np.array([8, 10, 11, 14, 17], dtype=float)
# regular = np.array([2, 4, 5, 6, 8, 9], dtype=float)

# p, low, upper, status = module["welch_test"](high, regular)
# expected = stats.ttest_ind(high, regular, equal_var=False)

# assert status == "ok"
# assert np.isclose(p, expected.pvalue)
# assert low < high.mean() - regular.mean() < upper

# missing = module["welch_test"](high[:1], regular)
# assert missing[3] == "insufficient_data"
# assert np.isnan(missing[0])

# constant = module["welch_test"](np.ones(3), np.zeros(3))
# assert constant[3] == "zero_variance"

# first = module["bootstrap_interval"](
#     high, regular, np.random.default_rng(42)
# )
# second = module["bootstrap_interval"](
#     high, regular, np.random.default_rng(42)
# )
# assert first == second
# assert first[0] <= first[1]

# print("계산 함수 점검 통과 — 실제 데이터 분석은 아직 수행하지 않았습니다.")
# PY