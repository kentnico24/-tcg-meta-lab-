"""Atomic optional country snapshot for player-perspective regional analysis.

The existing match snapshot remains the single source of truth for match records.
Country codes are self-reported by players on Limitless Play and may be missing.
"""
import csv
import os
import tempfile
from pathlib import Path

from region_labels import normalize_country

COLUMNS = ['id', 'country_a', 'country_b']


def initialize(conn):
    conn.execute(
        """CREATE TABLE IF NOT EXISTS match_countries(
            id TEXT PRIMARY KEY,
            country_a TEXT NOT NULL DEFAULT '',
            country_b TEXT NOT NULL DEFAULT ''
        )"""
    )
    conn.commit()


def upsert_countries(conn, records):
    """Keep previously known values when the API omits country information."""
    cleaned = [(str(match_id), normalize_country(a), normalize_country(b))
               for match_id, a, b in records if match_id]
    conn.executemany(
        """INSERT INTO match_countries(id,country_a,country_b)
           VALUES (?,?,?)
           ON CONFLICT(id) DO UPDATE SET
              country_a=CASE WHEN excluded.country_a!=''
                             THEN excluded.country_a
                             ELSE match_countries.country_a END,
              country_b=CASE WHEN excluded.country_b!=''
                             THEN excluded.country_b
                             ELSE match_countries.country_b END""",
        cleaned,
    )
    return len(cleaned)


def read_country_snapshot(path):
    path = Path(path)
    if not path.exists():
        return []
    with path.open(newline='', encoding='utf-8') as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != COLUMNS:
            raise ValueError('Unexpected country snapshot columns')
        rows = list(reader)
    seen = set()
    for row in rows:
        if None in row or any(v is None for v in row.values()) or not row['id']:
            raise ValueError('Malformed country snapshot; refusing update')
        if row['id'] in seen:
            raise ValueError('Duplicate country snapshot ID; refusing update')
        seen.add(row['id'])
        for name in ('country_a', 'country_b'):
            code = row[name]
            if code and normalize_country(code) != code:
                raise ValueError('Malformed country code; refusing update')
    return rows


def restore_countries(conn, path):
    rows = read_country_snapshot(path)
    with conn:
        upsert_countries(conn, [(r['id'], r['country_a'], r['country_b'])
                                for r in rows])
    return len(rows)


def export_countries(conn, path):
    """Write a full country sidecar, never removing previously known match IDs.

    Country corrections are accepted, but known codes cannot disappear because
    of a transient API omission. Missing player countries remain blank.
    """
    path = Path(path)
    old = read_country_snapshot(path)
    old_by_id = {r['id']: r for r in old}
    rows = conn.execute(
        """SELECT games.id,
                  COALESCE(match_countries.country_a, ''),
                  COALESCE(match_countries.country_b, '')
           FROM games LEFT JOIN match_countries ON games.id=match_countries.id
           ORDER BY games.id"""
    ).fetchall()
    current = {r[0]: r for r in rows}
    for match_id, previous in old_by_id.items():
        if match_id not in current:
            raise ValueError('Country snapshot would lose match ID ' + match_id)
        now = current[match_id]
        if (previous['country_a'] and not now[1]
                or previous['country_b'] and not now[2]):
            raise ValueError('Country snapshot would lose known country for ' + match_id)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(
                mode='w', newline='', encoding='utf-8',
                dir=path.parent, delete=False) as output:
            tmp = output.name
            writer = csv.writer(output)
            writer.writerow(COLUMNS)
            writer.writerows(rows)
            output.flush()
            os.fsync(output.fileno())
        os.replace(tmp, path)
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)
    return len(rows)
