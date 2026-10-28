"""Ensure Crunching Hammer Dragapult is a permanent, verifiable deck type."""
import ast
import csv
import json
from pathlib import Path
import unittest

from deck_names import deck_name
from deck_variants import (
    classify_dragapult, DRAGAPULT_HAMMER, DRAGAPULT_BASE,
)

ROOT = Path(__file__).resolve().parents[1]


class CrushingHammerArchetypeTests(unittest.TestCase):
    def test_only_verified_card_inclusion_becomes_own_deck_type(self):
        self.assertEqual(classify_dragapult(
            "Dragapult", {"Dreepy": 4, "Crushing Hammer": 4}),
            DRAGAPULT_HAMMER)
        self.assertEqual(classify_dragapult(
            "Dragapult", {"Dreepy": 4, "クラッシュハンマー": "1"}),
            DRAGAPULT_HAMMER)
        self.assertEqual(classify_dragapult(
            "Dragapult", {"Dreepy": 4, " CRUSHING HAMMER ": 2}),
            DRAGAPULT_HAMMER)

    def test_no_hammer_or_unknown_cards_stay_plain_dragapult(self):
        examples = [
            {"Dreepy": 4, "Dragapult ex": 3, "Rare Candy": 3},
            {"Dreepy": 4, "Crushing Hammer": 0},
            {"Dreepy": 4, "Crushing Hammer": -1},
            {"Dreepy": 4, "Crushing Hammer": "unknown"},
            {"Dreepy": 4, "Crushing Hammer": True},
            {"Crushing Hammer": 0}, {}, None, "", [], {"Dreepy": 4},
        ]
        for cards in examples:
            with self.subTest(cards=cards):
                self.assertEqual(classify_dragapult("Dragapult", cards),
                                 DRAGAPULT_BASE)

    def test_existing_compound_archetypes_are_not_misidentified(self):
        for deck in ("Dragapult Dusknoir", "Dragapult Dudunsparce",
                     "Dragapult Blaziken", "Dragapult Froslass",
                     "Mega Dragapult", "Gengar"):
            self.assertEqual(classify_dragapult(
                deck, {"Crushing Hammer": 4}), deck)

    def test_standard_list_has_only_one_new_type(self):
        self.assertEqual(deck_name(DRAGAPULT_HAMMER), "クラハンドラパ")
        self.assertEqual(deck_name(DRAGAPULT_BASE), "ドラパルト")
        labels = [deck_name(classify_dragapult("Dragapult", cards))
                  for cards in (
                      {"Crushing Hammer": 4}, {"Rare Candy": 3}, None)]
        self.assertEqual(labels,
                         ["クラハンドラパ", "ドラパルト", "ドラパルト"])
        self.assertEqual(len(set(labels)), 2)

    def test_app_classification_is_unconditional_and_affects_both_sides(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        ast.parse(source)
        self.assertNotIn("split_hammer=st.checkbox(", source)
        self.assertNotIn("if split_hammer:", source)
        self.assertIn("for side in ('a','b'):", source)
        self.assertIn("df.loc[mask,deck_column]", source)
        self.assertIn("classify_dragapult('Dragapult',normalize_list(value))",
                      source)
        self.assertIn("decks=available_decks(df,region)", source)
        self.assertIn("q=perspective(df,name,region)", source)
        self.assertLess(
            source.index("# Automatically identify this as a proper deck type"),
            source.index("with st.expander('集計条件',expanded=True):"))
        self.assertIn("df=df.copy()", source)

    def test_actual_world_snapshot_contains_two_categories(self):
        hammer_sides = regular_sides = 0
        # Stream through the published CSV instead of loading all its
        # matches into memory; mirrors count one perspective for each side.
        with (ROOT / "matches_snapshot.csv").open(
                newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                for side in ("a", "b"):
                    if row["deck_" + side] != DRAGAPULT_BASE:
                        continue
                    cardlist = json.loads(
                        row["decklist_" + side] or "{}")
                    group = classify_dragapult(DRAGAPULT_BASE, cardlist)
                    if group == DRAGAPULT_HAMMER:
                        hammer_sides += 1
                    else:
                        regular_sides += 1
        self.assertGreater(hammer_sides, 10)
        self.assertGreater(regular_sides, 10)


if __name__ == "__main__":
    unittest.main()
