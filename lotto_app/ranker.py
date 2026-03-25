from __future__ import annotations

import math

from .features import FeatureRow
from .model_types import ModelPredictionRow

MODEL_FEATURES = [
    "omit_now",
    "freq_5",
    "freq_10",
    "freq_30",
    "freq_100",
    "freq_300",
    "freq_all",
    "heat_score",
    "gap_stddev",
    "gap_cv",
    "gap_ratio",
    "gap_percentile",
    "is_hot",
    "is_cold",
    "is_warm",
    "is_trend_reverse",
    "is_pile",
    "is_re_pile",
    "is_n_bottom",
    "is_flag_range",
]


class LogisticBallRanker:
    def __init__(self, feature_names: list[str] | None = None, learning_rate: float = 0.05, epochs: int = 250):
        self.feature_names = feature_names or MODEL_FEATURES
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.weights = [0.0 for _ in self.feature_names]
        self.bias = 0.0
        self.means = [0.0 for _ in self.feature_names]
        self.scales = [1.0 for _ in self.feature_names]

    @staticmethod
    def _sigmoid(value: float) -> float:
        if value >= 0:
            exp_value = math.exp(-value)
            return 1.0 / (1.0 + exp_value)
        exp_value = math.exp(value)
        return exp_value / (1.0 + exp_value)

    def _vector(self, row: FeatureRow) -> list[float]:
        return [float(getattr(row, name)) for name in self.feature_names]

    def fit(self, rows: list[FeatureRow], label_name: str = "y_1") -> None:
        valid_rows = [row for row in rows if getattr(row, label_name) >= 0]
        if not valid_rows:
            return

        vectors = [self._vector(row) for row in valid_rows]
        labels = [float(getattr(row, label_name)) for row in valid_rows]
        dimensions = len(self.feature_names)

        for index in range(dimensions):
            column = [vector[index] for vector in vectors]
            mean = sum(column) / len(column)
            variance = sum((value - mean) ** 2 for value in column) / len(column)
            scale = math.sqrt(variance) or 1.0
            self.means[index] = mean
            self.scales[index] = scale

        normalized = [
            [(vector[index] - self.means[index]) / self.scales[index] for index in range(dimensions)]
            for vector in vectors
        ]

        for _ in range(self.epochs):
            grad_w = [0.0 for _ in range(dimensions)]
            grad_b = 0.0
            for vector, label in zip(normalized, labels):
                score = sum(weight * value for weight, value in zip(self.weights, vector)) + self.bias
                prediction = self._sigmoid(score)
                error = prediction - label
                for index in range(dimensions):
                    grad_w[index] += error * vector[index]
                grad_b += error

            step = self.learning_rate / len(normalized)
            for index in range(dimensions):
                self.weights[index] -= step * grad_w[index]
            self.bias -= step * grad_b

    def predict_proba(self, row: FeatureRow) -> float:
        vector = self._vector(row)
        normalized = [
            (vector[index] - self.means[index]) / self.scales[index]
            for index in range(len(self.feature_names))
        ]
        score = sum(weight * value for weight, value in zip(self.weights, normalized)) + self.bias
        return self._sigmoid(score)


def rank_rows(rows: list[FeatureRow], ranker: LogisticBallRanker) -> list[ModelPredictionRow]:
    return rank_rows_by_score(rows, ranker.predict_proba)


def rank_rows_by_score(rows: list[FeatureRow], score_fn) -> list[ModelPredictionRow]:
    predictions: list[ModelPredictionRow] = []
    grouped: dict[tuple[int, str], list[tuple[FeatureRow, float]]] = {}
    for row in rows:
        probability = score_fn(row)
        grouped.setdefault((row.draw_index, row.serial), []).append((row, probability))

    for (_, _), values in grouped.items():
        ranked = sorted(values, key=lambda item: item[1], reverse=True)
        for rank, (row, probability) in enumerate(ranked, start=1):
            predictions.append(
                ModelPredictionRow(
                    target=row.ball_type,
                    draw_index=row.draw_index,
                    serial=row.serial,
                    draw_date=row.draw_date,
                    ball=row.ball,
                    probability_y1=probability,
                    rank_y1=rank,
                    y_1=row.y_1,
                )
            )

    return sorted(predictions, key=lambda row: (row.draw_index, row.rank_y1, row.ball))
