#단백질 수치 없이 당류, 나트륜, 포화지방만 보고
#단백질 강조 제품인지 예측할 수 있는가?

from pathlib import Path
import runpy

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sklearn.base import clone
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    balanced_accuracy_score,
    f1_score,
    ConfusionMatrixDisplay,
)
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier, plot_tree


ROOT = Path(__file__).resolve().parents[2]
INPUT_PATH = ROOT / "shared/data/processed/series_ml.csv"
RESULT_DIR = ROOT / "shared/results"
FIGURE_DIR = ROOT / "shared/figures"

FEATURES = ["sugar_mean", "sodium_mean", "sat_fat_mean"]
GROUP_UNITS = {"bar": "g", "yogurt": "g", "dairy_drink": "mL"}

SEED = 42
N_SPLITS = 5


def load_ml_data(statistics):
    """ML表の形式と、統計表との識別情報の一致を確認する。"""
    if not INPUT_PATH.is_file():
        raise FileNotFoundError(
            f"入力ファイルがありません: {INPUT_PATH}"
        )

    data = pd.read_csv(
        INPUT_PATH,
        encoding="utf-8-sig",
        dtype={
            "series_id": "string",
            "food_group": "string",
            "basis_unit": "string",
            "data_version": "string",
        },
    )

    required = {
        "series_id", "food_group", "protein_claim",
        "basis_unit", "data_version", "n_complete_products",
        *FEATURES,
    }
    missing = sorted(required - set(data.columns))
    if missing:
        raise ValueError(f"필수 컬럼이 없습니다: {missing}")

    for column in [
        "series_id", "food_group", "basis_unit", "data_version"
    ]:
        values = data[column]
        if (
            values.isna().any()
            or values.str.strip().eq("").any()
            or values.ne(values.str.strip()).any()
        ):
            raise ValueError(f"{column}의 결측·공백을 확인하세요.")

    if data["series_id"].duplicated().any():
        raise ValueError("ML 데이터의 series_id가 중복됩니다.")

    if not data["food_group"].isin(GROUP_UNITS).all():
        raise ValueError("허용되지 않은 식품군이 있습니다.")

    if not data["basis_unit"].eq(
        data["food_group"].map(GROUP_UNITS)
    ).all():
        raise ValueError("식품군별 기준 단위가 잘못되었습니다.")

    numeric_columns = [
        "protein_claim", "n_complete_products", *FEATURES
    ]
    for column in numeric_columns:
        data[column] = pd.to_numeric(data[column], errors="raise")
        values = data[column].to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise ValueError(f"{column}에 결측 또는 무한대가 있습니다.")

    if not data["protein_claim"].isin([0, 1]).all():
        raise ValueError("protein_claim은 0 또는 1이어야 합니다.")

    if (data[FEATURES] < 0).any().any():
        raise ValueError("영양성분에 음수가 있습니다.")

    counts = data["n_complete_products"]
    if ((counts < 1) | (counts % 1 != 0)).any():
        raise ValueError("n_complete_products는 1 이상의 정수여야 합니다.")

    # 통계표와 ML표의 평균은 달라도 되지만 ID·집단·버전은 같아야 한다.
    reference = statistics.set_index("series_id")
    if not data["series_id"].isin(reference.index).all():
        raise ValueError("통계표에 없는 series_id가 ML표에 있습니다.")

    aligned = reference.loc[data["series_id"]].reset_index()
    for column in [
        "food_group", "protein_claim", "basis_unit", "data_version"
    ]:
        if not np.array_equal(
            data[column].to_numpy(),
            aligned[column].to_numpy(),
        ):
            raise ValueError(f"통계표와 ML표의 {column}이 다릅니다.")

    # 완전 관측 제품 수는 각 성분의 유효 제품 수보다 클 수 없다.
    for column in [
        "n_products_total", "n_sugar", "n_sodium", "n_sat_fat"
    ]:
        if (
            data["n_complete_products"].to_numpy()
            > aligned[column].to_numpy()
        ).any():
            raise ValueError(
                f"n_complete_products가 통계표의 {column}보다 큽니다."
            )

    data["protein_claim"] = data["protein_claim"].astype(int)
    return data.sort_values(
        ["food_group", "series_id"]
    ).reset_index(drop=True)


