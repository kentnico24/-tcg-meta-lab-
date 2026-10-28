"""Domestic 7-day top-16 share × worldwide Limitless Play matchup ranking.

Only public JAPANESE CITY LEAGUE *placements* determine meta weights.
Only public WORLDWIDE LIMITLESS PLAY *matches* determine matchup results.
Never substitute international usage for Japanese share, and never infer
Swiss-round win rates from Japanese City League standings.

The algorithm uses transparent Bayesian shrinkage toward 50% and neutralizes
missing matchups. These are *decision-support scores*, not a prediction of the
user's personal win rate or an official statistical forecast.
"""
from collections import Counter, defaultdict
from datetime import date, timedelta
import re


# Deliberate, conservative common archetype identifiers. Do not conflate a
# Pokemon's generic form with Mega X/Y or N's Zoroark with generic Zoroark.
CITY_PRIMARY_OVERRIDES = {
    "dusknoir dragapult": "dragapult",
    "dudunsparce lopunny-mega": "lopunny-mega",
    "thwackey dipplin": "dipplin",
}
WORLD_PRIMARY_OVERRIDES = {
    "N's Zoroark": "n-zoroark",
    "Raging Bolt Ogerpon": "raging-bolt",
    "Basic Box": "basic-box",
    "Festival Lead": "festival-lead",
    "Other": "",  # Unclassified archetypes cannot be a recommendation.
}
PRIOR = 12.0
MIN_PAIR_SAMPLES = 4
MIN_RELEVANT_GAMES = 12
MIN_CANDIDATE_MATCHES = 35
MIN_MATCHED_SHARE = 0.20


def city_archetype(name):
    """Return a family key for the City League *usage-only* distribution."""
    if not isinstance(name, str):
        return ""
    text = " ".join(name.lower().strip().split())
    if not text:
        return ""
    return CITY_PRIMARY_OVERRIDES.get(text, text.split()[0])


def world_archetype(name):
    """Conservative cross-source family key; source deck text stays unchanged."""
    if not isinstance(name, str):
        return ""
    clean = name.strip()
    if not clean:
        return ""
    if clean in WORLD_PRIMARY_OVERRIDES:
        return WORLD_PRIMARY_OVERRIDES[clean]
    if clean.startswith("Mega "):
        parts = clean.split()
        if len(parts) >= 2:
            return re.sub(r"[^a-z0-9]+", "-", parts[1].lower()).strip("-") + "-mega"
    if clean.startswith("Rocket's "):
        parts = clean.split()
        return "rocket-" + (parts[1].lower() if len(parts) > 1 else "other")
    parts = clean.lower().split()
    if not parts:
        return ""
    head = parts[0]
    if head in ("raging", "basic", "festival") and len(parts) >= 2:
        return head + "-" + parts[1].strip("'")
    return re.sub(r"[^a-z0-9-]", "", head)


def calculate_domestic_share(city_records, as_of, days=7):
    """Share of identifiable top-16 City League *placings*, not all entrants."""
    if isinstance(as_of, str):
        as_of = date.fromisoformat(as_of)
    start = as_of - timedelta(days=days - 1)
    unique = {}
    for row in city_records:
        try:
            event_date = date.fromisoformat(str(row.get("date", ""))[:10])
        except ValueError:
            continue
        if not start <= event_date <= as_of:
            continue
        url = str(row.get("event_url", ""))
        if not url.startswith("https://limitlesstcg.com/tournaments/jp/"):
            continue
        key = str(row.get("key", "")).strip()
        deck = str(row.get("deck", "")).strip()
        family = city_archetype(deck)
        if not key or not family:
            continue
        unique[(url, key)] = (url, family, event_date)
    counts = Counter(family for _, family, _ in unique.values())
    total = sum(counts.values())
    shares = {family: count / total for family, count in counts.items()} if total else {}
    return {
        "as_of": as_of.isoformat(),
        "start": start.isoformat(),
        "end": as_of.isoformat(),
        "events": len({url for url, _, _ in unique.values()}),
        "placements": total,
        "counts": dict(counts),
        "shares": shares,
    }


