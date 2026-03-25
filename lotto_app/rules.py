from __future__ import annotations

from dataclasses import dataclass, field
import json

from .features import FeatureRow


@dataclass(frozen=True)
class RuleConfig:
    omit_threshold: int = 10
    gap_ratio_threshold: float = 1.5
    active_recent_min_hits: int = 2
    inactive_recent_window: int = 10
    heat_score_threshold: float = 0.6
    gap_cv_threshold: float = 0.5
    trend_reverse_min_omit: int = 17
    pile_long_min: int = 15
    pile_mid_min: int = 8
    pile_short_min: int = 3
    flag_range_start_min: int = 5
    flag_range_start_max: int = 6
    flag_range_min_repeat: int = 2

    def as_dict(self) -> dict[str, object]:
        return {
            "omit_threshold": self.omit_threshold,
            "gap_ratio_threshold": self.gap_ratio_threshold,
            "active_recent_min_hits": self.active_recent_min_hits,
            "inactive_recent_window": self.inactive_recent_window,
            "heat_score_threshold": self.heat_score_threshold,
            "gap_cv_threshold": self.gap_cv_threshold,
            "trend_reverse_min_omit": self.trend_reverse_min_omit,
            "pile_long_min": self.pile_long_min,
            "pile_mid_min": self.pile_mid_min,
            "pile_short_min": self.pile_short_min,
            "flag_range_start_min": self.flag_range_start_min,
            "flag_range_start_max": self.flag_range_start_max,
            "flag_range_min_repeat": self.flag_range_min_repeat,
        }


@dataclass(frozen=True)
class RuleDefinition:
    name: str
    description: str

    def match(self, row: FeatureRow) -> bool:
        raise NotImplementedError

    def parameters(self) -> dict[str, object]:
        return {}

    def parameter_summary(self) -> str:
        return json.dumps(self.parameters(), ensure_ascii=False, sort_keys=True)


@dataclass(frozen=True)
class LambdaRule(RuleDefinition):
    predicate: object
    parameter_values: dict[str, object] = field(default_factory=dict)

    def match(self, row: FeatureRow) -> bool:
        return bool(self.predicate(row))

    def parameters(self) -> dict[str, object]:
        return self.parameter_values.copy()


def _recent_window_hit_count(row: FeatureRow, window_size: int) -> int:
    field_name = f"freq_{window_size}"
    if not hasattr(row, field_name):
        raise RuntimeError(f"unsupported recent window: {window_size}")
    return int(getattr(row, field_name))


def default_rules(config: RuleConfig | None = None) -> list[RuleDefinition]:
    config = config or RuleConfig()
    return [
        LambdaRule("hot_rule", "号码在最近1-5期与6-10期都出现过", lambda row: row.is_hot == 1),
        LambdaRule("cold_rule", "号码在最近10期内从未出现", lambda row: row.is_cold == 1),
        LambdaRule("warm_rule", "号码处于温号状态", lambda row: row.is_warm == 1),
        LambdaRule(
            "deep_omit_rule",
            "当前遗漏值大于等于设定阈值",
            lambda row: row.omit_now >= config.omit_threshold,
            {"omit_threshold": config.omit_threshold},
        ),
        LambdaRule(
            "high_gap_ratio_rule",
            "当前遗漏值超过历史平均设定倍数",
            lambda row: row.avg_gap > 0 and row.gap_ratio >= config.gap_ratio_threshold,
            {"gap_ratio_threshold": config.gap_ratio_threshold},
        ),
        LambdaRule(
            "active_recent_rule",
            "最近5期达到设定命中次数",
            lambda row: row.freq_5 >= config.active_recent_min_hits,
            {"window_size": 5, "min_hits": config.active_recent_min_hits},
        ),
        LambdaRule(
            "inactive_recent_rule",
            "最近设定窗口内未出现且当前非热号",
            lambda row: _recent_window_hit_count(row, config.inactive_recent_window) == 0 and row.is_hot == 0,
            {"window_size": config.inactive_recent_window, "max_hits": 0},
        ),
        LambdaRule(
            "high_heat_score_rule",
            "热度分数大于等于设定阈值",
            lambda row: row.heat_score >= config.heat_score_threshold,
            {"heat_score_threshold": config.heat_score_threshold},
        ),
        LambdaRule(
            "volatile_gap_rule",
            "遗漏波动系数大于等于设定阈值",
            lambda row: row.avg_gap > 0 and row.gap_cv >= config.gap_cv_threshold,
            {"gap_cv_threshold": config.gap_cv_threshold},
        ),
        LambdaRule("trend_reverse_rule", "触发趋势逆转模式", lambda row: row.is_trend_reverse == 1),
        LambdaRule("pile_rule", "触发层叠模式", lambda row: row.is_pile == 1),
        LambdaRule("re_pile_rule", "触发反向层叠模式", lambda row: row.is_re_pile == 1),
        LambdaRule("n_bottom_rule", "触发n倍底模式", lambda row: row.is_n_bottom == 1),
        LambdaRule("flag_range_rule", "触发旗式排列模式", lambda row: row.is_flag_range == 1),
    ]
