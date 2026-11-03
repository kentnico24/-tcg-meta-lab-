"""Sync public Limitless Play PTCG matches and submitted decklists into the app database."""
import argparse
import os
import json
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from snapshot_store import restore, preferred_snapshot
from country_store import (initialize as initialize_countries,
                           upsert_countries, restore_countries)
from region_labels import normalize_country

BASE = 'https://play.limitlesstcg.com/api'
DB = Path(os.environ.get('TCG_DB_PATH', str(Path(__file__).with_name('research.sqlite3'))))
DEADLINE = float('inf')
NEXT_REQUEST = 0.0
REQUEST_DELAY = 2.0

def pause(seconds):
    if time.monotonic() + seconds >= DEADLINE:
        raise TimeoutError('Sync runtime budget exhausted')
    time.sleep(seconds)


COLUMNS = '(id,event,played_at,deck_a,deck_b,winner,decklist_a,decklist_b,source)'


def fetch(path, params=None, attempts=4):
    global NEXT_REQUEST
    url = BASE + path + ('?' + urllib.parse.urlencode(params) if params else '')
    for attempt in range(attempts):
        pause(max(0, NEXT_REQUEST - time.monotonic()))
        try:
            NEXT_REQUEST = time.monotonic() + REQUEST_DELAY
            req = urllib.request.Request(url, headers={'User-Agent': 'TCGMetaLabResearch/0.3 (public API)', 'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=max(0.1, min(35, DEADLINE - time.monotonic()))) as response:
                return json.load(response)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            if isinstance(exc, urllib.error.HTTPError) and exc.code not in (429, 500, 502, 503, 504):
                raise
            if attempt == attempts - 1:
                raise
            pause(min(30, 2 ** attempt * 3))


def cards(decklist):
    """Normalize common Limitless PTCG list shapes; unknown structures remain empty."""
    result = {}
    if isinstance(decklist, dict):
        if isinstance(decklist.get('cards'), (list, dict)):
            return cards(decklist['cards'])
        if all(isinstance(v, (int, float)) for v in decklist.values()):
            return {str(k): int(v) for k, v in decklist.items() if int(v) > 0}
        for value in decklist.values():
            sub = cards(value)
            for name, qty in sub.items():
                result[name] = result.get(name, 0) + qty
    elif isinstance(decklist, list):
        for item in decklist:
            if not isinstance(item, dict):
                continue
            name = item.get('name') or (item.get('card') or {}).get('name') if isinstance(item.get('card'), dict) else item.get('name')
            qty = item.get('count', item.get('quantity', 0))
            if name and str(qty).isdigit():
                result[str(name)] = result.get(str(name), 0) + int(qty)
            else:
                for key in ('cards', 'pokemon', 'trainer', 'energy'):
                    if key in item:
                        for n, q in cards(item[key]).items():
                            result[n] = result.get(n, 0) + q
    return result


def initialize(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS games(id TEXT PRIMARY KEY,event TEXT,played_at TEXT,deck_a TEXT,deck_b TEXT,winner TEXT,decklist_a TEXT,decklist_b TEXT,source TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS synced_tournaments(id TEXT PRIMARY KEY, date TEXT, synced_at TEXT, matches INTEGER)''')
    initialize_countries(conn)
    conn.commit()


def sync_tournament(conn, t, delay):
    tid = str(t['id'])
    standings = fetch(f'/tournaments/{tid}/standings')
    pause(delay)
    pairings = fetch(f'/tournaments/{tid}/pairings')
    pause(delay)
    if not isinstance(standings, list) or not isinstance(pairings, list):
        raise ValueError('Invalid tournament response')
    if any(not isinstance(m, dict) for m in pairings):
        raise ValueError('Invalid pairing')
    players = {str(p['player']): p for p in standings if isinstance(p, dict) and p.get('player') is not None}
    existing = {(r[0].rsplit(':', 1)[0] if len(r[0].split(':')) == 5 else r[0]): r[0] for r in conn.execute(
        'SELECT id FROM games WHERE source=?', ('limitless-play:' + tid,))}
    rows = []
    regions = []
    for idx, match in enumerate(pairings):
        a, b = str(match.get('player1') or ''), str(match.get('player2') or '')
        winner = str(match.get('winner', ''))
        if not a or not b or a == b or a not in players or b not in players:
            continue
        if winner not in (a, b, '0'):
            continue
        pa, pb = players[a], players[b]
        da, db = pa.get('deck') or {}, pb.get('deck') or {}
        deck_a = da.get('name') or da.get('id') if isinstance(da, dict) else None
        deck_b = db.get('name') or db.get('id') if isinstance(db, dict) else None
        if not deck_a or not deck_b:
            continue
        outcome = 'draw' if winner == '0' else ('a' if winner == a else 'b')
        key = f"{tid}:{match.get('phase',0)}:{match.get('round',0)}:{match.get('table',match.get('match',idx))}:{idx}"
        prefix = key.rsplit(':', 1)[0]
        # Reuse legacy IDs (which included a response-order suffix).
        key = existing.get(prefix, prefix) if ('table' in match or 'match' in match) else (
            f"{tid}:{match.get('phase',0)}:{match.get('round',0)}:players:{':'.join(sorted((a,b)))}")
        rows.append((key, t.get('name', tid), t.get('date', ''), deck_a, deck_b, outcome,
                     json.dumps(cards(pa.get('decklist')), ensure_ascii=False),
                     json.dumps(cards(pb.get('decklist')), ensure_ascii=False), 'limitless-play:' + tid))
        regions.append((key, normalize_country(pa.get('country')),
                        normalize_country(pb.get('country'))))
    if len({r[0] for r in rows}) != len(rows):
        raise ValueError('Ambiguous duplicate match keys for tournament ' + tid)
    # Merge atomically and reject incomplete refreshes.
    previous = conn.execute('SELECT COUNT(*) FROM games WHERE source=?', ('limitless-play:' + tid,)).fetchone()[0]
    if previous > len({r[0] for r in rows}):
        raise ValueError('Refusing reduced refresh for tournament ' + tid)
    with conn:
        conn.executemany(f'INSERT OR REPLACE INTO games {COLUMNS} VALUES (?,?,?,?,?,?,?,?,?)', rows)
        upsert_countries(conn, regions)
        conn.execute('INSERT OR REPLACE INTO synced_tournaments VALUES (?,?,datetime("now"),?)', (tid, t.get('date', ''), len(rows)))
    return len(rows)


def select_events(events, known_ids, limit, now=None, latest_days=0, today=None):
    """Order all eligible tournaments: recent first, then historical, then rechecks.

    With latest_days > 0, the tournament count is unlimited when limit=0.
    Retry cooldowns prevent repeatedly broken tournaments from blocking progress.
    The old limited scheduling remains available for legacy/manual invocations.
    """
    now = time.time() if now is None else now
    eligible = [t for t in events.values()
                if t.get('retry_after', 0) <= now]
    pending = [t for t in eligible
               if str(t['id']) not in known_ids and not t.get('checked')]

    if latest_days:
        today = today or datetime.now(ZoneInfo('Asia/Tokyo')).date()
        cutoff = today - timedelta(days=latest_days - 1)
        recent = lambda t: date.fromisoformat(str(t['date'])[:10]) >= cutoff
        pending_ids = {str(t['id']) for t in pending}
        recent_pending = sorted((t for t in pending if recent(t)),
                                key=lambda t: (t['date'], str(t['id'])), reverse=True)
        historical_pending = sorted((t for t in pending if not recent(t)),
                                    key=lambda t: (t['date'], str(t['id'])))
        # Recent results can gain pairings after first publication: recheck once
        # per JST day, before spending remaining runtime on historical backlog.
        to_recheck = [t for t in eligible
                      if str(t['id']) not in pending_ids
                      and str(t.get('checked', ''))[:10] < today.isoformat()]
        recent_rechecks = sorted((t for t in to_recheck if recent(t)),
                                 key=lambda t: (t.get('checked', ''), t['date'], str(t['id'])))
        historical_rechecks = sorted((t for t in to_recheck if not recent(t)),
                                     key=lambda t: (t.get('checked', ''), t['date'], str(t['id'])))
        selected = recent_pending + recent_rechecks + historical_pending + historical_rechecks
        return selected[:limit] if limit else selected

    pending.sort(key=lambda t: (t['date'], str(t['id'])))
    rechecks = sorted((t for t in eligible if t not in pending),
                      key=lambda t: (t.get('checked', ''), t['date'], str(t['id'])))
    refresh_slots = min(len(rechecks), max(1, limit // 5), limit - 1) if pending else limit
    selected = pending[:max(0, limit - refresh_slots)] + rechecks[:refresh_slots]
    selected_ids = {str(t['id']) for t in selected}
    for t in pending + rechecks:
        if len(selected) >= limit:
            break
        if str(t['id']) not in selected_ids:
            selected.append(t)
            selected_ids.add(str(t['id']))
    return selected


def main():
    global DEADLINE, REQUEST_DELAY
    parser = argparse.ArgumentParser()
    parser.add_argument('--pages', type=int, default=2)
    parser.add_argument('--limit', type=int, default=50)
    parser.add_argument('--recent-pages', type=int, default=0,
                        help='Legacy fixed count of newest discovery pages')
    parser.add_argument('--latest-days', type=int, default=0,
                        help='Prioritize every discoverable event from the last N JST days')
    parser.add_argument('--max-tournaments', type=int, default=10,
                        help='Maximum events per run; 0 means no count cap')
    parser.add_argument('--caught-up-refresh', type=int, default=25,
                        help='Maximum daily rechecks once the entire season is discovered and initial backlog is cleared')
    parser.add_argument('--delay', type=float, default=2.0)
    parser.add_argument('--refresh', action='store_true', help='Compatibility: existing events are always rechecked')
    parser.add_argument('--since', type=date.fromisoformat, default=date(2026, 9, 1))
    parser.add_argument('--max-seconds', type=float, default=600)
    parser.add_argument('--state', type=Path, default=Path(__file__).with_name('sync_state.json'))
    args = parser.parse_args()
    if args.pages < 1 or args.recent_pages < 0 or args.latest_days < 0 or args.limit < 1 or args.max_tournaments < 0 or args.caught_up_refresh < 1 or args.max_seconds <= 0:
        parser.error('Collection limits must be positive')
    REQUEST_DELAY = max(1.0, args.delay)
    DEADLINE = time.monotonic() + args.max_seconds
    DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB, timeout=30) as conn:
        initialize(conn)
        restored = restore(conn, preferred_snapshot(Path(__file__).parent))
        print(f'Restored {restored} snapshot matches', flush=True)
        restored_regions = restore_countries(
            conn, Path(__file__).with_name('match_countries.csv'))
        print(f'Restored {restored_regions} player-country annotations', flush=True)
        state = json.loads(args.state.read_text()) if args.state.exists() else {'page': 1, 'events': {}}
        events = state['events']
        # Snapshot sources are also eligible for later corrections on fresh runners.
        for tid, event, played_at in conn.execute("SELECT substr(source,16),event,played_at FROM games WHERE source LIKE 'limitless-play:%' GROUP BY source"):
            events.setdefault(tid, {'id': tid, 'name': event, 'date': played_at, 'checked': ''})
        known_ids = {str(row[0]) for row in conn.execute(
            "SELECT DISTINCT substr(source, 16) FROM games "
            "WHERE source LIKE 'limitless-play:%'")}
        cursor = max(1, int(state.get('page', 1)))
        today_jst = datetime.now(ZoneInfo('Asia/Tokyo')).date()
        latest_cutoff = (max(args.since, today_jst - timedelta(days=args.latest_days - 1))
                         if args.latest_days else None)

        def discover_page(page):
            tournaments = fetch('/tournaments', {
                'game': 'PTCG', 'format': 'STANDARD', 'page': page,
                'limit': min(100, args.limit)})
            if not isinstance(tournaments, list):
                raise ValueError('Invalid tournaments response')
            reached_start = not tournaments
            crossed_latest = not tournaments
            for t in tournaments:
                if not isinstance(t, dict) or not t.get('id') or not t.get('date'):
                    raise ValueError('Invalid tournament metadata')
                event_date = date.fromisoformat(str(t['date'])[:10])
                if latest_cutoff and event_date < latest_cutoff:
                    crossed_latest = True
                if event_date < args.since:
                    reached_start = True
                    continue
                tid = str(t['id'])
                previous = events.get(tid, {})
                events[tid] = {
                    **t,
                    'checked': previous.get('checked', ''),
                    'failures': previous.get('failures', 0),
                    'retry_after': previous.get('retry_after', 0),
                }
            return reached_start, crossed_latest

        # Discover *all* recent pages, not just the first 50 events. Preserve
        # enough of the 20-minute budget to actually retrieve pairings.
        recent_scanned = set()
        boundary_reached = False
        if latest_cutoff:
            scan_until = time.monotonic() + min(180, args.max_seconds / 4)
            page = 1
            while time.monotonic() < scan_until and time.monotonic() + 60 < DEADLINE:
                reached_start, crossed_latest = discover_page(page)
                recent_scanned.add(page)
                boundary_reached |= reached_start
                if crossed_latest or reached_start:
                    break
                page += 1

        # Continue the saved historical discovery cursor; avoid duplicate reads
        # of pages already scanned in the recent phase.
        pages = list(range(1, args.recent_pages + 1))
        pages.extend(p for p in range(cursor, cursor + args.pages)
                     if p not in pages)
        next_cursor = cursor
        for page in pages:
            if page in recent_scanned:
                if page >= cursor:
                    next_cursor = page + 1
                continue
            if time.monotonic() + 60 >= DEADLINE:
                print('Discovery time budget exhausted; syncing known events', flush=True)
                break
            reached_start, _ = discover_page(page)
            if page >= cursor:
                next_cursor = 1 if reached_start else page + 1
            if reached_start:
                boundary_reached = True
                if page < cursor:
                    next_cursor = 1
                break
        state['page'] = next_cursor
        state['season_boundary_seen'] = bool(state.get('season_boundary_seen') or boundary_reached)

        eligible = {tid: t for tid, t in events.items()
                    if date.fromisoformat(str(t['date'])[:10]) >= args.since}
        pending_count = sum(1 for t in eligible.values()
                            if str(t['id']) not in known_ids and not t.get('checked'))
        quota = args.max_tournaments
        if state['season_boundary_seen'] and pending_count == 0:
            quota = min(quota, args.caught_up_refresh)
        selected = select_events(eligible, known_ids, quota,
                                 latest_days=args.latest_days, today=today_jst)
        successes = 0
        failures = 0
        for t in selected:
            if time.monotonic() + 15 >= DEADLINE:
                print('Runtime budget nearly exhausted; remaining events will be retried', flush=True)
                break
            try:
                count = sync_tournament(conn, t, REQUEST_DELAY)
            except Exception as exc:
                # Do not lose successful events because one event is temporarily
                # inaccessible, changed layout, or has an incomplete response.
                failures += 1
                attempts = min(20, int(t.get('failures', 0)) + 1)
                cooldown = min(7 * 86400, 6 * 3600 * 2 ** min(5, attempts - 1))
                t['failures'] = attempts
                t['retry_after'] = int(time.time() + cooldown)
                error = str(exc).replace('\n', ' ')[:250]
                print(f"::warning::Tournament {t['id']} failed ({type(exc).__name__}): {error}", flush=True)
                if time.monotonic() >= DEADLINE:
                    break
                continue
            successes += 1
            t['checked'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            t['failures'] = 0
            t['retry_after'] = 0
            print(f"{t['id']}: {count} usable matches", flush=True)
        total, oldest, newest = conn.execute(
            'SELECT COUNT(*), MIN(played_at), MAX(played_at) FROM games').fetchone()
        state['last_sync'] = {
            'at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'saved_matches': total,
            'oldest_match_date': str(oldest or '')[:10],
            'newest_match_date': str(newest or '')[:10],
            'discovered_tournaments': len(eligible),
            'checked_tournaments': sum(bool(t.get('checked')) for t in eligible.values()),
            'pending_tournaments': sum(not t.get('checked') for t in eligible.values()),
            'latest_cutoff_jst': latest_cutoff.isoformat() if latest_cutoff else None,
            'latest_pending_tournaments': sum(not t.get('checked') and date.fromisoformat(str(t['date'])[:10]) >= latest_cutoff for t in eligible.values()) if latest_cutoff else None,
            'successful_tournaments': successes,
            'failed_tournaments': failures,
        }
        # Persist the successful work even if some individual tournaments failed.
        # The subsequent exporter refuses to remove any pre-existing match IDs.
        temp = args.state.with_suffix('.tmp')
        temp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n',
                        encoding='utf-8')
        os.replace(temp, args.state)
        print(f'Sync finished: {successes} successful, {failures} failed, '
              f'{len(eligible)} eligible tournaments, {total} saved matches; '
              f'oldest={str(oldest or "")[:10]}', flush=True)



if __name__ == '__main__':
    main()
