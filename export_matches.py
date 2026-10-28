
import csv
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "research.sqlite3"
OUTPUT = ROOT / "matches_snapshot.csv"

COLUMNS = [
    "id", "event", "played_at", "deck_a",
    "deck_b", "winner", "decklist_a",
    "decklist_b", "source"
]

if not DB.exists():
    raise FileNotFoundError(f"Database not found: {DB}")

with sqlite3.connect(DB) as conn:
    rows = conn.execute(
        "SELECT " + ", ".join(COLUMNS) +
        " FROM games ORDER BY id"
    ).fetchall()

with OUTPUT.open("w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(COLUMNS)
    writer.writerows(rows)

print(f"Exported {len(rows)} matches to {OUTPUT.name}")
