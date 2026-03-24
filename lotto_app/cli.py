from __future__ import annotations

import argparse
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
from .constants import DEFAULT_HISTORY_URL, MAX_DRAWS
from .deps import ensure_excel_dependencies
from .excel import WorkbookBuilder
from .features import FeatureRow, build_feature_rows
from .fetcher import DrawRecord, populate_state_from_records
from .models import ModelMetricRow, ModelPredictionRow, train_and_rank
from .report import export_feature_rows, export_model_metrics, export_model_predictions, export_rule_report
from .rules import default_rules
from .state import LottoState

logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="Fetch and analyze 双色球 results.")
    parser.add_argument("--xlsx", default=str(Path(__file__).resolve().parents[1] / "data" / "data.xlsx"), help="Path to the output workbook.")
    parser.add_argument("--draws", type=int, default=MAX_DRAWS, help="How many recent draws to fetch. Default: %(default)s")
    parser.add_argument("--full-history-draws", type=int, default=0, help="How many draws to use for feature/backtest exports. Default: 0 means all available history.")
    parser.add_argument("--url", default=DEFAULT_HISTORY_URL, help="Base URL template for the draw history source. Use {page} as the page placeholder.")
    parser.add_argument("--sample-csv", default=str(Path(__file__).resolve().parents[1] / "data" / "sample_features.csv"), help="Path to the exported sample feature table.")
    parser.add_argument("--rule-report-csv", default=str(Path(__file__).resolve().parents[1] / "data" / "rule_effectiveness.csv"), help="Path to the exported rule effectiveness report.")
    parser.add_argument("--model-ranking-csv", default=str(Path(__file__).resolve().parents[1] / "data" / "model_ranking.csv"), help="Path to the exported latest-draw model ranking table.")
    parser.add_argument("--model-metrics-csv", default=str(Path(__file__).resolve().parents[1] / "data" / "model_metrics.csv"), help="Path to the exported model evaluation metrics.")
    parser.add_argument("--rolling-min-train-draws", type=int, default=100, help="Minimum history size before rolling evaluation starts. Default: %(default)s")
    parser.add_argument("--rolling-step", type=int, default=1, help="Rolling evaluation step size in draws. Default: %(default)s")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Logging level. Default: %(default)s")
    args = parser.parse_args()
    if args.draws < MAX_DRAWS:
        parser.error("--draws must be at least %d because the analysis logic depends on 100 draws." % MAX_DRAWS)
    return args


def configure_logging(level: str) -> None:
    logging.basicConfig(level=getattr(logging, level), format="%(levelname)s %(name)s: %(message)s")


def _phase_one_outputs_exist(paths: list[Path]) -> bool:
    return all(path.exists() for path in paths)


def _build_phase_one_outputs(
    records: list[DrawRecord],
    args,
    sample_csv_path: Path,
    rule_report_csv_path: Path,
    model_ranking_csv_path: Path,
    model_metrics_csv_path: Path,
) -> tuple[list[FeatureRow], list, list[ModelPredictionRow], list[ModelMetricRow]]:
    stage_start = time.perf_counter()
    logger.info("building feature rows for %s draws", len(records))
    feature_rows = build_feature_rows(records)
    logger.info("built %s feature rows in %.2fs", len(feature_rows), time.perf_counter() - stage_start)

    stage_start = time.perf_counter()
    logger.info("evaluating %s rules with rolling_min_train_draws=%s rolling_step=%s", len(default_rules()), args.rolling_min_train_draws, args.rolling_step)
    rule_rows = evaluate_rules(
        feature_rows,
        default_rules(),
        rolling_min_train_draws=args.rolling_min_train_draws,
        rolling_step=args.rolling_step,
    )
    logger.info("completed rule evaluation in %.2fs", time.perf_counter() - stage_start)

    stage_start = time.perf_counter()
    logger.info("training ranking model")
    model_ranking_rows, model_metric_rows = train_and_rank(feature_rows)
    logger.info("completed model training and ranking in %.2fs", time.perf_counter() - stage_start)

    stage_start = time.perf_counter()
    logger.info("writing phase-1 csv outputs")
    export_feature_rows(sample_csv_path, feature_rows)
    export_rule_report(rule_report_csv_path, rule_rows)
    export_model_predictions(model_ranking_csv_path, model_ranking_rows)
    export_model_metrics(model_metrics_csv_path, model_metric_rows)
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
        model_ranking_csv_path = Path(args.model_ranking_csv).expanduser().resolve()
        model_metrics_csv_path = Path(args.model_metrics_csv).expanduser().resolve()
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
        )
        pipeline_state = load_pipeline_state(pipeline_state_path)
        output_paths = [sample_csv_path, rule_report_csv_path, model_ranking_csv_path, model_metrics_csv_path]
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
                model_ranking_csv_path,
                model_metrics_csv_path,
            )
            save_pipeline_state(
                pipeline_state_path,
                {
                    "pipeline_signature": pipeline_signature,
                    "record_count": len(phase_one_records),
                    "latest_serial": phase_one_records[0].serial if phase_one_records else "",
                    "workbook_signature": workbook_signature,
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
