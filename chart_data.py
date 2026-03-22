"""
Reference charts for future functions (e.g. suji / discard safety).

Chart 1: suji strength by turn passed and tile category (Non / Half / Full suji bands).
Chart 2: suji vs yakuhai / guest wind visibility.
"""

from __future__ import annotations

from typing import Any

# -----------------------------------------------------------------------------
# Chart 1 — column layout (left to right, matching numeric row order)
# -----------------------------------------------------------------------------

CHART1_TURN_KEY = "turn_passed"

# Top-level groups and sub-column labels (for documentation / UI).
CHART1_COLUMN_GROUPS: list[dict[str, Any]] = [
    {
        "group": "Non suji",
        "columns": ["5", "46", "37", "28", "19"],
    },
    {
        "group": "Half suji",
        "columns": ["5", "46A", "46B", "37", "28", "19"],
    },
    {
        "group": "Full suji",
        "columns": ["5", "46"],
    },
]

# 5 + 6 + 2 = 13 band columns (no separate "passed suji" column).
CHART1_COLUMN_LABELS: list[str] = []
for g in CHART1_COLUMN_GROUPS:
    prefix = g["group"].replace(" suji", "").lower().replace(" ", "_")
    for c in g["columns"]:
        CHART1_COLUMN_LABELS.append(f"{prefix}_{c}")

CHART1_EXPECTED_NCOLS = len(CHART1_COLUMN_LABELS)  # 13

# Turn 1: original paste omitted last two Full suji cells — padded None.
CHART1_ROWS: list[dict[str, Any]] = [
    {
        "turn": 1,
        "values": [5.7, 5.7, 5.8, 4.7, 3.4, 2.5, 2.5, 3.1, 5.6, 3.8, 1.8, None, None],
    },
    {"turn": 2, "values": [6.6, 6.9, 6.3, 5.2, 4.0, 3.5, 3.5, 4.1, 5.3, 3.5, 1.9, 0.8, 2.6]},
    {"turn": 3, "values": [7.7, 8.0, 6.7, 5.8, 4.6, 4.3, 4.1, 4.9, 5.2, 3.6, 1.8, 1.6, 2.0]},
    {"turn": 4, "values": [8.5, 8.9, 7.1, 6.2, 5.1, 4.8, 4.7, 5.6, 5.2, 3.8, 1.7, 1.6, 2.0]},
    {"turn": 5, "values": [9.4, 9.7, 7.5, 6.7, 5.5, 5.3, 5.1, 6.0, 5.3, 3.7, 1.7, 1.7, 2.0]},
    {"turn": 6, "values": [10.2, 10.5, 7.9, 7.1, 5.9, 5.8, 5.6, 6.4, 5.2, 3.7, 1.7, 1.8, 2.0]},
    {"turn": 7, "values": [11.0, 11.3, 8.4, 7.5, 6.3, 6.3, 6.1, 6.8, 5.3, 3.7, 1.7, 2.0, 2.1]},
    {"turn": 8, "values": [11.9, 12.2, 8.9, 8.0, 6.8, 6.9, 6.6, 7.4, 5.3, 3.8, 1.7, 2.1, 2.2]},
    {"turn": 9, "values": [12.8, 13.1, 9.5, 8.6, 7.4, 7.4, 7.2, 7.9, 5.5, 3.9, 1.8, 2.2, 2.3]},
    {"turn": 10, "values": [13.8, 14.1, 10.1, 9.2, 8.0, 8.0, 7.8, 8.5, 5.6, 4.0, 1.9, 2.4, 2.4]},
    {"turn": 11, "values": [14.9, 15.1, 10.8, 9.9, 8.7, 8.7, 8.5, 9.2, 5.7, 4.2, 2.0, 2.5, 2.6]},
    {"turn": 12, "values": [16.0, 16.3, 11.6, 10.6, 9.4, 9.4, 9.2, 9.9, 6.0, 4.4, 2.2, 2.7, 2.7]},
    {"turn": 13, "values": [17.2, 17.5, 12.4, 11.4, 10.2, 10.2, 10.0, 10.6, 6.2, 4.6, 2.4, 3.0, 3.0]},
    {"turn": 14, "values": [18.5, 18.8, 13.3, 12.3, 11.1, 11.0, 10.9, 11.4, 6.6, 4.9, 2.7, 3.2, 3.1]},
    {"turn": 15, "values": [19.9, 20.1, 14.3, 13.3, 12.0, 11.9, 11.8, 12.3, 7.0, 5.3, 3.0, 3.4, 3.4]},
    {"turn": 16, "values": [21.3, 21.7, 15.4, 14.3, 13.1, 12.9, 12.8, 13.3, 7.4, 5.7, 3.3, 3.7, 3.6]},
    {"turn": 17, "values": [22.9, 23.2, 16.6, 15.4, 14.2, 14.0, 13.8, 14.4, 8.0, 6.1, 3.6, 3.9, 3.9]},
    {"turn": 18, "values": [24.7, 24.9, 17.9, 16.7, 15.4, 15.2, 15.0, 15.6, 8.5, 6.6, 4.0, 4.3, 4.2]},
    {"turn": 19, "values": [27.5, 27.8, 20.4, 19.1, 17.8, 17.5, 17.5, 17.5, 9.8, 7.4, 5.0, 5.1, 5.1]},
]

