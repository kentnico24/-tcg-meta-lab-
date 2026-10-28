"""Explicit Dragapult Crushing Hammer decklist-based archetype split.

Only a complete public 60-card list can prove an absence of Crushing Hammer.
An unknown or partial list never silently becomes a non-Hammer Dragapult.
Variants are assigned *per player in each actual match*, so each match
remains counted once from each perspective, with no fabricated outcomes.
"""
import json
import unicodedata

DRAGAPULT_HAMMER = "Dragapult Crushing Hammer"
DRAGAPULT_NON_HAMMER = "Dragapult Without Crushing Hammer"
DRAGAPULT_UNKNOWN = "Dragapult Decklist Unknown"

DRAGAPULT_CLASSIFICATION_OPTIONS = (
    "クラハン採用で分類",
    "従来のデッキタイプ別",
)

_HAMMER_CARD_NAMES = {"crushing hammer", "クラッシュハンマー"}


def is_dragapult_archetype(name):
    """Match all Limitless Dragapult subtypes, but not unrelated decks."""
    return isinstance(name, str) and (
        name == "Dragapult" or name.startswith("Dragapult "))


def _complete_card_counts(decklist):
    """Extract a published 60-card dictionary or return None for uncertainty."""
    if isinstance(decklist, str):
        if not decklist.strip():
            return None
        try:
            decklist = json.loads(decklist)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
    if not isinstance(decklist, dict) or not decklist:
        return None
    result = {}
    for name, amount in decklist.items():
        if not isinstance(name, str) or not name.strip():
            return None
        if isinstance(amount, bool):
            return None
        try:
            quantity = int(amount)
        except (TypeError, ValueError, OverflowError):
            return None
        if str(amount) != str(quantity) or quantity <= 0:
            return None
        key = unicodedata.normalize("NFKC", name).strip().casefold()
        result[key] = result.get(key, 0) + quantity
    if sum(result.values()) != 60:
        return None
    return result


def classify_dragapult(name, decklist):
    """Tag a *single player's* archetype from the actual submitted 60 cards."""
    if not is_dragapult_archetype(name):
        return name
    cards = _complete_card_counts(decklist)
    if cards is None:
        return DRAGAPULT_UNKNOWN
    if any(cards.get(key, 0) >= 1 for key in _HAMMER_CARD_NAMES):
        return DRAGAPULT_HAMMER
    return DRAGAPULT_NON_HAMMER


def classify_match_decks(df):
    """Return a copy with both sides tagged, preserving IDs, winners and lists.

    Expects a pandas DataFrame in the main app but avoids a pandas import,
    allowing dependency-light unit tests for the classification itself.
    """
    categorized = df.copy()
    categorized["deck_a"] = [
        classify_dragapult(name, cards)
        for name, cards in zip(df["deck_a"], df["decklist_a"])
    ]
    categorized["deck_b"] = [
        classify_dragapult(name, cards)
        for name, cards in zip(df["deck_b"], df["decklist_b"])
    ]
    return categorized
