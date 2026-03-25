from __future__ import annotations


def build_rule_grid_rows(config_name: str, rule_rows: list) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for row in rule_rows:
        payload = row.as_dict()
        payload["config_name"] = config_name
        rows.append(payload)
    return rows


def build_rule_grid_summary_rows(rule_grid_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    ranked_rows = sorted(
        rule_grid_rows,
        key=lambda row: (
            float(row.get("rolling_lift_y1", 0.0)),
            float(row.get("lift_y1_test", 0.0)),
            float(row.get("rolling_lift_y3", 0.0)),
            float(row.get("lift_y3_test", 0.0)),
            -int(row.get("trigger_count_test", 0)),
        ),
        reverse=True,
    )

    summary_rows: list[dict[str, object]] = []
    for rank, row in enumerate(ranked_rows, start=1):
        score = (
            float(row.get("rolling_lift_y1", 0.0)) * 0.5
            + float(row.get("lift_y1_test", 0.0)) * 0.3
            + float(row.get("rolling_lift_y3", 0.0)) * 0.15
            + float(row.get("lift_y3_test", 0.0)) * 0.05
        )
        summary_rows.append(
            {
                "rank": rank,
                "config_name": row.get("config_name", ""),
                "rule_name": row.get("rule_name", ""),
                "description": row.get("description", ""),
                "parameters": row.get("parameters", "{}"),
                "score": round(score, 6),
                "lift_y1_test": row.get("lift_y1_test", 0.0),
                "rolling_lift_y1": row.get("rolling_lift_y1", 0.0),
                "lift_y3_test": row.get("lift_y3_test", 0.0),
                "rolling_lift_y3": row.get("rolling_lift_y3", 0.0),
                "trigger_count_test": row.get("trigger_count_test", 0),
                "rolling_trigger_count": row.get("rolling_trigger_count", 0),
            }
        )
    return summary_rows
