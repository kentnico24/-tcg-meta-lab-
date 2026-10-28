"""Verifiable Japanese tournament matches, kept separate from online results.

City League placements only prove the actual final between placing #1
(winner) and placing #2 (runner-up). Never invent Swiss rounds or bracket
pairings from the top-16 finishing order.

When future CL / PJCS match-by-match results are verified, ingest them via
a separate reviewed CSV. No CL outcomes are fabricated in the absence of data.
"""
import csv
from collections import defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

MATCH_COLUMNS = [
    "id", "date", "event_type", "stage", "event_name",
    "deck_a", "deck_b", "winner", "source_url",
]
TRUSTED_CL_HOSTS = {"pokemon-card.com", "www.pokemon-card.com",
                    "limitlesstcg.com", "www.limitlesstcg.com",
                    "pokekameshi.com", "www.pokekameshi.com",
                    "pokecahack.com", "www.pokecahack.com"}


def city_final_matches(rows):
    """Extract exactly one confirmed final per City League tournament.

    Ranks must be unique and both finalists must have a published deck name.
    A 1st-place deck defeated the 2nd-place deck by the structure of a
    single-elimination final; rankings 3-16 do NOT identify actual pairings.
    """
    grouped = defaultdict(list)
    for row in rows:
        url = str(row.get("event_url") or "").strip()
        if urlparse(url).netloc != "limitlesstcg.com" or "/tournaments/jp/" not in url:
            continue
        grouped[url].append(row)

    finals = []
    for url, event_rows in sorted(grouped.items()):
        champions = [r for r in event_rows if str(r.get("rank", "")).strip() == "1"]
        runners_up = [r for r in event_rows if str(r.get("rank", "")).strip() == "2"]
        if len(champions) != 1 or len(runners_up) != 1:
            continue
        champ, second = champions[0], runners_up[0]
        deck_a = str(champ.get("deck", "")).strip()
        deck_b = str(second.get("deck", "")).strip()
        date_a = str(champ.get("date", "")).strip()
        if not deck_a or not deck_b or date_a != str(second.get("date", "")).strip():
            continue
        try:
            date.fromisoformat(date_a)
        except ValueError:
            continue
        finals.append({
            "id": "city-final:" + url.rstrip("/").split("/")[-1],
            "date": date_a,
            "event_type": "シティリーグ",
            "stage": "決勝",
            "event_name": str(champ.get("shop", "")).strip() or "シティリーグ",
            "deck_a": deck_a,
            "deck_b": deck_b,
            "winner": "a",
            "source_url": url,
        })
    return finals


def read_verified_cl_matches(path):
    """Read independently confirmed CL/PJCS matches; absent file means unavailable."""
    path = Path(path)
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != MATCH_COLUMNS:
            raise ValueError("Unexpected CL match columns")
        rows = list(reader)
    seen = set()
    for row in rows:
        if (None in row or any(v is None for v in row.values())
                or not all(row[k] for k in (
                    "id", "date", "event_name", "stage", "deck_a", "deck_b",
                    "winner", "source_url"))
                or row["event_type"] not in ("CL", "PJCS")
                or row["winner"] not in ("a", "b", "draw")
                or row["id"] in seen):
            raise ValueError("Unverifiable or duplicate CL/PJCS match entry")
        seen.add(row["id"])
        try:
            date.fromisoformat(row["date"])
        except ValueError as exc:
            raise ValueError("Invalid CL/PJCS match date") from exc
        url = urlparse(row["source_url"])
        if url.scheme != "https" or url.netloc not in TRUSTED_CL_HOSTS:
            raise ValueError("CL/PJCS match must cite a trusted source page")
    return rows


def player_perspectives(matches, exclude_mirrors=True):
    """Create two observations per non-mirror match, with win/loss/draw score."""
    result = []
    for match in matches:
        a, b = match["deck_a"], match["deck_b"]
        if exclude_mirrors and a == b:
            continue
        winner = match["winner"]
        if winner not in ("a", "b", "draw"):
            continue
        score_a = 0.5 if winner == "draw" else (1.0 if winner == "a" else 0.0)
        score_b = 1.0 - score_a
        for deck, opponent, score in [(a, b, score_a), (b, a, score_b)]:
            result.append({
                "id": match["id"], "date": match["date"],
                "event_type": match["event_type"],
                "stage": match["stage"], "event_name": match["event_name"],
                "deck": deck, "opponent": opponent,
                "win": int(score == 1.0), "loss": int(score == 0.0),
                "draw": int(score == 0.5), "result": score,
                "source_url": match["source_url"],
            })
    return result
