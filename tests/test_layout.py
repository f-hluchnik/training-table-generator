"""Phase layout (T-04). The cases and their expected layouts were confirmed by the owner in S3."""

from dataclasses import replace
from datetime import date

import pytest

from ttg.layout import Layout, lay_out, phase_lengths
from ttg.model import (
    PhaseKind,
    Priority,
    Race,
    SeasonError,
    WarningCode,
)
from ttg.spec import load_season

from support import SEASONS, TODAY, season

BUILD, SPECIFIC, TAPER, RECOVERY = PhaseKind.BUILD, PhaseKind.SPECIFIC, PhaseKind.TAPER, PhaseKind.RECOVERY
C1, C2 = WarningCode.RACES_TOO_CLOSE, WarningCode.PLAN_TOO_SHORT

MARATHON = Race("Marathon", date(2027, 10, 10), 42.195)


def phases(layout: Layout) -> list[tuple[PhaseKind, int, int, str | None]]:
    """(kind, first week, last week, race name), after checking the phases cover the plan."""
    weeks = [week for phase in layout.phases for week in range(phase.first_week, phase.last_week + 1)]
    assert weeks == list(range(1, layout.calendar.weeks + 1))
    return [(phase.kind, phase.first_week, phase.last_week, phase.race and phase.race.name) for phase in layout.phases]


def warnings(layout: Layout) -> list[tuple[WarningCode, int | None, str]]:
    return [(warning.code, warning.week, warning.message) for warning in layout.warnings]


# --- the cases of the ticket ---------------------------------------------------


def test_reference_2026_matches_the_reference_phases():
    layout = lay_out(load_season(SEASONS / "2026.toml"), TODAY)
    # Reference blocks: base 1–4, strength 5–8, volume 9–14, ultra 15–17, pivot 18–21,
    # race 22–23. Only the labels differ (D-026), and "pivot" is recovery + marathon.
    assert phases(layout) == [
        (BUILD, 1, 8, None),
        (SPECIFIC, 9, 14, "Beskydská sedmička"),
        (TAPER, 15, 17, "Beskydská sedmička"),
        (RECOVERY, 18, 19, "Beskydská sedmička"),
        (SPECIFIC, 20, 21, "Běhej Lesy Lednice"),
        (TAPER, 22, 23, "Běhej Lesy Lednice"),
    ]
    assert warnings(layout) == [
        (
            C1,
            23,
            '"Běhej Lesy Lednice": specific block shortened from 6 to 2 weeks '
            '("Beskydská sedmička" and "Běhej Lesy Lednice" are too close)',
        )
    ]


def test_2026_with_default_lengths_compresses_the_marathon_block_to_one_week():
    reference = load_season(SEASONS / "2026.toml")
    ultra = replace(reference.races[0], taper_weeks=None, recovery_weeks=None)
    layout = lay_out(replace(reference, races=(ultra, reference.races[1])), TODAY)
    assert phases(layout) == [
        (BUILD, 1, 9, None),
        (SPECIFIC, 10, 15, "Beskydská sedmička"),
        (TAPER, 16, 17, "Beskydská sedmička"),
        (RECOVERY, 18, 20, "Beskydská sedmička"),
        (SPECIFIC, 21, 21, "Běhej Lesy Lednice"),
        (TAPER, 22, 23, "Běhej Lesy Lednice"),
    ]
    assert [warning.code for warning in layout.warnings] == [C1]


def test_one_race():
    layout = lay_out(season(MARATHON, start=date(2027, 5, 3)), TODAY)
    assert phases(layout) == [(BUILD, 1, 15, None), (SPECIFIC, 16, 21, "Marathon"), (TAPER, 22, 23, "Marathon")]
    assert layout.warnings == ()


def test_two_a_races_three_weeks_apart_keep_the_taper():
    half = Race("Half", date(2027, 5, 9), 21.0975)  # week 10
    marathon = Race("Marathon", date(2027, 5, 30), 42.195)  # week 13
    layout = lay_out(season(half, marathon, start=date(2027, 3, 1)), TODAY)
    assert phases(layout) == [
        (BUILD, 1, 4, None),
        (SPECIFIC, 5, 8, "Half"),
        (TAPER, 9, 10, "Half"),
        (RECOVERY, 11, 11, "Half"),
        (TAPER, 12, 13, "Marathon"),
    ]
    assert warnings(layout) == [
        (C1, 13, '"Half": recovery shortened from 2 to 1 week ("Half" and "Marathon" are too close)'),
        (C1, 13, '"Marathon": specific block shortened from 6 to 0 weeks ("Half" and "Marathon" are too close)'),
    ]


