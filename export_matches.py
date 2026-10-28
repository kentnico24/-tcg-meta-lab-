"""Export only when every existing snapshot match remains present."""
import sqlite3
from limitless_sync import DB
from snapshot_store import export
from pathlib import Path

if __name__ == '__main__':
    if not DB.exists():
        raise FileNotFoundError(DB)
    with sqlite3.connect(DB) as conn:
        count = export(conn, Path(__file__).with_name('matches_snapshot.csv'))
    print(f'Exported {count} matches')
