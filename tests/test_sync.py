import csv
import io
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import urllib.error
import limitless_sync as sync
from snapshot_store import COLUMNS, restore, export
from deck_names import deck_name

ROOT = Path(__file__).resolve().parents[1]


class ProtectionTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        sync.initialize(self.conn)
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'matches.csv'
        self.path.write_bytes((ROOT / 'matches_snapshot.csv').read_bytes())
        self.original = self.path.read_bytes()
        restore(self.conn, self.path)
        self.baseline = len(list(csv.DictReader(io.StringIO(self.original.decode()))))

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_actual_1028_restored_and_exported(self):
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM games').fetchone()[0], self.baseline)
        self.assertEqual(export(self.conn, self.path), self.baseline)
        self.assertEqual({r['id'] for r in csv.DictReader(io.StringIO(self.original.decode()))},
                         {r[0] for r in self.conn.execute('SELECT id FROM games')})

    def test_repeated_restore_deduplicates(self):
        restore(self.conn, self.path)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM games').fetchone()[0], self.baseline)

    def test_loss_export_keeps_original_bytes(self):
        self.conn.execute('DELETE FROM games WHERE id=(SELECT id FROM games LIMIT 1)')
        with self.assertRaises(ValueError):
            export(self.conn, self.path)
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_malformed_snapshot_rejected(self):
        self.path.write_text('id,deck_a\nx,A\n')
        with self.assertRaises(ValueError):
            restore(self.conn, self.path)

    def event(self):
        return {'id': 'test', 'name': 'Test', 'date': '2026-10-01'}

    def standings(self):
        return [{'player': p, 'deck': {'name': d}} for p, d in [('p1', 'Dragapult'), ('p2', 'Gholdengo')]]

    def pairing(self, table=1, winner='p1'):
        return {'player1': 'p1', 'player2': 'p2', 'winner': winner, 'phase': 1, 'round': 1, 'table': table}

    def run_event(self, pairings):
        with patch.object(sync, 'fetch', side_effect=[self.standings(), pairings]), patch.object(sync, 'pause'):
            return sync.sync_tournament(self.conn, self.event(), 0)

    def test_new_matches_and_late_updates_deduplicated_after_reorder(self):
        self.run_event([self.pairing(1), self.pairing(2)])
        self.run_event([self.pairing(2), self.pairing(1, 'p2')])
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM games').fetchone()[0], self.baseline + 2)
        self.assertEqual(self.conn.execute("SELECT winner FROM games WHERE id='test:1:1:1'").fetchone()[0], 'b')
        self.assertEqual(export(self.conn, self.path), self.baseline + 2)

    def test_legacy_id_reused(self):
        self.run_event([self.pairing()])
        self.conn.execute("UPDATE games SET id='test:1:1:1:0' WHERE id='test:1:1:1'")
        self.conn.commit()
        self.run_event([self.pairing(1, 'p2')])
        self.assertEqual(self.conn.execute("SELECT id,winner FROM games WHERE source='limitless-play:test'").fetchall(), [('test:1:1:1:0', 'b')])

    def test_partial_and_empty_refresh_rollback(self):
        self.run_event([self.pairing(1), self.pairing(2)])
        for pairs in ([], [self.pairing(1)], {'error': 'bad'}):
            with self.assertRaises(ValueError):
                self.run_event(pairs)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM games').fetchone()[0], self.baseline + 2)

    def test_network_failure_does_not_touch_data(self):
        with patch.object(sync, 'fetch', side_effect=urllib.error.URLError('offline')):
            with self.assertRaises(urllib.error.URLError):
                sync.sync_tournament(self.conn, self.event(), 0)
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertEqual(export(self.conn, self.path), self.baseline)

    def test_retry_and_runtime_limit(self):
        response = io.StringIO('[]')
        with patch.object(sync.urllib.request, 'urlopen', side_effect=[urllib.error.HTTPError('url', 429, '', {}, None), response]) as request, patch.object(sync, 'pause'):
            self.assertEqual(sync.fetch('/tournaments'), [])
            self.assertEqual(request.call_count, 2)
        with patch.object(sync, 'DEADLINE', 0):
            with self.assertRaises(TimeoutError):
                sync.pause(0)

    def test_incremental_discovery_state_and_recheck(self):
        state = Path(self.tmp.name) / 'state.json'
        db = Path(self.tmp.name) / 'db.sqlite3'
        event = {**self.event(), 'date': '2026-10-29'}
        with patch.object(sync, 'DB', db), patch('sys.argv', ['sync', '--since', '2026-10-29', '--pages', '1', '--state', str(state)]), patch.object(sync, 'fetch', side_effect=[[event], self.standings(), [self.pairing()]]), patch.object(sync, 'pause'):
            sync.main()
        import json
        saved = json.loads(state.read_text())
        self.assertEqual(saved['page'], 2)
        self.assertTrue(saved['events']['test']['checked'])
        with patch.object(sync, 'DB', db), patch('sys.argv', ['sync', '--since', '2026-10-29', '--pages', '1', '--state', str(state)]), patch.object(sync, 'fetch', side_effect=[[], self.standings(), [self.pairing(1, 'p2')]]) as request, patch.object(sync, 'pause'):
            sync.main()
            self.assertEqual(request.call_args_list[0].args[1]['page'], 2)
        self.assertEqual(json.loads(state.read_text())['page'], 1)
        with sqlite3.connect(db) as conn:
            self.assertEqual(conn.execute("SELECT winner FROM games WHERE id='test:1:1:1'").fetchone()[0], 'b')

    def test_japanese_display_only_and_fallback(self):
        for english, japanese in [('Basic Box', 'ベーシックBOX'), ('Dragapult', 'ドラパルト'), ('Gholdengo', 'サーフゴー'), ("N's Zoroark", 'Nのゾロアーク'), ('Unregistered', 'Unregistered')]:
            self.assertEqual(deck_name(english), japanese)
        self.assertEqual(self.path.read_bytes(), self.original)


if __name__ == '__main__':
    unittest.main()
