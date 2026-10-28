"""Regression coverage for incremental season discovery and nightly safety."""
import json
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import limitless_sync as sync

ROOT = Path(__file__).resolve().parents[1]


class NightlyCollectionTests(unittest.TestCase):
    def test_new_event_priority_and_failure_cooldown(self):
        events = {
            'fresh': {'id': 'fresh', 'date': '2026-10-28', 'checked': ''},
            'old': {'id': 'old', 'date': '2026-10-20', 'checked': '2026-10-21'},
            'retry': {'id': 'retry', 'date': '2026-10-27', 'checked': '',
                      'retry_after': 2000},
        }
        selected = sync.select_events(events, {'old'}, 2, now=1000)
        self.assertEqual([e['id'] for e in selected], ['fresh', 'old'])
        self.assertNotIn('retry', [e['id'] for e in selected])

    def test_newest_page_revisited_while_backfill_cursor_advances(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            state = folder / 'state.json'
            db = folder / 'games.sqlite3'
            state.write_text(json.dumps({'page': 4, 'events': {}}))
            recent = {'id': 'newest', 'name': 'Latest event',
                      'date': '2026-10-28'}
            backfill = {'id': 'older', 'name': 'Older event',
                        'date': '2026-09-20'}
            argv = ['sync', '--since', '2026-09-01', '--recent-pages', '1',
                    '--pages', '1', '--max-tournaments', '1',
                    '--state', str(state)]
            with patch.object(sync, 'DB', db), patch('sys.argv', argv), \
                    patch.object(sync, 'fetch', side_effect=[[recent], [backfill]]) as fetch, \
                    patch.object(sync, 'sync_tournament', return_value=1):
                sync.main()
            self.assertEqual([c.args[1]['page'] for c in fetch.call_args_list],
                             [1, 4])
            saved = json.loads(state.read_text())
            self.assertEqual(saved['page'], 5)
            self.assertIn('newest', saved['events'])
            self.assertIn('older', saved['events'])

    def test_failed_tournament_does_not_discard_other_progress(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            state = folder / 'state.json'
            db = folder / 'games.sqlite3'
            events = {name: {'id': name, 'date': '2026-10-28',
                             'name': name, 'checked': ''}
                      for name in ('aa-bad', 'bb-good')}
            state.write_text(json.dumps({'page': 1, 'events': events}))
            argv = ['sync', '--since', '2026-09-01',
                    '--pages', '1', '--max-tournaments', '10',
                    '--state', str(state)]

            def sync_one(conn, tournament, delay):
                if tournament['id'] == 'aa-bad':
                    raise ValueError('incomplete pairings')
                return 1

            with patch.object(sync, 'DB', db), patch('sys.argv', argv), \
                    patch.object(sync, 'fetch', return_value=[]), \
                    patch.object(sync, 'sync_tournament', side_effect=sync_one):
                sync.main()
            saved = json.loads(state.read_text())
            self.assertEqual(saved['events']['aa-bad']['failures'], 1)
            self.assertGreater(saved['events']['aa-bad']['retry_after'],
                               time.time())
            self.assertTrue(saved['events']['bb-good']['checked'])
            self.assertEqual(saved['events']['bb-good']['failures'], 0)

            # The existing production snapshot is read-only throughout sync.
            self.assertTrue((ROOT / 'matches_snapshot.csv').is_file())

    def test_ambiguous_duplicate_keys_do_not_overwrite_matches(self):
        with sqlite3.connect(':memory:') as conn:
            sync.initialize(conn)
            standings = [
                {'player': 'p1', 'deck': {'name': 'Dragapult'}},
                {'player': 'p2', 'deck': {'name': 'Gholdengo'}},
            ]
            pairing = {'player1': 'p1', 'player2': 'p2',
                       'winner': 'p1', 'phase': 1,
                       'round': 1, 'table': 3}
            event = {'id': 'new-event', 'name': 'Example',
                     'date': '2026-10-28'}
            with patch.object(sync, 'fetch',
                              side_effect=[standings, [pairing, pairing]]), \
                    patch.object(sync, 'pause'):
                with self.assertRaisesRegex(ValueError, 'Ambiguous'):
                    sync.sync_tournament(conn, event, 0)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM games')
                             .fetchone()[0], 0)


if __name__ == '__main__':
    unittest.main()