def test_c_race_inside_a_build_changes_no_phase():
    tune_up = Race("10 km", date(2027, 6, 26), 10, priority=Priority.C)
    layout = lay_out(season(tune_up, MARATHON, start=date(2027, 5, 3)), TODAY)
    assert phases(layout) == [(BUILD, 1, 15, None), (SPECIFIC, 16, 21, "Marathon"), (TAPER, 22, 23, "Marathon")]
    assert layout.calendar.week_of(tune_up.date) == 8
    assert layout.warnings == ()


def test_six_week_plan_for_a_marathon_keeps_the_taper_and_warns():
    layout = lay_out(season(MARATHON, weeks=6), TODAY)
    assert phases(layout) == [(SPECIFIC, 1, 4, "Marathon"), (TAPER, 5, 6, "Marathon")]
    assert warnings(layout) == [
        (C2, 6, '"Marathon": specific block shortened from 6 to 4 weeks (the plan starts too late)'),
    ]


def test_start_after_the_race_is_an_error():
    with pytest.raises(SeasonError, match=r"^start: "):
        lay_out(season(MARATHON), date(2027, 10, 11))


def test_test_2027_season():
    layout = lay_out(load_season(SEASONS / "test-2027.toml"), TODAY)
    assert phases(layout) == [(BUILD, 1, 24, None), (SPECIFIC, 25, 30, "Marathon"), (TAPER, 31, 32, "Marathon")]
    assert layout.warnings == ()


# --- further rules -------------------------------------------------------------


def test_race_in_the_first_week_has_only_its_race_week():
    layout = lay_out(season(MARATHON, weeks=1), TODAY)
    assert phases(layout) == [(TAPER, 1, 1, "Marathon")]
    assert [warning.message.split(":")[1] for warning in layout.warnings] == [
        " specific block shortened from 6 to 0 weeks (the plan starts too late)",
        " taper shortened from 2 to 1 week (the plan starts too late)",
    ]


def test_races_in_consecutive_weeks():
    marathon = Race("Marathon", date(2027, 5, 9), 42.195)  # week 10
    half = Race("Half", date(2027, 5, 16), 21.0975)  # week 11
    layout = lay_out(season(marathon, half, start=date(2027, 3, 1)), TODAY)
    assert phases(layout) == [
        (BUILD, 1, 2, None),
        (SPECIFIC, 3, 8, "Marathon"),
        (TAPER, 9, 10, "Marathon"),
        (TAPER, 11, 11, "Half"),
    ]
    assert [(code, message.split(" (")[0]) for code, _, message in warnings(layout)] == [
        (C1, '"Marathon": recovery shortened from 2 to 0 weeks'),
        (C1, '"Half": specific block shortened from 4 to 0 weeks'),
        (C1, '"Half": taper shortened from 2 to 1 week'),
    ]


def test_two_races_in_the_same_week_share_one_race_week():
    saturday = Race("10 km", date(2027, 10, 9), 10)
    layout = lay_out(season(saturday, MARATHON, start=date(2027, 5, 3)), TODAY)
    assert phases(layout) == [(BUILD, 1, 15, None), (SPECIFIC, 16, 21, "Marathon"), (TAPER, 22, 23, "Marathon")]
    assert warnings(layout) == [
        (C1, 23, '"10 km" and "Marathon" are in the same week: one race week, no recovery after "10 km"'),
    ]


def test_weeks_after_the_last_key_race_are_recovery_then_build():
    autumn_10k = Race("10 km", date(2027, 11, 6), 10, priority=Priority.C)  # 4 weeks after the marathon
    layout = lay_out(season(MARATHON, autumn_10k, start=date(2027, 5, 3)), TODAY)
    assert phases(layout)[-2:] == [(RECOVERY, 24, 25, "Marathon"), (BUILD, 26, 27, None)]


def test_multi_day_race_into_the_next_week_has_its_race_week_on_the_first_day():
    sunday_to_monday = replace(MARATHON, end=date(2027, 10, 11))
    layout = lay_out(season(sunday_to_monday, start=date(2027, 5, 3)), TODAY)
    assert phases(layout)[-2:] == [(TAPER, 22, 23, "Marathon"), (RECOVERY, 24, 24, "Marathon")]


def test_only_c_races_give_a_build_only_plan():
    layout = lay_out(season(replace(MARATHON, priority=Priority.C), start=date(2027, 5, 3)), TODAY)
    assert phases(layout) == [(BUILD, 1, 23, None)]


@pytest.mark.parametrize(
    ("race", "taper"),
    [
        (replace(MARATHON, priority=Priority.B), 1),
        (Race("10 km", date(2027, 10, 10), 10, priority=Priority.B), 1),  # never below the race week
        (Race("Ultra", date(2027, 10, 10), 101, priority=Priority.B), 2),
        (Race("Ultra", date(2027, 10, 10), 101, priority=Priority.B, taper_weeks=3), 3),  # an override is taken as is
    ],
)
def test_b_race_taper_is_one_week_shorter(race, taper):
    assert phase_lengths(race).taper == taper
