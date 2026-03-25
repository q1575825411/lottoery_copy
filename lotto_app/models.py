from __future__ import annotations

from .features import FeatureRow
from .model_metrics import apply_baseline_lifts, metrics, random_baseline_metric, score_by_heat, score_by_omit
from .model_types import ModelMetricRow, ModelPredictionRow
from .ranker import LogisticBallRanker, rank_rows, rank_rows_by_score


def _default_rolling_min_train_draws(rows: list[FeatureRow], train_ratio: float) -> int:
    if not rows:
        return 1
    split_index = int(max(row.draw_index for row in rows) * train_ratio)
    train_draws = sorted({row.draw_index for row in rows if row.y_1 >= 0 and row.draw_index <= split_index})
    return max(1, len(train_draws))


def _rolling_rank_rows(
    rows: list[FeatureRow],
    *,
    min_train_draws: int,
    step: int,
) -> list[ModelPredictionRow]:
    if not rows:
        return []

    valid_rows = [row for row in rows if row.y_1 >= 0]
    draw_indices = sorted({row.draw_index for row in valid_rows})
    if len(draw_indices) <= min_train_draws:
        return []

    predictions: list[ModelPredictionRow] = []
    for test_position in range(min_train_draws, len(draw_indices), step):
        test_draw_index = draw_indices[test_position]
        train_draw_indices = set(draw_indices[:test_position])
        train_rows = [row for row in valid_rows if row.draw_index in train_draw_indices]
        test_rows = [row for row in valid_rows if row.draw_index == test_draw_index]
        if not train_rows or not test_rows:
            continue

        ranker = LogisticBallRanker()
        ranker.fit(train_rows, label_name="y_1")
        predictions.extend(rank_rows(test_rows, ranker))

    return sorted(predictions, key=lambda row: (row.draw_index, row.rank_y1, row.ball))


def train_and_rank(
    rows: list[FeatureRow],
    train_ratio: float = 0.7,
    *,
    target: str = "red",
    top_primary_k: int = 6,
    top_secondary_k: int = 10,
    rolling_min_train_draws: int | None = None,
    rolling_step: int = 1,
) -> tuple[list[ModelPredictionRow], list[ModelMetricRow]]:
    latest_predictions, _, metric_rows = train_rank_and_backtest(
        rows,
        train_ratio=train_ratio,
        target=target,
        top_primary_k=top_primary_k,
        top_secondary_k=top_secondary_k,
        rolling_min_train_draws=rolling_min_train_draws,
        rolling_step=rolling_step,
    )
    return latest_predictions, metric_rows


def train_rank_and_backtest(
    rows: list[FeatureRow],
    train_ratio: float = 0.7,
    *,
    target: str = "red",
    top_primary_k: int = 6,
    top_secondary_k: int = 10,
    rolling_min_train_draws: int | None = None,
    rolling_step: int = 1,
) -> tuple[list[ModelPredictionRow], list[ModelPredictionRow], list[ModelMetricRow]]:
    trainable_rows = [row for row in rows if row.y_1 >= 0]
    if not trainable_rows:
        latest_draw_index = max((row.draw_index for row in rows), default=-1)
        latest_rows = [row for row in rows if row.draw_index == latest_draw_index] if latest_draw_index >= 0 else []
        latest_predictions = rank_rows_by_score(latest_rows, score_by_heat) if latest_rows else []
        return latest_predictions, [], [metrics([], "rolling", "logistic", target=target, top_primary_k=top_primary_k, top_secondary_k=top_secondary_k)]

    ranker = LogisticBallRanker()
    ranker.fit(trainable_rows, label_name="y_1")
    latest_draw_index = max(row.draw_index for row in rows)
    latest_rows = [row for row in rows if row.draw_index == latest_draw_index]
    latest_predictions = rank_rows(latest_rows, ranker)

    min_train_draws = rolling_min_train_draws
    if min_train_draws is None:
        min_train_draws = _default_rolling_min_train_draws(rows, train_ratio)
    min_train_draws = max(1, min_train_draws)

    rolling_predictions = _rolling_rank_rows(rows, min_train_draws=min_train_draws, step=max(1, rolling_step))
    rolling_draw_indices = {row.draw_index for row in rolling_predictions}
    evaluation_rows = [row for row in trainable_rows if row.draw_index in rolling_draw_indices]

    random_metric = random_baseline_metric(
        rolling_predictions,
        "rolling",
        target=target,
        top_primary_k=top_primary_k,
        top_secondary_k=top_secondary_k,
    )
    omit_predictions = rank_rows_by_score(evaluation_rows, score_by_omit)
    heat_predictions = rank_rows_by_score(evaluation_rows, score_by_heat)
    omit_metric = metrics(omit_predictions, "rolling", "omit_baseline", target=target, top_primary_k=top_primary_k, top_secondary_k=top_secondary_k)
    heat_metric = metrics(heat_predictions, "rolling", "heat_baseline", target=target, top_primary_k=top_primary_k, top_secondary_k=top_secondary_k)
    logistic_metric = apply_baseline_lifts(
        metrics(rolling_predictions, "rolling", "logistic", target=target, top_primary_k=top_primary_k, top_secondary_k=top_secondary_k),
        random_metric,
        omit_metric,
        heat_metric,
    )

    return latest_predictions, rolling_predictions, [logistic_metric, random_metric, omit_metric, heat_metric]


__all__ = [
    "LogisticBallRanker",
    "ModelMetricRow",
    "ModelPredictionRow",
    "train_and_rank",
    "train_rank_and_backtest",
]
