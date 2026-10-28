"""Export region annotations without changing the match CSV schema."""
import sqlite3
from pathlib import Path

from limitless_sync import DB
from country_store import initialize, export_countries


if __name__ == '__main__':
    if not DB.exists():
        raise FileNotFoundError(DB)
    with sqlite3.connect(DB) as conn:
        initialize(conn)
        total = export_countries(
            conn, Path(__file__).with_name('match_countries.csv'))
        known = conn.execute(
            """SELECT COUNT(*)
               FROM games JOIN match_countries USING(id)
               WHERE match_countries.country_a<>'' OR match_countries.country_b<>''"""
        ).fetchone()[0]
    print(f'Exported country annotations for {total} matches ({known} with at least one known country)')
