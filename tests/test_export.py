"""Plan → plan.json (D-027): display strings, days, labels and the gauge. The contract's shape is
checked for every sample and snapshot in tests/test_sample_plan.py."""

from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from ttg.expand import expand
from ttg.export import export, long_run_text, phase_label, quality_text, race_text
from ttg.model import LongRun, Phase, PhaseKind, PlanWarning, Priority, Race, Session, SessionType, WarningCode
from ttg.spec import load_season

SEASONS = Path(__file__).parents[1] / "seasons"
TODAY = date(2026, 11, 13)
MARATHON = Race("Marathon", date(2027, 10, 10), 42.195)


@pytest.fixture(scope="module")
def plan_2026():
    return expand(load_season(SEASONS / "2026.toml"), TODAY)


@pytest.fixture(scope="module")
def document_2026(plan_2026):
    return export(plan_2026, plan_2026.warnings)


def week(document, number):
    return document["weeks"][number - 1]


@pytest.mark.parametrize(
    ("quality", "text"),
    [
        (Session(SessionType.HILLS, reps=6, minutes=1), "H: 6x1'"),
        (Session(SessionType.HILLS, reps=5, minutes=1.5), "H: 5x1.5'"),
        (Session(SessionType.THRESHOLD, reps=6, km=1), "T: 6x1 km"),
        (Session(SessionType.MARATHON_PACE, reps=3, km=3), "MP: 3x3 km"),
        (Session(SessionType.STRIDES), "S"),
        (Session(SessionType.NONE), "–"),
        (Race("Tune-up", date(2027, 4, 4), 10, Priority.C), "RACE 10 km"),
    ],
)
def test_quality_text(quality, text):
    assert quality_text(quality) == text


@pytest.mark.parametrize(
    ("long_run", "text"),
    [(LongRun(15), "15 km"), (LongRun(20, 6), "20 km (6 MP)"), (MARATHON, "RACE 42 km"), (None, "–")],
)
def test_long_run_text(long_run, text):
    assert long_run_text(long_run) == text


@pytest.mark.parametrize(
    ("phase", "label"),
    [
        (Phase(PhaseKind.BUILD, 1, 8), "build"),
        (Phase(PhaseKind.SPECIFIC, 9, 6, MARATHON), "marathon"),
        (Phase(PhaseKind.TAPER, 15, 2, MARATHON), "taper"),
        (Phase(PhaseKind.RECOVERY, 17, 2, MARATHON), "recovery"),
    ],
)
def test_phase_labels_are_derived(phase, label):
    assert phase_label(phase) == label


def test_a_deload_in_a_specific_block_keeps_the_blocks_label(document_2026):
    assert (week(document_2026, 12)["kind"], week(document_2026, 12)["phase_label"]) == ("deload", "ultra")


def test_race_days_are_marked_and_days_after_the_last_race_are_null(document_2026):
    ultra_week = [day["race"] for day in week(document_2026, 17)["days"]]
    assert ultra_week == [False, False, False, False, True, True, False]  # 28–29 Aug
    last = week(document_2026, 23)["days"]
    assert [day and day["text"] for day in last] == ["5", "6", "7", "8", "9", "10", None]
    assert last[5]["race"]


def test_month_is_the_month_of_the_thursday(document_2026):
    assert week(document_2026, 13)["month"] == "jul"  # 27 Jul – 2 Aug
    assert week(document_2026, 22)["month"] == "oct"  # 28 Sep – 4 Oct


def test_note_is_the_planned_km_a_word_or_the_override(document_2026):
    assert week(document_2026, 1)["note"] == str(week(document_2026, 1)["planned_km"])
    notes = [week(document_2026, n)["note"] for n in (15, 17, 18, 19, 20)]
    assert notes == ["taper", "race", "recovery", "flush", "check"]


def test_race_week_long_run_is_not_counted(document_2026):
    assert week(document_2026, 17)["long"] == {"km": 0, "mp_km": 0, "text": "RACE 101 km"}


def test_a_c_race_is_a_quality_run_of_type_race(plan_2026):
    tune_up = Race("Tune-up", date(2026, 5, 10), 10, Priority.C)  # Sunday of week 1
    season = replace(plan_2026.season, races=(tune_up, *plan_2026.season.races))
    plan = expand(season, TODAY)
    assert week(export(plan, ()), 1)["quality"] == {"type": "race", "km": 10, "text": "RACE 10 km"}


@pytest.mark.parametrize(
    ("race", "text"),
    [
        (MARATHON, "Marathon 10 oct (A)"),
        (Race("Ultra", date(2026, 8, 28), 101, Priority.B, end=date(2026, 8, 29)), "Ultra 28–29 aug (B)"),
        (Race("Stage race", date(2026, 8, 31), 101, end=date(2026, 9, 2)), "Stage race 31 aug – 2 sep (A)"),
    ],
)
def test_race_list_entry(race, text):
    assert race_text(race) == text


def test_footer_lists_the_races(document_2026):
    races = ["Beskydská sedmička 28–29 aug (B)", "Běhej Lesy Lednice 10 oct (A)"]
    assert document_2026["footer"]["races"] == races


def test_gauge_covers_the_highest_week_and_the_80_percent_box(document_2026):
    assert document_2026["gauge"] == {"km_per_box": 1, "boxes": 80, "label_every_km": 10}
    first = week(document_2026, 1)
    assert first["box_80pct"] == 32  # ⌈0.8 × 39⌉


def test_pace_legend_in_print_order(document_2026):
    assert document_2026["paces"] == [
        {"code": "ER", "pace": "5:30", "label": "easy"},
        {"code": "I", "pace": "4:15+2'", "label": "hard"},
        {"code": "T", "pace": "4:30+2'", "label": "comfortably hard"},
        {"code": "MP", "pace": "4:58", "label": ""},
        {"code": "LR", "pace": "5:30", "label": "easy"},
    ]


def test_title_footer_and_warnings(plan_2026):
    warning = PlanWarning(WarningCode.PLAN_TOO_SHORT, None, "message")
    document = export(plan_2026, [warning])
    assert document["title"] == "marathon training plan"
    assert document["footer"]["rules"] == list(plan_2026.season.sheet.rules)
    assert document["footer"]["success"] == "A week counts at ≥ 80 % of the planned km."
    assert document["warnings"] == [{"code": "C2", "week": None, "message": "message"}]
