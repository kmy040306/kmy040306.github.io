#고단백과 일반 사이의 효율 차이가 
# 바, 요거트, 음료(식품군별)에서 서로 다른가?

from pathlib import Path
import runpy

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[2]
RESULT_DIR = ROOT / "shared/results"
FIGURE_DIR = ROOT / "shared/figures"

FORMULA = "efficiency_mean ~ protein_claim * C(food_group)"


def main():
    validator = runpy.run_path(
        str(Path(__file__).with_name("00_validate_statistics.py"))
    )
    data, sample_summary = validator["validate_statistics"]()

    version = data["data_version"].iloc[0]
    groups = sample_summary.index[
        sample_summary["eligible_for_inference"]
    ].tolist()

    analysis = data.loc[
        data["food_group"].isin(groups)
    ].dropna(subset=["efficiency_mean"]).copy()

    # statsmodels의 수식 처리에 사용할 일반 문자열로 변환한다.
    analysis["food_group"] = analysis["food_group"].astype(str)
    analysis["protein_claim"] = analysis["protein_claim"].astype(int)

    result = {
        "data_version": version,
        "analysis_type": "exploratory",
        "formula": FORMULA,
        "food_groups": "|".join(groups),
        "n_groups": len(groups),
        "n_series": len(analysis),
        "covariance": "HC3",
        "test": "joint_Wald_chi2",
        "statistic": np.nan,
        "df": np.nan,
        "p_value": np.nan,
        "status": "not_run",
    }

    coefficient_columns = [
        "data_version", "term", "coefficient",
        "standard_error", "ci_low", "ci_high", "p_value"
    ]
    coefficients = pd.DataFrame(columns=coefficient_columns)

    if len(groups) < 2:
        result["status"] = "fewer_than_two_eligible_groups"
    else:
        model = smf.ols(FORMULA, data=analysis)

        if np.linalg.matrix_rank(model.exog) < model.exog.shape[1]:
            result["status"] = "rank_deficient_design"
        else:
            fit = model.fit(cov_type="HC3")

            # protein_claim × food_group에 해당하는 계수만 선택한다.
            interaction_indices = [
                i for i, name in enumerate(fit.params.index)
                if ":" in name
            ]

            # 선택한 계수가 모두 0이라는 귀무가설을 공동 검정한다.
            restriction = np.eye(len(fit.params))[
                interaction_indices
            ]
            covariance = np.asarray(fit.cov_params())
            joint_covariance = (
                restriction @ covariance @ restriction.T
            )

            if not np.isfinite(joint_covariance).all():
                result["status"] = "nonfinite_covariance"
            elif (
                np.linalg.matrix_rank(joint_covariance)
                < len(interaction_indices)
            ):
                result["status"] = "singular_joint_covariance"
            else:
                test = fit.wald_test(
                    restriction,
                    use_f=False,
                    scalar=True,
                )
                statistic = float(np.asarray(test.statistic).item())
                p_value = float(np.asarray(test.pvalue).item())

                if not np.isfinite([statistic, p_value]).all():
                    result["status"] = "nonfinite_test_result"
                else:
                    result.update({
                        "statistic": statistic,
                        "df": len(interaction_indices),
                        "p_value": p_value,
                        "status": "ok",
                    })

                    ci = np.asarray(fit.conf_int(alpha=0.05))
                    coefficients = pd.DataFrame({
                        "data_version": version,
                        "term": fit.params.index,
                        "coefficient": np.asarray(fit.params),
                        "standard_error": np.asarray(fit.bse),
                        "ci_low": ci[:, 0],
                        "ci_high": ci[:, 1],
                        "p_value": np.asarray(fit.pvalues),
                    })

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)

    # 보류한 경우에도 상태를 저장해 이전 결과와 혼동하지 않게 한다.
    pd.DataFrame([result]).to_csv(
        RESULT_DIR / "interaction_results.csv",
        index=False,
        encoding="utf-8-sig",
    )
    coefficients.to_csv(
        RESULT_DIR / "interaction_coefficients.csv",
        index=False,
        encoding="utf-8-sig",
    )

    figure_path = FIGURE_DIR / "b_interaction_means.png"

    if len(groups) >= 2:
        means = (
            analysis.groupby(["food_group", "protein_claim"])[
                "efficiency_mean"
            ]
            .mean()
            .unstack()
            .reindex(index=groups, columns=[0, 1])
        )

        fig, ax = plt.subplots(figsize=(7, 4.5))

        for claim, label in [
            (0, "Regular"),
            (1, "Protein claim"),
        ]:
            ax.plot(
                groups,
                means[claim],
                marker="o",
                linewidth=2,
                label=label,
            )

        ax.set_xlabel("Food group")
        ax.set_ylabel("Mean protein efficiency (g / 100 kcal)")
        ax.set_title(f"Series-level means | {version}")
        ax.legend()
        ax.grid(axis="y", alpha=0.25)

        fig.tight_layout()
        fig.savefig(figure_path, dpi=180)
        plt.close(fig)
    else:
        # 이번 실행에서 만들 수 없는 오래된 그림은 제거한다.
        figure_path.unlink(missing_ok=True)

    print(pd.DataFrame([result]).to_string(index=False))
    print(f"\n결과 저장 위치: {RESULT_DIR}")
    print("이 분석은 기본 가설검정과 별도의 탐색 분석입니다.")

    if result["status"] != "ok":
        print("보류 사유를 shared/docs/decisions.md에도 기록하세요.")


if __name__ == "__main__":
    main()