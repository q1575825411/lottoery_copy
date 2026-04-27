from __future__ import annotations

from .constants import RED_BALL_COUNT, RED_BALL_MAX
from .state import LottoState


def draw_limit(state: LottoState) -> int:
    return len(state.serials)


def set_omit_table(state: LottoState) -> None:
    limit = draw_limit(state)
    for ball in range(1, RED_BALL_MAX + 1):
        omit = 0
        for row in range(limit - 1, -1, -1):
            for col in range(RED_BALL_COUNT):
                if state.red_balls[row][col] == ball:
                    omit = 0
            state.omit_table[row][ball] = omit
            omit += 1


def omit(state: LottoState, start: int) -> list[int]:
    limit = draw_limit(state)
    omitted = [-1 for _ in range(RED_BALL_COUNT)]
    for i in range(RED_BALL_COUNT):
        for j in range(start + 1, limit):
            for k in range(RED_BALL_COUNT):
                if state.red_balls[j][k] == state.red_balls[start][i]:
                    omitted[i] = j - start - 1
                    break
            if omitted[i] != -1:
                break
    return omitted


def omit_dict(state: LottoState, start: int, out: dict[int, int]) -> dict[int, int]:
    limit = draw_limit(state)
    found = False
    for i in range(RED_BALL_COUNT):
        for j in range(start + 1, limit):
            for k in range(RED_BALL_COUNT):
                if state.red_balls[j][k] == state.red_balls[start][i]:
                    out[state.red_balls[start][i]] = j - start - 1
                    found = True
                    break
            if found:
                found = False
                break
    return out


def count_omit(state: LottoState, ball: int, start: int) -> int | None:
    limit = draw_limit(state)
    for i in range(start, limit):
        for j in range(RED_BALL_COUNT):
            if state.red_balls[i][j] == ball:
                return i - start
    return None
