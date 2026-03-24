import unittest

from lotto_app.backtest import evaluate_rules
from lotto_app.features import build_feature_rows
from lotto_app.fetcher import DrawRecord
from lotto_app.models import train_and_rank
from lotto_app.rules import LambdaRule, default_rules


class FeatureAndBacktestTests(unittest.TestCase):
    def setUp(self):
        self.records = [
            DrawRecord(serial="2025004", draw_date="2025-01-04", red=[1, 7, 8, 9, 10, 11], blue=1),
            DrawRecord(serial="2025003", draw_date="2025-01-03", red=[2, 12, 13, 14, 15, 16], blue=2),
            DrawRecord(serial="2025002", draw_date="2025-01-02", red=[1, 17, 18, 19, 20, 21], blue=3),
            DrawRecord(serial="2025001", draw_date="2025-01-01", red=[3, 22, 23, 24, 25, 26], blue=4),
        ]

    def test_build_feature_rows_marks_incomplete_future_windows(self):
        rows = build_feature_rows(self.records)
        first_draw_ball_1 = next(row for row in rows if row.serial == "2025001" and row.ball == 1)
        last_draw_ball_1 = next(row for row in rows if row.serial == "2025004" and row.ball == 1)

        self.assertEqual(1, first_draw_ball_1.y_1)
        self.assertEqual(1, first_draw_ball_1.y_3)
        self.assertEqual(-1, first_draw_ball_1.y_5)
        self.assertEqual(-1, last_draw_ball_1.y_1)
        self.assertEqual(-1, last_draw_ball_1.y_3)
        self.assertIn("is_trend_reverse", first_draw_ball_1.as_dict())
        self.assertIn("is_pile", first_draw_ball_1.as_dict())
        self.assertIn("is_flag_range", first_draw_ball_1.as_dict())
        self.assertIn("freq_100", first_draw_ball_1.as_dict())
        self.assertIn("freq_300", first_draw_ball_1.as_dict())
        self.assertIn("freq_all", first_draw_ball_1.as_dict())

    def test_evaluate_rules_ignores_incomplete_future_labels(self):
        rows = build_feature_rows(self.records)
        rule = LambdaRule("ball_one_rule", "ball == 1", lambda row: row.ball == 1)

        reports = evaluate_rules(rows, [rule], train_ratio=0.5, rolling_min_train_draws=1, rolling_step=1)

        self.assertEqual(1, len(reports))
        self.assertEqual("ball_one_rule", reports[0].rule_name)
        self.assertGreaterEqual(reports[0].rule_y1_train, 0.0)
        self.assertGreaterEqual(reports[0].rule_y1_test, 0.0)
        self.assertGreaterEqual(reports[0].rolling_splits, 1)

    def test_default_rules_include_pattern_rules(self):
        rule_names = {rule.name for rule in default_rules()}
        self.assertIn("trend_reverse_rule", rule_names)
        self.assertIn("pile_rule", rule_names)
        self.assertIn("re_pile_rule", rule_names)
        self.assertIn("n_bottom_rule", rule_names)
        self.assertIn("flag_range_rule", rule_names)

    def test_train_and_rank_returns_ranked_latest_draw(self):
        rows = build_feature_rows(self.records)

        ranking_rows, metric_rows = train_and_rank(rows, train_ratio=0.5)

        self.assertEqual(33, len(ranking_rows))
        self.assertEqual(1, len(metric_rows))
        self.assertEqual("test", metric_rows[0].split)
        self.assertEqual("2025003", ranking_rows[0].serial)
        self.assertEqual(list(range(1, 34)), [row.rank_y1 for row in ranking_rows])


if __name__ == "__main__":
    unittest.main()
