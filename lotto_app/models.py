from __future__ import annotations

import math
from dataclasses import dataclass

from .features import FeatureRow

MODEL_FEATURES = [
    "omit_now",
    "freq_5",
    "freq_10",
    "freq_30",
    "freq_100",
    "freq_300",
    "freq_all",
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


@dataclass(frozen=True)
class ModelPredictionRow:
    draw_index: int
    serial: str
    draw_date: str
    ball: int
    probability_y1: float
    rank_y1: int
    y_1: int

    def as_dict(self) -> dict[str, object]:
        return {
            "draw_index": self.draw_index,
            "serial": self.serial,
            "draw_date": self.draw_date,
            "ball": self.ball,
            "probability_y1": round(self.probability_y1, 6),
            "rank_y1": self.rank_y1,
            "y_1": self.y_1,
        }


@dataclass(frozen=True)
class ModelMetricRow:
    split: str
    draw_count: int
    top_6_avg_hits: float
    top_10_avg_hits: float
    top_6_full_cover_rate: float
    top_6_any_hit_rate: float

    def as_dict(self) -> dict[str, object]:
        return {
            "split": self.split,
            "draw_count": self.draw_count,
            "top_6_avg_hits": round(self.top_6_avg_hits, 6),
            "top_10_avg_hits": round(self.top_10_avg_hits, 6),
            "top_6_full_cover_rate": round(self.top_6_full_cover_rate, 6),
            "top_6_any_hit_rate": round(self.top_6_any_hit_rate, 6),
        }


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


def _split_rows(rows: list[FeatureRow], train_ratio: float) -> tuple[list[FeatureRow], list[FeatureRow]]:
    if not rows:
        return [], []
    max_draw_index = max(row.draw_index for row in rows)
    split_index = int(max_draw_index * train_ratio)
    train_rows = [row for row in rows if row.draw_index <= split_index and row.y_1 >= 0]
    test_rows = [row for row in rows if row.draw_index > split_index and row.y_1 >= 0]
    return train_rows, test_rows


def _rank_rows(rows: list[FeatureRow], ranker: LogisticBallRanker) -> list[ModelPredictionRow]:
    predictions: list[ModelPredictionRow] = []
    grouped: dict[tuple[int, str], list[tuple[FeatureRow, float]]] = {}
    for row in rows:
        probability = ranker.predict_proba(row)
        grouped.setdefault((row.draw_index, row.serial), []).append((row, probability))

    for (_, _), values in grouped.items():
        ranked = sorted(values, key=lambda item: item[1], reverse=True)
        for rank, (row, probability) in enumerate(ranked, start=1):
            predictions.append(
                ModelPredictionRow(
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


def _metrics(predictions: list[ModelPredictionRow], split_name: str) -> ModelMetricRow:
    grouped: dict[str, list[ModelPredictionRow]] = {}
    for row in predictions:
        grouped.setdefault(row.serial, []).append(row)

    if not grouped:
        return ModelMetricRow(split=split_name, draw_count=0, top_6_avg_hits=0.0, top_10_avg_hits=0.0, top_6_full_cover_rate=0.0, top_6_any_hit_rate=0.0)

    top_6_hits = []
    top_10_hits = []
    top_6_full_cover = 0
    top_6_any_hit = 0
    for rows in grouped.values():
        ranked = sorted(rows, key=lambda row: row.rank_y1)
        top_6 = ranked[:6]
        top_10 = ranked[:10]
        hit_6 = sum(row.y_1 for row in top_6)
        hit_10 = sum(row.y_1 for row in top_10)
        top_6_hits.append(hit_6)
        top_10_hits.append(hit_10)
        if hit_6 == 6:
            top_6_full_cover += 1
        if hit_6 > 0:
            top_6_any_hit += 1

    draw_count = len(grouped)
    return ModelMetricRow(
        split=split_name,
        draw_count=draw_count,
        top_6_avg_hits=sum(top_6_hits) / draw_count,
        top_10_avg_hits=sum(top_10_hits) / draw_count,
        top_6_full_cover_rate=top_6_full_cover / float(draw_count),
        top_6_any_hit_rate=top_6_any_hit / float(draw_count),
    )


def train_and_rank(rows: list[FeatureRow], train_ratio: float = 0.7) -> tuple[list[ModelPredictionRow], list[ModelMetricRow]]:
    train_rows, test_rows = _split_rows(rows, train_ratio)
    ranker = LogisticBallRanker()
    ranker.fit(train_rows, label_name="y_1")

    latest_draw_index = max(row.draw_index for row in rows if row.y_1 >= 0)
    latest_rows = [row for row in rows if row.draw_index == latest_draw_index and row.y_1 >= 0]
    latest_predictions = _rank_rows(latest_rows, ranker)
    test_predictions = _rank_rows(test_rows, ranker)

    return latest_predictions, [_metrics(test_predictions, "test")]
