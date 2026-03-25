from __future__ import annotations

import argparse
from itertools import product
import json
import logging
import sys
import time
from pathlib import Path

from .analysis import set_omit_table
from .backtest import evaluate_rules
from .cache import (
    compute_pipeline_signature,
    compute_workbook_signature,
    load_pipeline_state,
    save_pipeline_state,
    sync_history_cache,
)
from .constants import DEFAULT_HISTORY_URL, MAX_DRAWS, SUPPORTED_RECENT_WINDOWS
from .deps import ensure_excel_dependencies
from .excel import WorkbookBuilder
from .features import FeatureRow, build_blue_feature_rows, build_feature_rows
from .fetcher import DrawRecord, populate_state_from_records
from .models import ModelMetricRow, ModelPredictionRow, train_rank_and_backtest
from .report import export_feature_rows, export_model_metrics, export_model_predictions, export_rule_report, export_rows
from .rule_grid import build_rule_grid_rows as _build_rule_grid_rows
from .rule_grid import build_rule_grid_summary_rows
from .rules import RuleConfig, default_rules
from .state import LottoState
from .strategy import build_candidate_combination_rows, build_candidate_pool_rows, build_strategy_backtest_rows

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Fetch and analyze 双色球 results.")
    parser.add_argument("--xlsx", default=str(Path(__file__).resolve().parents[1] / "data" / "data.xlsx"), help="Path to the output workbook.")
    parser.add_argument("--draws", type=int, default=MAX_DRAWS, help="How many recent draws to fetch. Default: %(default)s")
    parser.add_argument("--full-history-draws", type=int, default=0, help="How many draws to use for feature/backtest exports. Default: 0 means all available history.")
    parser.add_argument("--url", default=DEFAULT_HISTORY_URL, help="Base URL template for the draw history source. Use {page} as the page placeholder.")
    parser.add_argument("--sample-csv", default=str(Path(__file__).resolve().parents[1] / "data" / "sample_features.csv"), help="Path to the exported sample feature table.")
    parser.add_argument("--rule-report-csv", default=str(Path(__file__).resolve().parents[1] / "data" / "rule_effectiveness.csv"), help="Path to the exported rule effectiveness report.")
    parser.add_argument("--rule-grid-report-csv", default=str(Path(__file__).resolve().parents[1] / "data" / "rule_grid_report.csv"), help="Path to the exported multi-config rule comparison report.")
    parser.add_argument("--rule-grid-summary-csv", default=str(Path(__file__).resolve().parents[1] / "data" / "rule_grid_summary.csv"), help="Path to the exported summarized multi-config rule ranking report.")
    parser.add_argument("--model-ranking-csv", default=str(Path(__file__).resolve().parents[1] / "data" / "model_ranking.csv"), help="Path to the exported latest-draw model ranking table.")
    parser.add_argument("--model-metrics-csv", default=str(Path(__file__).resolve().parents[1] / "data" / "model_metrics.csv"), help="Path to the exported model evaluation metrics.")
    parser.add_argument("--blue-model-ranking-csv", default=str(Path(__file__).resolve().parents[1] / "data" / "model_blue_ranking.csv"), help="Path to the exported latest-draw blue-ball model ranking table.")
    parser.add_argument("--blue-model-metrics-csv", default=str(Path(__file__).resolve().parents[1] / "data" / "model_blue_metrics.csv"), help="Path to the exported blue-ball model evaluation metrics.")
    parser.add_argument("--candidate-pools-csv", default=str(Path(__file__).resolve().parents[1] / "data" / "candidate_pools.csv"), help="Path to the exported candidate pool summary.")
    parser.add_argument("--candidate-combinations-csv", default=str(Path(__file__).resolve().parents[1] / "data" / "candidate_combinations.csv"), help="Path to the exported constrained red-ball candidate combinations.")
    parser.add_argument("--strategy-backtest-csv", default=str(Path(__file__).resolve().parents[1] / "data" / "strategy_backtest.csv"), help="Path to the exported historical strategy backtest report.")
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
    return args


def configure_logging(level: str) -> None:
    logging.basicConfig(level=getattr(logging, level), format="%(levelname)s %(name)s: %(message)s")


def _phase_one_outputs_exist(paths: list[Path]) -> bool:
    return all(path.exists() for path in paths)


