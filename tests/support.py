"""What many tests share: the repository folders, "today" and a season builder."""

from datetime import date, timedelta
from pathlib import Path
from typing import Any

from ttg.model import Load, Paces, Race, RaceResult, Season

ROOT = Path(__file__).parents[1]
SEASONS = ROOT / "seasons"
FIXTURES = Path(__file__).parent / "fixtures"

# "Today", passed into the pure core (D-013): a Friday. Seasons with a start date ignore it.
TODAY = date(2026, 11, 13)

# The owner's 2026 marathon, the pace anchor of the test seasons: VDOT 44.5, derived T 4:40.2
# (TRAINING_MODEL.md §2).
RACE_RESULT = RaceResult(42.195, timedelta(hours=3, minutes=30, seconds=2))
LOAD = Load(easy_run_km=12, long_run_km=15)  # 2026's starting load
PACES = Paces(RACE_RESULT)


def season(*races: Race, **fields: Any) -> Season:
    """A season of `races` with 2026's paces and load unless `fields` give others."""
    fields.setdefault("paces", PACES)
    fields.setdefault("load", LOAD)
    return Season(races=tuple(sorted(races, key=lambda race: race.date)), **fields)
