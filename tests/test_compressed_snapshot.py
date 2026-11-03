"""Compressed snapshot migration, read compatibility and safety regression tests."""
import csv
import gzip
import sqlite3
import tempfile
import unittest
from pathlib import Path

from snapshot_store import (
    COLUMNS, export, open_snapshot_text, preferred_snapshot, read_snapshot, restore
)
from limitless_sync import initialize


def sample(identifier, played_at="2026-11-03"):
    return (identifier, "Test event", played_at, "Dragapult", "Gholdengo",
            "a", "{}", "{}", "limitless-play:test")


class CompressedSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.legacy = self.root / "matches_snapshot.csv"
        self.compressed = self.root / "matches_snapshot.csv.gz"
        with self.legacy.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(COLUMNS)
            writer.writerow(sample("old"))
        self.db = sqlite3.connect(":memory:")
        initialize(self.db)

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_compress_initial_legacy_csv_and_prefer_latest(self):
        self.assertEqual(preferred_snapshot(self.root), self.legacy)
        self.assertEqual(restore(self.db, preferred_snapshot(self.root)), 1)
        self.db.execute("INSERT INTO games VALUES (?,?,?,?,?,?,?,?,?)",
                        sample("new"))
        self.db.commit()
        self.assertEqual(export(self.db, self.compressed), 2)
        self.assertEqual(preferred_snapshot(self.root), self.compressed)
        self.assertEqual(len(read_snapshot(self.compressed)), 2)
        self.assertEqual(len(read_snapshot(self.legacy)), 1)
        self.assertEqual(read_snapshot(self.compressed)[-1]["id"], "old")
        with open_snapshot_text(preferred_snapshot(self.root)) as handle:
            self.assertEqual(len(list(csv.DictReader(handle))), 2)

    def test_next_sync_restores_all_compressed_matches(self):
        restore(self.db, self.legacy)
        self.db.execute("INSERT INTO games VALUES (?,?,?,?,?,?,?,?,?)",
                        sample("new"))
        export(self.db, self.compressed)
        with sqlite3.connect(":memory:") as second:
            initialize(second)
            self.assertEqual(restore(second, preferred_snapshot(self.root)), 2)
            self.assertEqual(second.execute("SELECT COUNT(*) FROM games").fetchone()[0], 2)

    def test_compressed_export_rejects_missing_saved_match_and_keeps_bytes(self):
        restore(self.db, self.legacy)
        self.db.execute("INSERT INTO games VALUES (?,?,?,?,?,?,?,?,?)",
                        sample("new"))
        export(self.db, self.compressed)
        before = self.compressed.read_bytes()
        self.db.execute("DELETE FROM games WHERE id='old'")
        self.db.commit()
        with self.assertRaisesRegex(ValueError, "lose matches"):
            export(self.db, self.compressed)
        self.assertEqual(self.compressed.read_bytes(), before)

    def test_corrupt_gzip_rejected_not_replaced_with_stale_csv(self):
        self.compressed.write_bytes(b"invalid compressed content")
        self.assertEqual(preferred_snapshot(self.root), self.compressed)
        with self.assertRaises((gzip.BadGzipFile, OSError, EOFError)):
            restore(self.db, preferred_snapshot(self.root))

    def test_no_plain_csv_change_when_gzip_written(self):
        before = self.legacy.read_bytes()
        restore(self.db, self.legacy)
        export(self.db, self.compressed)
        self.assertEqual(self.legacy.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
