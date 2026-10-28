"""Tests for season-boundary discovery and bounded post-backfill refreshes."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import limitless_sync as sync


class BackfillAccelerationTests(unittest.TestCase):
    def test_backfill_finds_september_and_prioritizes_oldest(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            state = work / "state.json"
            database = work / "data.sqlite3"
            state.write_text(json.dumps({"page": 4, "events": {}}))
            page1 = [{"id": "latest", "name": "Latest", "date": "2026-10-28"}]
            page4 = [{"id": "sept", "name": "September", "date": "2026-09-02"}]
            page5 = [{"id": "august", "name": "Out of season", "date": "2026-08-31"}]
            seen = []
            argv = ["sync", "--pages", "2", "--recent-pages", "1",
                    "--since", "2026-09-01", "--max-tournaments", "1",
                    "--state", str(state)]
            def collect(connection, tournament, delay):
                seen.append(tournament["id"])
                return 1
            with patch.object(sync, "DB", database), \
                    patch("sys.argv", argv), \
                    patch.object(sync, "fetch", side_effect=[page1, page4, page5]) as fetched, \
                    patch.object(sync, "sync_tournament", side_effect=collect):
                sync.main()
            self.assertEqual([x.args[1]["page"] for x in fetched.call_args_list], [1, 4, 5])
            self.assertEqual(seen, ["sept"])
            result = json.loads(state.read_text())
            self.assertTrue(result["season_boundary_seen"])
            self.assertEqual(result["page"], 1)
            self.assertNotIn("august", result["events"])
            self.assertIn("oldest_match_date", result["last_sync"])

    def test_refresh_quota_drops_after_full_discovery_and_no_backlog(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            state = work / "state.json"
            events = {
                f"checked-{i}": {"id": f"checked-{i}", "name": "Past",
                                "date": "2026-09-15", "checked": f"2026-10-{i+1:02d}"}
                for i in range(5)
            }
            state.write_text(json.dumps({"page": 1, "season_boundary_seen": True,
                                         "events": events}))
            calls = []
            argv = ["sync", "--pages", "1", "--max-tournaments", "10",
                    "--caught-up-refresh", "2", "--since", "2026-09-01",
                    "--state", str(state)]
            def collect(connection, tournament, delay):
                calls.append(tournament["id"])
                return 0
            with patch.object(sync, "DB", work / "db.sqlite3"), \
                    patch("sys.argv", argv), \
                    patch.object(sync, "fetch", return_value=[]), \
                    patch.object(sync, "sync_tournament", side_effect=collect):
                sync.main()
            self.assertEqual(len(calls), 2)
            report = json.loads(state.read_text())["last_sync"]
            self.assertGreaterEqual(report["discovered_tournaments"], 5)
            self.assertEqual(report["successful_tournaments"], 2)
            self.assertEqual(report["failed_tournaments"], 0)


if __name__ == "__main__":
    unittest.main()
