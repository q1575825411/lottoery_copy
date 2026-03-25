from __future__ import annotations

from functools import lru_cache
from itertools import combinations
from math import comb

from .constants import BLUE_BALL_MAX, RED_BALL_COUNT, RED_BALL_MAX
from .models import ModelPredictionRow


def _group_prediction_rows(rows: list[ModelPredictionRow]) -> dict[str, list[ModelPredictionRow]]:
    grouped: dict[str, list[ModelPredictionRow]] = {}
    for row in rows:
        grouped.setdefault(row.serial, []).append(row)
    return grouped


def _hypergeometric_at_least(population_size: int, hit_population: int, sample_size: int, min_hits: int) -> float:
    if min_hits <= 0:
        return 1.0
    max_hits = min(hit_population, sample_size)
    denominator = comb(population_size, sample_size)
    probability = 0.0
    for hit_count in range(min_hits, max_hits + 1):
        probability += (
            comb(hit_population, hit_count)
            * comb(population_size - hit_population, sample_size - hit_count)
            / float(denominator)
        )
    return probability


def _random_ticket_bundle_success_rate(population_size: int, hit_population: int, sample_size: int, min_hits: int, ticket_count: int) -> float:
    if ticket_count <= 0:
        return 0.0
    single_ticket_rate = _hypergeometric_at_least(population_size, hit_population, sample_size, min_hits)
    return 1.0 - (1.0 - single_ticket_rate) ** ticket_count


def _ticket_prize(red_hits: int, blue_hit: bool) -> float:
    if red_hits == 6 and blue_hit:
        return 5000000.0
    if red_hits == 6:
        return 100000.0
    if red_hits == 5 and blue_hit:
        return 3000.0
    if red_hits == 5 or (red_hits == 4 and blue_hit):
        return 200.0
    if red_hits == 4 or (red_hits == 3 and blue_hit):
        return 10.0
    if blue_hit and red_hits in (0, 1, 2):
        return 5.0
    return 0.0


@lru_cache(maxsize=1)
def _single_ticket_prize_distribution() -> dict[float, float]:
    red_denominator = comb(RED_BALL_MAX, RED_BALL_COUNT)
    distribution: dict[float, float] = {}
    for red_hits in range(RED_BALL_COUNT + 1):
        red_probability = (
            comb(RED_BALL_COUNT, red_hits)
            * comb(RED_BALL_MAX - RED_BALL_COUNT, RED_BALL_COUNT - red_hits)
            / float(red_denominator)
        )
        for blue_hit in (False, True):
            blue_probability = (1.0 / BLUE_BALL_MAX) if blue_hit else ((BLUE_BALL_MAX - 1) / float(BLUE_BALL_MAX))
            prize = _ticket_prize(red_hits, blue_hit)
            distribution[prize] = distribution.get(prize, 0.0) + (red_probability * blue_probability)
    return distribution


def _random_bundle_profit_success_rate(ticket_count: int, ticket_cost: float) -> float:
    if ticket_count <= 0:
        return 0.0

    payout_distribution = {0.0: 1.0}
    single_ticket_distribution = _single_ticket_prize_distribution()
    for _ in range(ticket_count):
        next_distribution: dict[float, float] = {}
        for total_payout, total_probability in payout_distribution.items():
            for prize, prize_probability in single_ticket_distribution.items():
                merged_payout = round(total_payout + prize, 6)
                next_distribution[merged_payout] = next_distribution.get(merged_payout, 0.0) + (total_probability * prize_probability)
        payout_distribution = next_distribution

    required_profit_payout = ticket_count * ticket_cost
    return sum(probability for payout, probability in payout_distribution.items() if payout > required_profit_payout)


