"""The beginner's rules (TRAINING_MODEL.md §11, D-054).

The case that started it (owner, S11): easy runs of 1 km, a 3 km long run, a 10 km race 15 weeks
away. The standard rules gave hill repeats in week 1, a long run growing 3 → 5 → 7 km and a 16 km
peak; the beginner's plan grows by about a kilometre a week and keeps intensity out for a month.
"""

from datetime import date, timedelta
from itertools import pairwise

import pytest

from ttg import beginner
from ttg.expand import expand
from ttg.export import CONVERSATIONAL_TEXT, export
from ttg.model import (
    BEGINNER_RULES,
    DEFAULT_BEGINNER_RUNS_PER_WEEK,
    Load,
    LongRun,
    Paces,
    Race,
    RaceResult,
    SeasonError,
    Session,
    SessionType,
    WarningCode,
)
from ttg.paces import Pace
from ttg.spec import parse_season
from ttg.web import generate

from support import TODAY, season

START = date(2026, 11, 23)
TEN_K = Race("City 10k", date(2027, 3, 7), 10.0)  # week 15
NO_RESULT = Paces(race_result=None)


def beginner_plan(*races: Race, paces: Paces = NO_RESULT, **load: int):
    fields = {"easy_run_km": 1, "long_run_km": 3, "runs_per_week": 4} | load
    return expand(season(*(races or (TEN_K,)), paces=paces, load=Load(beginner=True, **fields), start=START), TODAY)


def sessions(plan):
    return [week.quality for week in plan.weeks if isinstance(week.quality, Session)]


# --- the season file ---------------------------------------------------------------


def minimal(load, **rest):
    return {"race": [{"name": "10k", "date": date(2027, 3, 7), "distance_km": 10}], "load": load, **rest}


def test_a_beginner_needs_no_race_result_nor_easy_run():
    parsed = parse_season(minimal({"beginner": True, "long_run_km": 4}))
    assert parsed.paces.race_result is None
    assert parsed.load.easy_run_km == 3  # ¾ of the long run
    assert parsed.load.runs_per_week == DEFAULT_BEGINNER_RUNS_PER_WEEK
    assert parsed.sheet.rules == BEGINNER_RULES


def test_everyone_else_still_needs_both():
    with pytest.raises(SeasonError, match=r"^paces: missing"):
        parse_season(minimal({"easy_run_km": 3, "long_run_km": 4}))
    with pytest.raises(SeasonError, match=r"^load.easy_run_km: missing"):
        parse_season(minimal({"long_run_km": 4}, paces={"race_result": {"distance_km": 5, "time": "30:00"}}))


@pytest.mark.parametrize(
    ("is_beginner", "runs", "valid"), [(True, 2, True), (True, 4, True), (True, 5, False), (False, 2, False)]
)
def test_runs_a_week(is_beginner, runs, valid):
    data = minimal(
        {"beginner": is_beginner, "easy_run_km": 3, "long_run_km": 4, "runs_per_week": runs},
        paces={"race_result": {"distance_km": 5, "time": "30:00"}},
    )
    if valid:
        assert parse_season(data).load.runs_per_week == runs
    else:
        with pytest.raises(SeasonError, match=r"^load.runs_per_week"):
            parse_season(data)


# --- the weeks --------------------------------------------------------------------


def test_the_first_month_has_no_quality_run_then_strides_then_hills():
    plan = beginner_plan()
    types = [week.quality.type for week in plan.weeks if isinstance(week.quality, Session)]
    assert set(types[: beginner.STRIDES_FROM_WEEK - 1]) == {SessionType.NONE}
    assert types[beginner.STRIDES_FROM_WEEK - 1] is SessionType.STRIDES
    first_hills = types.index(SessionType.HILLS) + 1
    assert first_hills == beginner.HILLS_FROM_WEEK


def test_hills_stay_short_and_there_are_no_intervals_threshold_or_marathon_pace():
    for plan in (beginner_plan(), beginner_plan(Race("Half", date(2027, 9, 5), 21.1))):
        types = {session.type for session in sessions(plan)}
        assert types <= {SessionType.NONE, SessionType.STRIDES, SessionType.HILLS}
        hills = [session for session in sessions(plan) if session.type is SessionType.HILLS]
        assert hills[0].reps == beginner.HILL_START_REPS
        assert max(session.reps or 0 for session in hills) == beginner.HILL_MAX_REPS


def test_a_loading_week_grows_by_one_step_in_turn_long_run_and_easy_run():
    plan = beginner_plan()
    loading = plan.weeks[:3]  # weeks 1–3, before the first deload
    assert [week.long_run_km for week in loading] == [3, 4, 4]
    assert [week.easy for week in loading] == [(1, 1, 1), (1, 1, 1), (2, 1, 1)]


