"""Incrementally collect public Japanese City League placements from Limitless TCG.

This is NOT a match feed: published placement/decklists are kept apart from
Limitless Play pairings. Do not calculate matchup win rates from placements.
"""
import argparse
import csv
from datetime import date, datetime
import os
from pathlib import Path
import re
import tempfile
import time
from urllib.parse import urljoin, urlparse
import urllib.error
import urllib.request

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
BASE = "https://limitlesstcg.com"
OUTPUT = ROOT / "city_league_results.csv"
FIELDS = ["key", "date", "prefecture", "shop", "rank", "deck",
          "player", "event_url", "decklist_url"]
EVENT_LINK = re.compile(r"^/tournaments/jp/(\d+)$")


def get_html(url, delay=2.5, attempts=3):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc not in ("limitlesstcg.com", "www.limitlesstcg.com"):
        raise ValueError("Disallowed City League URL")
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "TCGMetaLabResearch/0.4 (City-League-public-results)",
                "Accept": "text/html",
            })
            with urllib.request.urlopen(req, timeout=25) as response:
                html = response.read(3 * 1024 * 1024 + 1)
                if len(html) > 3 * 1024 * 1024:
                    raise ValueError("Unexpectedly large City League page")
                return html.decode("utf-8", errors="replace")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
            if attempt == attempts - 1:
                raise
            time.sleep(delay * (2 ** attempt))
    raise RuntimeError("Failed to fetch City League data")


def read_saved(path):
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != FIELDS:
            raise ValueError("Unexpected City League snapshot columns")
        data = {}
        for row in reader:
            if None in row or not row["key"]:
                raise ValueError("Invalid City League snapshot")
            data[row["key"]] = row
        return data


def parse_listing(html, since):
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None:
        raise ValueError("City League index: missing tournament table")
    events = []
    reached_start = False
    for tr in table.find_all("tr"):
        cells = tr.find_all("td", recursive=False)
        if len(cells) < 4:
            continue
        try:
            event_date = datetime.strptime(cells[0].get_text(strip=True), "%d %b %y").date()
        except ValueError:
            continue
        if event_date < since:
            reached_start = True
            continue
        link = next((a.get("href", "") for a in tr.find_all("a")
                     if EVENT_LINK.match(urlparse(a.get("href", "")).path)), None)
        if not link:
            continue
        relative = urlparse(link).path
        events.append({
            "id": EVENT_LINK.match(relative).group(1),
            "date": event_date.isoformat(),
            "prefecture": cells[1].get_text(" ", strip=True),
            "shop": cells[2].get_text(" ", strip=True),
            "event_url": urljoin(BASE, relative),
        })
    return events, reached_start


def deck_from_cell(cell):
    """Use explicitly present names only, never infer from player or shop."""
    texts = []
    for img in cell.find_all("img"):
        alt = (img.get("alt") or "").strip()
        src = (img.get("src") or "").lower()
        if "pokemon" not in src and "sprite" not in src:
            continue
        if alt and alt.lower() not in ("deck", "pokemon"):
            texts.append(alt)
        else:
            filename = urlparse(src).path.split("/")[-1].rsplit(".", 1)[0]
            if re.fullmatch(r"[a-z][a-z0-9_-]{1,40}", filename):
                texts.append(filename.replace("-", " ").replace("_", " ").title())
    if texts:
        return " ".join(dict.fromkeys(texts))
    label = cell.get_text(" ", strip=True)
    return label if label and len(label) < 75 and not label.isdigit() else ""


def parse_placements(html, event, limit=16):
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="striped") or soup.find("table", class_="standings")
    if table is None:
        for candidate in soup.find_all("table"):
            if len(candidate.find_all("tr")) >= 4:
                table = candidate
                break
    if table is None:
        raise ValueError("City League event missing placement table")
    result = []
    for order, tr in enumerate(table.find_all("tr")[1:]):
        cells = tr.find_all("td", recursive=False)
        if len(cells) < 3:
            continue
        try:
            rank = int(cells[0].get_text(strip=True).rstrip("."))
        except ValueError:
            continue
        if rank > limit:
            continue
        deck = deck_from_cell(cells[2])
        link_url = ""
        for cell in cells[2:]:
            for a in cell.find_all("a"):
                href = urlparse(a.get("href", "")).path
                if href.startswith("/decks/list/"):
                    link_url = urljoin(BASE, href)
        result.append({
            "key": f"{event['id']}:{order}",
            "date": event["date"],
            "prefecture": event["prefecture"],
            "shop": event["shop"],
            "rank": str(rank),
            "deck": deck,
            "player": cells[1].get_text(" ", strip=True),
            "event_url": event["event_url"],
            "decklist_url": link_url,
        })
    if not result:
        raise ValueError("City League event has no usable placings")
    return result