def world_matchup_evidence(world_records, as_of, lookback_days=60):
    """Accumulate real worldwide match results; count each match only once."""
    if isinstance(as_of, str):
        as_of = date.fromisoformat(as_of)
    start = max(date(2026, 9, 1), as_of - timedelta(days=lookback_days - 1))
    outcomes = defaultdict(lambda: [0, 0.0])  # (candidate deck, opponent family)
    exposures = Counter()
    seen = set()
    total = 0
    for row in world_records:
        match_id = str(row.get("id", "")).strip()
        if not match_id or match_id in seen:
            continue
        try:
            match_day = date.fromisoformat(str(row.get("played_at", ""))[:10])
        except ValueError:
            continue
        if not start <= match_day <= as_of:
            continue
        source = row.get("source")
        if source is not None and not str(source).startswith("limitless-play:"):
            continue
        a = str(row.get("deck_a", "")).strip()
        b = str(row.get("deck_b", "")).strip()
        winner = str(row.get("winner", "")).strip()
        if not a or not b or a == "Other" or b == "Other":
            continue
        if winner not in {"a", "b", "draw"}:
            continue
        family_a, family_b = world_archetype(a), world_archetype(b)
        if not family_a or not family_b:
            continue
        seen.add(match_id)
        total += 1
        exposures[a] += 1
        exposures[b] += 1
        if family_a == family_b:
            # Same-family games are not reliable evidence of a counter deck.
            continue
        score_a = 0.5 if winner == "draw" else float(winner == "a")
        score_b = 1.0 - score_a
        outcomes[(a, family_b)][0] += 1
        outcomes[(a, family_b)][1] += score_a
        outcomes[(b, family_a)][0] += 1
        outcomes[(b, family_a)][1] += score_b
    return {
        "start": start.isoformat(),
        "end": as_of.isoformat(),
        "matches": total,
        "exposures": exposures,
        "outcomes": outcomes,
    }


def recommend(city_records, world_records, as_of, limit=5):
    """Rank World archetypes against domestic top-16 share, with explicit gaps.

    The 50-point neutral baseline is adjusted using only pairings with at
    least MIN_PAIR_SAMPLES real worldwide games. Sparse pairings are neutral.
    Display a separate data coverage %: unknown opponents never become
    invented wins. Candidate eligibility requires a meaningful evidence floor.
    """
    jp = calculate_domestic_share(city_records, as_of)
    world = world_matchup_evidence(world_records, as_of)
    output = {"japan": jp, "world": {
        "start": world["start"], "end": world["end"],
        "matches": world["matches"],
    }, "recommendations": [], "scored_candidates": 0}
    if jp["placements"] < 16 or jp["events"] < 2 or world["matches"] < 100:
        return output
    weights = jp["shares"]
    results = []
    for candidate, appearances in world["exposures"].items():
        if appearances < MIN_CANDIDATE_MATCHES or not world_archetype(candidate):
            continue
        score = 50.0
        represented = 0.0
        samples = 0
        relevant = []
        for family, share in weights.items():
            if family == world_archetype(candidate):
                # Against itself, a deck family is defined as 50:50.
                represented += share
                continue
            n, wins = world["outcomes"].get((candidate, family), (0, 0))
            if n < MIN_PAIR_SAMPLES:
                continue
            represented += share
            samples += n
            empirical = 100.0 * wins / n
            shrunken = 100.0 * (wins + 0.5 * PRIOR) / (n + PRIOR)
            score += share * (shrunken - 50.0)
            relevant.append({
                "family": family,
                "jp_share": round(share * 100, 1),
                "games": n,
                "wins_equivalent": wins,
                "world_win_rate": round(empirical, 1),
                "conservative_rate": round(shrunken, 1),
                "impact": round(share * (shrunken - 50.0), 2),
            })
        if samples < MIN_RELEVANT_GAMES or represented < MIN_MATCHED_SHARE:
            continue
        # Do not reward tiny datasets or broad unknown gaps with unqualified
        # high scores. Coverage and sample counts are shown separately too.
        confidence_penalty = 5.0 * (1.0 - represented)
        ranking_score = score - confidence_penalty
        relevant.sort(key=lambda x: (-x["jp_share"], x["family"]))
        results.append({
            "deck": candidate,
            "meta_score": round(score, 1),
            "ranking_score": round(ranking_score, 2),
            "world_matches": appearances,
            "matched_games": samples,
            "matched_share": round(100.0 * represented, 1),
            "evidence": relevant,
        })
    results.sort(key=lambda x: (-x["ranking_score"], -x["matched_share"],
                                -x["matched_games"], x["deck"]))
    output["recommendations"] = results[:max(0, limit)]
    output["scored_candidates"] = len(results)
    return output