def _build_candidate_combination_rows_for_draw(
    red_rows: list[ModelPredictionRow],
    blue_rows: list[ModelPredictionRow],
    *,
    limit: int,
) -> list[dict[str, object]]:
    if not red_rows or not blue_rows or limit <= 0:
        return []

    latest_red = sorted(red_rows, key=lambda row: row.rank_y1)
    latest_blue = sorted(blue_rows, key=lambda row: row.rank_y1)
    latest_serial = latest_red[0].serial
    latest_draw_date = latest_red[0].draw_date
    red_dan_pool = {row.ball for row in latest_red[:3]}
    red_candidates = latest_red[:10]
    blue_candidate_pool = ",".join(f"{row.ball:02d}" for row in latest_blue[:3])

    ranked_combos: list[tuple[float, tuple[ModelPredictionRow, ...]]] = []
    for combo in combinations(red_candidates, RED_BALL_COUNT):
        balls = sorted(row.ball for row in combo)
        score = sum(row.probability_y1 for row in combo)
        dan_hits = sum(1 for ball in balls if ball in red_dan_pool)
        odd_count = sum(1 for ball in balls if ball % 2 == 1)
        small_count = sum(1 for ball in balls if ball <= 16)
        zone_counts = (
            sum(1 for ball in balls if 1 <= ball <= 11),
            sum(1 for ball in balls if 12 <= ball <= 22),
            sum(1 for ball in balls if 23 <= ball <= 33),
        )
        total_sum = sum(balls)

        if dan_hits < 2:
            continue
        if not 2 <= odd_count <= 4:
            continue
        if not 3 <= small_count <= 5:
            continue
        if sum(1 for count in zone_counts if count > 0) < 2:
            continue
        if not 70 <= total_sum <= 150:
            continue

        ranked_combos.append((score, combo))

    ranked_combos.sort(key=lambda item: item[0], reverse=True)
    rows: list[dict[str, object]] = []
    for rank, (score, combo) in enumerate(ranked_combos[:limit], start=1):
        balls = sorted(row.ball for row in combo)
        odd_count = sum(1 for ball in balls if ball % 2 == 1)
        even_count = RED_BALL_COUNT - odd_count
        small_count = sum(1 for ball in balls if ball <= 16)
        big_count = RED_BALL_COUNT - small_count
        zone_counts = (
            sum(1 for ball in balls if 1 <= ball <= 11),
            sum(1 for ball in balls if 12 <= ball <= 22),
            sum(1 for ball in balls if 23 <= ball <= 33),
        )
        rows.append(
            {
                "serial": latest_serial,
                "draw_date": latest_draw_date,
                "combo_rank": rank,
                "red_balls": ",".join(f"{ball:02d}" for ball in balls),
                "red_score": round(score, 6),
                "dan_hit_count": sum(1 for ball in balls if ball in red_dan_pool),
                "odd_even_ratio": f"{odd_count}:{even_count}",
                "small_big_ratio": f"{small_count}:{big_count}",
                "zone_ratio": f"{zone_counts[0]}:{zone_counts[1]}:{zone_counts[2]}",
                "sum_value": sum(balls),
                "suggested_blue_pool": blue_candidate_pool,
            }
        )
    return rows


def build_candidate_pool_rows(
    red_ranking_rows: list[ModelPredictionRow],
    blue_ranking_rows: list[ModelPredictionRow],
) -> list[dict[str, object]]:
    if not red_ranking_rows or not blue_ranking_rows:
        return []

    latest_red = sorted(red_ranking_rows, key=lambda row: row.rank_y1)
    latest_blue = sorted(blue_ranking_rows, key=lambda row: row.rank_y1)
    latest_serial = latest_red[0].serial
    latest_draw_date = latest_red[0].draw_date

    red_dan_pool = latest_red[:3]
    red_candidate_pool = latest_red[:10]
    red_kill_pool = sorted(latest_red[-8:], key=lambda row: row.ball)
    blue_dan_pool = latest_blue[:1]
    blue_candidate_pool = latest_blue[:3]
    blue_kill_pool = sorted(latest_blue[-5:], key=lambda row: row.ball)

    return [
        {
            "serial": latest_serial,
            "draw_date": latest_draw_date,
            "red_dan_pool": ",".join(f"{row.ball:02d}" for row in red_dan_pool),
            "red_candidate_pool": ",".join(f"{row.ball:02d}" for row in red_candidate_pool),
            "red_kill_pool": ",".join(f"{row.ball:02d}" for row in red_kill_pool),
            "blue_dan_pool": ",".join(f"{row.ball:02d}" for row in blue_dan_pool),
            "blue_candidate_pool": ",".join(f"{row.ball:02d}" for row in blue_candidate_pool),
            "blue_kill_pool": ",".join(f"{row.ball:02d}" for row in blue_kill_pool),
        }
    ]


