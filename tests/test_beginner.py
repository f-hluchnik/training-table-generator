"""The beginner's rules (TRAINING_MODEL.md §11, D-054).

The case that started it (owner, S11): easy runs of 1 km, a 3 km long run, a 10 km goal 15 weeks
away. The standard rules gave hill repeats in week 1, a long run growing 3 → 5 → 7 km and a 16 km
peak. After the owner's review and a second coach review: gentle intensity from week 3, inside a
run; the easy runs catch up first and the long run holds each distance below 5 km for two weeks.
"""

from datetime import date, timedelta
from itertools import pairwise

import pytest

from ttg import beginner
from ttg.expand import expand
from ttg.export import CONVERSATIONAL_TEXT, duration_text, export
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
    WeekKind,
)
from ttg.paces import Pace
from ttg.spec import parse_season
from ttg.web import generate

from support import TODAY, season

START = date(2026, 11, 23)
TEN_K = Race("City 10k", date(2027, 3, 7), 10.0)  # week 15
HALF = Race("Half", date(2027, 9, 5), 21.1)
NO_RESULT = Paces(race_result=None)
GENTLE = {SessionType.NONE, SessionType.STRIDES, SessionType.FARTLEK, SessionType.HILLS}


def beginner_plan(*races: Race, paces: Paces = NO_RESULT, **load: int):
    fields = {"easy_run_km": 1, "long_run_km": 3, "runs_per_week": 3} | load
    load_ = Load(beginner=True, **fields)
    return expand(season(*(races or (TEN_K,)), paces=paces, load=load_, start=START), TODAY)


def sessions(plan):
    return [week.quality for week in plan.weeks if isinstance(week.quality, Session)]


def loading_long_runs(plan):
    return [week.long_run.km for week in plan.weeks if week.kind.is_loading and isinstance(week.long_run, LongRun)]


# --- the season file ---------------------------------------------------------------


def minimal(load, **rest):
    return {"race": [{"name": "10k", "date": date(2027, 3, 7), "distance_km": 10}], "load": load, **rest}


def test_a_beginner_needs_no_race_result_nor_easy_run():
    parsed = parse_season(minimal({"beginner": True, "long_run_km": 4}))
    assert parsed.paces.race_result is None
    assert parsed.load.easy_run_km == 3  # ¾ of the long run
    assert parsed.load.runs_per_week == DEFAULT_BEGINNER_RUNS_PER_WEEK
    assert parsed.sheet.rules == BEGINNER_RULES


def test_a_beginner_needs_no_race():
    assert parse_season({"load": {"beginner": True, "long_run_km": 2}}).races == ()


def test_everyone_else_still_needs_a_race_a_result_and_an_easy_run():
    with pytest.raises(SeasonError, match=r"^race: at least one"):
        parse_season({"load": {"easy_run_km": 3, "long_run_km": 4}})
    with pytest.raises(SeasonError, match=r"^paces: missing"):
        parse_season(minimal({"easy_run_km": 3, "long_run_km": 4}))
    with pytest.raises(SeasonError, match=r"^load.easy_run_km: missing"):
        parse_season(minimal({"long_run_km": 4}, paces={"race_result": {"distance_km": 5, "time": "30:00"}}))


def test_a_race_can_be_a_goal():
    data = minimal({"beginner": True, "long_run_km": 4})
    data["race"][0]["goal"] = True
    assert parse_season(data).races[0].goal


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


# --- the quality run ----------------------------------------------------------------


def test_nothing_in_weeks_1_and_2_strides_from_week_3_fartlek_and_hills_from_week_5():
    types = [session.type for session in sessions(beginner_plan())]
    assert types[:2] == [SessionType.NONE] * 2
    assert types[2:4] == [SessionType.STRIDES] * 2
    assert types[4:7] == [SessionType.FARTLEK, SessionType.HILLS, SessionType.FARTLEK]


