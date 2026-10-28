"""Dependency-free CSS colors for win-rate matchup matrix cells.

pandas Styler.background_gradient requires optional matplotlib; Streamlit's
main app must not crash simply because that package is not installed.
"""
import math

# Light enough for dark text while retaining a red/yellow/green overview.
_LOSS = (249, 204, 202)
_NEUTRAL = (255, 246, 194)
_WIN = (190, 233, 205)


def matrix_cell_css(value):
    """Return a cell-only CSS declaration for a numeric 0-100 win rate."""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return ""
    if not math.isfinite(numeric):
        return ""
    numeric = min(100.0, max(0.0, numeric))
    if numeric < 50:
        left, right, fraction = _LOSS, _NEUTRAL, numeric / 50.0
    else:
        left, right, fraction = _NEUTRAL, _WIN, (numeric - 50.0) / 50.0
    color = tuple(
        round(left[index] + (right[index] - left[index]) * fraction)
        for index in range(3)
    )
    return (
        "background-color: #{:02x}{:02x}{:02x};"
        " color: #222222;"
    ).format(*color)
