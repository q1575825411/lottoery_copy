from __future__ import annotations

from dataclasses import dataclass

from .features import FeatureRow
from .rules import RuleDefinition


@dataclass(frozen=True)
class RuleReportRow:
    rule_name: str
    description: str
    trigger_count_total: int
    trigger_count_train: int
    trigger_count_test: int
    baseline_y1_train: float
    baseline_y1_test: float
    baseline_y3_train: float
    baseline_y3_test: float
    baseline_y5_train: float
    baseline_y5_test: float
    rule_y1_train: float
    rule_y1_test: float
    rule_y3_train: float
    rule_y3_test: float
    rule_y5_train: float
    rule_y5_test: float
    lift_y1_test: float
    lift_y3_test: float
    lift_y5_test: float
    rolling_splits: int
    rolling_trigger_count: int
    rolling_baseline_y1: float
    rolling_rule_y1: float
    rolling_lift_y1: float
    rolling_baseline_y3: float
    rolling_rule_y3: float
    rolling_lift_y3: float
    rolling_baseline_y5: float
    rolling_rule_y5: float
    rolling_lift_y5: float

    def as_dict(self) -> dict[str, object]:
        return self.__dict__.copy()


def _valid_rows(rows: list[FeatureRow], label_name: str) -> list[FeatureRow]:
    return [row for row in rows if getattr(row, label_name) >= 0]


def _rate(rows: list[FeatureRow], label_name: str) -> float:
    valid_rows = _valid_rows(rows, label_name)
    if not valid_rows:
        return 0.0
    return sum(getattr(row, label_name) for row in valid_rows) / float(len(valid_rows))


def _split_rows(rows: list[FeatureRow], train_ratio: float) -> tuple[list[FeatureRow], list[FeatureRow]]:
    if not rows:
        return [], []
    max_draw_index = max(row.draw_index for row in rows)
    split_index = int(max_draw_index * train_ratio)
    train_rows = [row for row in rows if row.draw_index <= split_index]
    test_rows = [row for row in rows if row.draw_index > split_index]
    return train_rows, test_rows


def _rolling_metrics(
    rows: list[FeatureRow],
    rule: RuleDefinition,
    label_name: str,
    min_train_draws: int,
    step: int,
) -> tuple[int, int, float, float, float]:
    if not rows:
        return 0, 0, 0.0, 0.0, 0.0

    draw_indices = sorted({row.draw_index for row in rows})
    split_count = 0
    trigger_count = 0
    baseline_sum = 0.0
    rule_sum = 0.0

    for split_draw in range(min_train_draws, len(draw_indices) - 1, step):
        train_rows = [row for row in rows if row.draw_index <= split_draw]
        test_rows = [row for row in rows if row.draw_index == split_draw + 1]
        baseline_rows = _valid_rows(test_rows, label_name)
        rule_rows = _valid_rows([row for row in test_rows if rule.match(row)], label_name)
        if not baseline_rows:
            continue

        split_count += 1
        baseline_sum += sum(getattr(row, label_name) for row in baseline_rows) / float(len(baseline_rows))
        if rule_rows:
            trigger_count += len(rule_rows)
            rule_sum += sum(getattr(row, label_name) for row in rule_rows) / float(len(rule_rows))
        else:
            rule_sum += 0.0

    if split_count == 0:
        return 0, 0, 0.0, 0.0, 0.0

    baseline_rate = baseline_sum / split_count
    rule_rate = rule_sum / split_count
    return split_count, trigger_count, baseline_rate, rule_rate, rule_rate - baseline_rate


def evaluate_rules(
    rows: list[FeatureRow],
    rules: list[RuleDefinition],
    train_ratio: float = 0.7,
    rolling_min_train_draws: int = 100,
    rolling_step: int = 1,
) -> list[RuleReportRow]:
    if not rows:
        return []

    train_rows, test_rows = _split_rows(rows, train_ratio)

    baseline_y1_train = _rate(train_rows, "y_1")
    baseline_y1_test = _rate(test_rows, "y_1")
    baseline_y3_train = _rate(train_rows, "y_3")
    baseline_y3_test = _rate(test_rows, "y_3")
    baseline_y5_train = _rate(train_rows, "y_5")
    baseline_y5_test = _rate(test_rows, "y_5")

    report_rows: list[RuleReportRow] = []
    for rule in rules:
        matched_all = [row for row in rows if rule.match(row)]
        matched_train = [row for row in train_rows if rule.match(row)]
        matched_test = [row for row in test_rows if rule.match(row)]

        rolling_splits, rolling_trigger_count, rolling_baseline_y1, rolling_rule_y1, rolling_lift_y1 = _rolling_metrics(
            rows, rule, "y_1", rolling_min_train_draws, rolling_step
        )
        _, _, rolling_baseline_y3, rolling_rule_y3, rolling_lift_y3 = _rolling_metrics(
            rows, rule, "y_3", rolling_min_train_draws, rolling_step
        )
        _, _, rolling_baseline_y5, rolling_rule_y5, rolling_lift_y5 = _rolling_metrics(
            rows, rule, "y_5", rolling_min_train_draws, rolling_step
        )

        rule_y1_train = _rate(matched_train, "y_1")
        rule_y1_test = _rate(matched_test, "y_1")
        rule_y3_train = _rate(matched_train, "y_3")
        rule_y3_test = _rate(matched_test, "y_3")
        rule_y5_train = _rate(matched_train, "y_5")
        rule_y5_test = _rate(matched_test, "y_5")

        report_rows.append(
            RuleReportRow(
                rule_name=rule.name,
                description=rule.description,
                trigger_count_total=len(matched_all),
                trigger_count_train=len(matched_train),
                trigger_count_test=len(matched_test),
                baseline_y1_train=baseline_y1_train,
                baseline_y1_test=baseline_y1_test,
                baseline_y3_train=baseline_y3_train,
                baseline_y3_test=baseline_y3_test,
                baseline_y5_train=baseline_y5_train,
                baseline_y5_test=baseline_y5_test,
                rule_y1_train=rule_y1_train,
                rule_y1_test=rule_y1_test,
                rule_y3_train=rule_y3_train,
                rule_y3_test=rule_y3_test,
                rule_y5_train=rule_y5_train,
                rule_y5_test=rule_y5_test,
                lift_y1_test=rule_y1_test - baseline_y1_test,
                lift_y3_test=rule_y3_test - baseline_y3_test,
                lift_y5_test=rule_y5_test - baseline_y5_test,
                rolling_splits=rolling_splits,
                rolling_trigger_count=rolling_trigger_count,
                rolling_baseline_y1=rolling_baseline_y1,
                rolling_rule_y1=rolling_rule_y1,
                rolling_lift_y1=rolling_lift_y1,
                rolling_baseline_y3=rolling_baseline_y3,
                rolling_rule_y3=rolling_rule_y3,
                rolling_lift_y3=rolling_lift_y3,
                rolling_baseline_y5=rolling_baseline_y5,
                rolling_rule_y5=rolling_rule_y5,
                rolling_lift_y5=rolling_lift_y5,
            )
        )

    return report_rows
