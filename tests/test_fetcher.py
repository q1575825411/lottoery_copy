import unittest
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError

from lotto_app.fetcher import load_history_records, parse_history_rows


SAMPLE_HTML = """
<table class="table table-bordered table-history">
  <tbody>
    <tr>
      <td><a href="/Result/Category/ssq?type=ssq&id=2026031">2026031</a></td>
      <td>2026-03-22(星期日)</td>
      <td><a class="text-primary" href="/Result/Category/ssq?type=ssq&id=2026031">详细</a></td>
      <td>
        <span class="pellet pellet-primary pellet-sm red">03</span>
        <span class="pellet pellet-primary pellet-sm red">10</span>
        <span class="pellet pellet-primary pellet-sm red">12</span>
        <span class="pellet pellet-primary pellet-sm red">13</span>
        <span class="pellet pellet-primary pellet-sm red">18</span>
        <span class="pellet pellet-primary pellet-sm red">33</span>
        <span class="pellet pellet-default pellet-sm blue">08</span>
      </td>
      <td>23.09亿</td>
    </tr>
  </tbody>
</table>
"""


class ParseHistoryRowsTests(unittest.TestCase):
    def test_parse_history_rows_extracts_draw_fields(self):
        rows = parse_history_rows(SAMPLE_HTML)

        self.assertEqual(1, len(rows))
        self.assertEqual("2026031", rows[0]["serial"])
        self.assertEqual("2026-03-22(星期日)", rows[0]["date"])
        self.assertEqual([3, 10, 12, 13, 18, 33], rows[0]["red"])
        self.assertEqual(8, rows[0]["blue"])

    def test_parse_history_rows_raises_when_table_missing(self):
        with self.assertRaises(RuntimeError):
            parse_history_rows("<html><body>missing</body></html>")

    def test_load_history_records_stops_on_404_after_data(self):
        responses = {
            "https://example.test/history?page=1": SAMPLE_HTML,
            "https://example.test/history?page=2": SAMPLE_HTML.replace("2026031", "2026030"),
        }

        def fake_fetch(url: str) -> str:
            if url in responses:
                return responses[url]
            raise HTTPError(url, 404, "Not Found", hdrs=None, fp=BytesIO(b""))

        with patch("lotto_app.fetcher.fetch_text", side_effect=fake_fetch):
            rows = load_history_records("https://example.test/history?page={page}")

        self.assertEqual(2, len(rows))
        self.assertEqual("2026031", rows[0].serial)
        self.assertEqual("2026030", rows[1].serial)


if __name__ == "__main__":
    unittest.main()
