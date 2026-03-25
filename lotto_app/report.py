from __future__ import annotations

import csv
from pathlib import Path

from .backtest import RuleReportRow
from .features import FeatureRow
from .models import ModelMetricRow, ModelPredictionRow


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def export_feature_rows(path: Path, rows: list[FeatureRow]) -> None:
    _write_csv(path, [row.as_dict() for row in rows])


def export_rule_report(path: Path, rows: list[RuleReportRow]) -> None:
    _write_csv(path, [row.as_dict() for row in rows])


def export_model_predictions(path: Path, rows: list[ModelPredictionRow]) -> None:
    _write_csv(path, [row.as_dict() for row in rows])


def export_model_metrics(path: Path, rows: list[ModelMetricRow]) -> None:
    _write_csv(path, [row.as_dict() for row in rows])


def export_rows(path: Path, rows: list[dict[str, object]]) -> None:
    _write_csv(path, rows)
