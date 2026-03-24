from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .analysis import set_omit_table
from .backtest import evaluate_rules
from .constants import DEFAULT_HISTORY_URL, MAX_DRAWS
from .deps import ensure_excel_dependencies
from .excel import WorkbookBuilder
from .features import build_feature_rows
from .fetcher import load_history_records, populate_state_from_records
from .models import train_and_rank
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


def main() -> int:
    try:
        args = parse_args()
        configure_logging(args.log_level)
        deps = ensure_excel_dependencies()
        all_records = load_history_records(args.url, args.full_history_draws or None)
        logger.info("loaded %s total history records for phase-1 exports", len(all_records))
        feature_rows = build_feature_rows(all_records)
        rule_rows = evaluate_rules(
            feature_rows,
            default_rules(),
            rolling_min_train_draws=args.rolling_min_train_draws,
            rolling_step=args.rolling_step,
        )
        model_ranking_rows, model_metric_rows = train_and_rank(feature_rows)
        export_feature_rows(Path(args.sample_csv).expanduser().resolve(), feature_rows)
        export_rule_report(Path(args.rule_report_csv).expanduser().resolve(), rule_rows)
        export_model_predictions(Path(args.model_ranking_csv).expanduser().resolve(), model_ranking_rows)
        export_model_metrics(Path(args.model_metrics_csv).expanduser().resolve(), model_metric_rows)
        logger.info("exported sample features to %s", args.sample_csv)
        logger.info("exported rule report to %s", args.rule_report_csv)
        logger.info("exported model ranking to %s", args.model_ranking_csv)
        logger.info("exported model metrics to %s", args.model_metrics_csv)

        state = LottoState()
        populate_state_from_records(state, all_records, args.draws)
        set_omit_table(state)

        workbook_path = Path(args.xlsx).expanduser().resolve()
        workbook_path.parent.mkdir(parents=True, exist_ok=True)

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
        logger.info("saved workbook to %s", workbook_path)
        return 0
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
