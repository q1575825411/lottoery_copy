from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPredictionRow:
    target: str
    draw_index: int
    serial: str
    draw_date: str
    ball: int
    probability_y1: float
    rank_y1: int
    y_1: int

    def as_dict(self) -> dict[str, object]:
        return {
            "target": self.target,
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
    model_name: str
    target: str
    split: str
    draw_count: int
    top_primary_k: int
    top_secondary_k: int
    top_primary_avg_hits: float
    top_secondary_avg_hits: float
    top_primary_full_cover_rate: float
    top_primary_any_hit_rate: float
    top_primary_avg_hits_lift_vs_random: float
    top_primary_avg_hits_lift_vs_omit: float
    top_primary_avg_hits_lift_vs_heat: float
    top_secondary_avg_hits_lift_vs_random: float
    top_secondary_avg_hits_lift_vs_omit: float
    top_secondary_avg_hits_lift_vs_heat: float

    def as_dict(self) -> dict[str, object]:
        return {
            "model_name": self.model_name,
            "target": self.target,
            "split": self.split,
            "draw_count": self.draw_count,
            "top_primary_k": self.top_primary_k,
            "top_secondary_k": self.top_secondary_k,
            "top_primary_avg_hits": round(self.top_primary_avg_hits, 6),
            "top_secondary_avg_hits": round(self.top_secondary_avg_hits, 6),
            "top_primary_full_cover_rate": round(self.top_primary_full_cover_rate, 6),
            "top_primary_any_hit_rate": round(self.top_primary_any_hit_rate, 6),
            "top_primary_avg_hits_lift_vs_random": round(self.top_primary_avg_hits_lift_vs_random, 6),
            "top_primary_avg_hits_lift_vs_omit": round(self.top_primary_avg_hits_lift_vs_omit, 6),
            "top_primary_avg_hits_lift_vs_heat": round(self.top_primary_avg_hits_lift_vs_heat, 6),
            "top_secondary_avg_hits_lift_vs_random": round(self.top_secondary_avg_hits_lift_vs_random, 6),
            "top_secondary_avg_hits_lift_vs_omit": round(self.top_secondary_avg_hits_lift_vs_omit, 6),
            "top_secondary_avg_hits_lift_vs_heat": round(self.top_secondary_avg_hits_lift_vs_heat, 6),
        }