@pytest.mark.parametrize("runs", [2, 3, 4])
def test_only_gentle_sessions_within_the_hard_time_limit(runs):
    plan = beginner_plan(HALF, runs_per_week=runs)
    assert {session.type for session in sessions(plan)} <= GENTLE
    for week in plan.weeks:
        if isinstance(week.quality, Session) and week.quality.type in beginner.EFFORT_STEPS:
            hard = (week.quality.reps or 0) * (week.quality.minutes or 0)
            assert hard <= beginner.hard_minutes_limit(week.planned_km, plan.paces.easy)


def test_each_effort_type_follows_its_steps():
    plan = beginner_plan(HALF)
    for session_type, steps in beginner.EFFORT_STEPS.items():
        indices = [steps.index((s.reps, s.minutes)) for s in sessions(plan) if s.type is session_type]
        # One step at a time, held where the week's hard-time limit stops it, up to the last step.
        assert indices[0] == 0 and indices[-1] == len(steps) - 1
        assert all(0 <= after - before <= 1 for before, after in pairwise(indices))


def test_a_week_too_small_for_the_first_step_has_strides():
    assert beginner.effort_step(SessionType.FARTLEK, 0, limit_minutes=5.0) is None
    tiny = beginner_plan(easy_run_km=1, long_run_km=1, runs_per_week=2)
    assert tiny.weeks[4].quality == Session(SessionType.STRIDES)


def test_the_quality_run_is_done_inside_the_shortest_run():
    week_5 = beginner_plan().weeks[4]
    assert week_5.quality == Session(SessionType.FARTLEK, reps=6, minutes=1)
    assert week_5.easy == (2,) and week_5.quality_km == 2


# --- growth -------------------------------------------------------------------------


def test_the_owners_case_with_three_runs_follows_the_coachs_table():
    plan = beginner_plan()
    assert [week.long_run_km for week in plan.weeks[:14]] == [3, 3, 3, 3, 4, 4, 5, 5, 5, 6, 7, 7, 8, 9]
    assert plan.weeks[1].easy == (2, 1)  # the 1 km easy runs catch up first


@pytest.mark.parametrize("runs", [2, 3, 4])
def test_one_step_at_most_and_each_distance_below_5_km_held_two_weeks(runs):
    loading = loading_long_runs(beginner_plan(runs_per_week=runs))
    assert all(after - before <= beginner.STEP_KM for before, after in pairwise(loading))
    for km in set(loading) - {max(loading)}:
        if km < beginner.LONG_RUN_HOLD_BELOW_KM:
            assert loading.count(km) >= beginner.LONG_RUN_HOLD_WEEKS


def test_the_long_run_peaks_near_the_race_distance():
    assert max(loading_long_runs(beginner_plan())) == 9  # 90 % of 10 km [source 35]


def test_a_deload_holds_and_has_strides():
    plan = beginner_plan()
    for previous, week in pairwise(plan.weeks):
        if week.kind is WeekKind.DELOAD:
            assert week.long_run_km == previous.long_run_km
            assert week.quality == Session(SessionType.STRIDES)


def test_two_runs_a_week_are_the_quality_run_and_the_long_run():
    plan = beginner_plan(runs_per_week=2)
    assert {len(week.easy) for week in plan.weeks[2:-1]} == {0}
    assert all(isinstance(week.long_run, LongRun) for week in plan.weeks[:-1])
    assert len(plan.weeks[-1].easy) == 1  # the race week keeps one short run
    assert export(plan)["weeks"][4]["easy"]["text"] == "–"


def test_the_race_week_has_no_quality_run_and_one_easy_run_fewer():
    race_week = beginner_plan(runs_per_week=4).weeks[-1]
    assert race_week.quality == Session(SessionType.NONE)
    assert len(race_week.easy) == 2  # of 3 runs besides the long run


# --- goals --------------------------------------------------------------------------


