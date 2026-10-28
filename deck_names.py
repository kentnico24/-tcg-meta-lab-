"""Display-only aliases. Add English API names here; stored keys stay unchanged."""
DECK_NAMES_JA = {
    'Basic Box': 'ベーシックBOX',
    'Dragapult': 'ドラパルト',
    'Gholdengo': 'サーフゴー',
    "N's Zoroark": 'Nのゾロアーク',
    'Charizard': 'リザードン',
    'Gardevoir': 'サーナイト',
    'Raging Bolt': 'タケルライコ',
    'Other': 'その他',
}


def deck_name(name):
    return DECK_NAMES_JA.get(name, name)
