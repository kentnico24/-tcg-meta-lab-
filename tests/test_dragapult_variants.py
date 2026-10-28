"""Safety checks for the optional Crushing Hammer Dragapult grouping."""
import ast
import csv
import json
from pathlib import Path
import unittest

from deck_names import deck_name
from deck_variants import (
    classify_dragapult, DRAGAPULT_HAMMER,
    DRAGAPULT_NO_HAMMER, DRAGAPULT_UNVERIFIED,
)

ROOT = Path(__file__).resolve().parents[1]


class CrushingHammerDragapultTests(unittest.TestCase):
    def test_plain_dragapult_adoption_variants(self):
        hammer = {"Dreepy": 4, "Dragapult ex": 3, "Crushing Hammer": 4}
        no_hammer = {"Dreepy": 4, "Dragapult ex": 3, "Rare Candy": 3}
        self.assertEqual(classify_dragapult("Dragapult", hammer),
                         DRAGAPULT_HAMMER)
        self.assertEqual(classify_dragapult("Dragapult", no_hammer),
                         DRAGAPULT_NO_HAMMER)
        self.assertEqual(classify_dragapult("Dragapult", {
            "Dreepy": 4, "Crushing Hammer": 0}), DRAGAPULT_NO_HAMMER)
        self.assertEqual(classify_dragapult("Dragapult", {
            "Dreepy": 4, "クラッシュハンマー": "1"}), DRAGAPULT_HAMMER)
        self.assertEqual(classify_dragapult("Dragapult", {
            "Dreepy": 4, " CRUSHING HAMMER ": 2}), DRAGAPULT_HAMMER)

    def test_missing_cards_are_not_assumed_to_have_zero_hammers(self):
        for unknown in ("", None, [], {}, {"Crushing Hammer": 0}, {
                "Crushing Hammer": "invalid"}):
            with self.subTest(unknown=unknown):
                self.assertEqual(classify_dragapult("Dragapult", unknown),
                                 DRAGAPULT_UNVERIFIED)

    def test_compound_dragapult_archetypes_remain_distinct(self):
        for deck in (
            "Dragapult Dusknoir", "Dragapult Dudunsparce",
            "Dragapult Blaziken", "Dragapult Froslass",
            "Mega Dragapult", "Gengar"):
            with self.subTest(deck=deck):
                self.assertEqual(classify_dragapult(
                    deck, {"Crushing Hammer": 4}), deck)

    def test_japanese_labels_are_explicit(self):
        self.assertEqual(deck_name(DRAGAPULT_HAMMER), "クラハンドラパ")
        self.assertEqual(deck_name(DRAGAPULT_NO_HAMMER),
                         "ドラパルト（クラハン非採用）")
        self.assertEqual(deck_name(DRAGAPULT_UNVERIFIED),
                         "ドラパルト（採用不明）")

    def test_app_labels_both_pairing_sides_without_editing_csv(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        ast.parse(source)
        self.assertIn("split_hammer=st.checkbox(", source)
        self.assertIn("for side in ('a','b'):", source)
        self.assertIn("df.loc[mask,deck_column]", source)
        self.assertIn("classify_dragapult('Dragapult',normalize_list(value))",
                      source)
        self.assertIn("df=df.copy()", source)

    def test_actual_world_snapshot_contains_both_variants(self):
        hammer = no_hammer = 0
        with (ROOT / "matches_snapshot.csv").open(
                newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                for side in ("a", "b"):
                    if row["deck_" + side] != "Dragapult":
                        continue
                    cardlist = json.loads(row["decklist_" + side] or "{}")
                    variant = classify_dragapult("Dragapult", cardlist)
                    if variant == DRAGAPULT_HAMMER:
                        hammer += 1
                    elif variant == DRAGAPULT_NO_HAMMER:
                        no_hammer += 1
        self.assertGreater(hammer, 10)
        self.assertGreater(no_hammer, 10)


if __name__ == "__main__":
    unittest.main()