# -----------------------------------------------------------------------------
# Chart 2 — one row per turn; honor visibility buckets (no leading suji column).
# -----------------------------------------------------------------------------

CHART2_TURN_KEY = "turn_passed"

CHART2_COLUMN_LABELS: list[str] = [
    "yakuhai_live",
    "yakuhai_1_visible",
    "yakuhai_2_visible",
    "guest_wind_live",
    "guest_wind_1_visible",
    "guest_wind_2_visible",
]

CHART2_EXPECTED_NCOLS = len(CHART2_COLUMN_LABELS)

CHART2_ROWS: list[dict[str, Any]] = [
    {"turn": 1, "values": [2.1, 1.2, 0.5, 2.4, 1.4, 1.2]},
    {"turn": 2, "values": [2.3, 1.2, 0.5, 2.7, 1.3, 0.4]},
    {"turn": 3, "values": [2.4, 1.2, 0.3, 2.6, 1.2, 0.3]},
    {"turn": 4, "values": [2.6, 1.1, 0.2, 2.6, 1.2, 0.2]},
    {"turn": 5, "values": [2.9, 1.2, 0.2, 2.8, 1.2, 0.2]},
    {"turn": 6, "values": [3.2, 1.3, 0.2, 2.9, 1.3, 0.2]},
    {"turn": 7, "values": [3.6, 1.4, 0.2, 3.2, 1.4, 0.2]},
    {"turn": 8, "values": [4.0, 1.6, 0.2, 3.5, 1.6, 0.2]},
    {"turn": 9, "values": [4.6, 1.9, 0.3, 4.0, 1.8, 0.2]},
    {"turn": 10, "values": [5.3, 2.2, 0.3, 4.6, 2.1, 0.3]},
    {"turn": 11, "values": [6.0, 2.6, 0.4, 5.1, 2.5, 0.3]},
    {"turn": 12, "values": [6.8, 3.1, 0.4, 5.9, 3.0, 0.4]},
    {"turn": 13, "values": [7.8, 3.7, 0.5, 6.6, 3.7, 0.5]},
    {"turn": 14, "values": [8.8, 4.4, 0.7, 7.4, 4.4, 0.6]},
    {"turn": 15, "values": [9.9, 5.2, 0.8, 8.4, 5.3, 0.8]},
    {"turn": 16, "values": [11.2, 6.2, 1.0, 9.4, 6.5, 0.9]},
    {"turn": 17, "values": [12.4, 7.3, 1.3, 10.5, 7.7, 1.2]},
    {"turn": 18, "values": [13.9, 8.5, 1.7, 11.8, 9.4, 1.6]},
    {"turn": 19, "values": [18.1, 12.1, 2.8, 14.7, 12.6, 2.1]},
]


def chart1_row_as_dict(turn: int) -> dict[str, float | None] | None:
    """Lookup Chart 1 row by turn; keys are CHART1_COLUMN_LABELS."""
    for row in CHART1_ROWS:
        if row["turn"] == turn:
            vals = row["values"]
            return {
                CHART1_COLUMN_LABELS[i]: vals[i]
                for i in range(min(len(vals), len(CHART1_COLUMN_LABELS)))
            }
    return None


def chart2_row_as_dict(turn: int) -> dict[str, float] | None:
    """Lookup Chart 2 row by turn; keys are CHART2_COLUMN_LABELS."""
    for row in CHART2_ROWS:
        if row["turn"] == turn:
            vals = row["values"]
            return {
                CHART2_COLUMN_LABELS[i]: vals[i]
                for i in range(len(CHART2_COLUMN_LABELS))
            }
    return None
