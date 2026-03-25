import unittest
from contextlib import redirect_stderr
from io import StringIO
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from lotto_app.cli import (
    build_candidate_combination_rows,
    build_candidate_pool_rows,
    build_rule_grid_summary_rows,
    build_strategy_backtest_rows,
    load_rule_config_entries,
    parse_args,
)
from lotto_app.backtest import evaluate_rules
from lotto_app.features import FeatureRow, build_blue_feature_rows, build_feature_rows
from lotto_app.fetcher import DrawRecord
from lotto_app.models import train_and_rank, train_rank_and_backtest
from lotto_app.rules import LambdaRule, RuleConfig, default_rules


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
        self.assertIn("heat_score", first_draw_ball_1.as_dict())
        self.assertIn("gap_stddev", first_draw_ball_1.as_dict())
        self.assertIn("gap_cv", first_draw_ball_1.as_dict())
        self.assertGreaterEqual(first_draw_ball_1.heat_score, 0.0)
        self.assertLessEqual(first_draw_ball_1.heat_score, 1.0)
        self.assertEqual("red", first_draw_ball_1.ball_type)

    def test_build_blue_feature_rows_builds_blue_samples(self):
        rows = build_blue_feature_rows(self.records)
        first_draw_ball_4 = next(row for row in rows if row.serial == "2025001" and row.ball == 4)
        last_draw_ball_4 = next(row for row in rows if row.serial == "2025004" and row.ball == 4)

        self.assertEqual("blue", first_draw_ball_4.ball_type)
        self.assertEqual(1, first_draw_ball_4.hit_current)
        self.assertEqual(-1, last_draw_ball_4.y_1)

    def test_evaluate_rules_ignores_incomplete_future_labels(self):
        rows = build_feature_rows(self.records)
        rule = LambdaRule("ball_one_rule", "ball == 1", lambda row: row.ball == 1)

        reports = evaluate_rules(rows, [rule], train_ratio=0.5, rolling_min_train_draws=1, rolling_step=1)

        self.assertEqual(1, len(reports))
        self.assertEqual("ball_one_rule", reports[0].rule_name)
        self.assertEqual("{}", reports[0].parameters)
        self.assertGreaterEqual(reports[0].rule_y1_train, 0.0)
        self.assertGreaterEqual(reports[0].rule_y1_test, 0.0)
        self.assertGreaterEqual(reports[0].rolling_splits, 1)

    def test_default_rules_include_pattern_rules(self):
        rules = default_rules()
        rule_names = {rule.name for rule in rules}
        self.assertIn("trend_reverse_rule", rule_names)
        self.assertIn("pile_rule", rule_names)
        self.assertIn("re_pile_rule", rule_names)
        self.assertIn("n_bottom_rule", rule_names)
        self.assertIn("flag_range_rule", rule_names)
        self.assertIn("high_heat_score_rule", rule_names)
        self.assertIn("volatile_gap_rule", rule_names)
        high_heat_rule = next(rule for rule in rules if rule.name == "high_heat_score_rule")
        self.assertIn("heat_score_threshold", high_heat_rule.parameters())

    def test_default_rules_apply_custom_thresholds(self):
        rules = default_rules(RuleConfig(omit_threshold=12, heat_score_threshold=0.75))

        deep_omit_rule = next(rule for rule in rules if rule.name == "deep_omit_rule")
        high_heat_rule = next(rule for rule in rules if rule.name == "high_heat_score_rule")

        self.assertEqual(12, deep_omit_rule.parameters()["omit_threshold"])
        self.assertEqual(0.75, high_heat_rule.parameters()["heat_score_threshold"])

    def test_default_rules_apply_inactive_recent_window_to_rule_logic(self):
        rules = default_rules(RuleConfig(inactive_recent_window=5))
        inactive_rule = next(rule for rule in rules if rule.name == "inactive_recent_rule")
        target_row = FeatureRow(
            ball_type="red",
            draw_index=9,
            serial="2025010",
            draw_date="2025-01-10",
            ball=2,
            hit_current=0,
            omit_now=6,
            freq_5=0,
            freq_10=1,
            freq_30=1,
            freq_100=1,
            freq_300=1,
            freq_all=1,
            avg_gap=6.0,
            last_gap=6,
            gap_stddev=0.0,
            gap_cv=0.0,
            gap_ratio=1.0,
            gap_percentile=0.5,
            heat_score=0.2,
            is_hot=0,
            is_cold=0,
            is_warm=1,
            is_trend_reverse=0,
            is_pile=0,
            is_re_pile=0,
            is_n_bottom=0,
            is_flag_range=0,
            y_1=0,
            y_3=0,
            y_5=0,
        )

        self.assertEqual(0, target_row.freq_5)
        self.assertEqual(1, target_row.freq_10)
        self.assertTrue(inactive_rule.match(target_row))

    def test_train_and_rank_returns_ranked_latest_draw(self):
        rows = build_feature_rows(self.records)

        ranking_rows, metric_rows = train_and_rank(rows, train_ratio=0.5, target="red", top_primary_k=6, top_secondary_k=10)

        self.assertEqual(33, len(ranking_rows))
        self.assertEqual(4, len(metric_rows))
        logistic_metric = next(row for row in metric_rows if row.model_name == "logistic")
        random_metric = next(row for row in metric_rows if row.model_name == "random_baseline")
        omit_metric = next(row for row in metric_rows if row.model_name == "omit_baseline")
        heat_metric = next(row for row in metric_rows if row.model_name == "heat_baseline")
        self.assertEqual("rolling", logistic_metric.split)
        self.assertEqual("red", logistic_metric.target)
        self.assertEqual(random_metric.draw_count, logistic_metric.draw_count)
        self.assertEqual(omit_metric.draw_count, logistic_metric.draw_count)
        self.assertEqual(heat_metric.draw_count, logistic_metric.draw_count)
        self.assertEqual("2025004", ranking_rows[0].serial)
        self.assertEqual(list(range(1, 34)), [row.rank_y1 for row in ranking_rows])
        self.assertGreaterEqual(random_metric.top_primary_avg_hits, 0.0)

    def test_train_and_rank_returns_ranked_latest_blue_draw(self):
        rows = build_blue_feature_rows(self.records)

        ranking_rows, metric_rows = train_and_rank(rows, train_ratio=0.5, target="blue", top_primary_k=1, top_secondary_k=3)

        self.assertEqual(16, len(ranking_rows))
        logistic_metric = next(row for row in metric_rows if row.model_name == "logistic")
        random_metric = next(row for row in metric_rows if row.model_name == "random_baseline")
        self.assertEqual("blue", logistic_metric.target)
        self.assertEqual(1, logistic_metric.top_primary_k)
        self.assertEqual(3, logistic_metric.top_secondary_k)
        self.assertEqual("blue", random_metric.target)
        self.assertEqual("2025004", ranking_rows[0].serial)

    def test_train_and_rank_returns_latest_predictions_when_no_labels_available(self):
        rows = build_feature_rows([self.records[-1]])

        ranking_rows, metric_rows = train_and_rank(rows, train_ratio=0.5, target="red", top_primary_k=6, top_secondary_k=10)

        self.assertEqual(33, len(ranking_rows))
        self.assertEqual("2025001", ranking_rows[0].serial)
        self.assertEqual(1, len(metric_rows))
        self.assertEqual(0, metric_rows[0].draw_count)
        self.assertEqual("logistic", metric_rows[0].model_name)
        self.assertEqual("rolling", metric_rows[0].split)

    def test_train_rank_and_backtest_uses_walk_forward_predictions(self):
        rows = build_feature_rows(self.records)

        _, backtest_rows, metric_rows = train_rank_and_backtest(rows, train_ratio=0.5, target="red", top_primary_k=6, top_secondary_k=10)

        self.assertEqual(33, len(backtest_rows))
        self.assertEqual({"2025003"}, {row.serial for row in backtest_rows})
        logistic_metric = next(row for row in metric_rows if row.model_name == "logistic")
        random_metric = next(row for row in metric_rows if row.model_name == "random_baseline")
        self.assertEqual(1, logistic_metric.draw_count)
        self.assertGreaterEqual(random_metric.top_secondary_avg_hits, random_metric.top_primary_avg_hits)

    def test_parse_args_rejects_invalid_rolling_step(self):
        with redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit):
                parse_args(["--rolling-step", "0"])

    def test_parse_args_rejects_negative_full_history_draws(self):
        with redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit):
                parse_args(["--full-history-draws", "-1"])

    def test_parse_args_accepts_rule_threshold_overrides(self):
        args = parse_args(["--omit-threshold", "12", "--heat-score-threshold", "0.75", "--gap-cv-threshold", "0.8"])

        self.assertEqual(12, args.omit_threshold)
        self.assertEqual(0.75, args.heat_score_threshold)
        self.assertEqual(0.8, args.gap_cv_threshold)

    def test_parse_args_accepts_sweep_thresholds(self):
        args = parse_args(["--sweep-omit-thresholds", "10,12", "--sweep-heat-score-thresholds", "0.6,0.75"])

        self.assertEqual("10,12", args.sweep_omit_thresholds)
        self.assertEqual("0.6,0.75", args.sweep_heat_score_thresholds)

    def test_parse_args_accepts_strategy_budget_overrides(self):
        args = parse_args(
            [
                "--strategy-start-bankroll",
                "500",
                "--strategy-ticket-cost",
                "3",
                "--strategy-combo-ticket-count",
                "4",
                "--strategy-blue-ticket-count",
                "2",
            ]
        )

        self.assertEqual(500.0, args.strategy_start_bankroll)
        self.assertEqual(3.0, args.strategy_ticket_cost)
        self.assertEqual(4, args.strategy_combo_ticket_count)
        self.assertEqual(2, args.strategy_blue_ticket_count)

    def test_parse_args_accepts_pattern_threshold_overrides(self):
        args = parse_args(["--trend-reverse-min-omit", "19", "--pile-long-min", "16", "--flag-range-min-repeat", "3"])

        self.assertEqual(19, args.trend_reverse_min_omit)
        self.assertEqual(16, args.pile_long_min)
        self.assertEqual(3, args.flag_range_min_repeat)

    def test_parse_args_rejects_unsupported_inactive_recent_window(self):
        with redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit):
                parse_args(["--inactive-recent-window", "7"])

    def test_load_rule_config_entries_reads_multiple_configs(self):
        payload = {
            "configs": [
                {"name": "base", "omit_threshold": 12},
                {"name": "aggressive", "heat_score_threshold": 0.8, "gap_cv_threshold": 0.9, "trend_reverse_min_omit": 19},
            ]
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "rules.json"
            config_path.write_text(json.dumps(payload), encoding="utf-8")

            entries = load_rule_config_entries(parse_args(["--rule-config", str(config_path)]))

        self.assertEqual(["base", "aggressive"], [name for name, _ in entries])
        self.assertEqual(12, entries[0][1].omit_threshold)
        self.assertEqual(0.8, entries[1][1].heat_score_threshold)
        self.assertEqual(0.9, entries[1][1].gap_cv_threshold)
        self.assertEqual(19, entries[1][1].trend_reverse_min_omit)

    def test_load_rule_config_entries_rejects_unsupported_recent_window(self):
        payload = {"configs": [{"name": "bad", "inactive_recent_window": 7}]}
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "rules.json"
            config_path.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaises(RuntimeError):
                load_rule_config_entries(parse_args(["--rule-config", str(config_path)]))

    def test_load_rule_config_entries_expands_sweeps(self):
        entries = load_rule_config_entries(
            parse_args(
                [
                    "--sweep-omit-thresholds",
                    "10,12",
                    "--sweep-heat-score-thresholds",
                    "0.6,0.75",
                ]
            )
        )

        self.assertEqual(4, len(entries))
        self.assertEqual("default_sweep_001", entries[0][0])
        self.assertEqual("default_sweep_004", entries[-1][0])
        self.assertEqual(10, entries[0][1].omit_threshold)
        self.assertEqual(0.75, entries[-1][1].heat_score_threshold)

    def test_load_rule_config_entries_sweep_preserves_pattern_thresholds(self):
        entries = load_rule_config_entries(
            parse_args(
                [
                    "--trend-reverse-min-omit",
                    "19",
                    "--pile-long-min",
                    "16",
                    "--flag-range-min-repeat",
                    "3",
                    "--sweep-omit-thresholds",
                    "10,12",
                ]
            )
        )

        self.assertEqual(2, len(entries))
        self.assertTrue(all(config.trend_reverse_min_omit == 19 for _, config in entries))
        self.assertTrue(all(config.pile_long_min == 16 for _, config in entries))
        self.assertTrue(all(config.flag_range_min_repeat == 3 for _, config in entries))

    def test_build_rule_grid_summary_rows_sorts_by_lift_score(self):
        rows = [
            {
                "config_name": "base",
                "rule_name": "rule_a",
                "description": "A",
                "parameters": "{}",
                "lift_y1_test": 0.02,
                "rolling_lift_y1": 0.01,
                "lift_y3_test": 0.01,
                "rolling_lift_y3": 0.0,
                "trigger_count_test": 5,
                "rolling_trigger_count": 7,
            },
            {
                "config_name": "aggressive",
                "rule_name": "rule_b",
                "description": "B",
                "parameters": "{}",
                "lift_y1_test": 0.05,
                "rolling_lift_y1": 0.03,
                "lift_y3_test": 0.02,
                "rolling_lift_y3": 0.01,
                "trigger_count_test": 4,
                "rolling_trigger_count": 6,
            },
        ]

        summary = build_rule_grid_summary_rows(rows)

        self.assertEqual(2, len(summary))
        self.assertEqual("aggressive", summary[0]["config_name"])
        self.assertEqual("rule_b", summary[0]["rule_name"])
        self.assertEqual(1, summary[0]["rank"])
        self.assertGreater(summary[0]["score"], summary[1]["score"])

    def test_build_candidate_pool_rows_returns_expected_pools(self):
        red_rows = build_feature_rows(self.records)
        red_ranking_rows, _ = train_and_rank(red_rows, train_ratio=0.5, target="red", top_primary_k=6, top_secondary_k=10)
        blue_rows = build_blue_feature_rows(self.records)
        blue_ranking_rows, _ = train_and_rank(blue_rows, train_ratio=0.5, target="blue", top_primary_k=1, top_secondary_k=3)

        pools = build_candidate_pool_rows(red_ranking_rows, blue_ranking_rows)

        self.assertEqual(1, len(pools))
        self.assertEqual("2025004", pools[0]["serial"])
        self.assertEqual(3, len(pools[0]["red_dan_pool"].split(",")))
        self.assertEqual(10, len(pools[0]["red_candidate_pool"].split(",")))
        self.assertEqual(8, len(pools[0]["red_kill_pool"].split(",")))
        self.assertEqual(1, len(pools[0]["blue_dan_pool"].split(",")))
        self.assertEqual(3, len(pools[0]["blue_candidate_pool"].split(",")))
        self.assertEqual(5, len(pools[0]["blue_kill_pool"].split(",")))

    def test_build_candidate_combination_rows_returns_constrained_combos(self):
        red_rows = build_feature_rows(self.records)
        red_ranking_rows, _ = train_and_rank(red_rows, train_ratio=0.5, target="red", top_primary_k=6, top_secondary_k=10)
        blue_rows = build_blue_feature_rows(self.records)
        blue_ranking_rows, _ = train_and_rank(blue_rows, train_ratio=0.5, target="blue", top_primary_k=1, top_secondary_k=3)

        combos = build_candidate_combination_rows(red_ranking_rows, blue_ranking_rows, limit=5)

        self.assertGreaterEqual(len(combos), 1)
        self.assertLessEqual(len(combos), 5)
        first = combos[0]
        balls = [int(item) for item in first["red_balls"].split(",")]
        self.assertEqual(6, len(balls))
        self.assertTrue(70 <= first["sum_value"] <= 150)
        self.assertIn(first["odd_even_ratio"], {"2:4", "3:3", "4:2"})
        self.assertIn(first["small_big_ratio"], {"3:3", "4:2", "5:1"})
        self.assertEqual(3, len(first["suggested_blue_pool"].split(",")))

    def test_build_strategy_backtest_rows_returns_per_draw_and_summary_rows(self):
        red_rows = build_feature_rows(self.records)
        _, red_backtest_rows, _ = train_rank_and_backtest(red_rows, train_ratio=0.5, target="red", top_primary_k=6, top_secondary_k=10)
        blue_rows = build_blue_feature_rows(self.records)
        _, blue_backtest_rows, _ = train_rank_and_backtest(blue_rows, train_ratio=0.5, target="blue", top_primary_k=1, top_secondary_k=3)

        strategy_rows = build_strategy_backtest_rows(
            red_backtest_rows,
            blue_backtest_rows,
            candidate_combo_limit=5,
            start_bankroll=100.0,
            ticket_cost=2.0,
            combo_ticket_count=2,
            blue_ticket_count=2,
        )

        self.assertGreaterEqual(len(strategy_rows), 14)
        per_draw_row = next(row for row in strategy_rows if row["scope"] == "per_draw" and row["strategy_name"] == "red_dan_pool")
        summary_row = next(row for row in strategy_rows if row["scope"] == "summary" and row["strategy_name"] == "red_combo_cover_4plus")
        bankroll_row = next(row for row in strategy_rows if row["scope"] == "per_draw" and row["strategy_name"] == "fixed_ticket_bundle")
        self.assertEqual("2025003", per_draw_row["serial"])
        self.assertEqual("SUMMARY", summary_row["serial"])
        self.assertGreaterEqual(per_draw_row["baseline_success_rate_random"], 0.0)
        self.assertLessEqual(per_draw_row["baseline_success_rate_random"], 1.0)
        self.assertGreater(bankroll_row["baseline_success_rate_random"], 0.0)
        self.assertLessEqual(bankroll_row["baseline_success_rate_random"], 1.0)
        self.assertGreaterEqual(summary_row["combo_count"], 0)
        self.assertGreaterEqual(bankroll_row["ticket_count"], 1)
        self.assertEqual(100.0 + bankroll_row["net_profit"], bankroll_row["bankroll_after"])

    def test_main_preserves_previous_workbook_signature_until_rebuild_finishes(self):
        from lotto_app import cli

        args = SimpleNamespace(
            xlsx="",
            draws=100,
            full_history_draws=0,
            url="https://example.test/history?page={page}",
            sample_csv="sample.csv",
            rule_report_csv="rule.csv",
            rule_grid_report_csv="rule_grid.csv",
            rule_grid_summary_csv="rule_summary.csv",
            model_ranking_csv="model.csv",
            model_metrics_csv="metrics.csv",
            blue_model_ranking_csv="blue_model.csv",
            blue_model_metrics_csv="blue_metrics.csv",
            candidate_pools_csv="pools.csv",
            candidate_combinations_csv="combos.csv",
            strategy_backtest_csv="strategy.csv",
            candidate_combo_limit=20,
            strategy_start_bankroll=1000.0,
            strategy_ticket_cost=2.0,
            strategy_combo_ticket_count=5,
            strategy_blue_ticket_count=3,
            rolling_min_train_draws=100,
            rolling_step=1,
            rule_config=None,
            omit_threshold=10,
            gap_ratio_threshold=1.5,
            active_recent_min_hits=2,
            inactive_recent_window=10,
            heat_score_threshold=0.6,
            gap_cv_threshold=0.5,
            sweep_omit_thresholds=None,
            sweep_gap_ratio_thresholds=None,
            sweep_heat_score_thresholds=None,
            sweep_gap_cv_thresholds=None,
            trend_reverse_min_omit=17,
            pile_long_min=15,
            pile_mid_min=8,
            pile_short_min=3,
            flag_range_start_min=5,
            flag_range_start_max=6,
            flag_range_min_repeat=2,
            log_level="INFO",
        )

        records = self.records * 30
        with tempfile.TemporaryDirectory() as temp_dir:
            workbook_path = Path(temp_dir) / "data.xlsx"
            workbook_path.write_text("placeholder", encoding="utf-8")
            args.xlsx = str(workbook_path)

            with (
                patch("lotto_app.cli.parse_args", return_value=args),
                patch("lotto_app.cli.configure_logging"),
                patch("lotto_app.cli.ensure_excel_dependencies", return_value=object()),
                patch("lotto_app.cli.sync_history_cache", return_value=(records, True)),
                patch("lotto_app.cli.compute_pipeline_signature", return_value="pipeline-new"),
                patch("lotto_app.cli.compute_workbook_signature", return_value="workbook-same"),
                patch("lotto_app.cli.load_pipeline_state", return_value={"pipeline_signature": "pipeline-old", "workbook_signature": "workbook-same"}),
                patch("lotto_app.cli._build_phase_one_outputs"),
                patch("lotto_app.cli.save_pipeline_state") as save_state_mock,
            ):
                self.assertEqual(0, cli.main())

        first_payload = save_state_mock.call_args_list[0].args[1]
        self.assertEqual("workbook-same", first_payload["workbook_signature"])
        self.assertEqual("pipeline-new", first_payload["pipeline_signature"])


if __name__ == "__main__":
    unittest.main()
