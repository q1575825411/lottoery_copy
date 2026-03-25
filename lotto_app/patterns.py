from __future__ import annotations

from dataclasses import dataclass

from .analysis import count_omit, draw_limit, set_omit_table
from .constants import RED_BALL_COUNT, RED_BALL_MAX
from .fetcher import DrawRecord, populate_state_from_records
from .state import LottoState


@dataclass(frozen=True)
class PatternHit:
    name: str
    ball: int
    detail: str


def _config_int(config, name: str, default: int) -> int:
    if config is None:
        return default
    return int(getattr(config, name, default))


def detect_trend_reverse_hits(state: LottoState, start_serial: int, config=None) -> list[PatternHit]:
    pattern = ["" for _ in range(RED_BALL_COUNT)]
    num = 1
    hits: list[PatternHit] = []
    limit = draw_limit(state)
    min_omit = _config_int(config, "trend_reverse_min_omit", 17)
    if start_serial + 5 >= limit:
        return hits

    for i in range(RED_BALL_COUNT):
        for j in range(start_serial + 4, start_serial, -1):
            found = False
            for k in range(RED_BALL_COUNT):
                if state.red_balls[j][k] == state.red_balls[start_serial][i]:
                    pattern[i] += "x"
                    found = True
                    num = 1
                    break
            if not found:
                pattern[i] += str(num)
                num += 1
        pattern[i] += "x"
        num = 1

    for i in range(RED_BALL_COUNT):
        ball = state.red_balls[start_serial][i]
        omitted = count_omit(state, ball, start_serial + 5)
        if omitted is None:
            continue
        if pattern[i] == "123xx" and omitted + 3 >= min_omit:
            hits.append(PatternHit("trend_reverse", ball, ("模式是1..%d " % (omitted + 3)) + pattern[i][3:5]))
        elif pattern[i] == "12x1x" and omitted + 2 >= min_omit:
            hits.append(PatternHit("trend_reverse", ball, ("模式是1..%d " % (omitted + 2)) + pattern[i][2:5]))
        elif pattern[i] == "1x12x" and omitted + 1 >= min_omit:
            hits.append(PatternHit("trend_reverse", ball, ("模式是1..%d " % (omitted + 1)) + pattern[i][1:5]))
        elif pattern[i] == "x123x" and omitted >= min_omit:
            hits.append(PatternHit("trend_reverse", ball, ("模式是1..%d " % omitted) + pattern[i]))
    return hits


def detect_pile_hits(state: LottoState, start_serial: int, config=None) -> list[PatternHit]:
    hits: list[PatternHit] = []
    limit = draw_limit(state)
    long_min = _config_int(config, "pile_long_min", 15)
    mid_min = _config_int(config, "pile_mid_min", 8)
    short_min = _config_int(config, "pile_short_min", 3)
    if start_serial + 1 >= limit:
        return hits

    for num in range(RED_BALL_COUNT):
        ser = start_serial + 1
        ball = state.red_balls[start_serial][num]
        omit_value = state.omit_table[ser][ball]
        omit2 = 0
        omit3 = 0
        pattern: list[str] = []
        if omit_value >= long_min:
            if ser + omit_value + 1 >= limit:
                continue
            omit2 = state.omit_table[ser + omit_value + 1][ball]
            if omit2 == 3:
                pattern.append("x123x 1..%d x" % omit_value)
                ser += 4
                if ser + omit_value + 1 >= limit:
                    continue
                omit2 = state.omit_table[ser + omit_value + 1][ball]
            elif omit2 == 2:
                pattern.append("x12x 1..%d x" % omit_value)
                ser += 3
                if ser + omit_value + 1 >= limit:
                    continue
                omit2 = state.omit_table[ser + omit_value + 1][ball]
            elif omit2 == 1:
                pattern.append("x1x 1..%d x" % omit_value)
                ser += 2
                if ser + omit_value + 1 >= limit:
                    continue
                omit2 = state.omit_table[ser + omit_value + 1][ball]
            elif omit2 == 0:
                pattern.append("xx 1..%d x" % omit_value)
                ser += 1
                if ser + omit_value + 1 >= limit:
                    continue
                omit2 = state.omit_table[ser + omit_value + 1][ball]
                while omit2 == 0:
                    ser += 1
                    if ser + omit_value + 1 >= limit:
                        break
                    omit2 = state.omit_table[ser + omit_value + 1][ball]
                    pattern.append("x")
            else:
                pattern.append("x 1..%d x" % omit_value)

            if mid_min <= omit2 <= long_min and ser + omit_value + omit2 + 2 < limit:
                omit3 = state.omit_table[ser + omit_value + 1 + omit2 + 1][ball]
                if omit3 == 3:
                    ser += 4
                    pattern.append("x123x 1..%d " % omit2)
                    if ser + omit_value + omit2 + 2 >= limit:
                        continue
                    omit3 = state.omit_table[ser + omit_value + 1 + omit2 + 1][ball]
                elif omit3 == 2:
                    ser += 3
                    pattern.append("x12x 1..%d " % omit2)
                    if ser + omit_value + omit2 + 2 >= limit:
                        continue
                    omit3 = state.omit_table[ser + omit_value + 1 + omit2 + 1][ball]
                elif omit3 == 1:
                    ser += 2
                    pattern.append("x1x 1..%d " % omit2)
                    if ser + omit_value + omit2 + 2 >= limit:
                        continue
                    omit3 = state.omit_table[ser + omit_value + 1 + omit2 + 1][ball]
                elif omit3 == 0:
                    ser += 1
                    pattern.append("xx 1..%d " % omit2)
                    if ser + omit_value + omit2 + 2 >= limit:
                        continue
                    omit3 = state.omit_table[ser + omit_value + 1 + omit2 + 1][ball]
                    while omit3 == 0:
                        ser += 1
                        if ser + omit_value + omit2 + 2 >= limit:
                            break
                        omit3 = state.omit_table[ser + omit_value + 1 + omit2 + 1][ball]
                        pattern.append("x")
                else:
                    pattern.append("x 1..%d " % omit2)

                if short_min <= omit3 <= mid_min:
                    pattern.append("x 1..%d " % omit3)
                    pattern.reverse()
                    hits.append(PatternHit("pile", ball, "".join(pattern)))
    return hits


