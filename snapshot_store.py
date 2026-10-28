"""Strict snapshot recovery and atomic, loss-checked export."""
import csv
import os
import tempfile
from pathlib import Path

COLUMNS = ['id', 'event', 'played_at', 'deck_a', 'deck_b', 'winner',
           'decklist_a', 'decklist_b', 'source']


def read_snapshot(path):
    path = Path(path)
    if not path.exists():
        return []
    with path.open(newline='', encoding='utf-8') as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != COLUMNS:
            raise ValueError('Unexpected snapshot columns')
        rows = list(reader)
    for row in rows:
        if (None in row or any(v is None for v in row.values()) or not row['id']
                or not row['deck_a'] or not row['deck_b']
                or row['winner'] not in ('a', 'b', 'draw')):
            raise ValueError('Invalid snapshot row; refusing update')
    return rows


def restore(conn, path):
    rows = read_snapshot(path)
    with conn:
        conn.executemany('INSERT OR IGNORE INTO games VALUES (?,?,?,?,?,?,?,?,?)',
                         [tuple(r[c] for c in COLUMNS) for r in rows])
    return len({r['id'] for r in rows})


def export(conn, path):
    path = Path(path)
    old = read_snapshot(path)
    rows = conn.execute('SELECT ' + ','.join(COLUMNS) + ' FROM games ORDER BY id').fetchall()
    ids = {r[0] for r in rows}
    if not rows or not {r['id'] for r in old}.issubset(ids) or len(rows) < len(old):
        raise ValueError('Snapshot would lose matches; refusing export')
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', newline='', encoding='utf-8',
                                         dir=path.parent, delete=False) as handle:
            temp = handle.name
            writer = csv.writer(handle)
            writer.writerow(COLUMNS)
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if temp and os.path.exists(temp):
            os.unlink(temp)
    return len(rows)
