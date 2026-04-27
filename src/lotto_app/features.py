from __future__ import annotations

from dataclasses import dataclass
import math

from .constants import BLUE_BALL_MAX, RED_BALL_MAX
from .fetcher import DrawRecord
from .patterns import build_pattern_flag_lookup


@dataclass(frozen=True)
class FeatureRow:
    ball_type: str
    draw_index: int
    serial: str
    draw_date: str
    ball: int
    hit_current: int
    omit_now: int
    freq_5: int
    freq_10: int
    freq_30: int
    freq_100: int
    freq_300: int
    freq_all: int
    avg_gap: float
    last_gap: int
    gap_stddev: float
    gap_cv: float
    gap_ratio: float
    gap_percentile: float
    heat_score: float
    is_hot: int
    is_cold: int
    is_warm: int
    is_trend_reverse: int
    is_pile: int
    is_re_pile: int
    is_n_bottom: int
    is_flag_range: int
    y_1: int
    y_3: int
    y_5: int

    def as_dict(self) -> dict[str, object]:
        return {
            "ball_type": self.ball_type,
            "draw_index": self.draw_index,
            "serial": self.serial,
            "draw_date": self.draw_date,
            "ball": self.ball,
            "hit_current": self.hit_current,
            "omit_now": self.omit_now,
            "freq_5": self.freq_5,
            "freq_10": self.freq_10,
            "freq_30": self.freq_30,
            "freq_100": self.freq_100,
            "freq_300": self.freq_300,
            "freq_all": self.freq_all,
            "avg_gap": round(self.avg_gap, 4),
            "last_gap": self.last_gap,
            "gap_stddev": round(self.gap_stddev, 4),
            "gap_cv": round(self.gap_cv, 4),
            "gap_ratio": round(self.gap_ratio, 4),
            "gap_percentile": round(self.gap_percentile, 4),
            "heat_score": round(self.heat_score, 4),
            "is_hot": self.is_hot,
            "is_cold": self.is_cold,
            "is_warm": self.is_warm,
            "is_trend_reverse": self.is_trend_reverse,
            "is_pile": self.is_pile,
            "is_re_pile": self.is_re_pile,
            "is_n_bottom": self.is_n_bottom,
            "is_flag_range": self.is_flag_range,
            "y_1": self.y_1,
            "y_3": self.y_3,
            "y_5": self.y_5,
        }


def _window_count(draw_sets: list[set[int]], end_index: int, window_size: int, ball: int) -> int:
    start_index = max(0, end_index - window_size + 1)
    return sum(1 for draw in draw_sets[start_index : end_index + 1] if ball in draw)


def _history_count(hit_positions: list[int]) -> int:
    return len(hit_positions)


def _label(draw_sets: list[set[int]], start_index: int, horizon: int, ball: int) -> int:
    end_index = min(len(draw_sets), start_index + 1 + horizon)
    if end_index - (start_index + 1) < horizon:
        return -1
    return int(any(ball in draw for draw in draw_sets[start_index + 1 : end_index]))


def _gap_stats(hit_positions: list[int], current_index: int, hit_current: bool) -> tuple[int, float, int, float, float, float]:
    current_positions = hit_positions + ([current_index] if hit_current else [])
    if current_positions:
        omit_now = current_index - current_positions[-1]
    else:
        omit_now = current_index + 1

    if len(current_positions) >= 2:
        gaps = [current_positions[i] - current_positions[i - 1] for i in range(1, len(current_positions))]
        avg_gap = sum(gaps) / float(len(gaps))
        last_gap = gaps[-1]
        variance = sum((gap - avg_gap) ** 2 for gap in gaps) / float(len(gaps))
        gap_stddev = math.sqrt(variance)
        gap_cv = (gap_stddev / avg_gap) if avg_gap else 0.0
        gap_ratio = (omit_now / avg_gap) if avg_gap else 0.0
        smaller_or_equal = sum(1 for gap in gaps if gap <= omit_now)
        gap_percentile = smaller_or_equal / float(len(gaps))
    else:
        avg_gap = 0.0
        last_gap = -1
        gap_stddev = 0.0
        gap_cv = 0.0
        gap_ratio = 0.0
        gap_percentile = 0.0

    return omit_now, avg_gap, last_gap, gap_stddev, gap_cv, gap_ratio, gap_percentile


def _heat_flags(draw_sets: list[set[int]], end_index: int, ball: int) -> tuple[int, int, int]:
    recent_5 = draw_sets[max(0, end_index - 4) : end_index + 1]
    prev_5 = draw_sets[max(0, end_index - 9) : max(0, end_index - 4)]
    in_recent_5 = any(ball in draw for draw in recent_5)
    in_prev_5 = any(ball in draw for draw in prev_5)
    is_hot = int(in_recent_5 and in_prev_5)
    is_cold = int(not in_recent_5 and not in_prev_5 and len(recent_5) + len(prev_5) >= 10)
    is_warm = int(not is_hot and not is_cold)
    return is_hot, is_cold, is_warm


