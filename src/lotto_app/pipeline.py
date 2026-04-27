from __future__ import annotations

import json
import logging
import time
from itertools import product
from pathlib import Path

from .backtest import evaluate_rules
from .cache import (
    compute_pipeline_signature,
    load_pipeline_state,
    save_pipeline_state,
)
from .constants import SUPPORTED_RECENT_WINDOWS
from .features import FeatureRow, build_blue_feature_rows, build_feature_rows
from .fetcher import DrawRecord
from .models import ModelMetricRow, ModelPredictionRow, train_rank_and_backtest
from .report import export_feature_rows, export_model_metrics, export_model_predictions, export_rule_report, export_rows
from .rule_grid import build_rule_grid_rows, build_rule_grid_summary_rows
from .rules import RuleConfig, default_rules
from .strategy import build_candidate_combination_rows, build_candidate_pool_rows, build_strategy_backtest_rows

logger = logging.getLogger(__name__)


def phase_one_outputs_exist(paths: list[Path]) -> bool:
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


def ensure_supported_recent_window(window_size: int) -> int:
    if window_size not in SUPPORTED_RECENT_WINDOWS:
        raise RuntimeError(
            "inactive_recent_window must be one of %s" % ", ".join(str(value) for value in SUPPORTED_RECENT_WINDOWS)
        )
    return window_size


def parse_sweep_values(raw_value: str | None, caster) -> list[object]:
    if not raw_value:
        return []
    values = []
    for part in raw_value.split(","):
        item = part.strip()
        if item:
            values.append(caster(item))
    return values


def build_rule_config_from_dict(payload: dict[str, object], fallback: RuleConfig) -> RuleConfig:
    return RuleConfig(
        omit_threshold=int(payload.get("omit_threshold", fallback.omit_threshold)),
        gap_ratio_threshold=float(payload.get("gap_ratio_threshold", fallback.gap_ratio_threshold)),
        active_recent_min_hits=int(payload.get("active_recent_min_hits", fallback.active_recent_min_hits)),
        inactive_recent_window=ensure_supported_recent_window(int(payload.get("inactive_recent_window", fallback.inactive_recent_window))),
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
            entries.append((name, build_rule_config_from_dict(item, cli_config)))

    sweep_omit_thresholds = parse_sweep_values(args.sweep_omit_thresholds, int)
    sweep_gap_ratio_thresholds = parse_sweep_values(args.sweep_gap_ratio_thresholds, float)
    sweep_heat_score_thresholds = parse_sweep_values(args.sweep_heat_score_thresholds, float)
    sweep_gap_cv_thresholds = parse_sweep_values(args.sweep_gap_cv_thresholds, float)

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


def build_phase_one_outputs(
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
        rule_grid_rows.extend(build_rule_grid_rows(config_name, evaluated_rows))
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


def build_pipeline_signature(records: list[DrawRecord], args) -> str:
    return compute_pipeline_signature(
        records,
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


def persist_pipeline_state(path: Path, pipeline_state: dict[str, object], signature: str, records: list[DrawRecord]) -> None:
    save_pipeline_state(
        path,
        {
            **pipeline_state,
            "pipeline_signature": signature,
            "record_count": len(records),
            "latest_serial": records[0].serial if records else "",
        },
    )


def load_existing_pipeline_state(path: Path) -> dict[str, object]:
    return load_pipeline_state(path)