def build_candidate_combination_rows(
    red_ranking_rows: list[ModelPredictionRow],
    blue_ranking_rows: list[ModelPredictionRow],
    *,
    limit: int = 20,
) -> list[dict[str, object]]:
    if not red_ranking_rows or not blue_ranking_rows or limit <= 0:
        return []
    return _build_candidate_combination_rows_for_draw(red_ranking_rows, blue_ranking_rows, limit=limit)


def build_strategy_backtest_rows(
    red_backtest_rows: list[ModelPredictionRow],
    blue_backtest_rows: list[ModelPredictionRow],
    *,
    candidate_combo_limit: int = 20,
    start_bankroll: float = 1000.0,
    ticket_cost: float = 2.0,
    combo_ticket_count: int = 5,
    blue_ticket_count: int = 3,
) -> list[dict[str, object]]:
    if not red_backtest_rows or not blue_backtest_rows:
        return []

    grouped_red = _group_prediction_rows(red_backtest_rows)
    grouped_blue = _group_prediction_rows(blue_backtest_rows)
    common_serials = sorted(
        set(grouped_red).intersection(grouped_blue),
        key=lambda serial: min(row.draw_index for row in grouped_red[serial]),
    )
    if not common_serials:
        return []

    per_draw_rows: list[dict[str, object]] = []
    red_dan_success_rate = _hypergeometric_at_least(RED_BALL_MAX, RED_BALL_COUNT, 3, 1)
    red_candidate_success_rate = _hypergeometric_at_least(RED_BALL_MAX, RED_BALL_COUNT, 10, 4)
    red_kill_success_rate = 1.0 - _hypergeometric_at_least(RED_BALL_MAX, RED_BALL_COUNT, 8, 1)
    blue_candidate_success_rate = _hypergeometric_at_least(BLUE_BALL_MAX, 1, 3, 1)
    random_red_ticket_hits = (RED_BALL_COUNT * RED_BALL_COUNT) / float(RED_BALL_MAX)
    bankroll = start_bankroll

    for serial in common_serials:
        red_rows = sorted(grouped_red[serial], key=lambda row: row.rank_y1)
        blue_rows = sorted(grouped_blue[serial], key=lambda row: row.rank_y1)
        draw_date = red_rows[0].draw_date
        actual_red_hits = {row.ball for row in red_rows if row.y_1 == 1}
        actual_blue_hits = {row.ball for row in blue_rows if row.y_1 == 1}
        red_dan_pool = {row.ball for row in red_rows[:3]}
        red_candidate_pool = {row.ball for row in red_rows[:10]}
        red_kill_pool = {row.ball for row in red_rows[-8:]}
        blue_candidate_pool = {row.ball for row in blue_rows[:3]}
        candidate_combos = _build_candidate_combination_rows_for_draw(red_rows, blue_rows, limit=candidate_combo_limit)
        combo_hit_counts = [
            len(actual_red_hits.intersection({int(ball) for ball in combo_row["red_balls"].split(",")}))
            for combo_row in candidate_combos
        ]
        combo_count = len(combo_hit_counts)
        best_combo_hits = max(combo_hit_counts) if combo_hit_counts else 0
        avg_combo_hits = (sum(combo_hit_counts) / float(combo_count)) if combo_count else 0.0
        purchased_combo_rows = candidate_combos[:combo_ticket_count]
        purchased_blue_rows = blue_rows[:blue_ticket_count]
        purchased_ticket_count = len(purchased_combo_rows) * len(purchased_blue_rows)
        stake_amount = purchased_ticket_count * ticket_cost
        fixed_ticket_random_success_rate = _random_bundle_profit_success_rate(purchased_ticket_count, ticket_cost)
        payout_amount = 0.0
        for combo_row in purchased_combo_rows:
            combo_red_balls = {int(ball) for ball in str(combo_row["red_balls"]).split(",")}
            combo_red_hits = len(actual_red_hits.intersection(combo_red_balls))
            for blue_row in purchased_blue_rows:
                payout_amount += _ticket_prize(combo_red_hits, blue_row.ball in actual_blue_hits)
        net_profit = payout_amount - stake_amount
        bankroll += net_profit

        per_draw_rows.extend(
            [
                {
                    "scope": "per_draw",
                    "strategy_name": "red_dan_pool",
                    "strategy_goal": "maximize_hits",
                    "target": "red",
                    "serial": serial,
                    "draw_date": draw_date,
                    "candidate_size": 3,
                    "combo_count": 0,
                    "actual_hits": len(actual_red_hits.intersection(red_dan_pool)),
                    "baseline_hits_random": round((3 * RED_BALL_COUNT) / float(RED_BALL_MAX), 6),
                    "hit_edge_vs_random": round(len(actual_red_hits.intersection(red_dan_pool)) - ((3 * RED_BALL_COUNT) / float(RED_BALL_MAX)), 6),
                    "success_flag": int(bool(actual_red_hits.intersection(red_dan_pool))),
                    "baseline_success_rate_random": round(red_dan_success_rate, 6),
                    "success_edge_vs_random": round(int(bool(actual_red_hits.intersection(red_dan_pool))) - red_dan_success_rate, 6),
                    "best_hits": "",
                    "avg_combo_hits": "",
                    "ticket_count": 0,
                    "stake_amount": 0.0,
                    "payout_amount": 0.0,
                    "net_profit": 0.0,
                    "bankroll_after": "",
                },
                {
                    "scope": "per_draw",
                    "strategy_name": "red_candidate_pool",
                    "strategy_goal": "maximize_hits",
                    "target": "red",
                    "serial": serial,
                    "draw_date": draw_date,
                    "candidate_size": 10,
                    "combo_count": 0,
                    "actual_hits": len(actual_red_hits.intersection(red_candidate_pool)),
                    "baseline_hits_random": round((10 * RED_BALL_COUNT) / float(RED_BALL_MAX), 6),
                    "hit_edge_vs_random": round(len(actual_red_hits.intersection(red_candidate_pool)) - ((10 * RED_BALL_COUNT) / float(RED_BALL_MAX)), 6),
                    "success_flag": int(len(actual_red_hits.intersection(red_candidate_pool)) >= 4),
                    "baseline_success_rate_random": round(red_candidate_success_rate, 6),
                    "success_edge_vs_random": round(int(len(actual_red_hits.intersection(red_candidate_pool)) >= 4) - red_candidate_success_rate, 6),
                    "best_hits": "",
                    "avg_combo_hits": "",
                    "ticket_count": 0,
                    "stake_amount": 0.0,
                    "payout_amount": 0.0,
                    "net_profit": 0.0,
                    "bankroll_after": "",
                },
                {
                    "scope": "per_draw",
                    "strategy_name": "red_kill_pool",
                    "strategy_goal": "minimize_hits",
                    "target": "red",
                    "serial": serial,
                    "draw_date": draw_date,
                    "candidate_size": 8,
                    "combo_count": 0,
                    "actual_hits": len(actual_red_hits.intersection(red_kill_pool)),
                    "baseline_hits_random": round((8 * RED_BALL_COUNT) / float(RED_BALL_MAX), 6),
                    "hit_edge_vs_random": round(((8 * RED_BALL_COUNT) / float(RED_BALL_MAX)) - len(actual_red_hits.intersection(red_kill_pool)), 6),
                    "success_flag": int(not actual_red_hits.intersection(red_kill_pool)),
                    "baseline_success_rate_random": round(red_kill_success_rate, 6),
                    "success_edge_vs_random": round(int(not actual_red_hits.intersection(red_kill_pool)) - red_kill_success_rate, 6),
                    "best_hits": "",
                    "avg_combo_hits": "",
                    "ticket_count": 0,
                    "stake_amount": 0.0,
                    "payout_amount": 0.0,
                    "net_profit": 0.0,
                    "bankroll_after": "",
                },
                {
                    "scope": "per_draw",
                    "strategy_name": "blue_candidate_pool",
                    "strategy_goal": "maximize_hits",
                    "target": "blue",
                    "serial": serial,
                    "draw_date": draw_date,
                    "candidate_size": 3,
                    "combo_count": 0,
                    "actual_hits": len(actual_blue_hits.intersection(blue_candidate_pool)),
                    "baseline_hits_random": round(3 / float(BLUE_BALL_MAX), 6),
                    "hit_edge_vs_random": round(len(actual_blue_hits.intersection(blue_candidate_pool)) - (3 / float(BLUE_BALL_MAX)), 6),
                    "success_flag": int(bool(actual_blue_hits.intersection(blue_candidate_pool))),
                    "baseline_success_rate_random": round(blue_candidate_success_rate, 6),
                    "success_edge_vs_random": round(int(bool(actual_blue_hits.intersection(blue_candidate_pool))) - blue_candidate_success_rate, 6),
                    "best_hits": "",
                    "avg_combo_hits": "",
                    "ticket_count": 0,
                    "stake_amount": 0.0,
                    "payout_amount": 0.0,
                    "net_profit": 0.0,
                    "bankroll_after": "",
                },
                {
                    "scope": "per_draw",
                    "strategy_name": "red_combo_cover_4plus",
                    "strategy_goal": "maximize_success",
                    "target": "red_combo",
                    "serial": serial,
                    "draw_date": draw_date,
                    "candidate_size": 10,
                    "combo_count": combo_count,
                    "actual_hits": round(avg_combo_hits, 6),
                    "baseline_hits_random": round(random_red_ticket_hits, 6),
                    "hit_edge_vs_random": round(avg_combo_hits - random_red_ticket_hits, 6),
                    "success_flag": int(best_combo_hits >= 4),
                    "baseline_success_rate_random": round(_random_ticket_bundle_success_rate(RED_BALL_MAX, RED_BALL_COUNT, RED_BALL_COUNT, 4, combo_count), 6),
                    "success_edge_vs_random": round(int(best_combo_hits >= 4) - _random_ticket_bundle_success_rate(RED_BALL_MAX, RED_BALL_COUNT, RED_BALL_COUNT, 4, combo_count), 6),
                    "best_hits": best_combo_hits,
                    "avg_combo_hits": round(avg_combo_hits, 6),
                    "ticket_count": 0,
                    "stake_amount": 0.0,
                    "payout_amount": 0.0,
                    "net_profit": 0.0,
                    "bankroll_after": "",
                },
                {
                    "scope": "per_draw",
                    "strategy_name": "red_combo_full_cover",
                    "strategy_goal": "maximize_success",
                    "target": "red_combo",
                    "serial": serial,
                    "draw_date": draw_date,
                    "candidate_size": 10,
                    "combo_count": combo_count,
                    "actual_hits": round(avg_combo_hits, 6),
                    "baseline_hits_random": round(random_red_ticket_hits, 6),
                    "hit_edge_vs_random": round(avg_combo_hits - random_red_ticket_hits, 6),
                    "success_flag": int(best_combo_hits == RED_BALL_COUNT),
                    "baseline_success_rate_random": round(_random_ticket_bundle_success_rate(RED_BALL_MAX, RED_BALL_COUNT, RED_BALL_COUNT, RED_BALL_COUNT, combo_count), 6),
                    "success_edge_vs_random": round(int(best_combo_hits == RED_BALL_COUNT) - _random_ticket_bundle_success_rate(RED_BALL_MAX, RED_BALL_COUNT, RED_BALL_COUNT, RED_BALL_COUNT, combo_count), 6),
                    "best_hits": best_combo_hits,
                    "avg_combo_hits": round(avg_combo_hits, 6),
                    "ticket_count": 0,
                    "stake_amount": 0.0,
                    "payout_amount": 0.0,
                    "net_profit": 0.0,
                    "bankroll_after": "",
                },
                {
                    "scope": "per_draw",
                    "strategy_name": "fixed_ticket_bundle",
                    "strategy_goal": "maximize_profit",
                    "target": "red_blue_combo",
                    "serial": serial,
                    "draw_date": draw_date,
                    "candidate_size": 10,
                    "combo_count": len(purchased_combo_rows),
                    "actual_hits": round(avg_combo_hits, 6),
                    "baseline_hits_random": round(random_red_ticket_hits, 6),
                    "hit_edge_vs_random": round(avg_combo_hits - random_red_ticket_hits, 6),
                    "success_flag": int(payout_amount > stake_amount),
                    "baseline_success_rate_random": round(fixed_ticket_random_success_rate, 6),
                    "success_edge_vs_random": round(int(payout_amount > stake_amount) - fixed_ticket_random_success_rate, 6),
                    "best_hits": best_combo_hits,
                    "avg_combo_hits": round(avg_combo_hits, 6),
                    "ticket_count": purchased_ticket_count,
                    "stake_amount": round(stake_amount, 6),
                    "payout_amount": round(payout_amount, 6),
                    "net_profit": round(net_profit, 6),
                    "bankroll_after": round(bankroll, 6),
                },
            ]
        )

    summary_rows: list[dict[str, object]] = []
    grouped_by_strategy: dict[str, list[dict[str, object]]] = {}
    for row in per_draw_rows:
        grouped_by_strategy.setdefault(str(row["strategy_name"]), []).append(row)

    for strategy_name, rows in grouped_by_strategy.items():
        summary_rows.append(
            {
                "scope": "summary",
                "strategy_name": strategy_name,
                "strategy_goal": rows[0]["strategy_goal"],
                "target": rows[0]["target"],
                "serial": "SUMMARY",
                "draw_date": "",
                "candidate_size": rows[0]["candidate_size"],
                "combo_count": round(sum(int(row["combo_count"]) for row in rows) / float(len(rows)), 6),
                "actual_hits": round(sum(float(row["actual_hits"]) for row in rows) / float(len(rows)), 6),
                "baseline_hits_random": round(sum(float(row["baseline_hits_random"]) for row in rows) / float(len(rows)), 6),
                "hit_edge_vs_random": round(sum(float(row["hit_edge_vs_random"]) for row in rows) / float(len(rows)), 6),
                "success_flag": round(sum(int(row["success_flag"]) for row in rows) / float(len(rows)), 6),
                "baseline_success_rate_random": round(sum(float(row["baseline_success_rate_random"]) for row in rows) / float(len(rows)), 6),
                "success_edge_vs_random": round(sum(float(row["success_edge_vs_random"]) for row in rows) / float(len(rows)), 6),
                "best_hits": round(sum(int(row["best_hits"] or 0) for row in rows) / float(len(rows)), 6),
                "avg_combo_hits": round(sum(float(row["avg_combo_hits"] or 0.0) for row in rows) / float(len(rows)), 6),
                "ticket_count": round(sum(int(row["ticket_count"]) for row in rows) / float(len(rows)), 6),
                "stake_amount": round(sum(float(row["stake_amount"]) for row in rows), 6),
                "payout_amount": round(sum(float(row["payout_amount"]) for row in rows), 6),
                "net_profit": round(sum(float(row["net_profit"]) for row in rows), 6),
                "bankroll_after": round(float(rows[-1]["bankroll_after"]) if rows[-1]["bankroll_after"] != "" else 0.0, 6),
            }
        )

    return per_draw_rows + summary_rows
