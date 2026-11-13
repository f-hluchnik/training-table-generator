"""`Plan` → the plan.json document (docs/PLAN.md §4, D-012, D-027).

Every value the sheet prints is computed here, display strings included; the
Typst template only lays them out. Pure (D-013).
"""

import math
from collections.abc import Iterable, Sequence
from datetime import date
from typing import Any

from ttg.model import LongRun, Phase, PhaseKind, Plan, Race, Session, SessionType, Week, WeekKind
from ttg.sessions import RECOVERY_JOG_MINUTES, STRIDES_COUNT, STRIDES_SECONDS, half_easy_run_km, round_km

# 2: `weeks[].phase` added, `gauge.km_per_box` dropped (D-037).
SCHEMA_VERSION = 2

# D-019: one box per km (not configurable), labels every 10 km; the gauge covers the highest planned week.
GAUGE_LABEL_EVERY_KM = 10
# D-006: a week counts at ≥ 80 % of its planned km.
SUCCESS_SHARE = 0.8
SUCCESS_TEXT = "A week counts at ≥ 80 % of the planned km."

MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")

# The pace legend, in print order, labelled as in the reference.
EASY_LABEL, INTERVAL_LABEL, THRESHOLD_LABEL = "easy", "hard", "comfortably hard"
STRIDES_LABEL = "easy, with fast relaxed strides"
HILLS_LABEL = "hard uphill effort, jog down"

# D-018 notation.
NO_SESSION = "–"
RACE_TEXT = "RACE"
STRIDES_TEXT = "S"
HILLY_TEXT = "hilly"  # in the footer's race list, so the hill repeats of its block make sense (D-041)

# The last column shows a word instead of the planned km in these weeks, as in the reference.
NOTE_WORDS = {WeekKind.TAPER: "taper", WeekKind.RACE: "race", WeekKind.RECOVERY: "recovery"}


def export(plan: Plan) -> dict[str, Any]:
    """The plan.json document of `plan`, warnings included (they are not printed on the sheet)."""
    sheet = plan.season.sheet
    phase_numbers = _phase_numbers(plan.weeks)
    return {
        "schema_version": SCHEMA_VERSION,
        "title": sheet.title,
        "paces": _pace_legend(plan),
        "gauge": {
            "boxes": _gauge_boxes(week.planned_km for week in plan.weeks),
            "label_every_km": GAUGE_LABEL_EVERY_KM,
        },
        "weeks": [_week(week, phase_numbers[week.phase], plan.season.races) for week in plan.weeks],
        "footer": {
            "races": [race_text(race) for race in plan.season.races],
            "rules": list(sheet.rules),
            "success": SUCCESS_TEXT,
        },
        "warnings": [{"code": str(w.code), "week": w.week, "message": w.message} for w in plan.warnings],
    }


def phase_label(phase: Phase) -> str:
    """D-026: build, the race type for a specific block, taper, recovery."""
    if phase.kind is PhaseKind.SPECIFIC:
        assert phase.race is not None  # a specific block belongs to its race
        return str(phase.race.type)
    return str(phase.kind)


def race_cell_text(race: Race) -> str:
    """`RACE 21 km`: which race it is, the footer's race list says (owner, S5)."""
    return f"{RACE_TEXT} {round_km(race.distance_km)} km"


def race_text(race: Race) -> str:
    """The footer's entry: `Prague Marathon 10 oct (A)`, `Beskydská sedmička 28–29 aug (B, hilly)`."""
    hilly = f", {HILLY_TEXT}" if race.hilly else ""
    return f"{race.name} {_date_range(race.date, race.last_day)} ({race.priority}{hilly})"


def quality_text(quality: Session | Race) -> str:
    if isinstance(quality, Race):
        return race_cell_text(quality)
    match quality.type:
        case SessionType.NONE:
            return NO_SESSION
        case SessionType.STRIDES:
            return STRIDES_TEXT
    if quality.km is not None:
        return f"{quality.type}: {quality.reps}x{_number(quality.km)} km"
    if quality.minutes is not None:
        return f"{quality.type}: {quality.reps}x{_number(quality.minutes)}'"
    raise ValueError(f"a {quality.type} session needs minutes or km")


