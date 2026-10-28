"""Regression tests for safe self-reported player country segmentation."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import limitless_sync as sync
from country_store import (read_country_snapshot, restore_countries,
                           export_countries, upsert_countries)
from region_labels import normalize_country, country_group, eligible_player


class CountryGroupsTests(unittest.TestCase):
    def test_player_country_is_not_tournament_location(self):
        self.assertEqual(normalize_country(' jp '), 'JP')
        self.assertEqual(normalize_country('us'), 'US')
        for bad in (None, '', '?', 'not-provided', 'XX', 'ZZ', 'UK', 1):
            self.assertEqual(normalize_country(bad), '')
        self.assertEqual(country_group('JP'), '国内')
        self.assertEqual(country_group('US'), '海外')
        self.assertEqual(country_group(''), '不明')

    def test_filter_is_perspective_specific(self):
        self.assertTrue(eligible_player('JP', 'US', 'a', '国内'))
        self.assertFalse(eligible_player('JP', 'US', 'b', '国内'))
        self.assertFalse(eligible_player('JP', 'US', 'a', '海外'))
        self.assertTrue(eligible_player('JP', 'US', 'b', '海外'))
        self.assertFalse(eligible_player('JP', 'US', 'a', '国内同士'))
        self.assertTrue(eligible_player('JP', 'JP', 'b', '国内同士'))
        self.assertFalse(eligible_player('JP', '', 'a', '国内同士'))
        self.assertTrue(eligible_player('', '', 'b', '国不明'))
        self.assertFalse(eligible_player('', '', 'b', '海外'))
        self.assertTrue(eligible_player('', 'US', 'b', 'すべて'))


class CountryStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'match_countries.csv'
        self.conn = sqlite3.connect(':memory:')
        sync.initialize(self.conn)
        self.conn.execute(
            'INSERT INTO games VALUES (?,?,?,?,?,?,?,?,?)',
            ('match-1', 'Event', '2026-09-02', 'Dragapult',
             'Gholdengo', 'a', '{}', '{}', 'test'))
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_export_restore_and_no_country_loss(self):
        self.assertEqual(export_countries(self.conn, self.path), 1)
        self.assertEqual(read_country_snapshot(self.path)[0]['country_a'], '')
        with self.conn:
            upsert_countries(self.conn, [('match-1', 'JP', 'US')])
        self.assertEqual(export_countries(self.conn, self.path), 1)
        self.assertEqual(len(read_country_snapshot(self.path)), 1)
        self.conn.execute('DELETE FROM match_countries')
        self.conn.commit()
        self.assertEqual(restore_countries(self.conn, self.path), 1)
        with self.conn:
            upsert_countries(self.conn, [('match-1', '', None)])
        self.assertEqual(
            self.conn.execute('SELECT country_a,country_b FROM match_countries').fetchone(),
            ('JP', 'US'))
        self.assertEqual(export_countries(self.conn, self.path), 1)

    def test_loss_of_old_match_rejected_without_overwriting_snapshot(self):
        with self.conn:
            upsert_countries(self.conn, [('match-1', 'JP', 'US')])
        export_countries(self.conn, self.path)
        original = self.path.read_bytes()
        self.conn.execute('DELETE FROM games')
        self.conn.commit()
        with self.assertRaisesRegex(ValueError, 'lose match ID'):
            export_countries(self.conn, self.path)
        self.assertEqual(self.path.read_bytes(), original)

    def test_invalid_or_duplicate_country_file_is_rejected(self):
        self.path.write_text('id,country_a,country_b\nx,JP,US\nx,JP,US\n')
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            restore_countries(self.conn, self.path)
        self.path.write_text('id,country_a,country_b\nx,JAPAN,US\n')
        with self.assertRaisesRegex(ValueError, 'Malformed country code'):
            restore_countries(self.conn, self.path)

    def test_limitless_standings_countries_saved_atomically(self):
        event = {'id': 'example', 'date': '2026-09-08', 'name': 'Online'}
        standings = [
            {'player': 'p1', 'deck': {'name': 'Dragapult'}, 'country': 'JP'},
            {'player': 'p2', 'deck': {'name': 'Gholdengo'}, 'country': 'US'}
        ]
        matches = [{'player1': 'p1', 'player2': 'p2',
                    'winner': 'p1', 'phase': 1, 'round': 1, 'table': 1}]
        with patch.object(sync, 'fetch', side_effect=[standings, matches]), \
                patch.object(sync, 'pause'):
            sync.sync_tournament(self.conn, event, 0)
        self.assertEqual(self.conn.execute(
            "SELECT country_a,country_b FROM match_countries WHERE id='example:1:1:1'"
        ).fetchone(), ('JP', 'US'))
        standings[0]['country'] = ''
        standings[1]['country'] = None
        with patch.object(sync, 'fetch', side_effect=[standings, matches]), \
                patch.object(sync, 'pause'):
            sync.sync_tournament(self.conn, event, 0)
        self.assertEqual(self.conn.execute(
            "SELECT country_a,country_b FROM match_countries WHERE id='example:1:1:1'"
        ).fetchone(), ('JP', 'US'))
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) FROM games WHERE source='limitless-play:example'"
        ).fetchone()[0], 1)


if __name__ == '__main__':
    unittest.main()
