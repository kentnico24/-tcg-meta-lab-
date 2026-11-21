"""Verified Alakazam / Lillie's Clefairy ex / Genesect variant tests."""
from pathlib import Path
import unittest

from deck_variants import (
    CLEFAIRY_ALAKAZAM_GENESECT, classify_clefairy_alakazam,
    classify_dragapult, DRAGAPULT_HAMMER,
)
from deck_names import deck_name


class ClefairyAlakazamTests(unittest.TestCase):
    def setUp(self):
        self.cards = {
            "Alakazam": 3, "Lillie's Clefairy ex": 2, "Genesect": 1,
            "Dudunsparce": 2, "Dunsparce": 3,
        }

    def test_identifies_verified_core_from_main_and_compound_archetypes(self):
        for name in ("Alakazam", "Alakazam Dudunsparce",
                     "Alakazam Lillie's Clefairy", "Lillie's Clefairy Alakazam"):
            with self.subTest(name=name):
                self.assertEqual(classify_clefairy_alakazam(name, self.cards),
                                 CLEFAIRY_ALAKAZAM_GENESECT)

    def test_list_variation_without_dudunsparce_still_qualifies(self):
        self.assertEqual(classify_clefairy_alakazam(
            "Alakazam", {"Alakazam": 1, "Lillie's Clefairy ex": 1, "Genesect": 2}),
            CLEFAIRY_ALAKAZAM_GENESECT)

    def test_japanese_and_smart_quote_name_variants(self):
        self.assertEqual(classify_clefairy_alakazam(
            "Alakazam Dudunsparce",
            {"フーディン": 3, "リーリエのピッピex": 2, "ゲノセクト": 1}),
            CLEFAIRY_ALAKAZAM_GENESECT)
        self.assertEqual(classify_clefairy_alakazam(
            "Alakazam",
            {" Alakazam ": 3, "Lillie’s   Clefairy  ex": "2", "Genesect": "1"}),
            CLEFAIRY_ALAKAZAM_GENESECT)

    def test_missing_lists_and_any_missing_core_keep_original_type(self):
        for cards in ({}, None, {"Alakazam": 3, "Lillie's Clefairy ex": 2},
                      {"Alakazam": 3, "Genesect": 1},
                      {"Lillie's Clefairy ex": 2, "Genesect": 1},
                      {"Alakazam": 3, "Lillie's Clefairy ex": 2, "Genesect": 0},
                      {"Alakazam": 3, "Lillie's Clefairy ex": 2, "Genesect": -1},
                      {"Alakazam": 3, "Lillie's Clefairy ex": 2, "Genesect": True}):
            with self.subTest(cards=cards):
                self.assertEqual(classify_clefairy_alakazam("Alakazam Dudunsparce", cards),
                                 "Alakazam Dudunsparce")

    def test_ex_and_other_card_names_are_not_confused(self):
        for cards in (
            {"Alakazam ex": 2, "Lillie's Clefairy ex": 2, "Genesect": 1},
            {"Alakazam": 2, "Lillie's Clefairy": 2, "Genesect": 1},
            {"Alakazam": 2, "Lillie's Clefairy ex": 2, "Genesect ex": 1},
            {"Alakazam": 2, "Lillie's Clefairy ex": 2, "Genesect V": 1},
        ):
            with self.subTest(cards=cards):
                self.assertEqual(classify_clefairy_alakazam("Alakazam", cards),
                                 "Alakazam")

    def test_unrelated_archetypes_and_idempotence(self):
        self.assertEqual(classify_clefairy_alakazam("Dragapult", self.cards), "Dragapult")
        self.assertEqual(classify_clefairy_alakazam("Mega Alakazam", self.cards),
                         "Mega Alakazam")
        self.assertEqual(classify_clefairy_alakazam(
            CLEFAIRY_ALAKAZAM_GENESECT, {}), CLEFAIRY_ALAKAZAM_GENESECT)
        self.assertEqual(classify_dragapult(
            "Dragapult", {"Crushing Hammer": 4}), DRAGAPULT_HAMMER)
        self.assertEqual(deck_name(CLEFAIRY_ALAKAZAM_GENESECT),
                         "ピッピフーディン（ゲノセクト型）")

    def test_app_classifies_both_sides_without_mutating_csv(self):
        source = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
        self.assertIn("for side in ('a','b'):", source)
        self.assertIn("classify_clefairy_alakazam(deck,normalize_list(cards))", source)
        self.assertIn("clefairy_alakazam_sides", source)
        self.assertIn("classify_dragapult('Dragapult',normalize_list(value))", source)


if __name__ == "__main__":
    unittest.main()
