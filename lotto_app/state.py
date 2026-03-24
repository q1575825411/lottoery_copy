from __future__ import annotations

from dataclasses import dataclass, field

from .constants import BUFFER_DRAWS, RED_BALL_COUNT, RED_BALL_MAX


def _red_ball_buffer():
    return [[0 for _ in range(RED_BALL_COUNT)] for _ in range(BUFFER_DRAWS)]


def _blue_ball_buffer():
    return [0 for _ in range(BUFFER_DRAWS)]


def _omit_buffer():
    return [[-1 for _ in range(RED_BALL_MAX + 1)] for _ in range(BUFFER_DRAWS)]


@dataclass
class LottoState:
    red_balls: list[list[int]] = field(default_factory=_red_ball_buffer)
    blue_balls: list[int] = field(default_factory=_blue_ball_buffer)
    omit_table: list[list[int]] = field(default_factory=_omit_buffer)
    serials: list[str] = field(default_factory=list)
    draw_dates: list[str] = field(default_factory=list)
    start_serial: int = 0

    def reset(self) -> None:
        self.serials.clear()
        self.draw_dates.clear()
        self.start_serial = 0

        for row in range(BUFFER_DRAWS):
            self.blue_balls[row] = 0
            for col in range(RED_BALL_COUNT):
                self.red_balls[row][col] = 0
            for col in range(RED_BALL_MAX + 1):
                self.omit_table[row][col] = -1
