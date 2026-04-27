from __future__ import annotations

import math

from .model_types import ModelMetricRow, ModelPredictionRow


def score_by_omit(row) -> float:
    return float(row.omit_now)


def score_by_heat(row) -> float:
    return float(row.heat_score)


def metrics(
    predictions: list[ModelPredictionRow],
    split_name: str,
    model_name: str,
    *,
    target: str,
    top_primary_k: int,
    top_secondary_k: int,
) -> ModelMetricRow:
    grouped: dict[str, list[ModelPredictionRow]] = {}
    for row in predictions:
        grouped.setdefault(row.serial, []).append(row)

    if not grouped:
        return ModelMetricRow(
            model_name=model_name,
            target=target,
            split=split_name,
            draw_count=0,
            top_primary_k=top_primary_k,
            top_secondary_k=top_secondary_k,
            top_primary_avg_hits=0.0,
            top_secondary_avg_hits=0.0,
            top_primary_full_cover_rate=0.0,
            top_primary_any_hit_rate=0.0,
            top_primary_avg_hits_lift_vs_random=0.0,
            top_primary_avg_hits_lift_vs_omit=0.0,
            top_primary_avg_hits_lift_vs_heat=0.0,
            top_secondary_avg_hits_lift_vs_random=0.0,
            top_secondary_avg_hits_lift_vs_omit=0.0,
            top_secondary_avg_hits_lift_vs_heat=0.0,
        )

    top_primary_hits = []
    top_secondary_hits = []
    top_primary_full_cover = 0
    top_primary_any_hit = 0
    for rows in grouped.values():
        ranked = sorted(rows, key=lambda row: row.rank_y1)
        top_primary = ranked[:top_primary_k]
        top_secondary = ranked[:top_secondary_k]
        hit_primary = sum(row.y_1 for row in top_primary)
        hit_secondary = sum(row.y_1 for row in top_secondary)
        top_primary_hits.append(hit_primary)
        top_secondary_hits.append(hit_secondary)
        if hit_primary == top_primary_k:
            top_primary_full_cover += 1
        if hit_primary > 0:
            top_primary_any_hit += 1

    draw_count = len(grouped)
    return ModelMetricRow(
        model_name=model_name,
        target=target,
        split=split_name,
        draw_count=draw_count,
        top_primary_k=top_primary_k,
        top_secondary_k=top_secondary_k,
        top_primary_avg_hits=sum(top_primary_hits) / draw_count,
        top_secondary_avg_hits=sum(top_secondary_hits) / draw_count,
        top_primary_full_cover_rate=top_primary_full_cover / float(draw_count),
        top_primary_any_hit_rate=top_primary_any_hit / float(draw_count),
        top_primary_avg_hits_lift_vs_random=0.0,
        top_primary_avg_hits_lift_vs_omit=0.0,
        top_primary_avg_hits_lift_vs_heat=0.0,
        top_secondary_avg_hits_lift_vs_random=0.0,
        top_secondary_avg_hits_lift_vs_omit=0.0,
        top_secondary_avg_hits_lift_vs_heat=0.0,
    )


def random_baseline_metric(
    predictions: list[ModelPredictionRow],
    split_name: str,
    *,
    target: str,
    top_primary_k: int,
    top_secondary_k: int,
) -> ModelMetricRow:
    grouped: dict[str, list[ModelPredictionRow]] = {}
    for row in predictions:
        grouped.setdefault(row.serial, []).append(row)

    if not grouped:
        return metrics([], split_name, "random_baseline", target=target, top_primary_k=top_primary_k, top_secondary_k=top_secondary_k)

    draw_count = len(grouped)
    primary_expected_hits = 0.0
    secondary_expected_hits = 0.0
    primary_any_hit_rate = 0.0
    primary_full_cover_rate = 0.0
    for rows in grouped.values():
        population_size = len(rows)
        hit_count = sum(row.y_1 for row in rows)
        hit_rate = (hit_count / float(population_size)) if population_size else 0.0
        primary_expected_hits += top_primary_k * hit_rate
        secondary_expected_hits += top_secondary_k * hit_rate
        if top_primary_k <= population_size:
            primary_any_hit_rate += 1.0 - (math.comb(population_size - hit_count, top_primary_k) / float(math.comb(population_size, top_primary_k)))
        if hit_count >= top_primary_k and top_primary_k > 0:
            primary_full_cover_rate += math.comb(hit_count, top_primary_k) / float(math.comb(population_size, top_primary_k))

    return ModelMetricRow(
        model_name="random_baseline",
        target=target,
        split=split_name,
        draw_count=draw_count,
        top_primary_k=top_primary_k,
        top_secondary_k=top_secondary_k,
        top_primary_avg_hits=primary_expected_hits / draw_count,
        top_secondary_avg_hits=secondary_expected_hits / draw_count,
        top_primary_full_cover_rate=primary_full_cover_rate / draw_count,
        top_primary_any_hit_rate=primary_any_hit_rate / draw_count,
        top_primary_avg_hits_lift_vs_random=0.0,
        top_primary_avg_hits_lift_vs_omit=0.0,
        top_primary_avg_hits_lift_vs_heat=0.0,
        top_secondary_avg_hits_lift_vs_random=0.0,
        top_secondary_avg_hits_lift_vs_omit=0.0,
        top_secondary_avg_hits_lift_vs_heat=0.0,
    )


def apply_baseline_lifts(
    target_metric: ModelMetricRow,
    random_metric: ModelMetricRow,
    omit_metric: ModelMetricRow,
    heat_metric: ModelMetricRow,
) -> ModelMetricRow:
    return ModelMetricRow(
        model_name=target_metric.model_name,
        target=target_metric.target,
        split=target_metric.split,
        draw_count=target_metric.draw_count,
        top_primary_k=target_metric.top_primary_k,
        top_secondary_k=target_metric.top_secondary_k,
        top_primary_avg_hits=target_metric.top_primary_avg_hits,
        top_secondary_avg_hits=target_metric.top_secondary_avg_hits,
        top_primary_full_cover_rate=target_metric.top_primary_full_cover_rate,
        top_primary_any_hit_rate=target_metric.top_primary_any_hit_rate,
        top_primary_avg_hits_lift_vs_random=target_metric.top_primary_avg_hits - random_metric.top_primary_avg_hits,
        top_primary_avg_hits_lift_vs_omit=target_metric.top_primary_avg_hits - omit_metric.top_primary_avg_hits,
        top_primary_avg_hits_lift_vs_heat=target_metric.top_primary_avg_hits - heat_metric.top_primary_avg_hits,
        top_secondary_avg_hits_lift_vs_random=target_metric.top_secondary_avg_hits - random_metric.top_secondary_avg_hits,
        top_secondary_avg_hits_lift_vs_omit=target_metric.top_secondary_avg_hits - omit_metric.top_secondary_avg_hits,
        top_secondary_avg_hits_lift_vs_heat=target_metric.top_secondary_avg_hits - heat_metric.top_secondary_avg_hits,
    )
