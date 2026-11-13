"""Phase rules → weeks and the overrides (T-06). The 2026 reference, week for week, is in
tests/test_golden_2026.py."""

from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import pytest

from ttg.expand import expand
from ttg.model import (
    EasyRuns,
    Load,
    LongRun,
    Paces,
    Plan,
    Priority,
    Race,
    RaceResult,
    Season,
    SeasonError,
    Session,
    SessionType,
    WarningCode,
    Week,
    WeekKind,
    WeekOverride,
)
from ttg.sessions import capped_interval_session, interval_limit_km, interval_session, round_km, work_km
from ttg.spec import load_season

SEASONS = Path(__file__).parents[1] / "seasons"
TODAY = date(2026, 11, 13)
H, I, T, MP, S, NONE = (
    SessionType.HILLS, SessionType.INTERVALS, SessionType.THRESHOLD,
    SessionType.MARATHON_PACE, SessionType.STRIDES, SessionType.NONE,
)  # fmt: skip
BUILD, DELOAD, SPECIFIC = WeekKind.BUILD, WeekKind.DELOAD, WeekKind.SPECIFIC
TAPER, RACE, RECOVERY = WeekKind.TAPER, WeekKind.RACE, WeekKind.RECOVERY

START = date(2027, 5, 3)  # a Monday
MARATHON = Race("Marathon", date(2027, 10, 10), 42.195)  # week 23 from START
FIRST_SPECIFIC = 17  # of the MARATHON-only plan: build 1–16, specific 17–21, taper 22–23


def season(*races: Race, **fields) -> Season:
    fields.setdefault("start", START)
    return Season(
        races=tuple(sorted(races, key=lambda race: race.date)),
        paces=Paces(RaceResult(42.195, timedelta(hours=3, minutes=30, seconds=2))),
        load=Load(easy_run_km=12, long_run_km=15),
        **fields,
    )


def plan_of(*races: Race, **fields) -> Plan:
    return expand(season(*races, **fields), TODAY)


def week_on(day: date) -> int:
    return (day - START).days // 7 + 1


def kinds(plan: Plan) -> list[WeekKind]:
    return [week.kind for week in plan.weeks]


def quality_types(weeks: list[Week]) -> list:
    return [week.quality.type if isinstance(week.quality, Session) else "race" for week in weeks]


def long_run_kms(weeks: list[Week]) -> list[int | None]:
    return [week.long_run.km if isinstance(week.long_run, LongRun) else None for week in weeks]


@pytest.fixture(scope="module")
def plan_2026() -> Plan:
    return expand(load_season(SEASONS / "2026.toml"), TODAY)


# --- week kinds and the 3:1 cycle ------------------------------------------------------


def test_2026_week_kinds(plan_2026):
    assert kinds(plan_2026) == [
        BUILD, BUILD, BUILD, DELOAD, BUILD, BUILD, BUILD, DELOAD,  # build 1–8
        SPECIFIC, SPECIFIC, SPECIFIC, DELOAD, SPECIFIC, SPECIFIC,  # ultra specific 9–14
        TAPER, TAPER, RACE,  # ultra taper 15–17
        RECOVERY, RECOVERY,  # 18–19
        SPECIFIC, SPECIFIC,  # marathon specific 20–21: the cycle restarted after the race
        TAPER, RACE,  # 22–23
    ]  # fmt: skip


def test_the_cycle_continues_from_build_into_the_specific_block():
    plan = plan_of(MARATHON)  # weeks 13–21
    assert kinds(plan)[12:21] == [BUILD, BUILD, BUILD, DELOAD, SPECIFIC, SPECIFIC, SPECIFIC, DELOAD, SPECIFIC]


# --- quality runs ------------------------------------------------------------------------


def test_build_rotation_h_i_t_each_type_progressing():
    loading = [week for week in plan_of(MARATHON).weeks if week.kind is BUILD]
    sessions = [week.quality for week in loading[:7]]
    assert [(s.type, s.reps, s.minutes) for s in sessions] == [
        (H, 6, 1), (I, 5, 3), (T, 3, 8), (H, 7, 1), (I, 6, 3), (T, 3, 10), (H, 8, 1),
    ]  # fmt: skip


def test_ultra_specific_block_continues_the_build_rotation(plan_2026):
    assert quality_types([plan_2026.weeks[n - 1] for n in (9, 10, 11, 13, 14)]) == [H, I, T, H, I]


@pytest.mark.parametrize(
    ("distance_km", "expected"),
    [(42.195, [MP, MP]), (21.0975, [T, T]), (10, [I, T])],
)
def test_specific_block_quality_by_race_type(distance_km, expected):
    plan = plan_of(replace(MARATHON, distance_km=distance_km))
    specific = [week for week in plan.weeks if week.kind is SPECIFIC]
    assert quality_types(specific[:2]) == expected


