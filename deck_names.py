"""Offline Japanese deck display names, keeping Limitless storage IDs untouched.

The displayed name is built from verified Pokémon / archetype names when
possible. Unknown components keep the original English label instead of
guessing. No paid translation service or API key is required.
"""

DECK_NAMES_JA = {
    "Basic Box": "ベーシックBOX",
    "Charizard": "リザードン",
    "Festival Lead": "おまつりおんど",
    "Gardevoir": "サーナイト",
    "Gholdengo": "サーフゴー",
    "N's Zoroark": "Nのゾロアーク",
    "Other": "その他",
    "Raging Bolt": "タケルライコ",
    "Tera Box": "テラスタルBOX",
}

# Longest phrases first lets new combinations translate without adding every
# individual archetype (e.g. Dragapult Dusknoir -> ドラパルト・ヨノワール).
_COMPONENTS = {
    "Abomasnow": "ユキノオー",
    "Absol": "アブソル",
    "Alakazam": "フーディン",
    "Alolan Exeggutor": "アローラナッシー",
    "Arboliva": "オリーヴァ",
    "Audino": "タブンネ",
    "Barbaracle": "ガメノデス",
    "Beedrill": "スピアー",
    "Bellibolt": "ハラバリー",
    "Blaziken": "バシャーモ",
    "Bronzong": "ドータクン",
    "Brute Bonnet": "アラブルタケ",
    "Camerupt": "バクーダ",
    "Ceruledge": "ソウブレイズ",
    "Chandelure": "シャンデラ",
    "Cinccino": "チラチーノ",
    "Clefairy": "ピッピ",
    "Crustle": "イワパレス",
    "Cynthia's Garchomp": "シロナのガブリアス",
    "Darkrai": "ダークライ",
    "Dhelmise": "ダダリン",
    "Dragapult": "ドラパルト",
    "Dudunsparce": "ノココッチ",
    "Dusknoir": "ヨノワール",
    "Eelektrik": "シビビール",
    "Ethan's Typhlosion": "ヒビキのバクフーン",
    "Excadrill": "ドリュウズ",
    "Festival Lead": "おまつりおんど",
    "Froslass": "ユキメノコ",
    "Garchomp": "ガブリアス",
    "Gengar": "ゲンガー",
    "Gholdengo": "サーフゴー",
    "Greninja": "ゲッコウガ",
    "Grimmsnarl": "オーロンゲ",
    "Hariyama": "ハリテヤマ",
    "Honchkrow": "ドンカラス",
    "Hop's Trevenant": "ホップのオーロット",
    "Hydrapple": "カミツオロチ",
    "Hydreigon": "サザンドラ",
    "Igglybuff": "ププリン",
    "Iono's Bellibolt": "ナンジャモのハラバリー",
    "Joltik": "バチュル",
    "Lillie's Clefairy": "リーリエのピッピ",
    "Lopunny": "ミミロップ",
    "Lucario": "ルカリオ",
    "Lunatone": "ルナトーン",
    "Mamoswine": "マンムー",
    "Manectric": "ライボルト",
    "Meganium": "メガニウム",
    "Metagross": "メタグロス",
    "Mew": "ミュウ",
    "Mewtwo": "ミュウツー",
    "N's Zoroark": "Nのゾロアーク",
    "Ogerpon": "オーガポン",
    "Okidogi": "イイネイヌ",
    "Palafin": "イルカマン",
    "Raging Bolt": "タケルライコ",
    "Relicanth": "ジーランス",
    "Rocket's Honchkrow": "ロケット団のドンカラス",
    "Rocket's Mewtwo": "ロケット団のミュウツー",
    "Rocket's Spidops": "ロケット団のワナイダー",
    "Salamence": "ボーマンダ",
    "Seaking": "アズマオウ",
    "Sharpedo": "サメハダー",
    "Sinistcha": "ヤバソチャ",
    "Slowking": "ヤドキング",
    "Spidops": "ワナイダー",
    "Starmie": "スターミー",
    "Steven's Metagross": "ダイゴのメタグロス",
    "Sylveon": "ニンフィア",
    "Toucannon": "ドデカバシ",
    "Toxtricity": "ストリンダー",
    "Trevenant": "オーロット",
    "Typhlosion": "バクフーン",
    "Ursaluna": "ガチグマ",
    "Venusaur": "フシギバナ",
    "Wailord": "ホエルオー",
    "Yanmega": "メガヤンマ",
    "Zoroark": "ゾロアーク",
    "Zygarde": "ジガルデ",
    "Azumarill": "マリルリ",
    "Banette": "ジュペッタ",
    "Dipplin": "カミッチュ",
    "Flareon": "ブースター",
    "Gourgeist": "パンプジン",
    "Kangaskhan": "ガルーラ",
    "Meowth": "ニャース",
    "Munkidori": "マシマシラ",
    "Noctowl": "ヨルノズク",
    "Pecharunt": "モモワロウ",
    "Porygon2": "ポリゴン2",
    "Rayquaza": "レックウザ",
    "Roserade": "ロズレイド",
    "Solrock": "ソルロック",
    "Talonflame": "ファイアロー",
    "Thwackey": "バチンキー",
}


def deck_name(name):
    """Translate labels only; leave unknown and non-string values unchanged."""
    if not isinstance(name, str):
        return name
    if name in DECK_NAMES_JA:
        return DECK_NAMES_JA[name]
    words = name.split()
    if not words:
        return name
    translated = []
    i = 0
    while i < len(words):
        if words[i] == "Mega" and i + 1 < len(words):
            base = _COMPONENTS.get(words[i + 1])
            if base:
                translated.append("メガ" + base)
                i += 2
                continue
        if words[i] in ("Box", "ex") and translated:
            translated[-1] += "BOX" if words[i] == "Box" else "ex"
            i += 1
            continue
        match = None
        size = 0
        for n in range(min(3, len(words) - i), 0, -1):
            candidate = " ".join(words[i:i + n])
            if candidate in _COMPONENTS:
                match = _COMPONENTS[candidate]
                size = n
                break
        if match is None:
            # Preserve the whole label to avoid misleading partial translations.
            return name
        translated.append(match)
        i += size
    return "・".join(translated)


def city_deck_name(name):
    """Translate City League sprite IDs, including mega suffixes.

    This is separate from the English display-name translator because the
    City League website uses lowercase hyphenated Pokémon sprite identifiers.
    Unrecognized identifiers remain untouched; no deck names are invented.
    """
    if not isinstance(name, str) or not name.strip():
        return name
    special = {"raging-bolt": "タケルライコ", "ho-oh": "ホウオウ"}
    translated = []
    for slug in name.lower().split():
        if slug in special:
            translated.append(special[slug])
            continue
        for suffix in ("-mega-x", "-mega-y", "-mega"):
            if slug.endswith(suffix):
                base = slug[:-len(suffix)]
                japanese = deck_name(base.title())
                if japanese == base.title():
                    return name
                variant = suffix[-1].upper() if suffix in ("-mega-x", "-mega-y") else ""
                translated.append("メガ" + japanese + variant)
                break
        else:
            base = slug.replace("-", " ").title()
            japanese = deck_name(base)
            if japanese == base:
                return name
            translated.append(japanese)
    return "・".join(translated)