def _heat_score(freq_5: int, freq_10: int, freq_30: int, gap_percentile: float) -> float:
    recent_component = 0.5 * (freq_5 / 5.0) + 0.3 * (freq_10 / 10.0) + 0.2 * (freq_30 / 30.0)
    score = 0.7 * recent_component + 0.3 * (1.0 - gap_percentile)
    return max(0.0, min(1.0, score))


def _build_feature_rows_for_ball_type(
    records: list[DrawRecord],
    *,
    ball_type: str,
    ball_max: int,
    draw_sets: list[set[int]],
    pattern_config=None,
) -> list[FeatureRow]:
    chronological_records = list(reversed(records))
    hit_history: dict[int, list[int]] = {ball: [] for ball in range(1, ball_max + 1)}
    pattern_flags = build_pattern_flag_lookup(records, pattern_config) if ball_type == "red" else {}
    rows: list[FeatureRow] = []

    for draw_index, record in enumerate(chronological_records):
        current_draw = draw_sets[draw_index]
        for ball in range(1, ball_max + 1):
            hit_current = ball in current_draw
            omit_now, avg_gap, last_gap, gap_stddev, gap_cv, gap_ratio, gap_percentile = _gap_stats(hit_history[ball], draw_index, hit_current)
            freq_5 = _window_count(draw_sets, draw_index, 5, ball)
            freq_10 = _window_count(draw_sets, draw_index, 10, ball)
            freq_30 = _window_count(draw_sets, draw_index, 30, ball)
            freq_100 = _window_count(draw_sets, draw_index, 100, ball)
            freq_300 = _window_count(draw_sets, draw_index, 300, ball)
            freq_all = _history_count(hit_history[ball]) + int(hit_current)
            is_hot, is_cold, is_warm = _heat_flags(draw_sets, draw_index, ball)
            heat_score = _heat_score(freq_5, freq_10, freq_30, gap_percentile)
            flags = pattern_flags.get(
                (record.serial, ball),
                {
                    "is_trend_reverse": 0,
                    "is_pile": 0,
                    "is_re_pile": 0,
                    "is_n_bottom": 0,
                    "is_flag_range": 0,
                },
            )
            rows.append(
                FeatureRow(
                    ball_type=ball_type,
                    draw_index=draw_index,
                    serial=record.serial,
                    draw_date=record.draw_date,
                    ball=ball,
                    hit_current=int(hit_current),
                    omit_now=omit_now,
                    freq_5=freq_5,
                    freq_10=freq_10,
                    freq_30=freq_30,
                    freq_100=freq_100,
                    freq_300=freq_300,
                    freq_all=freq_all,
                    avg_gap=avg_gap,
                    last_gap=last_gap,
                    gap_stddev=gap_stddev,
                    gap_cv=gap_cv,
                    gap_ratio=gap_ratio,
                    gap_percentile=gap_percentile,
                    heat_score=heat_score,
                    is_hot=is_hot,
                    is_cold=is_cold,
                    is_warm=is_warm,
                    is_trend_reverse=flags["is_trend_reverse"],
                    is_pile=flags["is_pile"],
                    is_re_pile=flags["is_re_pile"],
                    is_n_bottom=flags["is_n_bottom"],
                    is_flag_range=flags["is_flag_range"],
                    y_1=_label(draw_sets, draw_index, 1, ball),
                    y_3=_label(draw_sets, draw_index, 3, ball),
                    y_5=_label(draw_sets, draw_index, 5, ball),
                )
            )

        for ball in current_draw:
            hit_history[ball].append(draw_index)

    return rows


def build_feature_rows(records: list[DrawRecord], pattern_config=None) -> list[FeatureRow]:
    chronological_records = list(reversed(records))
    red_draw_sets = [set(record.red) for record in chronological_records]
    return _build_feature_rows_for_ball_type(
        records,
        ball_type="red",
        ball_max=RED_BALL_MAX,
        draw_sets=red_draw_sets,
        pattern_config=pattern_config,
    )


def build_blue_feature_rows(records: list[DrawRecord]) -> list[FeatureRow]:
    chronological_records = list(reversed(records))
    blue_draw_sets = [{record.blue} for record in chronological_records]
    return _build_feature_rows_for_ball_type(
        records,
        ball_type="blue",
        ball_max=BLUE_BALL_MAX,
        draw_sets=blue_draw_sets,
        pattern_config=None,
    )
