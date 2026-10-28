"""Sorting modes for per-deck matchup win-rate tables.

Sort numeric rates and counts before translating deck labels. This keeps
Streamlit's table, chart and CSV in the same deterministic order on mobile.
"""

MATCHUP_SORT_OPTIONS = (
    "試合数が多い順",
    "勝率が高い順",
    "勝率が低い順",
    "試合数が少ない順",
)


def sort_matchup_rows(rows, mode="試合数が多い順"):
    """Return a sorted copy of matchup-stat records; never modify input."""
    if mode not in MATCHUP_SORT_OPTIONS:
        raise ValueError("Unknown matchup sort mode")
    keys = {
        "試合数が多い順": lambda row: (
            -int(row["試合数"]), -float(row["勝率"]), str(row["対面"])),
        "勝率が高い順": lambda row: (
            -float(row["勝率"]), -int(row["試合数"]), str(row["対面"])),
        "勝率が低い順": lambda row: (
            float(row["勝率"]), -int(row["試合数"]), str(row["対面"])),
        "試合数が少ない順": lambda row: (
            int(row["試合数"]), -float(row["勝率"]), str(row["対面"])),
    }
    return sorted(rows, key=keys[mode])
