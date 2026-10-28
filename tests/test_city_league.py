"""Smoke tests for City League HTML, persistence, and strict source separation."""
from datetime import date
import tempfile
import unittest
from pathlib import Path

from city_league_sync import (
    FIELDS, parse_listing, parse_placements, read_saved, save_atomic,
)


class CityLeagueTests(unittest.TestCase):
    def test_listing_parses_real_city_league_paths_and_season_window(self):
        html = """
        <table><tr><th>Date</th><th>Prefecture</th><th>Shop</th><th>Winner</th></tr>
        <tr><td>26 Oct 26</td><td><a href="/tournaments/jp/5148">Tōkyō</a></td>
        <td>ドラゴンスター秋葉原駅前店</td><td></td></tr>
        <tr><td>20 Aug 26</td><td><a href="/tournaments/jp/4000">Ōsaka</a></td>
        <td>Shop</td><td></td></tr></table>"""
        events, reached = parse_listing(html, date(2026, 9, 1))
        self.assertTrue(reached)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['id'], '5148')
        self.assertEqual(events[0]['date'], '2026-10-26')
        self.assertEqual(events[0]['prefecture'], 'Tōkyō')
        self.assertEqual(events[0]['event_url'],
                         'https://limitlesstcg.com/tournaments/jp/5148')

    def test_placement_contains_rank_and_deck_without_matchup_invention(self):
        html = """
        <table class="striped"><tr><th>#</th><th>Player</th><th>Deck</th><th>List</th></tr>
        <tr><td>1</td><td>プレイヤー</td><td><a href="/decks/list/123">
        <img src="/images/pokemon/dragapult.png" alt="Dragapult"></a></td>
        <td><a href="/decks/list/123">List</a></td></tr>
        <tr><td>2</td><td>ほか</td><td></td><td></td></tr>
        </table>"""
        event = {'id': '5148', 'date': '2026-10-26',
                 'prefecture': 'Tōkyō', 'shop': 'shop',
                 'event_url': 'https://limitlesstcg.com/tournaments/jp/5148'}
        rows = parse_placements(html, event)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['rank'], '1')
        self.assertEqual(rows[0]['deck'], 'Dragapult')
        self.assertEqual(rows[0]['decklist_url'],
                         'https://limitlesstcg.com/decks/list/123')
        self.assertEqual(rows[1]['deck'], '')
        self.assertEqual(set(rows[0]), set(FIELDS))
        self.assertNotIn('winner', rows[0])

    def test_unreadable_pages_do_not_replace_existing_results(self):
        with self.assertRaisesRegex(ValueError, 'missing tournament table'):
            parse_listing('<p>blocked</p>', date(2026, 9, 1))
        with self.assertRaisesRegex(ValueError, 'placement table'):
            parse_placements('<p>blocked</p>', {'id': '1'})
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'city_league_results.csv'
            record = {key: '' for key in FIELDS}
            record.update({'key': '5148:1', 'date': '2026-10-26',
                           'rank': '1', 'deck': 'Dragapult',
                           'event_url': 'https://limitlesstcg.com/tournaments/jp/5148'})
            save_atomic(path, {record['key']: record})
            before = path.read_bytes()
            self.assertEqual(read_saved(path)['5148:1']['deck'], 'Dragapult')
            with self.assertRaisesRegex(ValueError, 'Unexpected'):
                path.write_text('bad,data\n1,2')
                read_saved(path)
            path.write_bytes(before)
            self.assertEqual(path.read_bytes(), before)


class CityDeckLabelTests(unittest.TestCase):
    def test_sprite_codes_translate_japanese(self):
        from deck_names import city_deck_name
        examples = {
            'dragapult': 'ドラパルト',
            'dragapult dudunsparce': 'ドラパルト・ノココッチ',
            'alakazam dudunsparce': 'フーディン・ノココッチ',
            'garchomp roserade': 'ガブリアス・ロズレイド',
            'lucario-mega hariyama': 'メガルカリオ・ハリテヤマ',
            'charizard-mega-y charizard-mega-x': 'メガリザードンY・メガリザードンX',
            'raging-bolt ogerpon': 'タケルライコ・オーガポン',
            'rayquaza-mega ho-oh': 'メガレックウザ・ホウオウ',
            'toxtricity pecharunt': 'ストリンダー・モモワロウ',
        }
        for english, japanese in examples.items():
            with self.subTest(english=english):
                self.assertEqual(city_deck_name(english), japanese)
        self.assertEqual(city_deck_name('unknown pokemon'), 'unknown pokemon')


if __name__ == '__main__':
    unittest.main()
