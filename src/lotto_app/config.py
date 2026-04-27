from __future__ import annotations

import argparse
from pathlib import Path

from .constants import DEFAULT_HISTORY_URL, MAX_DRAWS, SUPPORTED_RECENT_WINDOWS


def parse_args(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Fetch and analyze 双色球 results.")
    parser.add_argument("--xlsx", default=str(Path(__file__).resolve().parents[2] / "data" / "output" / "data.xlsx"), help="Path to the output workbook.")
    parser.add_argument("--draws", type=int, default=MAX_DRAWS, help="How many recent draws to fetch. Default: %(default)s")
    parser.add_argument("--full-history-draws", type=int, default=0, help="How many draws to use for feature/backtest exports. Default: 0 means all available history.")
    parser.add_argument("--url", default=DEFAULT_HISTORY_URL, help="Base URL template for the draw history source. Use {page} as the page placeholder.")
    parser.add_argument("--sample-csv", default=str(Path(__file__).resolve().parents[2] / "data" / "output" / "sample_features.csv"), help="Path to the exported sample feature table.")
    parser.add_argument("--rule-report-csv", default=str(Path(__file__).resolve().parents[2] / "data" / "output" / "rule_effectiveness.csv"), help="Path to the exported rule effectiveness report.")
    parser.add_argument("--rule-grid-report-csv", default=str(Path(__file__).resolve().parents[2] / "data" / "output" / "rule_grid_report.csv"), help="Path to the exported multi-config rule comparison report.")
    parser.add_argument("--rule-grid-summary-csv", default=str(Path(__file__).resolve().parents[2] / "data" / "output" / "rule_grid_summary.csv"), help="Path to the exported summarized multi-config rule ranking report.")
    parser.add_argument("--model-ranking-csv", default=str(Path(__file__).resolve().parents[2] / "data" / "output" / "model_ranking.csv"), help="Path to the exported latest-draw model ranking table.")
    parser.add_argument("--model-metrics-csv", default=str(Path(__file__).resolve().parents[2] / "data" / "output" / "model_metrics.csv"), help="Path to the exported model evaluation metrics.")
    parser.add_argument("--blue-model-ranking-csv", default=str(Path(__file__).resolve().parents[2] / "data" / "output" / "model_blue_ranking.csv"), help="Path to the exported latest-draw blue-ball model ranking table.")
    parser.add_argument("--blue-model-metrics-csv", default=str(Path(__file__).resolve().parents[2] / "data" / "output" / "model_blue_metrics.csv"), help="Path to the exported blue-ball model evaluation metrics.")
    parser.add_argument("--candidate-pools-csv", default=str(Path(__file__).resolve().parents[2] / "data" / "output" / "candidate_pools.csv"), help="Path to the exported candidate pool summary.")
    parser.add_argument("--candidate-combinations-csv", default=str(Path(__file__).resolve().parents[2] / "data" / "output" / "candidate_combinations.csv"), help="Path to the exported constrained red-ball candidate combinations.")
    parser.add_argument("--strategy-backtest-csv", default=str(Path(__file__).resolve().parents[2] / "data" / "output" / "strategy_backtest.csv"), help="Path to the exported historical strategy backtest report.")
    parser.add_argument("--candidate-combo-limit", type=int, default=20, help="Maximum number of candidate combinations to export. Default: %(default)s")
    parser.add_argument("--strategy-start-bankroll", type=float, default=1000.0, help="Starting bankroll for the fixed-ticket strategy simulation. Default: %(default)s")
    parser.add_argument("--strategy-ticket-cost", type=float, default=2.0, help="Cost per simulated ticket in the fixed-ticket strategy. Default: %(default)s")
    parser.add_argument("--strategy-combo-ticket-count", type=int, default=5, help="How many top red combinations to buy per draw in the fixed-ticket strategy. Default: %(default)s")
    parser.add_argument("--strategy-blue-ticket-count", type=int, default=3, help="How many top blue candidates to pair with each red combination in the fixed-ticket strategy. Default: %(default)s")
    parser.add_argument("--rolling-min-train-draws", type=int, default=100, help="Minimum history size before rolling evaluation starts. Default: %(default)s")
    parser.add_argument("--rolling-step", type=int, default=1, help="Rolling evaluation step size in draws. Default: %(default)s")
    parser.add_argument("--model-retrain-interval", type=int, default=5, help="How many draws to reuse the fitted ranking model before retraining during rolling backtests. Default: %(default)s")
    parser.add_argument("--model-train-epochs", type=int, default=120, help="Training epochs for the logistic ranking model. Lower values run faster. Default: %(default)s")
    parser.add_argument("--rule-config", help="Path to a JSON rule config file. Supports a single config object, a list, or an object with a 'configs' list.")
    parser.add_argument("--omit-threshold", type=int, default=10, help="Threshold for the deep omit rule. Default: %(default)s")
    parser.add_argument("--gap-ratio-threshold", type=float, default=1.5, help="Threshold for the high gap ratio rule. Default: %(default)s")
    parser.add_argument("--active-recent-min-hits", type=int, default=2, help="Minimum recent hits for the active recent rule. Default: %(default)s")
    parser.add_argument("--inactive-recent-window", type=int, default=10, help="Recent-window size recorded for the inactive recent rule. Default: %(default)s")
    parser.add_argument("--heat-score-threshold", type=float, default=0.6, help="Threshold for the heat score rule. Default: %(default)s")
    parser.add_argument("--gap-cv-threshold", type=float, default=0.5, help="Threshold for the gap volatility rule. Default: %(default)s")
    parser.add_argument("--sweep-omit-thresholds", help="Comma-separated omit thresholds for automatic rule sweep generation.")
    parser.add_argument("--sweep-gap-ratio-thresholds", help="Comma-separated gap-ratio thresholds for automatic rule sweep generation.")
    parser.add_argument("--sweep-heat-score-thresholds", help="Comma-separated heat-score thresholds for automatic rule sweep generation.")
    parser.add_argument("--sweep-gap-cv-thresholds", help="Comma-separated gap-cv thresholds for automatic rule sweep generation.")
    parser.add_argument("--trend-reverse-min-omit", type=int, default=17, help="Minimum omit threshold for trend-reverse pattern hits. Default: %(default)s")
    parser.add_argument("--pile-long-min", type=int, default=15, help="Minimum omit value for the long segment in pile/re-pile patterns. Default: %(default)s")
    parser.add_argument("--pile-mid-min", type=int, default=8, help="Minimum omit value for the middle segment in pile/re-pile patterns. Default: %(default)s")
    parser.add_argument("--pile-short-min", type=int, default=3, help="Minimum omit value for the short segment in pile/re-pile patterns. Default: %(default)s")
    parser.add_argument("--flag-range-start-min", type=int, default=5, help="Minimum initial omit value for flag-range pattern hits. Default: %(default)s")
    parser.add_argument("--flag-range-start-max", type=int, default=6, help="Maximum initial omit value for flag-range pattern hits. Default: %(default)s")
    parser.add_argument("--flag-range-min-repeat", type=int, default=2, help="Minimum repeated flag-range segments before a hit is recorded. Default: %(default)s")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Logging level. Default: %(default)s")
    args = parser.parse_args(argv)
    validate_args(parser, args)
    return args


def validate_args(parser: argparse.ArgumentParser, args) -> None:
    if args.draws < MAX_DRAWS:
        parser.error("--draws must be at least %d because the analysis logic depends on 100 draws." % MAX_DRAWS)
    if args.full_history_draws < 0:
        parser.error("--full-history-draws must be greater than or equal to 0.")
    if args.rolling_min_train_draws <= 0:
        parser.error("--rolling-min-train-draws must be greater than 0.")
    if args.rolling_step <= 0:
        parser.error("--rolling-step must be greater than 0.")
    if args.model_retrain_interval <= 0:
        parser.error("--model-retrain-interval must be greater than 0.")
    if args.model_train_epochs <= 0:
        parser.error("--model-train-epochs must be greater than 0.")
    if args.omit_threshold < 0:
        parser.error("--omit-threshold must be greater than or equal to 0.")
    if args.gap_ratio_threshold <= 0:
        parser.error("--gap-ratio-threshold must be greater than 0.")
    if args.active_recent_min_hits <= 0:
        parser.error("--active-recent-min-hits must be greater than 0.")
    if args.inactive_recent_window <= 0:
        parser.error("--inactive-recent-window must be greater than 0.")
    if args.inactive_recent_window not in SUPPORTED_RECENT_WINDOWS:
        parser.error("--inactive-recent-window must be one of %s." % ", ".join(str(value) for value in SUPPORTED_RECENT_WINDOWS))
    if not 0.0 <= args.heat_score_threshold <= 1.0:
        parser.error("--heat-score-threshold must be between 0 and 1.")
    if args.gap_cv_threshold < 0:
        parser.error("--gap-cv-threshold must be greater than or equal to 0.")
    if args.trend_reverse_min_omit <= 0:
        parser.error("--trend-reverse-min-omit must be greater than 0.")
    if args.pile_short_min <= 0:
        parser.error("--pile-short-min must be greater than 0.")
    if args.pile_mid_min < args.pile_short_min:
        parser.error("--pile-mid-min must be greater than or equal to --pile-short-min.")
    if args.pile_long_min < args.pile_mid_min:
        parser.error("--pile-long-min must be greater than or equal to --pile-mid-min.")
    if args.flag_range_start_min <= 0:
        parser.error("--flag-range-start-min must be greater than 0.")
    if args.flag_range_start_max < args.flag_range_start_min:
        parser.error("--flag-range-start-max must be greater than or equal to --flag-range-start-min.")
    if args.flag_range_min_repeat <= 0:
        parser.error("--flag-range-min-repeat must be greater than 0.")
    if args.candidate_combo_limit <= 0:
        parser.error("--candidate-combo-limit must be greater than 0.")
    if args.strategy_start_bankroll < 0:
        parser.error("--strategy-start-bankroll must be greater than or equal to 0.")
    if args.strategy_ticket_cost <= 0:
        parser.error("--strategy-ticket-cost must be greater than 0.")
    if args.strategy_combo_ticket_count <= 0:
        parser.error("--strategy-combo-ticket-count must be greater than 0.")
    if args.strategy_blue_ticket_count <= 0:
        parser.error("--strategy-blue-ticket-count must be greater than 0.")
