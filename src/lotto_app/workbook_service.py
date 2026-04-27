from __future__ import annotations

import logging
import time
from pathlib import Path

from .analysis import set_omit_table
from .cache import load_pipeline_state, save_pipeline_state
from .excel import WorkbookBuilder
from .fetcher import DrawRecord, populate_state_from_records
from .state import LottoState

logger = logging.getLogger(__name__)


def rebuild_workbook_if_needed(
    *,
    deps,
    records: list[DrawRecord],
    workbook_path: Path,
    workbook_signature: str,
    previous_workbook_signature: str | None,
    draws: int,
    pipeline_state_path: Path,
) -> None:
    workbook_path.parent.mkdir(parents=True, exist_ok=True)
    if workbook_path.exists() and previous_workbook_signature == workbook_signature:
        logger.info("recent %s draws unchanged; reusing existing workbook %s", draws, workbook_path)
        return

    workbook_stage_start = time.perf_counter()
    logger.info("rebuilding workbook for the latest %s draws", draws)
    state = LottoState()
    populate_state_from_records(state, records, draws)
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