def build_rule_config(args) -> RuleConfig:
    return RuleConfig(
        omit_threshold=args.omit_threshold,
        gap_ratio_threshold=args.gap_ratio_threshold,
        active_recent_min_hits=args.active_recent_min_hits,
        inactive_recent_window=args.inactive_recent_window,
        heat_score_threshold=args.heat_score_threshold,
        gap_cv_threshold=args.gap_cv_threshold,
        trend_reverse_min_omit=args.trend_reverse_min_omit,
        pile_long_min=args.pile_long_min,
        pile_mid_min=args.pile_mid_min,
        pile_short_min=args.pile_short_min,
        flag_range_start_min=args.flag_range_start_min,
        flag_range_start_max=args.flag_range_start_max,
        flag_range_min_repeat=args.flag_range_min_repeat,
    )


def _ensure_supported_recent_window(window_size: int) -> int:
    if window_size not in SUPPORTED_RECENT_WINDOWS:
        raise RuntimeError(
            "inactive_recent_window must be one of %s" % ", ".join(str(value) for value in SUPPORTED_RECENT_WINDOWS)
        )
    return window_size


def _parse_sweep_values(raw_value: str | None, caster) -> list[object]:
    if not raw_value:
        return []
    values = []
    for part in raw_value.split(","):
        item = part.strip()
        if not item:
            continue
        values.append(caster(item))
    return values


def _build_rule_config_from_dict(payload: dict[str, object], fallback: RuleConfig) -> RuleConfig:
    return RuleConfig(
        omit_threshold=int(payload.get("omit_threshold", fallback.omit_threshold)),
        gap_ratio_threshold=float(payload.get("gap_ratio_threshold", fallback.gap_ratio_threshold)),
        active_recent_min_hits=int(payload.get("active_recent_min_hits", fallback.active_recent_min_hits)),
        inactive_recent_window=_ensure_supported_recent_window(int(payload.get("inactive_recent_window", fallback.inactive_recent_window))),
        heat_score_threshold=float(payload.get("heat_score_threshold", fallback.heat_score_threshold)),
        gap_cv_threshold=float(payload.get("gap_cv_threshold", fallback.gap_cv_threshold)),
        trend_reverse_min_omit=int(payload.get("trend_reverse_min_omit", fallback.trend_reverse_min_omit)),
        pile_long_min=int(payload.get("pile_long_min", fallback.pile_long_min)),
        pile_mid_min=int(payload.get("pile_mid_min", fallback.pile_mid_min)),
        pile_short_min=int(payload.get("pile_short_min", fallback.pile_short_min)),
        flag_range_start_min=int(payload.get("flag_range_start_min", fallback.flag_range_start_min)),
        flag_range_start_max=int(payload.get("flag_range_start_max", fallback.flag_range_start_max)),
        flag_range_min_repeat=int(payload.get("flag_range_min_repeat", fallback.flag_range_min_repeat)),
    )


