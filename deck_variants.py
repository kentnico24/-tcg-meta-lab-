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


# The Alakazam / Lillie's Clefairy ex / Ace Canceller Genesect core is
# a verified cardlist variant, not an assertion about all Alakazam decks.
CLEFAIRY_ALAKAZAM_GENESECT = "Alakazam [Lillie's Clefairy ex + Genesect]"

_ALAKAZAM_CARD = frozenset(("alakazam", "フーディン"))
_CLEFAIRY_CARD = frozenset(("lillie's clefairy ex", "リーリエのピッピex"))
_GENESECT_CARD = frozenset(("genesect", "ゲノセクト"))


def _normalized_card_quantities(cards):
    """Return normalized, positively counted printed card names only."""
    quantities = {}
    if not isinstance(cards, dict):
        return quantities
    for name, amount in cards.items():
        card_name = " ".join(str(name).replace("’", "'").replace("‘", "'").split()).casefold()
        if not card_name or isinstance(amount, bool):
            continue
        try:
            quantity = int(amount)
        except (TypeError, ValueError, OverflowError):
            continue
        if quantity > 0:
            quantities[card_name] = quantities.get(card_name, 0) + quantity
    return quantities


def classify_clefairy_alakazam(deck, cards):
    """Separate only published Alakazam lists with the complete three-card core.

    Alakazam ex, Lillie's Clefairy without ex, Genesect ex and unlisted decks
    must not be misreported as this variant. Dudunsparce, support cards and
    quantities other than at least one of each core card are not required.
    """
    if not isinstance(deck, str):
        return deck
    if deck == CLEFAIRY_ALAKAZAM_GENESECT:
        return deck
    if deck.startswith(("Mega ", "メガ")):
        return deck
    if not (deck == "Alakazam" or deck.startswith("Alakazam ")
            or deck.endswith(" Alakazam")):
        return deck
    names = _normalized_card_quantities(cards)
    if (any(name in names for name in _ALAKAZAM_CARD)
            and any(name in names for name in _CLEFAIRY_CARD)
            and any(name in names for name in _GENESECT_CARD)):
        return CLEFAIRY_ALAKAZAM_GENESECT
    return deck