def test_a_goal_prints_goal():
    exported = export(beginner_plan(Race("10 km", date(2027, 3, 7), 10.0, goal=True)))
    assert exported["weeks"][-1]["long"]["text"] == "GOAL 10 km"
    assert exported["footer"]["races"][0]["details"] == "goal"


@pytest.mark.parametrize(("length", "weeks"), [({"start": START}, beginner.NO_GOAL_WEEKS), ({"weeks": 12}, 12)])
def test_without_a_race_the_plan_works_towards_5_km(length, weeks):
    plan = expand(parse_season({"load": {"beginner": True, "long_run_km": 2}} | length), TODAY)
    assert len(plan.weeks) == weeks
    assert export(plan)["weeks"][-1]["long"]["text"] == "GOAL 5 km"


# --- warnings -----------------------------------------------------------------------


def test_a_beginner_gets_no_warnings_even_for_a_tiny_start():
    assert beginner_plan(easy_run_km=1, long_run_km=1, runs_per_week=2).warnings == ()


def test_a_beginner_marathon_on_a_small_base_gets_one_encouraging_note():
    marathon = Race("Marathon", date(2027, 3, 7), 42.195)
    warnings = beginner_plan(marathon, runs_per_week=2).warnings
    assert [warning.code for warning in warnings] == [WarningCode.MARATHON_BASE]
    assert "Walk breaks in the race are fine" in warnings[0].message
    assert beginner_plan().warnings == ()  # not for a 10 km


# --- the rules' pieces --------------------------------------------------------------


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


@pytest.mark.parametrize(("minutes", "text"), [(1, "1′"), (0.5, "30″"), (0.75, "45″"), (1.5, "1′30″"), (2, "2′")])
def test_durations_print_in_minutes_and_seconds(minutes, text):
    assert duration_text(minutes) == text


# --- the sheet ----------------------------------------------------------------------


def legend(plan):
    return {entry["code"]: (entry["pace"], entry["label"]) for entry in export(plan)["paces"]}


def test_without_a_race_result_the_easy_pace_is_conversational():
    shown = legend(beginner_plan())
    assert list(shown) == ["ER", "S", "F", "H", "LR"]
    assert shown["ER"][0] == shown["LR"][0] == CONVERSATIONAL_TEXT
    assert shown["LR"][1] == "easy, walk breaks fine"


def test_with_a_race_result_the_easy_pace_is_printed():
    result = Paces(RaceResult(5.0, timedelta(minutes=35)))
    assert legend(beginner_plan(paces=result))["ER"][0] == "8:38"


def test_an_override_puts_its_session_in_the_legend():
    overrides = {"10": {"quality": {"type": "T", "reps": 2, "minutes": 5}}}
    data = minimal({"beginner": True, "long_run_km": 4}, start=START, overrides=overrides)
    assert "T" in legend(expand(parse_season(data), TODAY))


def test_an_easy_override_uses_the_weeks_own_runs():
    data = minimal(
        {"beginner": True, "easy_run_km": 3, "long_run_km": 4}, start=START, overrides={"15": {"easy": "regular"}}
    )
    plan = expand(parse_season(data), TODAY)
    assert plan.weeks[-1].easy == plan.weeks[-2].easy[:1]  # the race week's run, not reduced


# --- the page ------------------------------------------------------------------------


@pytest.mark.parametrize("races", [[{"name": "10k", "date": "2027-03-07", "distance_km": "10"}], []])
def test_the_page_builds_a_beginner_without_a_race_result_or_a_race(races):
    form = {
        "start": "2026-11-23",
        "race": races,
        "paces": {"race_result": {"distance_km": "", "time": ""}},
        "load": {"beginner": True, "easy_run_km": "", "long_run_km": "3"},
    }
    generated = generate(form, TODAY)
    assert "beginner = true" in generated.season_toml
    assert "[paces]" not in generated.season_toml
    assert generated.plan["warnings"] == []