def detect_re_pile_hits(state: LottoState, start_serial: int, config=None) -> list[PatternHit]:
    hits: list[PatternHit] = []
    limit = draw_limit(state)
    long_min = _config_int(config, "pile_long_min", 15)
    mid_min = _config_int(config, "pile_mid_min", 8)
    short_min = _config_int(config, "pile_short_min", 3)
    if start_serial + 1 >= limit:
        return hits

    for num in range(RED_BALL_COUNT):
        ser = start_serial + 1
        ball = state.red_balls[start_serial][num]
        omit_value = state.omit_table[ser][ball]
        omit2 = 0
        omit3 = 0
        pattern: list[str] = []
        if short_min <= omit_value <= mid_min:
            if ser + omit_value + 1 >= limit:
                continue
            omit2 = state.omit_table[ser + omit_value + 1][ball]
            if omit2 == 3:
                pattern.append("x123x 1..%d x" % omit_value)
                ser += 4
                if ser + omit_value + 1 >= limit:
                    continue
                omit2 = state.omit_table[ser + omit_value + 1][ball]
            elif omit2 == 2:
                pattern.append("x12x 1..%d x" % omit_value)
                ser += 3
                if ser + omit_value + 1 >= limit:
                    continue
                omit2 = state.omit_table[ser + omit_value + 1][ball]
            elif omit2 == 1:
                pattern.append("x1x 1..%d x" % omit_value)
                ser += 2
                if ser + omit_value + 1 >= limit:
                    continue
                omit2 = state.omit_table[ser + omit_value + 1][ball]
            elif omit2 == 0:
                pattern.append("xx 1..%d x" % omit_value)
                ser += 1
                if ser + omit_value + 1 >= limit:
                    continue
                omit2 = state.omit_table[ser + omit_value + 1][ball]
                while omit2 == 0:
                    ser += 1
                    if ser + omit_value + 1 >= limit:
                        break
                    omit2 = state.omit_table[ser + omit_value + 1][ball]
                    pattern.append("x")
            else:
                pattern.append("x 1..%d x" % omit_value)

            if mid_min <= omit2 <= long_min and ser + omit_value + omit2 + 2 < limit:
                omit3 = state.omit_table[ser + omit_value + 1 + omit2 + 1][ball]
                if omit3 == 3:
                    ser += 4
                    pattern.append("x123x 1..%d " % omit2)
                    if ser + omit_value + omit2 + 2 >= limit:
                        continue
                    omit3 = state.omit_table[ser + omit_value + 1 + omit2 + 1][ball]
                elif omit3 == 2:
                    ser += 3
                    pattern.append("x12x 1..%d " % omit2)
                    if ser + omit_value + omit2 + 2 >= limit:
                        continue
                    omit3 = state.omit_table[ser + omit_value + 1 + omit2 + 1][ball]
                elif omit3 == 1:
                    ser += 2
                    pattern.append("x1x 1..%d " % omit2)
                    if ser + omit_value + omit2 + 2 >= limit:
                        continue
                    omit3 = state.omit_table[ser + omit_value + 1 + omit2 + 1][ball]
                elif omit3 == 0:
                    ser += 1
                    pattern.append("xx 1..%d " % omit2)
                    if ser + omit_value + omit2 + 2 >= limit:
                        continue
                    omit3 = state.omit_table[ser + omit_value + 1 + omit2 + 1][ball]
                    while omit3 == 0:
                        ser += 1
                        if ser + omit_value + omit2 + 2 >= limit:
                            break
                        omit3 = state.omit_table[ser + omit_value + 1 + omit2 + 1][ball]
                        pattern.append("x")
                else:
                    pattern.append("x 1..%d " % omit2)

                if omit3 >= long_min:
                    pattern.append("x 1..%d " % omit3)
                    pattern.reverse()
                    hits.append(PatternHit("re_pile", ball, "".join(pattern)))
    return hits


