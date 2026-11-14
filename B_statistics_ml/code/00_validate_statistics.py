from pathlib import Path

import numpy as np
import pandas as pd


# 이 파일의 위치를 기준으로 저장소 최상위 폴더를 찾는다.
ROOT = Path(__file__).resolve().parents[2]
INPUT_PATH = ROOT / "shared/data/processed/series_statistics.csv"

# 명세서에서 정한 식품군별 기준 단위
GROUP_UNITS = {
    "bar": "g",
    "yogurt": "g",
    "dairy_drink": "mL",
}

# 평균 컬럼과 그 평균 계산에 사용한 제품 수 컬럼
METRIC_COUNTS = {
    "efficiency_mean": "n_efficiency",
    "sugar_mean": "n_sugar",
    "sodium_mean": "n_sodium",
    "sat_fat_mean": "n_sat_fat",
    "energy_mean": "n_energy",
}


def validate_statistics(path=INPUT_PATH):
    """통계용 시리즈 데이터를 검수하고 데이터와 표본 수 요약을 반환한다."""
    path = Path(path)

    if not path.is_file():
        raise FileNotFoundError(
            f"입력 파일이 없습니다: {path}\n"
            "A에게 받은 series_statistics.csv를 해당 위치에 넣어 주세요."
        )

    df = pd.read_csv(
        path,
        encoding="utf-8-sig",
        dtype={
            "series_id": "string",
            "food_group": "string",
            "basis_unit": "string",
            "data_version": "string",
        },
    )

    required = {
        "series_id",
        "food_group",
        "protein_claim",
        "basis_unit",
        "n_products_total",
        "data_version",
        *METRIC_COUNTS.keys(),
        *METRIC_COUNTS.values(),
    }

    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"필수 컬럼이 없습니다: {missing}")

    if df.empty:
        raise ValueError("데이터에 시리즈가 하나도 없습니다.")

    # 필수 식별 정보의 결측과 공백을 확인한다.
    text_columns = [
        "series_id", "food_group", "basis_unit", "data_version"
    ]
    for column in text_columns:
        values = df[column]
        invalid = values.isna() | values.str.strip().eq("")
        if invalid.any():
            raise ValueError(f"{column}에 결측 또는 빈 문자열이 있습니다.")
        if values.ne(values.str.strip()).any():
            raise ValueError(f"{column} 값 앞뒤에 불필요한 공백이 있습니다.")

    if df["series_id"].duplicated().any():
        duplicates = df.loc[
            df["series_id"].duplicated(keep=False), "series_id"
        ].tolist()
        raise ValueError(f"series_id가 중복되었습니다: {duplicates}")

    if df["data_version"].nunique() != 1:
        raise ValueError("여러 데이터 버전이 섞여 있습니다.")

    if not df["food_group"].isin(GROUP_UNITS).all():
        raise ValueError("food_group은 bar, yogurt, dairy_drink만 가능합니다.")

    expected_units = df["food_group"].map(GROUP_UNITS)
    if not df["basis_unit"].eq(expected_units).all():
        raise ValueError("바·요거트는 g, 유제품 기반 음료는 mL여야 합니다.")

    # 문자열 오류를 결측으로 숨기지 않고 명시적으로 실패시킨다.
    numeric_columns = [
        "protein_claim",
        "n_products_total",
        *METRIC_COUNTS.keys(),
        *METRIC_COUNTS.values(),
    ]
    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="raise")
        observed = df[column].dropna()
        if not np.isfinite(observed.to_numpy(dtype=float)).all():
            raise ValueError(f"{column}에 무한대 값이 있습니다.")

    if not df["protein_claim"].isin([0, 1]).all():
        raise ValueError("protein_claim은 0 또는 1이어야 합니다.")

    # 제품 수는 결측이 없는 정수여야 한다.
    count_columns = ["n_products_total", *METRIC_COUNTS.values()]
    for column in count_columns:
        values = df[column]
        if values.isna().any() or (values < 0).any():
            raise ValueError(f"{column}에 결측 또는 음수가 있습니다.")
        if (values % 1 != 0).any():
            raise ValueError(f"{column}은 정수여야 합니다.")

    if (df["n_products_total"] < 1).any():
        raise ValueError("각 시리즈에는 최소 1개 제품이 있어야 합니다.")

    for metric, count in METRIC_COUNTS.items():
        if (df[count] > df["n_products_total"]).any():
            raise ValueError(f"{count}가 전체 제품 수보다 큽니다.")

        # 유효 제품 0개이면 평균은 결측, 1개 이상이면 평균이 있어야 한다.
        if not df[metric].isna().eq(df[count].eq(0)).all():
            raise ValueError(f"{metric}의 결측과 {count}가 일치하지 않습니다.")

        if (df[metric].dropna() < 0).any():
            raise ValueError(f"{metric}에 음수가 있습니다.")

    # count()는 효율이 결측인 시리즈를 제외하고 센다.
    counts = (
        df.groupby(["food_group", "protein_claim"])["efficiency_mean"]
        .count()
        .unstack(fill_value=0)
        .reindex(index=list(GROUP_UNITS), columns=[0, 1], fill_value=0)
    )

    counts.columns = ["n_regular", "n_high"]
    counts["eligible_for_inference"] = (
        (counts["n_regular"] >= 10) & (counts["n_high"] >= 10)
    )

    return df, counts


if __name__ == "__main__":
    data, summary = validate_statistics()

    print("통계용 시리즈 데이터의 형식 검수를 통과했습니다.")
    print(f"데이터 버전: {data['data_version'].iloc[0]}")
    print(f"전체 시리즈 수: {len(data)}")
    print("\n식품군별 효율 계산 가능 시리즈 수:")
    print(summary.to_string())
    print("\n※ 추론 분석 가능 여부는 양 집단 각각 10시리즈 기준입니다.")
    print("※ 원본 대조 및 제품별 평균 재계산 검수는 별도로 수행해야 합니다.")
