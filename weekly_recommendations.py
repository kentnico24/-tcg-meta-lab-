"""Weekly Japan City League meta x worldwide Limitless Play matchups.

City League *placements* define the domestic seven-day meta weights.
Limitless Play *matches* define the (imperfect, worldwide) matchup evidence.
Never substitute international deck share or unverified City League pairings.

Deck families are deliberately conservative. Keep Mega and N's Zoroark
distinct from non-Mega and generic Zoroark. Unmatched domestic families
remain in the meta denominator and contribute a neutral 50% to predictions.
"""
from collections import Counter, defaultdict
from datetime import date, timedelta
import re

from deck_names import city_deck_name, deck_name

WORLD_DAYS = 30
LOCAL_DAYS = 7
ELIGIBILITY_DAYS = 60
MIN_PAIR_MATCHES = 5
MIN_TOTAL_MATCHES = 12
MIN_COVERAGE = 0.20
PRIOR_MATCHES = 16.0
TOP_THREATS = 12
CITY_2027_START = date(2026, 9, 25)

# Reverse-order sprite lists are explicit exceptions, not fuzzy matching.
CITY_FAMILY_OVERRIDES = {
    "dusknoir dragapult": "Dragapult",
    "dudunsparce lopunny-mega": "Mega Lopunny",
    "thwackey dipplin": "Dipplin",
    "thwackey seaking": "Seaking",
    "metagross excadrill-mega": "Metagross",
    "dusknoir clefairy": "Clefairy",
}
SPECIAL_SLUGS = {
    "raging-bolt": "Raging Bolt",
    "ho-oh": "Ho-Oh",
    "porygon2": "Porygon2",
}


def city_family(slug):
    """Map a published Japanese City League sprite to a broad deck family.

    Do not pretend detailed variants are interchangeable in match results:
    this is explicitly a broad *type-level* estimate.
    """
    if not isinstance(slug, str):
        return ""
    slug = " ".join(slug.lower().strip().split())
    if not slug or slug in ("other", "unknown"):
        return ""
    if slug in CITY_FAMILY_OVERRIDES:
        return CITY_FAMILY_OVERRIDES[slug]
    first = slug.split()[0]
    if first in SPECIAL_SLUGS:
        return SPECIAL_SLUGS[first]
    m = re.fullmatch(r"([a-z][a-z0-9-]*)-mega(?:-([xy]))?", first)
    if m:
        variant = " " + m.group(2).upper() if m.group(2) else ""
        return "Mega " + m.group(1).replace("-", " ").title() + variant
    if re.fullmatch(r"[a-z][a-z0-9-]*", first):
        return first.replace("-", " ").title()
    return ""


def worldwide_family(name):
    """Normalize stored online archetypes to the same broad name scheme.

    Never collapse N's Zoroark into Zoroark or Mega into a regular Pokemon.
    """
    if not isinstance(name, str):
        return ""
    name = " ".join(name.split())
    if not name or name == "Other" or name.lower() == "unknown":
        return ""
    if name.startswith("Mega "):
        parts = name.split()
        if len(parts) >= 2:
            return "Mega " + parts[1] + (
                " " + parts[2] if len(parts) > 2 and parts[2] in ("X", "Y") else "")
    if name.startswith("N's Zoroark"):
        return "N's Zoroark"
    if name.startswith("Raging Bolt"):
        return "Raging Bolt"
    if name.startswith("Festival Lead"):
        return "Festival Lead"
    if name.startswith("Basic Box"):
        return "Basic Box"
    return name.split()[0]


def family_label(name):
    """Japanese name for the broad type, without altering stored IDs."""
    if name.startswith("Mega "):
        pieces = name.split()
        base = deck_name(pieces[1])
        if base != pieces[1]:
            return "メガ" + base + (pieces[2] if len(pieces) == 3 else "")
    result = deck_name(name)
    return result if result != name else city_deck_name(name.lower())


def date_in_window(value, first, last):
    if not isinstance(value, str):
        return False
    try:
        day = date.fromisoformat(value[:10])
    except ValueError:
        return False
    return first <= day <= last


def domestic_meta(placements, as_of):
    """Shares use ONLY published Japan City League placements, NEVER matches."""
    start = max(CITY_2027_START, as_of - timedelta(days=LOCAL_DAYS-1))
    counts = Counter()
    days = set()
    events = set()
    unknown = 0
    seen = set()
    for r in placements:
        if not date_in_window(r.get("date", ""), start, as_of):
            continue
        key = (r.get("event_url"), r.get("key"))
        if not key[0] or not key[1] or key in seen:
            continue
        seen.add(key)
        events.add(key[0])
        days.add(r["date"][:10])
        f = city_family(r.get("deck", ""))
        if f:
            counts[f] += 1
        else:
            unknown += 1
    total = sum(counts.values())
    shares = {k: count/total for k,count in counts.items()} if total else {}
    return {"start": start, "end": as_of, "counts": counts,
            "shares": shares, "total": total,
            "unknown": unknown, "events": len(events), "days": len(days),
            "last_event": max(days) if days else None}


