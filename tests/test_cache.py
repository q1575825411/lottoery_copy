from contextlib import contextmanager
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from lotto_app.cache import (
    compute_pipeline_signature,
    compute_workbook_signature,
    load_history_cache,
    load_pipeline_state,
    save_history_cache,
    save_pipeline_state,
    sync_history_cache,
)
from lotto_app.fetcher import DrawRecord


@contextmanager
def workspace_temp_dir():
    root = Path(__file__).resolve().parents[1] / ".test_tmp"
    path = root / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.records = [
            DrawRecord(serial="2026002", draw_date="2026-03-23", red=[1, 2, 3, 4, 5, 6], blue=7),
            DrawRecord(serial="2026001", draw_date="2026-03-21", red=[8, 9, 10, 11, 12, 13], blue=14),
        ]

    def test_history_cache_round_trip(self):
        with workspace_temp_dir() as temp_dir:
            cache_path = temp_dir / "history_cache.json"

            save_history_cache(cache_path, "https://example.test/history?page={page}", self.records)
            loaded = load_history_cache(cache_path, "https://example.test/history?page={page}")

        self.assertEqual(self.records, loaded)

    def test_sync_history_cache_initializes_from_full_fetch(self):
        with workspace_temp_dir() as temp_dir:
            cache_path = temp_dir / "history_cache.json"
            with patch("lotto_app.cache.load_history_records", return_value=self.records) as load_mock:
                loaded, updated = sync_history_cache("https://example.test/history?page={page}", cache_path)

        self.assertTrue(updated)
        self.assertEqual(self.records, loaded)
        load_mock.assert_called_once_with("https://example.test/history?page={page}")

    def test_sync_history_cache_fetches_only_incremental_rows(self):
        html = """
        <table class="table table-bordered table-history">
          <tbody>
            <tr>
              <td>2026004</td>
              <td>2026-03-27</td>
              <td></td>
              <td>
                <span class="pellet pellet-primary pellet-sm red">01</span>
                <span class="pellet pellet-primary pellet-sm red">02</span>
                <span class="pellet pellet-primary pellet-sm red">03</span>
                <span class="pellet pellet-primary pellet-sm red">04</span>
                <span class="pellet pellet-primary pellet-sm red">05</span>
                <span class="pellet pellet-primary pellet-sm red">06</span>
                <span class="pellet pellet-default pellet-sm blue">07</span>
              </td>
            </tr>
            <tr>
              <td>2026003</td>
              <td>2026-03-25</td>
              <td></td>
              <td>
                <span class="pellet pellet-primary pellet-sm red">08</span>
                <span class="pellet pellet-primary pellet-sm red">09</span>
                <span class="pellet pellet-primary pellet-sm red">10</span>
                <span class="pellet pellet-primary pellet-sm red">11</span>
                <span class="pellet pellet-primary pellet-sm red">12</span>
                <span class="pellet pellet-primary pellet-sm red">13</span>
                <span class="pellet pellet-default pellet-sm blue">14</span>
              </td>
            </tr>
            <tr>
              <td>2026002</td>
              <td>2026-03-23</td>
              <td></td>
              <td>
                <span class="pellet pellet-primary pellet-sm red">01</span>
                <span class="pellet pellet-primary pellet-sm red">02</span>
                <span class="pellet pellet-primary pellet-sm red">03</span>
                <span class="pellet pellet-primary pellet-sm red">04</span>
                <span class="pellet pellet-primary pellet-sm red">05</span>
                <span class="pellet pellet-primary pellet-sm red">06</span>
                <span class="pellet pellet-default pellet-sm blue">07</span>
              </td>
            </tr>
          </tbody>
        </table>
        """
        with workspace_temp_dir() as temp_dir:
            cache_path = temp_dir / "history_cache.json"
            save_history_cache(cache_path, "https://example.test/history?page={page}", self.records)

            with patch("lotto_app.cache.fetch_text", return_value=html):
                loaded, updated = sync_history_cache("https://example.test/history?page={page}", cache_path)

        self.assertTrue(updated)
        self.assertEqual(["2026004", "2026003", "2026002", "2026001"], [record.serial for record in loaded])

    def test_pipeline_state_round_trip(self):
        state = {"pipeline_signature": "abc123", "record_count": 2}
        with workspace_temp_dir() as temp_dir:
            state_path = temp_dir / "pipeline_state.json"

            save_pipeline_state(state_path, state)
            loaded = load_pipeline_state(state_path)

        self.assertEqual(state, loaded)

    def test_pipeline_signature_changes_when_data_changes(self):
        signature_a = compute_pipeline_signature(
            self.records,
            base_url="https://example.test/history?page={page}",
            rolling_min_train_draws=100,
            rolling_step=1,
            rule_parameters={"omit_threshold": 10},
        )
        signature_b = compute_pipeline_signature(
            self.records + [DrawRecord(serial="2026000", draw_date="2026-03-20", red=[1, 3, 5, 7, 9, 11], blue=2)],
            base_url="https://example.test/history?page={page}",
            rolling_min_train_draws=100,
            rolling_step=1,
            rule_parameters={"omit_threshold": 10},
        )

        self.assertNotEqual(signature_a, signature_b)

    def test_pipeline_signature_changes_when_rule_parameters_change(self):
        signature_a = compute_pipeline_signature(
            self.records,
            base_url="https://example.test/history?page={page}",
            rolling_min_train_draws=100,
            rolling_step=1,
            rule_parameters={"omit_threshold": 10, "heat_score_threshold": 0.6},
        )
        signature_b = compute_pipeline_signature(
            self.records,
            base_url="https://example.test/history?page={page}",
            rolling_min_train_draws=100,
            rolling_step=1,
            rule_parameters={"omit_threshold": 12, "heat_score_threshold": 0.6},
        )

        self.assertNotEqual(signature_a, signature_b)

    def test_workbook_signature_changes_when_recent_draws_change(self):
        signature_a = compute_workbook_signature(self.records, draw_count=2, base_url="https://example.test/history?page={page}")
        changed_records = [DrawRecord(serial="2026002", draw_date="2026-03-23", red=[1, 2, 3, 4, 5, 7], blue=7), self.records[1]]
        signature_b = compute_workbook_signature(changed_records, draw_count=2, base_url="https://example.test/history?page={page}")

        self.assertNotEqual(signature_a, signature_b)


if __name__ == "__main__":
    unittest.main()
