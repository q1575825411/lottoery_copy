import unittest

from lotto_app.analysis import count_omit, omit, omit_dict, set_omit_table
from lotto_app.state import LottoState


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.state = LottoState()
        draws = [
            [1, 2, 3, 4, 5, 6],
            [7, 8, 9, 10, 11, 12],
            [1, 13, 14, 15, 16, 17],
            [2, 18, 19, 20, 21, 22],
        ]
        for row, balls in enumerate(draws):
            self.state.red_balls[row][:] = balls
            self.state.serials.append(f"202500{row+1}")
            self.state.draw_dates.append(f"2025-01-0{row+1}")

    def test_omit_returns_gaps_for_current_draw(self):
        result = omit(self.state, 0)
        self.assertEqual([1, 2, -1, -1, -1, -1], result)

    def test_omit_dict_collects_seen_balls(self):
        result = omit_dict(self.state, 0, {})
        self.assertEqual({1: 1, 2: 2}, result)

    def test_count_omit_returns_distance_from_start(self):
        self.assertEqual(1, count_omit(self.state, 1, 1))
        self.assertIsNone(count_omit(self.state, 33, 0))

    def test_set_omit_table_populates_current_row(self):
        set_omit_table(self.state)
        self.assertEqual(0, self.state.omit_table[0][1])
        self.assertEqual(1, self.state.omit_table[0][7])
        self.assertEqual(2, self.state.omit_table[0][13])


if __name__ == "__main__":
    unittest.main()