def load_rule_config_entries(args) -> list[tuple[str, RuleConfig]]:
    cli_config = build_rule_config(args)
    if not args.rule_config:
        entries: list[tuple[str, RuleConfig]] = [("default", cli_config)]
    else:
        payload = json.loads(Path(args.rule_config).expanduser().read_text(encoding="utf-8"))
        if isinstance(payload, dict) and "configs" in payload:
            raw_entries = payload["configs"]
        elif isinstance(payload, list):
            raw_entries = payload
        else:
            raw_entries = [payload]

        entries = []
        for index, item in enumerate(raw_entries, start=1):
            if not isinstance(item, dict):
                raise RuntimeError("rule config entries must be JSON objects")
            name = str(item.get("name", f"config_{index}"))
            entries.append((name, _build_rule_config_from_dict(item, cli_config)))

    sweep_omit_thresholds = _parse_sweep_values(args.sweep_omit_thresholds, int)
    sweep_gap_ratio_thresholds = _parse_sweep_values(args.sweep_gap_ratio_thresholds, float)
    sweep_heat_score_thresholds = _parse_sweep_values(args.sweep_heat_score_thresholds, float)
    sweep_gap_cv_thresholds = _parse_sweep_values(args.sweep_gap_cv_thresholds, float)

    if not any([sweep_omit_thresholds, sweep_gap_ratio_thresholds, sweep_heat_score_thresholds, sweep_gap_cv_thresholds]):
        return entries

    expanded_entries: list[tuple[str, RuleConfig]] = []
    for base_name, base_config in entries:
        omit_values = sweep_omit_thresholds or [base_config.omit_threshold]
        gap_ratio_values = sweep_gap_ratio_thresholds or [base_config.gap_ratio_threshold]
        heat_score_values = sweep_heat_score_thresholds or [base_config.heat_score_threshold]
        gap_cv_values = sweep_gap_cv_thresholds or [base_config.gap_cv_threshold]
        for index, (omit_threshold, gap_ratio_threshold, heat_score_threshold, gap_cv_threshold) in enumerate(
            product(omit_values, gap_ratio_values, heat_score_values, gap_cv_values),
            start=1,
        ):
            expanded_entries.append(
                (
                    f"{base_name}_sweep_{index:03d}",
                    RuleConfig(
                        omit_threshold=int(omit_threshold),
                        gap_ratio_threshold=float(gap_ratio_threshold),
                        active_recent_min_hits=base_config.active_recent_min_hits,
                        inactive_recent_window=base_config.inactive_recent_window,
                        heat_score_threshold=float(heat_score_threshold),
                        gap_cv_threshold=float(gap_cv_threshold),
                        trend_reverse_min_omit=base_config.trend_reverse_min_omit,
                        pile_long_min=base_config.pile_long_min,
                        pile_mid_min=base_config.pile_mid_min,
                        pile_short_min=base_config.pile_short_min,
                        flag_range_start_min=base_config.flag_range_start_min,
                        flag_range_start_max=base_config.flag_range_start_max,
                        flag_range_min_repeat=base_config.flag_range_min_repeat,
                    ),
                )
            )
    return expanded_entries

def _build_phase_one_outputs(
    records: list[DrawRecord],
    args,
    sample_csv_path: Path,
    rule_report_csv_path: Path,
    rule_grid_report_csv_path: Path,
    rule_grid_summary_csv_path: Path,
    model_ranking_csv_path: Path,
    model_metrics_csv_path: Path,
    blue_model_ranking_csv_path: Path,
    blue_model_metrics_csv_path: Path,
    candidate_pools_csv_path: Path,
    candidate_combinations_csv_path: Path,
    strategy_backtest_csv_path: Path,
) -> tuple[list[FeatureRow], list, list[ModelPredictionRow], list[ModelMetricRow]]:
    config_entries = load_rule_config_entries(args)
    primary_config = config_entries[0][1]
    stage_start = time.perf_counter()
    logger.info("building feature rows for %s draws", len(records))
    feature_rows = build_feature_rows(records, pattern_config=primary_config)
    logger.info("built %s feature rows in %.2fs", len(feature_rows), time.perf_counter() - stage_start)

    stage_start = time.perf_counter()
    logger.info("evaluating %s rule config set(s) with rolling_min_train_draws=%s rolling_step=%s", len(config_entries), args.rolling_min_train_draws, args.rolling_step)
    rule_rows = []
    rule_grid_rows: list[dict[str, object]] = []
    for config_name, rule_config in config_entries:
        config_feature_rows = feature_rows if rule_config == primary_config else build_feature_rows(records, pattern_config=rule_config)
        evaluated_rows = evaluate_rules(
            config_feature_rows,
            default_rules(rule_config),
            rolling_min_train_draws=args.rolling_min_train_draws,
            rolling_step=args.rolling_step,
        )
        if not rule_rows:
            rule_rows = evaluated_rows
        rule_grid_rows.extend(_build_rule_grid_rows(config_name, evaluated_rows))
    logger.info("completed rule evaluation in %.2fs", time.perf_counter() - stage_start)

    stage_start = time.perf_counter()
    logger.info("training ranking model")
    model_ranking_rows, red_backtest_ranking_rows, model_metric_rows = train_rank_and_backtest(
        feature_rows,
        target="red",
        top_primary_k=6,
        top_secondary_k=10,
        rolling_min_train_draws=args.rolling_min_train_draws,
        rolling_step=args.rolling_step,
        retrain_interval=args.model_retrain_interval,
        train_epochs=args.model_train_epochs,
    )
    blue_feature_rows = build_blue_feature_rows(records)
    blue_model_ranking_rows, blue_backtest_ranking_rows, blue_model_metric_rows = train_rank_and_backtest(
        blue_feature_rows,
        target="blue",
        top_primary_k=1,
        top_secondary_k=3,
        rolling_min_train_draws=args.rolling_min_train_draws,
        rolling_step=args.rolling_step,
        retrain_interval=args.model_retrain_interval,
        train_epochs=args.model_train_epochs,
    )
    logger.info("completed model training and ranking in %.2fs", time.perf_counter() - stage_start)

    stage_start = time.perf_counter()
    logger.info("writing phase-1 csv outputs")
    export_feature_rows(sample_csv_path, feature_rows)
    export_rule_report(rule_report_csv_path, rule_rows)
    export_rows(rule_grid_report_csv_path, rule_grid_rows)
    export_rows(rule_grid_summary_csv_path, build_rule_grid_summary_rows(rule_grid_rows))
    export_model_predictions(model_ranking_csv_path, model_ranking_rows)
    export_model_metrics(model_metrics_csv_path, model_metric_rows)
    export_model_predictions(blue_model_ranking_csv_path, blue_model_ranking_rows)
    export_model_metrics(blue_model_metrics_csv_path, blue_model_metric_rows)
    export_rows(candidate_pools_csv_path, build_candidate_pool_rows(model_ranking_rows, blue_model_ranking_rows))
    export_rows(
        candidate_combinations_csv_path,
        build_candidate_combination_rows(
            model_ranking_rows,
            blue_model_ranking_rows,
            limit=args.candidate_combo_limit,
        ),
    )
    export_rows(
        strategy_backtest_csv_path,
        build_strategy_backtest_rows(
            red_backtest_ranking_rows,
            blue_backtest_ranking_rows,
            candidate_combo_limit=args.candidate_combo_limit,
            start_bankroll=args.strategy_start_bankroll,
            ticket_cost=args.strategy_ticket_cost,
            combo_ticket_count=args.strategy_combo_ticket_count,
            blue_ticket_count=args.strategy_blue_ticket_count,
        ),
    )
    logger.info("wrote phase-1 csv outputs in %.2fs", time.perf_counter() - stage_start)
    return feature_rows, rule_rows, model_ranking_rows, model_metric_rows