def test_the_long_run_never_grows_more_than_a_step_and_peaks_near_the_race_distance():
    plan = beginner_plan()
    loading = [week.long_run.km for week in plan.weeks if week.kind.is_loading and isinstance(week.long_run, LongRun)]
    assert all(after - before <= beginner.STEP_KM for before, after in pairwise(loading))
    assert max(loading) == 9  # 90 % of 10 km [source 35]


def test_a_strides_run_is_the_easy_run_whose_place_it_takes():
    week_5 = beginner_plan().weeks[4]
    assert week_5.quality == Session(SessionType.STRIDES)
    assert week_5.easy == (2, 1) and week_5.quality_km == 1


def test_two_runs_a_week_are_an_easy_run_and_the_long_run():
    plan = beginner_plan(runs_per_week=2)
    assert {session.type for session in sessions(plan)} == {SessionType.NONE}
    assert {len(week.easy) for week in plan.weeks} == {1}


def test_the_race_week_has_no_quality_run_and_one_easy_run_fewer():
    race_week = beginner_plan().weeks[-1]
    assert race_week.quality == Session(SessionType.NONE)
    assert len(race_week.easy) == 2  # of 3 slots besides the long run


def test_a_beginner_gets_no_warnings_even_for_a_tiny_start():
    plan = beginner_plan(easy_run_km=1, long_run_km=1, runs_per_week=2)
    assert plan.warnings == ()


def test_a_beginner_marathon_on_a_small_base_gets_one_encouraging_note():
    marathon = Race("Marathon", date(2027, 3, 7), 42.195)
    warnings = beginner_plan(marathon, long_run_km=3, runs_per_week=2).warnings
    assert [warning.code for warning in warnings] == [WarningCode.MARATHON_BASE]
    assert "Walk breaks in the race are fine" in warnings[0].message
    assert beginner_plan(long_run_km=3).warnings == ()  # not for a 10 km


@pytest.mark.parametrize(
    ("race", "cap"),
    [
        (Race("5k", date(2027, 3, 7), 5.0), 5),
        (TEN_K, 9),
        (Race("Half", date(2027, 3, 7), 21.1), 16),
        (Race("Marathon", date(2027, 3, 7), 42.195), 23),  # 3 h at 7:57
    ],
)
def test_the_long_run_cap(race, cap):
    assert beginner.long_run_cap(race, Pace.parse("7:57")) == cap


def test_a_fast_beginner_marathon_is_capped_at_32_km():
    assert beginner.long_run_cap(Race("M", date(2027, 3, 7), 42.195), Pace.parse("5:00")) == 32


def test_a_reduced_week_takes_a_km_off_each_easy_run_but_not_below_two():
    assert beginner.reduced((4, 3, 2, 1)) == (3, 2, 2, 1)


def test_growth_goes_to_the_shortest_easy_run_up_to_the_cap():
    assert beginner.grown((3, 2, 2), cap_km=5) == (3, 3, 2)
    assert beginner.grown((5, 5), cap_km=5) is None


# --- the sheet ----------------------------------------------------------------------


def legend(plan):
    return {entry["code"]: entry["pace"] for entry in export(plan)["paces"]}


def test_without_a_race_result_the_easy_pace_is_conversational():
    assert legend(beginner_plan()) == {
        "ER": CONVERSATIONAL_TEXT,
        "S": "easy run + 6×20″",
        "H": "",
        "LR": CONVERSATIONAL_TEXT,
    }


def test_with_a_race_result_the_easy_pace_is_printed():
    result = Paces(RaceResult(5.0, timedelta(minutes=35)))
    assert legend(beginner_plan(paces=result))["ER"] == "8:38"


def test_an_override_puts_its_session_in_the_legend():
    data = minimal(
        {"beginner": True, "long_run_km": 4},
        start=START,
        overrides={"10": {"quality": {"type": "T", "reps": 2, "minutes": 5}}},
    )
    plan = expand(parse_season(data), TODAY)
    assert "T" in legend(plan)


def test_an_easy_override_in_a_reduced_week_uses_the_weeks_own_runs():
    data = minimal(
        {"beginner": True, "easy_run_km": 3, "long_run_km": 4}, start=START, overrides={"4": {"easy": "regular"}}
    )
    week_4 = expand(parse_season(data), TODAY).weeks[3]
    assert week_4.kind == "deload" and week_4.easy == (4, 3)


# --- the page ------------------------------------------------------------------------


def test_the_page_builds_a_beginner_without_a_race_result():
    form = {
        "start": "2026-11-23",
        "race": [{"name": "10k", "date": "2027-03-07", "distance_km": "10"}],
        "paces": {"race_result": {"distance_km": "", "time": ""}},
        "load": {"beginner": True, "easy_run_km": "", "long_run_km": "3"},
    }
    generated = generate(form, TODAY)
    assert "beginner = true" in generated.season_toml
    assert "[paces]" not in generated.season_toml
    assert generated.plan["warnings"] == []
