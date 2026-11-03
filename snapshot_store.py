"""Strict snapshot recovery and atomic, loss-checked export."""
import csv
import gzip
import os
import tempfile
from pathlib import Path

def preferred_snapshot(root):
    """Use the fully updated gzip snapshot when present; legacy CSV otherwise."""
    root = Path(root)
    compressed = root / 'matches_snapshot.csv.gz'
    return compressed if compressed.exists() else root / 'matches_snapshot.csv'


def open_snapshot_text(path):
    path = Path(path)
    if path.suffix == '.gz':
        return gzip.open(path, 'rt', newline='', encoding='utf-8')
    return path.open(newline='', encoding='utf-8')


COLUMNS = ['id', 'event', 'played_at', 'deck_a', 'deck_b', 'winner',
           'decklist_a', 'decklist_b', 'source']


def read_snapshot(path):
    path = Path(path)
    if not path.exists():
        return []
    with open_snapshot_text(path) as handle:
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
    baseline = path
    if path.suffix == '.gz' and not path.exists():
        baseline = path.with_suffix('')  # First migration uses the tracked CSV.
    old = read_snapshot(baseline)
    rows = conn.execute('SELECT ' + ','.join(COLUMNS) + ' FROM games ORDER BY id').fetchall()
    ids = {r[0] for r in rows}
    if not rows or not {r['id'] for r in old}.issubset(ids) or len(rows) < len(old):
        raise ValueError('Snapshot would lose matches; refusing export')
    temp = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
            temp = handle.name
        if path.suffix == '.gz':
            with gzip.open(temp, 'wt', newline='', encoding='utf-8',
                           compresslevel=6) as handle:
                writer = csv.writer(handle)
                writer.writerow(COLUMNS)
                writer.writerows(rows)
        else:
            with open(temp, 'w', newline='', encoding='utf-8') as handle:
                writer = csv.writer(handle)
                writer.writerow(COLUMNS)
                writer.writerows(rows)
        with open(temp, 'rb') as handle:
            os.fsync(handle.fileno())
        if path.suffix == '.gz' and os.path.getsize(temp) >= 95_000_000:
            raise ValueError('Compressed snapshot approaches GitHub file limit; external storage required')
        os.replace(temp, path)
    finally:
        if temp and os.path.exists(temp):
            os.unlink(temp)
    return len(rows)
