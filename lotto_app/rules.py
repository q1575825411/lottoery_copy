from __future__ import annotations

from dataclasses import dataclass

from .features import FeatureRow


@dataclass(frozen=True)
class RuleDefinition:
    name: str
    description: str

    def match(self, row: FeatureRow) -> bool:
        raise NotImplementedError


@dataclass(frozen=True)
class LambdaRule(RuleDefinition):
    predicate: object

    def match(self, row: FeatureRow) -> bool:
        return bool(self.predicate(row))


def default_rules() -> list[RuleDefinition]:
    return [
        LambdaRule("hot_rule", "号码在最近1-5期与6-10期都出现过", lambda row: row.is_hot == 1),
        LambdaRule("cold_rule", "号码在最近10期内从未出现", lambda row: row.is_cold == 1),
        LambdaRule("warm_rule", "号码处于温号状态", lambda row: row.is_warm == 1),
        LambdaRule("deep_omit_rule", "当前遗漏值大于等于10", lambda row: row.omit_now >= 10),
        LambdaRule("high_gap_ratio_rule", "当前遗漏值超过历史平均1.5倍", lambda row: row.avg_gap > 0 and row.gap_ratio >= 1.5),
        LambdaRule("active_recent_rule", "最近5期至少出现2次", lambda row: row.freq_5 >= 2),
        LambdaRule("inactive_recent_rule", "最近10期未出现且当前非热号", lambda row: row.freq_10 == 0 and row.is_hot == 0),
        LambdaRule("trend_reverse_rule", "触发趋势逆转模式", lambda row: row.is_trend_reverse == 1),
        LambdaRule("pile_rule", "触发层叠模式", lambda row: row.is_pile == 1),
        LambdaRule("re_pile_rule", "触发反向层叠模式", lambda row: row.is_re_pile == 1),
        LambdaRule("n_bottom_rule", "触发n倍底模式", lambda row: row.is_n_bottom == 1),
        LambdaRule("flag_range_rule", "触发旗式排列模式", lambda row: row.is_flag_range == 1),
    ]
