"""Coverage and safety checks for Japanese display-only deck labels."""
import unittest
from deck_names import deck_name


# The 78 archetypes present in the initial 1,028-match production snapshot.
# Keep this fixture stable so unseen future labels may still fall back to English.
KNOWN_2026_DECKS = (
    "Dragapult",
    "Other",
    "Dhelmise",
    "Basic Box",
    "Slowking",
    "Alakazam Dudunsparce",
    "N's Zoroark",
    "Ogerpon Meganium Hydrapple",
    "Dragapult Blaziken",
    "Mega Excadrill",
    "Sharpedo Toxtricity",
    "Dragapult Dusknoir",
    "Mega Lucario",
    "Crustle",
    "Alakazam Dusknoir",
    "Festival Lead",
    "Absol Audino",
    "Lopunny Dudunsparce",
    "Rocket's Mewtwo",
    "Okidogi Barbaracle",
    "Mega Greninja",
    "Lucario Hariyama",
    "Grimmsnarl Froslass",
    "Mew Box",
    "Raging Bolt Ogerpon",
    "Igglybuff",
    "Lopunny Dusknoir",
    "Blaziken",
    "Rocket's Honchkrow",
    "Beedrill",
    "Cynthia's Garchomp",
    "Ogerpon Meganium Arboliva",
    "Dragapult Dudunsparce",
    "Gengar",
    "Cinccino",
    "Ethan's Typhlosion",
    "Mega Darkrai",
    "Steven's Metagross",
    "Mega Starmie",
    "Hop's Trevenant",
    "Ceruledge",
    "Mega Lopunny",
    "Greninja",
    "Mega Froslass",
    "Seaking Festival Lead",
    "Toxtricity",
    "Ursaluna Lunatone",
    "Toucannon",
    "Mega Zygarde",
    "Mega Venusaur",
    "Joltik Box",
    "Rocket's Spidops",
    "Mega Camerupt",
    "Iono's Bellibolt",
    "Palafin",
    "Relicanth",
    "Manectric Eelektrik",
    "Yanmega",
    "Sinistcha Ogerpon",
    "Mega Abomasnow",
    "Starmie Froslass",
    "Toxtricity Brute Bonnet",
    "Sylveon",
    "Mega Absol Box",
    "Hydreigon",
    "Mega Chandelure",
    "Mega Gengar",
    "Salamence",
    "Alakazam",
    "Bronzong",
    "Ogerpon Meganium",
    "Eelektrik",
    "Mamoswine",
    "Tera Box",
    "Alolan Exeggutor ex",
    "Wailord",
    "Lillie's Clefairy",
    "Toxtricity Box",
)


class DeckNamesTests(unittest.TestCase):
    def test_all_original_archetypes_have_japanese_labels(self):
        self.assertEqual(len(KNOWN_2026_DECKS), 78)
        for name in KNOWN_2026_DECKS:
            with self.subTest(name=name):
                self.assertNotEqual(deck_name(name), name)
                self.assertTrue(deck_name(name))

    def test_composite_names_translate_without_per_deck_entries(self):
        examples = {
            "Absol Audino": "アブソル・タブンネ",
            "Alakazam Dudunsparce": "フーディン・ノココッチ",
            "Alakazam Dusknoir": "フーディン・ヨノワール",
            "Dragapult Dusknoir": "ドラパルト・ヨノワール",
            "Ogerpon Meganium Hydrapple": "オーガポン・メガニウム・カミツオロチ",
            "Mega Excadrill": "メガドリュウズ",
            "Alolan Exeggutor ex": "アローラナッシーex",
            "Mew Box": "ミュウBOX",
            "Rocket's Honchkrow": "ロケット団のドンカラス",
            "Festival Lead": "おまつりおんど",
        }
        for english, japanese in examples.items():
            with self.subTest(name=english):
                self.assertEqual(deck_name(english), japanese)

    def test_unknown_names_are_not_guessed(self):
        for name in ("Unreleased Archetype", "Dragapult Unknown", "", "Other Unreleased"):
            self.assertEqual(deck_name(name), name)
        self.assertIsNone(deck_name(None))


if __name__ == "__main__":
    unittest.main()