def detect_n_bottom_hits(state: LottoState, start_serial: int) -> list[PatternHit]:
    hits: list[PatternHit] = []
    limit = draw_limit(state)
    for ball in range(1, RED_BALL_MAX + 1):
        ser = start_serial
        count = 1
        pattern: list[str] = []
        target_range = -1
        if ser >= limit or state.omit_table[ser][ball] == 0:
            continue

        while True:
            omit_value = state.omit_table[ser][ball]
            i = 0
            while omit_value == 0:
                i += 1
                ser += 1
                if ser >= limit:
                    break
                omit_value = state.omit_table[ser][ball]
            if ser >= limit or ser + omit_value + 1 >= limit:
                break

            omit2 = state.omit_table[ser + omit_value + 1][ball]
            j = 0
            while omit2 == 0:
                j += 1
                ser += 1
                if ser + omit_value + 1 >= limit:
                    break
                omit2 = state.omit_table[ser + omit_value + 1][ball]
            if ser + omit_value + 1 >= limit:
                break

            if target_range == -1:
                target_range = omit_value

            if (omit_value >= 2 and omit2 >= 2) and (omit_value in (target_range, target_range + 1, target_range - 1)) and (omit2 in (target_range, target_range + 1, target_range - 1)):
                if count == 1:
                    for index in range(omit_value, 0, -1):
                        pattern.append(str(index))
                while i != 0:
                    pattern.append("x")
                    i -= 1
                pattern.append("x")
                count += 1
                ser = ser + omit_value + 1
                while j != 0:
                    pattern.append("x")
                    j -= 1
                for k in range(omit2, 0, -1):
                    pattern.append(str(k))
            else:
                if count != 1:
                    pattern.append("x")
                    pattern.reverse()
                    hits.append(PatternHit("n_bottom", ball, "%d倍底：%s" % (count, "".join(pattern))))
                break
    return hits


def detect_flag_range_hits(state: LottoState, start_serial: int, config=None) -> list[PatternHit]:
    hits: list[PatternHit] = []
    limit = draw_limit(state)
    start_min = _config_int(config, "flag_range_start_min", 5)
    start_max = _config_int(config, "flag_range_start_max", 6)
    min_repeat = _config_int(config, "flag_range_min_repeat", 2)
    for ball in range(1, RED_BALL_MAX + 1):
        ser = start_serial
        pattern: list[str] = []
        is_ok = False
        if ser >= limit or state.omit_table[ser][ball] == 0:
            continue
        is_init = True
        count = 0
        while True:
            if ser >= limit:
                break
            omit_value = state.omit_table[ser][ball]
            if is_init and not (start_min <= omit_value <= start_max):
                is_ok = True
                break

            if start_min <= omit_value <= start_max:
                ser = ser + omit_value + 1
                if not is_init:
                    pattern.append("x")
                for j in range(omit_value, 0, -1):
                    pattern.append(str(j))
                if ser > limit - 1:
                    break
                is_init = False
            elif omit_value < 3:
                if omit_value == 2:
                    pattern.append("x12x")
                    ser = ser + omit_value + 1
                elif omit_value == 1:
                    pattern.append("x1x")
                    ser = ser + omit_value + 1
                elif omit_value == 0:
                    pattern.append("x")
                    while omit_value == 0:
                        ser += 1
                        if ser >= limit:
                            break
                        omit_value = state.omit_table[ser][ball]
                        pattern.append("x")
                is_init = True
            else:
                break
            count += 1

        if count >= min_repeat and is_ok:
            pattern.reverse()
            hits.append(PatternHit("flag_range", ball, "".join(pattern)))
    return hits


def detect_all_pattern_hits(state: LottoState, start_serial: int, config=None) -> list[PatternHit]:
    return (
        detect_trend_reverse_hits(state, start_serial, config)
        + detect_pile_hits(state, start_serial, config)
        + detect_re_pile_hits(state, start_serial, config)
        + detect_n_bottom_hits(state, start_serial)
        + detect_flag_range_hits(state, start_serial, config)
    )


def build_pattern_flag_lookup(records: list[DrawRecord], config=None) -> dict[tuple[str, int], dict[str, int]]:
    state = LottoState()
    populate_state_from_records(state, records, len(records))
    set_omit_table(state)

    lookup: dict[tuple[str, int], dict[str, int]] = {}
    for row_index, serial in enumerate(state.serials):
        for hit in detect_all_pattern_hits(state, row_index, config):
            key = (serial, hit.ball)
            flags = lookup.setdefault(
                key,
                {
                    "is_trend_reverse": 0,
                    "is_pile": 0,
                    "is_re_pile": 0,
                    "is_n_bottom": 0,
                    "is_flag_range": 0,
                },
            )
            if hit.name == "trend_reverse":
                flags["is_trend_reverse"] = 1
            elif hit.name == "pile":
                flags["is_pile"] = 1
            elif hit.name == "re_pile":
                flags["is_re_pile"] = 1
            elif hit.name == "n_bottom":
                flags["is_n_bottom"] = 1
            elif hit.name == "flag_range":
                flags["is_flag_range"] = 1
    return lookup