def test_specific_10k_alternation_continues_each_types_progression():
    plan = plan_of(replace(MARATHON, distance_km=10))
    build_intervals = sum(1 for w in plan.weeks if w.kind is BUILD and w.quality.type is I)
    first_specific = next(w for w in plan.weeks if w.kind is SPECIFIC)
    other_km = sum(first_specific.easy) + first_specific.long_run_km
    assert first_specific.quality == capped_interval_session(build_intervals, plan.paces, 12, other_km)


def test_intervals_hold_within_daniels_limit_for_their_week():
    plan = plan_of(MARATHON)
    intervals = [w for w in plan.weeks if isinstance(w.quality, Session) and w.quality.type is I]
    for week in intervals:
        assert round_km(work_km(week.quality, plan.paces.interval)) <= interval_limit_km(week.planned_km)
    assert intervals[-1].quality == interval_session(2)  # 5 × 4′: 6 × 4′ would be 6 km in a 59 km week


def test_deload_taper_race_and_recovery_quality(plan_2026):
    weeks = {week.number: week for week in plan_2026.weeks}
    assert weeks[4].quality == Session(S)
    assert weeks[15].quality == weeks[16].quality == Session(T, reps=6, km=1)
    assert weeks[17].quality == Session(S)  # strides keep the legs sharp before the race
    assert weeks[18].quality.type is weeks[19].quality.type is NONE


# --- C races -------------------------------------------------------------------------------


TUNE_UP = Race("Tune-up 10 km", START + timedelta(weeks=1, days=6), 10, Priority.C)  # Sunday, week 2
TUNE_UP_HALF = replace(TUNE_UP, name="Tune-up half", distance_km=21.0975)


def test_a_c_race_up_to_10_km_replaces_the_quality_run_and_counts_its_distance():
    week = plan_of(TUNE_UP, MARATHON).weeks[1]
    assert week.quality == TUNE_UP
    assert week.quality_km == 10
    assert week.long_run == LongRun(17)
    assert week.planned_km == sum(week.easy) + 10 + 17


def test_the_rotation_continues_with_the_session_a_c_race_replaced():
    loading = [week for week in plan_of(TUNE_UP, MARATHON).weeks if week.kind is BUILD]
    assert quality_types(loading[:4]) == [H, "race", I, T]


def test_a_longer_c_race_replaces_the_long_run_and_the_quality_run():
    weeks = plan_of(TUNE_UP_HALF, MARATHON).weeks
    assert (weeks[1].quality, weeks[1].long_run, weeks[1].long_run_km) == (Session(NONE), TUNE_UP_HALF, 21)
    assert weeks[1].planned_km == sum(weeks[1].easy) + 21
    # Neither progression advanced: week 3 continues where week 1 stopped.
    assert (weeks[2].quality.type, weeks[2].long_run) == (I, LongRun(17))


def test_a_deload_after_three_long_c_races_reduces_the_starting_long_run():
    """The C races took every long run before the deload, so there is no last loading long run."""
    halves = [replace(TUNE_UP_HALF, name=f"Half {n}", date=START + timedelta(days=6 + 7 * n)) for n in range(3)]
    week_4 = plan_of(*halves, MARATHON).weeks[3]
    assert (week_4.kind, week_4.long_run) == (DELOAD, LongRun(12))  # 75 % of 15, at least an easy run


def test_a_c_race_in_a_recovery_block_warns():
    half = Race("Half", date(2027, 6, 27), 21.0975)  # recovery weeks 9–10
    tune_up = replace(TUNE_UP, date=date(2027, 7, 4))  # Sunday of week 9
    warnings = plan_of(half, tune_up, MARATHON).warnings
    assert [(w.code, w.week) for w in warnings] == [(WarningCode.RACES_TOO_CLOSE, 9)]
    assert '"Tune-up 10 km" falls in the recovery after "Half"' in warnings[0].message


def test_two_c_races_in_one_week_warn_and_the_first_replaces_the_quality_run():
    second = replace(TUNE_UP, name="Second", date=TUNE_UP.date - timedelta(days=1), distance_km=5)
    plan = plan_of(TUNE_UP, second, MARATHON)
    assert plan.weeks[1].quality == second
    assert [(w.code, w.week) for w in plan.warnings] == [(WarningCode.RACES_TOO_CLOSE, 2)]


# --- long runs -------------------------------------------------------------------------------


def test_long_run_grows_two_km_a_loading_week_up_to_the_build_cap():
    weeks = plan_of(MARATHON).weeks
    # 3:1 cycle; deloads at 75 % of the last loading week; the marathon's build cap is 24 km.
    assert long_run_kms(weeks[:12]) == [15, 17, 19, 14, 21, 23, 24, 18, 24, 24, 24, 18]


def test_long_run_reaches_the_full_cap_only_in_the_specific_block():
    weeks = plan_of(MARATHON).weeks
    specific = [week for week in weeks if week.kind in (SPECIFIC, DELOAD) and week.number >= FIRST_SPECIFIC]
    assert long_run_kms(specific) == [26, 28, 30, 23, 32]


