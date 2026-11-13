"""Warnings C3–C9 (T-07, D-043): each check fires and stays quiet; 2026 gives the expected warnings."""

from dataclasses import replace
from datetime import date

import pytest

from ttg.checks import (
    check,
    hill_volume,
    interval_volume,
    long_run_above_cap,
    long_run_share,
    pace_consistency,
    threshold_volume,
    weekly_ramp,
)
from ttg.expand import expand
from ttg.model import (
    Load,
    Paces,
    Plan,
    Priority,
    Race,
    Session,
    SessionType,
    WarningCode,
    WeekKind,
    WeekOverride,
)
from ttg.paces import Pace
from ttg.spec import load_season

from support import LOAD, PACES, SEASONS, TODAY
from support import season as support_season

MARATHON = Race("Marathon", date(2027, 10, 10), 42.195)
C1, C3, C4, C8 = (WarningCode.RACES_TOO_CLOSE, WarningCode.WEEKLY_RAMP,
                  WarningCode.LONG_RUN_SHARE, WarningCode.PACE_CONSISTENCY)  # fmt: skip


def plan_of(*overrides: WeekOverride, load: Load = LOAD, paces: Paces = PACES) -> Plan:
    season = support_season(MARATHON, paces=paces, load=load, start=date(2027, 5, 3), overrides=overrides)
    return expand(season, TODAY)


def weeks_of(warnings) -> list[int | None]:
    return [warning.week for warning in warnings]


# --- C3 weekly ramp ------------------------------------------------------------------------


def test_c3_quiet_for_the_default_progression():
    assert list(weekly_ramp(plan_of())) == []


def test_c3_fires_for_a_jump_of_easy_runs_and_long_run():
    warnings = list(weekly_ramp(plan_of(WeekOverride(2, long_run_km=22))))  # 15 → 22 km
    assert weeks_of(warnings) == [2]
    assert warnings[0].message == "easy runs and long run: 46 km, +18 % on week 1's 39 km (more than 10 %)"


def test_c3_ignores_the_quality_run_estimate():
    # Week 2 gets a much longer quality run; easy runs + long run grow as usual.
    assert list(weekly_ramp(plan_of(WeekOverride(2, quality=Session(SessionType.THRESHOLD, reps=5, km=4))))) == []


def test_c3_not_after_a_deload():
    plan = plan_of()
    assert plan.weeks[3].kind is WeekKind.DELOAD  # week 5 is far above week 4, by design
    assert 5 not in weeks_of(weekly_ramp(plan))


# --- C4 long-run share ---------------------------------------------------------------------


def test_c4_quiet_for_the_default_plan():
    assert list(long_run_share(plan_of())) == []


def test_c4_fires_above_half_of_the_week():
    assert weeks_of(long_run_share(plan_of(WeekOverride(3, long_run_km=40)))) == [3]


# --- C5 long run above cap -----------------------------------------------------------------


def test_c5_quiet_at_the_cap():
    assert list(long_run_above_cap(plan_of(WeekOverride(3, long_run_km=32)))) == []


def test_c5_fires_above_the_target_races_cap():
    warnings = list(long_run_above_cap(plan_of(WeekOverride(3, long_run_km=35))))
    assert weeks_of(warnings) == [3]
    assert warnings[0].message == 'the long run of 35 km is above the 32 km cap for "Marathon" (marathon)'


def test_c5_fires_when_the_starting_long_run_is_above_the_cap():
    assert weeks_of(long_run_above_cap(plan_of(load=Load(12, 34))))[:3] == [1, 2, 3]


def test_c4_and_c5_ignore_a_race_in_the_long_runs_place():
    """A 50 km C race in a marathon plan is not a long run above the 32 km cap (D-039)."""
    ultra = Race("Ultra", date(2027, 5, 30), 50, Priority.C)  # Sunday of week 4
    season = support_season(ultra, MARATHON, start=date(2027, 5, 3))
    plan = expand(season, TODAY)
    assert plan.weeks[3].long_run == ultra
    assert list(long_run_share(plan)) == []
    assert list(long_run_above_cap(plan)) == []


# --- C6 threshold volume -------------------------------------------------------------------


def test_c6_quiet_at_40_minutes():
    forty_minutes = Session(SessionType.THRESHOLD, reps=5, minutes=8)
    assert list(threshold_volume(plan_of(WeekOverride(3, quality=forty_minutes)))) == []


