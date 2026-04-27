from __future__ import annotations

import logging
import sys
from pathlib import Path

from .cache import compute_workbook_signature, sync_history_cache
from .config import parse_args
from .deps import ensure_excel_dependencies
from .pipeline import (
    build_phase_one_outputs,
    build_pipeline_signature,
    load_existing_pipeline_state,
    persist_pipeline_state,
    phase_one_outputs_exist,
)
from .workbook_service import rebuild_workbook_if_needed

logger = logging.getLogger(__name__)


def configure_logging(level: str) -> None:
    logging.basicConfig(level=getattr(logging, level), format="%(levelname)s %(name)s: %(message)s")


def main() -> int:
    try:
        args = parse_args()
        configure_logging(args.log_level)
        deps = ensure_excel_dependencies()
        data_dir = Path(__file__).resolve().parents[2] / "data"
        history_cache_path = data_dir / "cache" / "history_cache.json"
        pipeline_state_path = data_dir / "cache" / "pipeline_state.json"
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

        pipeline_signature = build_pipeline_signature(phase_one_records, args)
        pipeline_state = load_existing_pipeline_state(pipeline_state_path)
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
        outputs_ready = phase_one_outputs_exist(output_paths)
        workbook_signature = compute_workbook_signature(all_records, draw_count=args.draws, base_url=args.url)
        workbook_changed = pipeline_state.get("workbook_signature") != workbook_signature

        if history_updated or pipeline_changed or not outputs_ready:
            if not outputs_ready:
                logger.info("phase-1 outputs missing, rebuilding exports")
            elif pipeline_changed:
                logger.info("phase-1 pipeline inputs changed, rebuilding exports")
            else:
                logger.info("history cache updated, rebuilding phase-1 exports")
            build_phase_one_outputs(
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
            persist_pipeline_state(pipeline_state_path, pipeline_state, pipeline_signature, phase_one_records)
        else:
            logger.info("history cache unchanged; reusing existing phase-1 csv outputs")

        rebuild_workbook_if_needed(
            deps=deps,
            records=all_records,
            workbook_path=workbook_path,
            workbook_signature=workbook_signature,
            previous_workbook_signature=None if workbook_changed else pipeline_state.get("workbook_signature"),
            draws=args.draws,
            pipeline_state_path=pipeline_state_path,
        )
        return 0
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