def test_every_other_marathon_specific_long_run_ends_with_mp_km():
    weeks = [w for w in plan_of(MARATHON).weeks if w.number >= FIRST_SPECIFIC and w.kind in (SPECIFIC, DELOAD)]
    # Weeks 17–21: MP, plain, MP, deload (no MP, not counted in the alternation), plain.
    assert [w.long_run.mp_km for w in weeks] == [6, 0, 8, 0, 0]


def test_no_mp_km_in_the_long_run_of_a_tune_up_race_week():
    tune_up = replace(TUNE_UP, date=date(2027, 8, 29))  # Sunday of week 17, the first MP long run
    weeks = plan_of(tune_up, MARATHON).weeks
    assert weeks[16].quality == tune_up
    assert weeks[16].long_run.mp_km == 0
    assert weeks[17].long_run.mp_km == 6  # the alternation goes on: the next one has MP
    assert all(w.long_run.mp_km == 0 for w in plan_of(MARATHON).weeks if w.kind is BUILD)


def test_taper_long_runs_reduce_from_the_peak_since_the_last_race(plan_2026):
    weeks = plan_2026.weeks
    # Ultra: computed peak 35 (week 13; week 14's 40 is an override, which changes only
    # its own week): 75 % then 60 %. Marathon: peak 26 → 60 %.
    assert long_run_kms(weeks[14:16]) == [26, 21]
    assert long_run_kms([weeks[21]]) == [16]


def test_the_race_replaces_the_long_run_and_is_not_counted(plan_2026):
    race_week = plan_2026.weeks[16]
    assert race_week.long_run == plan_2026.season.races[0]
    assert race_week.long_run_km == 0
    assert race_week.planned_km == sum(race_week.easy) + race_week.quality_km == 24


def test_recovery_first_week_without_long_run_then_one_easy_run_length(plan_2026):
    assert long_run_kms(plan_2026.weeks[17:19]) == [None, 12]


def test_long_run_restarts_after_a_race_at_the_next_races_build_cap(plan_2026):
    # 75 % of the ultra's peak (35) would be 26; the marathon's build cap is 24.
    assert long_run_kms(plan_2026.weeks[19:21]) == [24, 26]


def test_long_run_restarts_at_three_quarters_of_a_smaller_previous_peak():
    half = Race("Half", date(2027, 6, 27), 21.0975)  # its specific block peaks at the 21 km cap
    weeks = plan_of(half, MARATHON).weeks
    first_after = next(w for w in weeks if w.number > week_on(half.date) and w.kind.is_loading)
    assert first_after.long_run.km == 16  # 75 % of 21, below the marathon's build cap (24)


# --- easy runs -------------------------------------------------------------------------------


def test_easy_runs_are_reduced_in_every_week_that_is_not_a_loading_week():
    for week in plan_of(MARATHON).weeks:
        assert week.easy == ((12, 12) if week.kind.is_loading else (12, 6))


# --- target race ---------------------------------------------------------------------------


def test_weeks_after_the_last_key_race_target_it():
    autumn_10k = Race("Autumn 10 km", date(2027, 11, 7), 10, Priority.C)
    plan = plan_of(MARATHON, autumn_10k)
    assert {week.target for week in plan.weeks} == {MARATHON}


def test_without_key_races_the_longest_race_is_the_target():
    only_c = (replace(MARATHON, priority=Priority.C), replace(TUNE_UP, distance_km=10))
    plan = plan_of(*only_c)
    assert {week.target.name for week in plan.weeks} == {"Marathon"}
    assert set(kinds(plan)) <= {BUILD, DELOAD}


# --- overrides -------------------------------------------------------------------------------


def test_an_override_changes_only_its_own_week():
    plain = plan_of(MARATHON).weeks
    overridden = plan_of(MARATHON, overrides=(WeekOverride(2, long_run_km=30),)).weeks
    assert overridden[1].long_run == LongRun(30)
    assert overridden[2:] == plain[2:]


def test_override_fields():
    overrides = (
        WeekOverride(1, easy=EasyRuns.REDUCED, quality=Session(MP, reps=3, km=3), note="holiday"),
        WeekOverride(2, long_run_km=0),
    )
    first, second = plan_of(MARATHON, overrides=overrides).weeks[:2]
    assert first.easy == (12, 6)
    assert first.quality == Session(MP, reps=3, km=3)
    assert first.quality_km == 13  # 9 km at MP + 24′ easy at 5:37
    assert first.note == "holiday"
    assert second.long_run is None
    assert second.planned_km == sum(second.easy) + second.quality_km


def test_a_long_run_override_keeps_the_mp_km_up_to_its_length():
    plan = plan_of(MARATHON)
    mp_week = next(w for w in plan.weeks if w.kind is SPECIFIC)
    overridden = plan_of(MARATHON, overrides=(WeekOverride(mp_week.number, long_run_km=4),))
    assert overridden.weeks[mp_week.number - 1].long_run == LongRun(4, 4)


def test_an_override_past_the_end_is_an_error():
    with pytest.raises(SeasonError, match=r"^overrides\.24: the plan has only 23 weeks$"):
        plan_of(MARATHON, overrides=(WeekOverride(24, note="x"),))
