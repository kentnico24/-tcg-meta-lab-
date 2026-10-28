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
from datetime import date
from snapshot_store import restore

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
    # Merge atomically and reject incomplete refreshes.
    previous = conn.execute('SELECT COUNT(*) FROM games WHERE source=?', ('limitless-play:' + tid,)).fetchone()[0]
    if previous > len({r[0] for r in rows}):
        raise ValueError('Refusing reduced refresh for tournament ' + tid)
    with conn:
        conn.executemany(f'INSERT OR REPLACE INTO games {COLUMNS} VALUES (?,?,?,?,?,?,?,?,?)', rows)
        conn.execute('INSERT OR REPLACE INTO synced_tournaments VALUES (?,?,datetime("now"),?)', (tid, t.get('date', ''), len(rows)))
    return len(rows)


def main():
    global DEADLINE, REQUEST_DELAY
    parser = argparse.ArgumentParser()
    parser.add_argument('--pages', type=int, default=2)
    parser.add_argument('--limit', type=int, default=50)
    parser.add_argument('--max-tournaments', type=int, default=10)
    parser.add_argument('--delay', type=float, default=2.0)
    parser.add_argument('--refresh', action='store_true', help='Compatibility: existing events are always rechecked')
    parser.add_argument('--since', type=date.fromisoformat, default=date(2026, 9, 1))
    parser.add_argument('--max-seconds', type=float, default=600)
    parser.add_argument('--state', type=Path, default=Path(__file__).with_name('sync_state.json'))
    args = parser.parse_args()
    if args.pages < 1 or args.limit < 1 or args.max_tournaments < 1 or args.max_seconds <= 0:
        parser.error('Collection limits must be positive')
    REQUEST_DELAY = max(1.0, args.delay)
    DEADLINE = time.monotonic() + args.max_seconds
    DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB, timeout=30) as conn:
        initialize(conn)
        restored = restore(conn, Path(__file__).with_name('matches_snapshot.csv'))
        print(f'Restored {restored} snapshot matches', flush=True)
        state = json.loads(args.state.read_text()) if args.state.exists() else {'page': 1, 'events': {}}
        events = state['events']
        # Snapshot sources are also eligible for later corrections on fresh runners.
        for tid, event, played_at in conn.execute("SELECT substr(source,16),event,played_at FROM games WHERE source LIKE 'limitless-play:%' GROUP BY source"):
            events.setdefault(tid, {'id': tid, 'name': event, 'date': played_at, 'checked': ''})
        for _ in range(args.pages):
            tournaments = fetch('/tournaments', {'game': 'PTCG', 'format': 'STANDARD', 'page': state['page'], 'limit': min(100, args.limit)})
            if not isinstance(tournaments, list):
                raise ValueError('Invalid tournaments response')
            for t in tournaments:
                if not isinstance(t, dict) or not t.get('id') or not t.get('date'):
                    raise ValueError('Invalid tournament metadata')
                if date.fromisoformat(t['date'][:10]) >= args.since:
                    tid = str(t['id'])
                    events[tid] = {**t, 'checked': events.get(tid, {}).get('checked', '')}
            if not tournaments or any(date.fromisoformat(t['date'][:10]) < args.since for t in tournaments):
                state['page'] = 1
                break
            state['page'] += 1
        eligible = [t for t in events.values() if date.fromisoformat(t['date'][:10]) >= args.since]
        # Oldest check first: newly discovered and previously failed events get priority.
        for t in sorted(eligible, key=lambda t: (t.get('checked', ''), str(t['id'])))[:args.max_tournaments]:
            count = sync_tournament(conn, t, REQUEST_DELAY)
            t['checked'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            print(f"{t['id']}: {count} usable matches", flush=True)
        # Only advance discovery/check state after a successful bounded batch.
        temp = args.state.with_suffix('.tmp')
        temp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n')
        os.replace(temp, args.state)


if __name__ == '__main__':
    main()