def worldwide_matchups(matches, as_of):
    """Only real, explicitly sourced worldwide pairings. One observation/ID.

    Results are from Limitless Play tournaments worldwide (not a sample of
    Japanese City League events). The date is UTC from the stored source;
    inclusive 30-day comparison window.
    """
    first = as_of-timedelta(days=WORLD_DAYS-1)
    counts = defaultdict(lambda: [0.0, 0])
    seen_ids = set()
    first_observed, last_observed = None, None
    kept = 0
    for r in matches:
        if not str(r.get("source","")).startswith("limitless-play:"):
            continue
        if not date_in_window(r.get("played_at",""), first, as_of):
            continue
        key = str(r.get("id",""))
        if not key or key in seen_ids:
            continue
        a = worldwide_family(r.get("deck_a", ""))
        b = worldwide_family(r.get("deck_b", ""))
        winner = str(r.get("winner","")).lower()
        if not a or not b or winner not in ("a","b","draw"):
            continue
        seen_ids.add(key)
        kept += 1
        day = r["played_at"][:10]
        if first_observed is None or day < first_observed:
            first_observed = day
        if last_observed is None or day > last_observed:
            last_observed = day
        if a == b:  # a family mirror is neutral by design; not matchup evidence.
            continue
        wa = 1.0 if winner == "a" else 0.0 if winner == "b" else 0.5
        counts[(a,b)][0] += wa
        counts[(a,b)][1] += 1
        counts[(b,a)][0] += 1-wa
        counts[(b,a)][1] += 1
    return {"pairs": dict(counts), "first": first, "end": as_of,
            "oldest_match": first_observed, "latest_match": last_observed,
            "matches": kept}


def rank_recommendations(placements, matches, as_of, n=5):
    """Rank supported domestic archetypes vs weighted last-7-day JP meta.

    Unknown matchups count 50%, observed rates are shrunk towards 50% by
    a 16-game prior. Recommendations require matchup evidence and coverage.
    Score is an *estimated suitability index*, NOT observed Japan winrate.
    """
    meta = domestic_meta(placements, as_of)
    global_stats = worldwide_matchups(matches, as_of)
    empty = {"meta": meta, "world": global_stats, "threats": [],
             "recommendations": [], "eligible": 0}
    if not meta["total"] or not global_stats["matches"]:
        return empty
    threats = sorted(meta["shares"].items(), key=lambda pair: (-pair[1], pair[0]))[:TOP_THREATS]
    # Domestic viability is observed during the current season, not inferred
    # from foreign-only wins or from nationwide player country codes.
    local_cutoff = max(CITY_2027_START, as_of-timedelta(days=ELIGIBILITY_DAYS-1))
    local_family = Counter()
    seen = set()
    for r in placements:
        if not date_in_window(r.get("date",""),local_cutoff,as_of):
            continue
        key = (r.get("event_url"),r.get("key"))
        if not key[0] or not key[1] or key in seen:
            continue
        seen.add(key)
        family = city_family(r.get("deck",""))
        if family:
            local_family[family] += 1
    candidates = []
    available = {k for pair in global_stats["pairs"] for k in pair}
    for candidate, local_count in local_family.items():
        if local_count < 2 or candidate not in available:
            continue
        predicted = 0.5
        coverage = 0.0
        sample = 0
        observed = []
        for opponent, share in threats:
            if candidate == opponent:
                # Same broad family: without build-specific data this is 50%.
                coverage += share
                continue
            wins, number = global_stats["pairs"].get((candidate,opponent),(0.0,0))
            if number < MIN_PAIR_MATCHES:
                continue
            raw = wins/number
            shrunk = (wins+0.5*PRIOR_MATCHES)/(number+PRIOR_MATCHES)
            predicted += share*(shrunk-0.5)
            coverage += share
            sample += number
            observed.append({
                "opponent": opponent, "share": share,
                "n": number, "raw": raw, "shrunk": shrunk,
                "contribution": share*(shrunk-0.5),
            })
        # Penalize missing coverage. Low sample sizes never get a 100% score.
        score = predicted - 0.015*(1.0-coverage)
        if sample < MIN_TOTAL_MATCHES or coverage < MIN_COVERAGE:
            continue
        observed.sort(key=lambda r: (-r["contribution"], -r["share"]))
        candidates.append({
            "family": candidate, "label": family_label(candidate),
            "index": max(0.0,min(1.0,score)),
            "estimate": predicted, "coverage": coverage,
            "world_n": sample, "domestic_placements": local_count,
            "strengths": [r for r in observed if r["shrunk"]>0.5][:3],
            "details": sorted(observed,key=lambda r:(-r["share"],r["opponent"])),
            "confidence": ("中" if sample>=50 and coverage>=0.55 else "低"),
        })
    candidates.sort(key=lambda x:(-x["index"],-x["coverage"],-x["world_n"],-x["domestic_placements"],x["family"]))
    return {"meta":meta, "world":global_stats,
            "threats":[{"family":f,"share":s,"count":meta["counts"][f],
                        "label":family_label(f)} for f,s in threats],
            "recommendations":candidates[:n], "eligible":len(candidates)}
