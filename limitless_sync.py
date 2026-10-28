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

BASE = 'https://play.limitlesstcg.com/api'
DB = Path(os.environ.get('TCG_DB_PATH', str(Path(__file__).with_name('research.sqlite3'))))
COLUMNS = '(id,event,played_at,deck_a,deck_b,winner,decklist_a,decklist_b,source)'


def fetch(path, params=None, attempts=4):
    url = BASE + path + ('?' + urllib.parse.urlencode(params) if params else '')
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'TCGMetaLabResearch/0.3 (public API)', 'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=35) as response:
                return json.load(response)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            if isinstance(exc, urllib.error.HTTPError) and exc.code not in (429, 500, 502, 503, 504):
                raise
            if attempt == attempts - 1:
                raise
            time.sleep(min(30, 2 ** attempt * 3))


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
    time.sleep(delay)
    pairings = fetch(f'/tournaments/{tid}/pairings')
    time.sleep(delay)
    players = {str(p['player']): p for p in standings if isinstance(p, dict) and p.get('player') is not None}
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
        rows.append((key, t.get('name', tid), t.get('date', ''), deck_a, deck_b, outcome,
                     json.dumps(cards(pa.get('decklist')), ensure_ascii=False),
                     json.dumps(cards(pb.get('decklist')), ensure_ascii=False), 'limitless-play:' + tid))
    # Atomic refresh: never replace previously saved matches with an empty result.
    previous = conn.execute('SELECT COUNT(*) FROM games WHERE source=?', ('limitless-play:' + tid,)).fetchone()[0]
    if previous and not rows:
        raise ValueError('Refusing empty refresh for tournament ' + tid)
    with conn:
        conn.execute('DELETE FROM games WHERE source=?', ('limitless-play:' + tid,))
        conn.executemany(f'INSERT OR REPLACE INTO games {COLUMNS} VALUES (?,?,?,?,?,?,?,?,?)', rows)
        conn.execute('INSERT OR REPLACE INTO synced_tournaments VALUES (?,?,datetime("now"),?)', (tid, t.get('date', ''), len(rows)))
    return len(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pages', type=int, default=1)
    parser.add_argument('--limit', type=int, default=50)
    parser.add_argument('--max-tournaments', type=int, default=10)
    parser.add_argument('--delay', type=float, default=2.0)
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB, timeout=30)
    initialize(conn)
    processed = 0
    for page in range(1, max(0, args.pages) + 1):
        tournaments = fetch('/tournaments', {'game': 'PTCG', 'format': 'STANDARD', 'page': page, 'limit': min(100, args.limit)})
        if not isinstance(tournaments, list) or not tournaments:
            break
        for t in tournaments:
            if processed >= args.max_tournaments:
                break
            tid = str(t['id'])
            if not args.refresh and conn.execute('SELECT 1 FROM synced_tournaments WHERE id=?', (tid,)).fetchone():
                continue
            try:
                count = sync_tournament(conn, t, args.delay)
                processed += 1
                print(f"{tid}: {count} usable matches | {t.get('name','')}", flush=True)
            except Exception as exc:
                print(f'{tid}: ERROR {exc}', flush=True)
            time.sleep(args.delay)
        if processed >= args.max_tournaments:
            break
    print('Finished; tournaments processed:', processed)


if __name__ == '__main__':
    main()