def main() -> int:
    try:
        args = parse_args()
        configure_logging(args.log_level)
        deps = ensure_excel_dependencies()
        data_dir = Path(__file__).resolve().parents[1] / "data"
        history_cache_path = data_dir / "history_cache.json"
        pipeline_state_path = data_dir / "pipeline_state.json"
        sample_csv_path = Path(args.sample_csv).expanduser().resolve()
        rule_report_csv_path = Path(args.rule_report_csv).expanduser().resolve()
        rule_grid_report_csv_path = Path(args.rule_grid_report_csv).expanduser().resolve()
        rule_grid_summary_csv_path = Path(args.rule_grid_summary_csv).expanduser().resolve()
        model_ranking_csv_path = Path(args.model_ranking_csv).expanduser().resolve()
        model_metrics_csv_path = Path(args.model_metrics_csv).expanduser().resolve()
        blue_model_ranking_csv_path = Path(args.blue_model_ranking_csv).expanduser().resolve()
        blue_model_metrics_csv_path = Path(args.blue_model_metrics_csv).expanduser().resolve()
        candidate_pools_csv_path = Path(args.candidate_pools_csv).expanduser().resolve()
        candidate_combinations_csv_path = Path(args.candidate_combinations_csv).expanduser().resolve()
        strategy_backtest_csv_path = Path(args.strategy_backtest_csv).expanduser().resolve()
        workbook_path = Path(args.xlsx).expanduser().resolve()

        all_records, history_updated = sync_history_cache(args.url, history_cache_path)
        logger.info("loaded %s total history records from local cache", len(all_records))
        phase_one_records = all_records[: args.full_history_draws] if args.full_history_draws else all_records
        logger.info("using %s history records for phase-1 exports", len(phase_one_records))

        pipeline_signature = compute_pipeline_signature(
            phase_one_records,
            base_url=args.url,
            rolling_min_train_draws=args.rolling_min_train_draws,
            rolling_step=args.rolling_step,
            rule_parameters={
                "rule_configs": [{"name": name, **config.as_dict()} for name, config in load_rule_config_entries(args)],
                "candidate_combo_limit": args.candidate_combo_limit,
                "model_retrain_interval": args.model_retrain_interval,
                "model_train_epochs": args.model_train_epochs,
                "strategy_start_bankroll": args.strategy_start_bankroll,
                "strategy_ticket_cost": args.strategy_ticket_cost,
                "strategy_combo_ticket_count": args.strategy_combo_ticket_count,
                "strategy_blue_ticket_count": args.strategy_blue_ticket_count,
            },
        )
        pipeline_state = load_pipeline_state(pipeline_state_path)
        output_paths = [
            sample_csv_path,
            rule_report_csv_path,
            rule_grid_report_csv_path,
            rule_grid_summary_csv_path,
            model_ranking_csv_path,
            model_metrics_csv_path,
            blue_model_ranking_csv_path,
            blue_model_metrics_csv_path,
            candidate_pools_csv_path,
            candidate_combinations_csv_path,
            strategy_backtest_csv_path,
        ]
        pipeline_changed = pipeline_state.get("pipeline_signature") != pipeline_signature
        outputs_ready = _phase_one_outputs_exist(output_paths)
        workbook_signature = compute_workbook_signature(all_records, draw_count=args.draws, base_url=args.url)
        workbook_changed = pipeline_state.get("workbook_signature") != workbook_signature

        if history_updated or pipeline_changed or not outputs_ready:
            if not outputs_ready:
                logger.info("phase-1 outputs missing, rebuilding exports")
            elif pipeline_changed:
                logger.info("phase-1 pipeline inputs changed, rebuilding exports")
            else:
                logger.info("history cache updated, rebuilding phase-1 exports")
            _build_phase_one_outputs(
                phase_one_records,
                args,
                sample_csv_path,
                rule_report_csv_path,
                rule_grid_report_csv_path,
                rule_grid_summary_csv_path,
                model_ranking_csv_path,
                model_metrics_csv_path,
                blue_model_ranking_csv_path,
                blue_model_metrics_csv_path,
                candidate_pools_csv_path,
                candidate_combinations_csv_path,
                strategy_backtest_csv_path,
            )
            save_pipeline_state(
                pipeline_state_path,
                {
                    **pipeline_state,
                    "pipeline_signature": pipeline_signature,
                    "record_count": len(phase_one_records),
                    "latest_serial": phase_one_records[0].serial if phase_one_records else "",
                },
            )
        else:
            logger.info("history cache unchanged; reusing existing phase-1 csv outputs")

        workbook_path.parent.mkdir(parents=True, exist_ok=True)
        if workbook_path.exists() and not workbook_changed:
            logger.info("recent %s draws unchanged; reusing existing workbook %s", args.draws, workbook_path)
        else:
            workbook_stage_start = time.perf_counter()
            logger.info("rebuilding workbook for the latest %s draws", args.draws)
            state = LottoState()
            populate_state_from_records(state, all_records, args.draws)
            set_omit_table(state)

            builder = WorkbookBuilder(deps, state)
            if workbook_path.exists():
                logger.info("loading existing workbook")
                builder.workbook = deps.load_workbook(workbook_path)
                if "原始数据" not in builder.workbook.sheetnames:
                    ws = builder.workbook.create_sheet("原始数据")
                    ws.append(["期号", "开奖日期", "红1", "红2", "红3", "红4", "红5", "红6", "蓝球"])
                    builder.apply_xls_font(ws)
                builder.sync_raw_data()
                if builder.check_complete(builder.workbook["文件信息"]):
                    builder.count_ball()
                else:
                    while state.start_serial != -1:
                        builder.count_ball()
                        state.start_serial -= 1
            else:
                logger.info("creating workbook")
                builder.workbook = builder.create_workbook()
                builder.sync_raw_data()
                state.start_serial = 49
                while state.start_serial != -1:
                    builder.count_ball()
                    state.start_serial -= 1

            builder.add_info(builder.workbook["文件信息"])
            builder.workbook.save(workbook_path)
            logger.info("saved workbook to %s in %.2fs", workbook_path, time.perf_counter() - workbook_stage_start)
            save_pipeline_state(
                pipeline_state_path,
                {
                    **load_pipeline_state(pipeline_state_path),
                    "workbook_signature": workbook_signature,
                },
            )
        return 0
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