def save_atomic(path, records):
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", dir=path.parent,
            delete=False
        ) as stream:
            tmp = stream.name
            writer = csv.DictWriter(stream, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(sorted(records.values(), key=lambda r:
                                    (r["date"], r["key"]), reverse=True))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


def select_events(events, known_events, limit, oldest_first=False):
    """Fill the collection quota without losing new tournaments.

    During initial backfill, reserve most requests for the oldest missing
    events (September first), but still check newly published results and
    a few previously collected events. The event list is expected to be
    discovered from a bounded set of public Limitless index pages.
    """
    unique = list({e["event_url"]: e for e in events}.values())
    pending = [e for e in unique if e["event_url"] not in known_events]
    refresh = [e for e in unique if e["event_url"] in known_events]
    pending.sort(key=lambda e: (e["date"], e["id"]))
    refresh.sort(key=lambda e: (e["date"], e["id"]), reverse=True)
    if not oldest_first:
        pending.reverse()
    refresh_quota = min(3, len(refresh), limit // 10)
    recent_quota = min(5, max(0, (limit - refresh_quota) // 10)) if oldest_first else 0
    selected = pending[:max(0, limit - refresh_quota - recent_quota)]
    seen = {e["event_url"] for e in selected}
    if recent_quota:
        for e in reversed(pending):
            if len(selected) >= limit - refresh_quota:
                break
            if e["event_url"] not in seen:
                selected.append(e)
                seen.add(e["event_url"])
    for e in refresh[:refresh_quota]:
        if e["event_url"] not in seen:
            selected.append(e)
            seen.add(e["event_url"])
    for e in pending + refresh:
        if len(selected) >= limit:
            break
        if e["event_url"] not in seen:
            selected.append(e)
            seen.add(e["event_url"])
    return selected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", type=date.fromisoformat, default=date(2026, 9, 1))
    parser.add_argument("--pages", type=int, default=3)
    parser.add_argument("--max-events", type=int, default=12)
    parser.add_argument("--delay", type=float, default=3.0)
    parser.add_argument("--oldest-first", action="store_true",
                        help="Prioritize earliest missing September tournaments during backfill")
    args = parser.parse_args()
    if not 1 <= args.pages <= 20 or not 1 <= args.max_events <= 120 or args.delay < 2:
        parser.error("Unsafe City League request budget")
    records = read_saved(OUTPUT)
    known_events = {row["event_url"] for row in records.values()}
    events = []
    for page in range(1, args.pages + 1):
        html = get_html(f"{BASE}/tournaments/jp?show=100&page={page}",
                        delay=args.delay)
        found, reached = parse_listing(html, args.since)
        events.extend(found)
        if reached or not found:
            break
        time.sleep(args.delay)
    selected = select_events(events, known_events, args.max_events,
                             oldest_first=args.oldest_first)
    print(f"City League index: {len({e['event_url'] for e in events})} tournaments "
          f"since {args.since}; {len(known_events)} already saved; "
          f"selected {len(selected)}; {'oldest-first' if args.oldest_first else 'newest-first'}",
          flush=True)
    if not selected:
        print("No new City League events in index")
        return
    successes = 0
    for event in selected:
        try:
            html = get_html(event["event_url"], delay=args.delay)
            parsed = parse_placements(html, event)
            # Use known non-empty deck info when a later page is incomplete.
            for row in parsed:
                old = records.get(row["key"])
                if old and old["deck"] and not row["deck"]:
                    row["deck"] = old["deck"]
                if old and old["decklist_url"] and not row["decklist_url"]:
                    row["decklist_url"] = old["decklist_url"]
                records[row["key"]] = row
            successes += 1
            print(f"City League {event['date']} {event['prefecture']}: {len(parsed)} placements", flush=True)
        except (ValueError, urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            print(f"::warning::City League {event['id']}: {exc}", flush=True)
        time.sleep(args.delay)
    if successes == 0:
        if not selected:
            return
        raise RuntimeError("No City League event fetched; leaving prior results unchanged")
    save_atomic(OUTPUT, records)
    print(f"Saved {len(records)} City League placements from "
          f"{len({r['event_url'] for r in records.values()})} tournaments", flush=True)


if __name__ == "__main__":
    main()