def long_run_text(long_run: LongRun | Race | None) -> str:
    if long_run is None:
        return NO_SESSION
    if isinstance(long_run, Race):
        return race_cell_text(long_run)
    if long_run.mp_km:
        return f"{long_run.km} km ({long_run.mp_km} MP)"
    return f"{long_run.km} km"


def _phase_numbers(weeks: Iterable[Week]) -> dict[Phase, int]:
    """Each phase's number on the sheet, from 1. Two adjacent phases can share a label (two tapers)."""
    phases = dict.fromkeys(week.phase for week in weeks)
    return {phase: number for number, phase in enumerate(phases, start=1)}


def _week(week: Week, phase_number: int, races: Sequence[Race]) -> dict[str, Any]:
    return {
        "number": week.number,
        "days": [_day(day, races) for day in week.days],
        "month": MONTHS[week.month - 1],
        "kind": str(week.kind),
        "phase": phase_number,
        "phase_label": phase_label(week.phase),
        "easy": {"km": list(week.easy), "text": "+".join(str(km) for km in week.easy)},
        "quality": {
            "type": "race" if isinstance(week.quality, Race) else str(week.quality.type),
            "km": week.quality_km,
            "text": quality_text(week.quality),
        },
        "long": {
            "km": week.long_run_km,
            "mp_km": week.long_run.mp_km if isinstance(week.long_run, LongRun) else 0,
            "text": long_run_text(week.long_run),
        },
        "planned_km": week.planned_km,
        "box_80pct": math.ceil(SUCCESS_SHARE * week.planned_km),
        "note": _note(week),
    }


def _day(day: date | None, races: Sequence[Race]) -> dict[str, Any] | None:
    if day is None:
        return None
    is_race_day = any(race.date <= day <= race.last_day for race in races)
    return {"date": day.isoformat(), "text": str(day.day), "race": is_race_day}


def _note(week: Week) -> str:
    if week.note is not None:
        return week.note
    return NOTE_WORDS.get(week.kind, str(week.planned_km))


def _pace_legend(plan: Plan) -> list[dict[str, str]]:
    paces = plan.paces
    recovery = f"+{RECOVERY_JOG_MINUTES}'"
    strides = f"{half_easy_run_km(plan.season.load.easy_run_km)} km + {STRIDES_COUNT}×{STRIDES_SECONDS}″"
    return [
        {"code": "ER", "pace": paces.easy.format(), "label": EASY_LABEL},
        {"code": "S", "pace": strides, "label": STRIDES_LABEL},
        {"code": "H", "pace": "", "label": HILLS_LABEL},  # effort-based, no pace (D-015)
        {"code": "I", "pace": paces.interval.format() + recovery, "label": INTERVAL_LABEL},
        {"code": "T", "pace": paces.threshold.format() + recovery, "label": THRESHOLD_LABEL},
        {"code": "MP", "pace": paces.mp.format(), "label": ""},
        {"code": "LR", "pace": paces.easy.format(), "label": EASY_LABEL},
    ]


def _gauge_boxes(planned_kms: Iterable[int]) -> int:
    """The highest planned week rounded up to the next label (D-019); at least one label."""
    highest = max(planned_kms, default=0)
    return max(1, math.ceil(highest / GAUGE_LABEL_EVERY_KM)) * GAUGE_LABEL_EVERY_KM


def _date_range(first: date, last: date) -> str:
    """`10 oct`, `28–29 aug`, `31 aug – 1 sep`."""
    if first == last:
        return _day_and_month(first)
    if first.month == last.month:
        return f"{first.day}–{_day_and_month(last)}"
    return f"{_day_and_month(first)} – {_day_and_month(last)}"


def _day_and_month(day: date) -> str:
    return f"{day.day} {MONTHS[day.month - 1]}"


def _number(value: float) -> str:
    """1.0 → "1", 1.5 → "1.5"."""
    return f"{value:g}"