def make_models():
    return {
        "baseline": DummyClassifier(strategy="most_frequent"),
        "logistic": Pipeline([
            ("scaler", StandardScaler()),
            ("model", LogisticRegression(
                max_iter=3000,
                random_state=SEED,
            )),
        ]),
        "tree": DecisionTreeClassifier(
            max_depth=3,
            random_state=SEED,
        ),
    }


def main():
    validator = runpy.run_path(
        str(Path(__file__).with_name("00_validate_statistics.py"))
    )
    statistics, _ = validator["validate_statistics"]()
    data = load_ml_data(statistics)
    version = statistics["data_version"].iloc[0]

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)

    metric_columns = [
        "data_version", "food_group", "model", "fold",
        "n_train", "n_test", "balanced_accuracy", "f1_high",
    ]
    prediction_columns = [
        "data_version", "series_id", "food_group", "model",
        "fold", "y_true", "y_pred",
    ]
    interpretation_columns = [
        "data_version", "food_group", "model", "fold",
        "feature", "quantity", "value",
    ]

    metric_rows = []
    prediction_rows = []
    interpretation_rows = []
    status_rows = []
    summary_rows = []

    for group in GROUP_UNITS:
        group_data = data.loc[
            data["food_group"].eq(group)
        ].reset_index(drop=True)

        counts = (
            group_data["protein_claim"]
            .value_counts()
            .reindex([0, 1], fill_value=0)
        )
        eligible = counts.min() >= N_SPLITS

        status_rows.append({
            "data_version": version,
            "food_group": group,
            "n_regular": int(counts[0]),
            "n_high": int(counts[1]),
            "status": "ok" if eligible else "minority_below_5",
        })

        confusion_path = FIGURE_DIR / f"b_ml_confusion_{group}.png"
        tree_path = FIGURE_DIR / f"b_ml_tree_{group}.png"

        if not eligible:
            confusion_path.unlink(missing_ok=True)
            tree_path.unlink(missing_ok=True)
            print(f"{group}: 어느 한 집단이 5시리즈 미만이므로 보류")
            continue

        X = group_data[FEATURES]
        y = group_data["protein_claim"]

        splitter = StratifiedKFold(
            n_splits=N_SPLITS,
            shuffle=True,
            random_state=SEED,
        )
        # 모든 모델에 동일한 학습·검증 분할을 사용한다.
        splits = list(splitter.split(X, y))
        models = make_models()
        group_predictions = {}

        for model_name, estimator in models.items():
            oof_predictions = np.full(len(y), -1, dtype=int)
            visit_count = np.zeros(len(y), dtype=int)
            fold_scores = []

            for fold, (train_idx, test_idx) in enumerate(splits, 1):
                fitted = clone(estimator)
                fitted.fit(X.iloc[train_idx], y.iloc[train_idx])
                predicted = fitted.predict(X.iloc[test_idx])

                oof_predictions[test_idx] = predicted
                visit_count[test_idx] += 1

                balanced = balanced_accuracy_score(
                    y.iloc[test_idx], predicted
                )
                f1 = f1_score(
                    y.iloc[test_idx],
                    predicted,
                    pos_label=1,
                    zero_division=0,
                )
                fold_scores.append([balanced, f1])

                metric_rows.append({
                    "data_version": version,
                    "food_group": group,
                    "model": model_name,
                    "fold": fold,
                    "n_train": len(train_idx),
                    "n_test": len(test_idx),
                    "balanced_accuracy": balanced,
                    "f1_high": f1,
                })

                for index, predicted_label in zip(test_idx, predicted):
                    prediction_rows.append({
                        "data_version": version,
                        "series_id": group_data.loc[index, "series_id"],
                        "food_group": group,
                        "model": model_name,
                        "fold": fold,
                        "y_true": int(y.iloc[index]),
                        "y_pred": int(predicted_label),
                    })

                if model_name == "logistic":
                    values = fitted.named_steps["model"].coef_[0]
                    quantity = "standardized_coefficient"
                elif model_name == "tree":
                    values = fitted.feature_importances_
                    quantity = "impurity_importance"
                else:
                    continue

                for feature, value in zip(FEATURES, values):
                    interpretation_rows.append({
                        "data_version": version,
                        "food_group": group,
                        "model": model_name,
                        "fold": fold,
                        "feature": feature,
                        "quantity": quantity,
                        "value": float(value),
                    })

            # 각 시리즈가 검증 데이터로 정확히 한 번 사용됐는지 확인한다.
            if not np.all(visit_count == 1):
                raise RuntimeError("교차검증 예측 횟수가 잘못되었습니다.")

            group_predictions[model_name] = oof_predictions
            scores = np.asarray(fold_scores)

            summary_rows.append({
                "data_version": version,
                "food_group": group,
                "model": model_name,
                "n_series": len(y),
                "balanced_accuracy_mean": scores[:, 0].mean(),
                "balanced_accuracy_sd": scores[:, 0].std(ddof=1),
                "f1_high_mean": scores[:, 1].mean(),
                "f1_high_sd": scores[:, 1].std(ddof=1),
            })

        # 학습 데이터에 대한 예측이 아닌 교차검증 예측으로 그린다.
        fig, axes = plt.subplots(1, 3, figsize=(12, 3.6))
        for ax, model_name in zip(axes, models):
            ConfusionMatrixDisplay.from_predictions(
                y,
                group_predictions[model_name],
                labels=[0, 1],
                display_labels=["Regular", "Claim"],
                colorbar=False,
                ax=ax,
            )
            ax.set_title(model_name)

        fig.suptitle(f"Out-of-fold predictions: {group} | {version}")
        fig.tight_layout()
        fig.savefig(confusion_path, dpi=180)
        plt.close(fig)

        # 전체 자료로 다시 맞춘 트리는 규칙 설명에만 사용한다.
        # 이 트리의 학습 정확도를 검증 성능으로 보고하지 않는다.
        descriptive_tree = clone(models["tree"])
        descriptive_tree.fit(X, y)

        fig, ax = plt.subplots(figsize=(15, 7))
        plot_tree(
            descriptive_tree,
            feature_names=FEATURES,
            class_names=["Regular", "Claim"],
            filled=True,
            rounded=True,
            fontsize=8,
            ax=ax,
        )
        ax.set_title(
            f"Full-data tree for interpretation only: {group} | {version}"
        )
        fig.tight_layout()
        fig.savefig(tree_path, dpi=180)
        plt.close(fig)

    metrics = pd.DataFrame(metric_rows, columns=metric_columns)
    predictions = pd.DataFrame(
        prediction_rows, columns=prediction_columns
    )
    interpretations = pd.DataFrame(
        interpretation_rows, columns=interpretation_columns
    )
    summary = pd.DataFrame(summary_rows, columns=[
        "data_version", "food_group", "model", "n_series",
        "balanced_accuracy_mean", "balanced_accuracy_sd",
        "f1_high_mean", "f1_high_sd",
    ])

    # 전부 보류되어도 헤더가 있는 빈 파일로 갱신한다.
    outputs = {
        "ml_fold_metrics.csv": metrics,
        "ml_predictions.csv": predictions,
        "ml_interpretation.csv": interpretations,
        "ml_summary.csv": summary,
        "ml_status.csv": pd.DataFrame(status_rows),
    }
    for filename, table in outputs.items():
        table.to_csv(
            RESULT_DIR / filename,
            index=False,
            encoding="utf-8-sig",
        )

    print("\n식품군별 실행 상태:")
    print(outputs["ml_status.csv"].to_string(index=False))

    if not summary.empty:
        print("\n교차검증 성능 요약:")
        print(summary.to_string(index=False))

    print(f"\n결과 저장 위치: {RESULT_DIR}")
    print("보류한 식품군의 사유는 decisions.md에도 기록하세요.")


if __name__ == "__main__":
    main()