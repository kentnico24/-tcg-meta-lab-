"""Recognize Crushing Hammer Dragapult as a first-class deck archetype.

The original Limitless Play archetype and lists remain unchanged in saved
matches. Only a verifiable Crushing Hammer inclusion creates a new category.
Other plain Dragapult matches retain their original name; unknown lists are
NOT claimed to be confirmed non-Hammer lists.
"""

DRAGAPULT_HAMMER = "Dragapult [Crushing Hammer]"
DRAGAPULT_BASE = "Dragapult"
CRUSHING_HAMMER_NAMES = frozenset(("crushing hammer", "クラッシュハンマー"))


def classify_dragapult(deck, cards):
    """Give verified Crushing Hammer Dragapult its own searchable deck type.

    The unmodified Dragapult archetype is the fallback for missing lists,
    lists without Hammer, or malformed card quantities. Compound named
    archetypes like Dragapult Dusknoir remain their original separate type.
    """
    if deck != DRAGAPULT_BASE or not isinstance(cards, dict):
        return deck
    for name, quantity in cards.items():
        if str(name).strip().casefold() not in CRUSHING_HAMMER_NAMES:
            continue
        try:
            # Booleans are not meaningful decklist quantities.
            amount = 0 if isinstance(quantity, bool) else int(quantity)
        except (ValueError, TypeError, OverflowError):
            continue
        if amount > 0:
            return DRAGAPULT_HAMMER
    return deck
