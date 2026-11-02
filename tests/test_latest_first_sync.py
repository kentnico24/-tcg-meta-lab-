"""Regression tests for latest-first uncapped nightly collection."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import limitless_sync as sync


class LatestFirstCollectionTests(unittest.TestCase):
    def test_latest_events_then_historical_backlog_then_refresh(self):
        today = datetime.now(ZoneInfo('Asia/Tokyo')).date()
        events = {
            'recent-1': {'id': 'recent-1', 'date': today.isoformat(), 'checked': ''},
            'recent-2': {'id': 'recent-2', 'date': (today - timedelta(days=1)).isoformat(), 'checked': ''},
            'recent-refresh': {'id': 'recent-refresh',
                               'date': (today - timedelta(days=2)).isoformat(),
                               'checked': (today - timedelta(days=1)).isoformat()},
            'recent-already-checked': {'id': 'recent-already-checked',
                                      'date': today.isoformat(),
                                      'checked': today.isoformat()},
            'historical-1': {'id': 'historical-1', 'date': (today - timedelta(days=20)).isoformat(), 'checked': ''},
            'historical-2': {'id': 'historical-2', 'date': (today - timedelta(days=10)).isoformat(), 'checked': ''},
            'old-refresh': {'id': 'old-refresh', 'date': (today - timedelta(days=30)).isoformat(),
                            'checked': (today - timedelta(days=15)).isoformat()},
            'cooldown': {'id': 'cooldown', 'date': today.isoformat(), 'checked': '',
                         'retry_after': 5000},
        }
        selected = sync.select_events(events, {'recent-refresh', 'recent-already-checked', 'old-refresh'},
                                      0, now=1000, latest_days=7, today=today)
        self.assertEqual([t['id'] for t in selected],
                         ['recent-1', 'recent-2', 'recent-refresh', 'historical-1',
                          'historical-2', 'old-refresh'])

    def test_count_quota_optional_and_cooldown_preserved(self):
        today = datetime.now(ZoneInfo('Asia/Tokyo')).date()
        events = {str(i): {'id': str(i), 'date': today.isoformat(), 'checked': ''}
                  for i in range(125)}
        self.assertEqual(len(sync.select_events(events, set(), 0, latest_days=7, today=today)), 125)
        self.assertEqual(len(sync.select_events(events, set(), 3, latest_days=7, today=today)), 3)

    def test_discovers_all_recent_pages_and_uses_remainder_for_backfill(self):
        today = datetime.now(ZoneInfo('Asia/Tokyo')).date()
        newest = {'id': 'newest', 'name': 'newest', 'date': today.isoformat()}
        recent = {'id': 'recent', 'name': 'recent',
                  'date': (today - timedelta(days=2)).isoformat()}
        old = {'id': 'old', 'name': 'old',
               'date': (today - timedelta(days=20)).isoformat()}
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            state = folder / 'state.json'
            db = folder / 'matches.db'
            state.write_text(json.dumps({'page': 3, 'events': {}}))
            argv = ['sync', '--since', '2026-09-01', '--pages', '1',
                    '--latest-days', '7', '--max-tournaments', '0',
                    '--state', str(state)]
            with patch.object(sync, 'DB', db), patch('sys.argv', argv), \
                    patch.object(sync, 'fetch', side_effect=[[newest], [recent, old], [old]]) as fetch, \
                    patch.object(sync, 'sync_tournament', return_value=1) as collect:
                sync.main()
            self.assertEqual([call.args[1]['page'] for call in fetch.call_args_list],
                             [1, 2, 3])
            self.assertEqual([call.args[1]['id'] for call in collect.call_args_list],
                             ['newest', 'recent', 'old'])
            saved = json.loads(state.read_text())
            self.assertEqual(saved['page'], 4)
            self.assertTrue(all(saved['events'][key]['checked'] for key in ('newest', 'recent', 'old')))


if __name__ == '__main__':
    unittest.main()