def test_c6_fires_above_40_minutes_also_for_km_repeats():
    by_minutes = Session(SessionType.THRESHOLD, reps=5, minutes=10)
    by_km = Session(SessionType.THRESHOLD, reps=5, km=2)  # 10 km at 4:40 = 47′
    plan = plan_of(WeekOverride(3, quality=by_minutes), WeekOverride(7, quality=by_km))
    assert weeks_of(threshold_volume(plan)) == [3, 7]


# --- C9 hill volume ------------------------------------------------------------------------


def test_c9_quiet_for_the_whole_hill_progression_and_at_the_limits():
    at_the_limits = Session(SessionType.HILLS, reps=10, minutes=2)  # 2′ reps, 20′ in all
    assert list(hill_volume(plan_of(WeekOverride(3, quality=at_the_limits)))) == []
    assert list(hill_volume(plan_of())) == []


@pytest.mark.parametrize(
    ("session", "message"),
    [
        (Session(SessionType.HILLS, reps=5, minutes=4), "hill repeats: reps of 4′ (at most 2′)"),
        (Session(SessionType.HILLS, reps=12, minutes=2), "hill repeats: 24′ in all (at most 20′)"),
        (Session(SessionType.HILLS, reps=6, minutes=4), "reps of 4′ (at most 2′) and 24′ in all (at most 20′)"),
        (Session(SessionType.HILLS, reps=5, km=0.5), "reps of 3′"),  # timed at easy pace, 5:37
    ],
)
def test_c9_fires_above_the_hill_limits(session, message):
    (warning,) = hill_volume(plan_of(WeekOverride(3, quality=session)))
    assert (warning.code, warning.week) == (WarningCode.HILL_VOLUME, 3)
    assert message in warning.message


# --- C7 interval volume --------------------------------------------------------------------


def test_c7_quiet_at_the_limit_in_whole_km():
    # 2026 week 2: I 5 × 3′ at 4:15 is 3.53 km; 8 % of 44 km is 3.52: equal in whole km.
    plan = expand(load_season(SEASONS / "2026.toml"), TODAY)
    assert list(interval_volume(plan)) == []


def test_c7_fires_above_8_percent_of_the_week():
    plan = plan_of(WeekOverride(2, quality=Session(SessionType.INTERVALS, reps=6, minutes=5)))  # 7 km
    assert weeks_of(interval_volume(plan)) == [2]


def test_c7_quiet_for_the_default_progression_which_holds_within_the_limit():
    assert list(interval_volume(plan_of())) == []


def test_c7_fires_above_10_km_in_a_big_week():
    big_week = Load(easy_run_km=30, long_run_km=30, runs_per_week=6)  # 8 % of ≥ 150 km > 10 km
    plan = plan_of(WeekOverride(2, quality=Session(SessionType.INTERVALS, reps=11, km=1)), load=big_week)
    warnings = list(interval_volume(plan))
    assert weeks_of(warnings) == [2]
    assert "at most 10" in warnings[0].message


# --- C8 pace consistency -------------------------------------------------------------------


def test_c8_quiet_without_a_threshold_override_or_close_to_the_derived_pace():
    assert list(pace_consistency(plan_of())) == []
    assert list(pace_consistency(plan_of(paces=replace(PACES, threshold=Pace.parse("4:31"))))) == []


@pytest.mark.parametrize(("threshold", "direction"), [("4:30", "faster"), ("4:51", "slower")])
def test_c8_fires_more_than_10_seconds_off(threshold, direction):
    warnings = list(pace_consistency(plan_of(paces=replace(PACES, threshold=Pace.parse(threshold)))))
    assert [(w.code, w.week) for w in warnings] == [(C8, None)]
    assert direction in warnings[0].message


# --- all checks ------------------------------------------------------------------------------


def test_2026_gives_the_expected_warnings():
    warnings = expand(load_season(SEASONS / "2026.toml"), TODAY).warnings
    assert [(w.code, w.week) for w in warnings] == [
        (C8, None),  # T 4:30 vs derived 4:40
        (C4, 13),  # 33 of 64 km: the hill session's estimate is low
        (C3, 14),  # the 40 km long-run override: easy runs + long run 57 → 64 km
        (C4, 14),  # 40 of 75 km
        (C1, 23),  # the marathon's specific block shortened to 2 weeks
    ]


def test_the_plan_carries_the_checks_warnings_too():
    plan = expand(load_season(SEASONS / "2026.toml"), TODAY)
    assert set(check(plan)) < set(plan.warnings)
