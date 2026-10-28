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


class SeptemberBackfillTests(unittest.TestCase):
    def test_city_league_september_2027_listing_is_included(self):
        from city_league_sync import parse_listing
        html = """
        <table><tr><th>Date</th><th>Prefecture</th><th>Shop</th><th>Winner</th></tr>
        <tr><td>26 Oct 26</td><td>Kanagawa<a href="/tournaments/jp/5201">City</a></td><td>Shop</td><td>x</td></tr>
        <tr><td>25 Sep 26</td><td>Chiba<a href="/tournaments/jp/4701">City</a></td><td>Shop</td><td>x</td></tr>
        <tr><td>01 Sep 26</td><td>Ōsaka<a href="/tournaments/jp/4001">City</a></td><td>Shop</td><td>x</td></tr>
        <tr><td>31 Aug 26</td><td>Ōsaka<a href="/tournaments/jp/3900">City</a></td><td>Shop</td><td>x</td></tr>
        </table>"""
        events, reached = parse_listing(html, date(2026, 9, 1))
        self.assertTrue(reached)
        self.assertEqual([x["date"] for x in events],
                         ["2026-10-26", "2026-09-25", "2026-09-01"])
        self.assertEqual(events[1]["id"], "4701")

    def test_oldest_missing_backfill_prioritizes_september(self):
        from city_league_sync import select_events
        sep = [
            {"id": str(i), "date": f"2026-09-{i:02d}",
             "event_url": f"https://limitlesstcg.com/tournaments/jp/{i}"}
            for i in range(1, 21)
        ]
        oct_events = [
            {"id": str(100 + i), "date": f"2026-10-{i:02d}",
             "event_url": f"https://limitlesstcg.com/tournaments/jp/{100 + i}"}
            for i in range(1, 21)
        ]
        previous = {
            "id": "400", "date": "2026-10-22",
            "event_url": "https://limitlesstcg.com/tournaments/jp/400",
        }
        all_events = list(reversed(sep + oct_events)) + [previous]
        choices = select_events(all_events, {previous["event_url"]}, 30,
                                oldest_first=True)
        self.assertEqual(len(choices), 30)
        self.assertEqual(choices[0]["date"], "2026-09-01")
        self.assertGreaterEqual(
            sum(x["date"].startswith("2026-09") for x in choices), 20)
        self.assertIn("2026-10-20", [x["date"] for x in choices])
        self.assertIn(previous["event_url"], [x["event_url"] for x in choices])
        self.assertEqual(len({x["event_url"] for x in choices}), len(choices))

    def test_no_pending_means_bounded_daily_refresh(self):
        from city_league_sync import select_events
        existing = [
            {"id": str(i), "date": f"2026-10-{(i % 27) + 1:02d}",
             "event_url": f"https://limitlesstcg.com/tournaments/jp/{i}"}
            for i in range(60)
        ]
        known = {x["event_url"] for x in existing}
        chosen = select_events(existing, known, 100, oldest_first=True)
        self.assertEqual(len(chosen), 10)
        self.assertEqual(len({x["event_url"] for x in chosen}), 10)

    def test_source_record_retention_after_backfill(self):
        from city_league_sync import read_saved, save_atomic
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "city_league_results.csv"
            old = {
                "key": "5201:0", "date": "2026-10-26", "prefecture": "Chiba",
                "shop": "A", "rank": "1", "deck": "dragapult",
                "player": "Example", "event_url":
                    "https://limitlesstcg.com/tournaments/jp/5201",
                "decklist_url": "",
            }
            newer = dict(old, key="4701:0", date="2026-09-25",
                         event_url="https://limitlesstcg.com/tournaments/jp/4701")
            save_atomic(path, {old["key"]: old})
            before = read_saved(path)
            saved = dict(before)
            saved[newer["key"]] = newer
            save_atomic(path, saved)
            after = read_saved(path)
            self.assertEqual(after[old["key"]], before[old["key"]])
            self.assertIn(newer["key"], after)


if __name__ == '__main__':
    unittest.main()
