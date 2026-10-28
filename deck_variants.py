"""Optional card-inclusion-based subtyping for the plain Dragapult deck.

The raw Limitless archetype name remains unchanged in stored snapshots.
All labels here are local, per-match perspectives only.
"""

DRAGAPULT_HAMMER = "Dragapult [Crushing Hammer]"
DRAGAPULT_NO_HAMMER = "Dragapult [No Crushing Hammer]"
DRAGAPULT_UNVERIFIED = "Dragapult [List Unknown]"
CRUSHING_HAMMER_NAMES = frozenset(("crushing hammer", "クラッシュハンマー"))


def classify_dragapult(deck, cards):
    """Split ONLY plain Dragapult; leave other named combinations unchanged.

    cards is a normalized nonempty {card_name: quantity} mapping. A missing or
    invalid list is *not* assumed to contain zero Crushing Hammers.
    """
    if deck != "Dragapult":
        return deck
    if not isinstance(cards, dict) or not cards:
        return DRAGAPULT_UNVERIFIED
    usable = False
    hammers = 0
    for key, qty in cards.items():
        try:
            number = int(qty)
        except (TypeError, ValueError, OverflowError):
            continue
        if number < 0:
            continue
        usable = usable or number > 0
        if str(key).strip().casefold() in CRUSHING_HAMMER_NAMES:
            hammers += number
    if not usable:
        return DRAGAPULT_UNVERIFIED
    return DRAGAPULT_HAMMER if hammers > 0 else DRAGAPULT_NO_HAMMER
