"""Select actual Japanese City League decklist examples for weekly picks.

No deck contents are fabricated. Exact published Limitless list links are
presented as external references. They are separate from worldwide win rates.
"""
from datetime import date, timedelta
import re
from urllib.parse import urlparse

from deck_names import city_deck_name
from weekly_recommendations import CITY_2027_START, city_family, valid_city_event


def trusted_list_url(value):
    """Accept only a real-looking Limitless Japanese deck-list URL."""
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return (parsed.scheme == "https"
            and parsed.netloc == "limitlesstcg.com"
            and re.fullmatch(r"/decks/list/jp/[0-9]+/?", parsed.path) is not None
            and not parsed.query and not parsed.fragment)


def select_domestic_decklists(placements, family, as_of, limit=3, days=60):
    """Return recent published Japanese deck lists matching a recommended family.

    The suggestion ranks broad deck *families*, not exact 60-card builds.
    These links are examples with tournament metadata, never claimed to be
    the exact list that produced the worldwide matchup percentages.
    """
    if not family or not isinstance(as_of, date) or limit < 1 or days < 1:
        return []
    start = max(CITY_2027_START, as_of - timedelta(days=days - 1))
    found = []
    seen_urls = set()
    for row in placements:
        if city_family(row.get("deck", "")) != family:
            continue
        event = row.get("event_url", "")
        url = row.get("decklist_url", "")
        if not valid_city_event(event) or not trusted_list_url(url):
            continue
        try:
            day = date.fromisoformat(str(row.get("date", "")).strip())
            rank = int(str(row.get("rank", "")).strip())
        except (ValueError, TypeError):
            continue
        if not (start <= day <= as_of and 1 <= rank <= 16):
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)
        found.append({
            "date": day.isoformat(),
            "rank": rank,
            "deck": city_deck_name(row.get("deck", "")),
            "shop": str(row.get("shop") or "").strip(),
            "player": str(row.get("player") or "").strip(),
            "event_url": event,
            "decklist_url": url,
        })
    # A current result is preferred, with good placements breaking date ties.
    found.sort(key=lambda r: (r["date"], -r["rank"], r["decklist_url"]),
               reverse=True)
    # Show different tournaments if possible, rather than three from one shop.
    selected = []
    used_events = set()
    for record in found:
        if record["event_url"] not in used_events:
            selected.append(record)
            used_events.add(record["event_url"])
            if len(selected) == limit:
                return selected
    used_urls = {record["decklist_url"] for record in selected}
    for record in found:
        if record["decklist_url"] not in used_urls:
            selected.append(record)
            used_urls.add(record["decklist_url"])
            if len(selected) == limit:
                break
    return selected
