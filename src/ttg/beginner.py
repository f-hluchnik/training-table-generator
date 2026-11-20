"""The beginner's rules (TRAINING_MODEL.md §11, D-054): gentle growth, gentle intensity, no warnings.

The phase layout and the long run's taper and restart are the standard ones; what differs is here: how
a week's runs grow, the long-run caps, the easy runs, which quality run a week gets, and a plan without
a race. `ttg.expand` applies them. Pure (D-013).

Studies give novices no progression numbers: a 10 % rule did not prevent injuries [source 21], and
the evidence on load changes is very limited [source 42]. The numbers follow established beginner
plans (NHS Couch to 5K, Higdon's novice plans), or are our own defaults fitted to them, as tagged.
"""

import datetime as dt
from collections.abc import Mapping
from dataclasses import replace
from enum import Enum, auto
from types import MappingProxyType

from ttg.calendar import ONE_WEEK, monday_of, monday_on_or_after
from ttg.model import Race, RaceType, Season, Session, SessionType, WeekKind
from ttg.paces import Pace
from ttg.sessions import round_km

# --- the runs of a week -----------------------------------------------------

# [default, coach S11] One step of 1 km a loading week, from week 2. Higdon's novice 10K adds about
# 0.8 km a week to the long run [source 35]. Whole km, as the sheet prints them.
STEP_KM = 1
# [default, coach S11] Which run takes the step: first the easy runs, while even the longest of them is
# shorter than half the long run (a 1 km run is too short to be useful); then the long run, once it has
# held its distance for 2 loading weeks or is 5 km or more, so that a step is at most 20 %; otherwise
# the shortest easy run. Only one easy run has to catch up, so that with 4 runs a week the long run is
# not held back by three short ones (owner, T-29). The
# race-specific block gives every step to the long run. Couch to 5K also holds a stage before the next
# jump [source 33]; a percentage rule has no evidence for novices [source 21, 41, 42].
EASY_CATCH_UP_SHARE = 0.5
LONG_RUN_HOLD_WEEKS = 2
LONG_RUN_HOLD_BELOW_KM = 5

# [default, fitted to Higdon] Without `easy_run_km`, an easy run is ¾ of the first long run:
# Higdon's novice plans start with weekday runs of 2.5 mi to a 3 mi long run (10K) and 3 mi to
# 4 mi (half) [source 35, 36].
DEFAULT_EASY_SHARE_OF_LONG_RUN = 0.75
MIN_DEFAULT_EASY_RUN_KM = 1

# [default] An easy run grows up to these lengths; Higdon's weekday runs top out at 3 mi (10K) and
# 5 mi (half) [source 35, 36]. It also stays at least 1 km shorter than the long run.
EASY_RUN_CAP_KM: Mapping[RaceType, int] = MappingProxyType(
    {RaceType.TEN_K: 5, RaceType.HALF: 8, RaceType.MARATHON: 8, RaceType.ULTRA: 8}
)
EASY_RUN_BELOW_LONG_RUN_KM = 1

# [default] A taper, race or recovery week takes 1 km off each easy run, but does not shorten a run
# below 2 km, about a Couch to 5K week-1 session [source 33]. A beginner's deload only holds: no step,
# strides instead of fartlek or hills [default, coach S11]; at these distances a 75 % long run would
# hardly differ from the week before.
REDUCTION_KM = 1
MIN_REDUCED_EASY_RUN_KM = 2
REDUCED_KINDS = (WeekKind.TAPER, WeekKind.RACE, WeekKind.RECOVERY)

# --- the long run -----------------------------------------------------------

# Higdon's novice plans peak at 4.8 km for a 5 km and 8.9 km for a 10 km [source 34, 35]: about
# 90 % of the race distance, which is the cap for races up to 10 km.
SHORT_RACE_CAP_SHARE = 0.9
# Higdon's novice half peaks at 10 mi [source 36].
HALF_CAP_KM = 16
# A marathon or longer: 20 mi in Higdon's novice plan [source 37], and at most 3 h at easy pace
# [default], looser than Daniels' 150 min for trained runners [source 25], since a beginner runs slower.
LONG_RACE_CAP_KM = 32
LONG_RACE_CAP_MINUTES = 180

# --- the quality run ----------------------------------------------------------

# Gentle intensity, by effort and never at a pace: strides first, then short hills and fartlek; full
# interval workouts are not for the start [source 45]. Untrained runners gain from short hard
# efforts [source 47], and progressing intensity was no riskier than progressing volume in
# recreational runners [source 48]; the injury signal of hard intervals in novices [source 47] is why
# they stay short. [default, coach S11] Weeks 1–2: none; from week 3 strides; from week 5 fartlek and
# hills in turn in the loading weeks (fartlek first), strides in deload, taper and bridge weeks.
STRIDES_FROM_WEEK = 3
EFFORTS_FROM_WEEK = 5
# [default, coach S11] Each type's steps as (reps, minutes each); the recovery lasts as long as the
# effort (`sessions.EQUAL_RECOVERY_TYPES`). A type stays at its last step.
EFFORT_STEPS: Mapping[SessionType, tuple[tuple[int, float], ...]] = MappingProxyType(
    {
        SessionType.FARTLEK: ((6, 1), (8, 1), (6, 1.5), (5, 2)),
        SessionType.HILLS: ((6, 0.5), (8, 0.5), (6, 0.75), (6, 1)),
    }
)
EFFORT_ROTATION = (SessionType.FARTLEK, SessionType.HILLS)
# [default, coach S11] Hard time at most 10 % of the week's running time and at most 10′: about half
# the hard share of polarised training in trained runners [source 49]. A step that would pass it is
# not taken; when even the first is too much, the week has strides.
MAX_HARD_SHARE_OF_WEEK = 0.10
MAX_HARD_MINUTES = 10

# [default, coach S11] Rest before the race or goal: the race week has no quality run and one easy
# run fewer, as in Higdon's novice race weeks [source 35, 36], but always one run besides the race.
RACE_WEEK_RUNS_LEFT_OUT = 1
MIN_RACE_WEEK_EASY_RUNS = 1

# --- a plan without a race ----------------------------------------------------

# [default, coach S11] "Just start running": 9 weeks towards 5 km, the length and the end of Couch to 5K
# [source 33], printed as a goal.
NO_GOAL_WEEKS = 9
NO_GOAL_KM = 5.0
NO_GOAL_NAME = "5 km"


def default_easy_run_km(long_run_km: int) -> int:
    return max(MIN_DEFAULT_EASY_RUN_KM, round_km(DEFAULT_EASY_SHARE_OF_LONG_RUN * long_run_km))


def with_a_goal(season: Season, today: dt.date) -> Season:
    """The season, with a goal of 5 km at the end of 9 weeks (or of `weeks`) when it has no race."""
    if season.races:
        return season
    first_monday = monday_of(season.start) if season.start is not None else monday_on_or_after(today)
    weeks = season.weeks or NO_GOAL_WEEKS
    goal_day = first_monday + weeks * ONE_WEEK - dt.timedelta(days=1)
    goal = Race(NO_GOAL_NAME, goal_day, NO_GOAL_KM, goal=True)
    return replace(season, races=(goal,), start=first_monday, weeks=None)


def long_run_cap(race: Race, easy: Pace) -> int:
    """The beginner's long-run cap for a race; reached in the race-specific block, as for anyone."""
    match race.type:
        case RaceType.TEN_K:
            return round_km(SHORT_RACE_CAP_SHARE * race.distance_km)
        case RaceType.HALF:
            return HALF_CAP_KM
    three_hours_km = round_km(LONG_RACE_CAP_MINUTES * 60 / easy.seconds_per_km)
    return min(LONG_RACE_CAP_KM, three_hours_km)


def easy_run_cap(race: Race, long_run_km: int) -> int:
    return min(EASY_RUN_CAP_KM[race.type], long_run_km - EASY_RUN_BELOW_LONG_RUN_KM)


def easy_runs_catch_up(long_run_km: int, longest_easy_km: int) -> bool:
    return longest_easy_km < EASY_CATCH_UP_SHARE * long_run_km


def long_run_may_grow(long_run_km: int, weeks_held: int) -> bool:
    """Below 5 km the long run holds each distance for 2 loading weeks (rule above)."""
    return weeks_held >= LONG_RUN_HOLD_WEEKS or long_run_km >= LONG_RUN_HOLD_BELOW_KM


def reduced(easy_kms: tuple[int, ...]) -> tuple[int, ...]:
    """A reduced week's easy runs: each 1 km shorter, but not below 2 km by the cut."""
    return tuple(max(km - REDUCTION_KM, min(km, MIN_REDUCED_EASY_RUN_KM)) for km in easy_kms)


def grown(easy_kms: tuple[int, ...], cap_km: int) -> tuple[int, ...] | None:
    """The easy runs with the shortest one 1 km longer, longest first; None when it is at the cap."""
    shortest = min(easy_kms)
    if shortest + STEP_KM > cap_km:
        return None
    runs = list(easy_kms)
    runs[runs.index(shortest)] += STEP_KM
    return tuple(sorted(runs, reverse=True))


class Quality(Enum):
    """What kind of quality run a beginner's week has."""

    NONE = auto()
    STRIDES = auto()
    EFFORT = auto()  # fartlek or hills, in turn (`EFFORT_ROTATION`)


def quality_of(kind: WeekKind, number: int) -> Quality:
    if kind in (WeekKind.RACE, WeekKind.RECOVERY) or number < STRIDES_FROM_WEEK:
        return Quality.NONE
    if kind.is_loading and number >= EFFORTS_FROM_WEEK:
        return Quality.EFFORT
    return Quality.STRIDES


def hard_minutes_limit(week_km: int, easy: Pace) -> float:
    week_minutes = week_km * easy.seconds_per_km / 60
    return min(MAX_HARD_MINUTES, MAX_HARD_SHARE_OF_WEEK * week_minutes)


def effort_step(session_type: SessionType, highest: int, limit_minutes: float) -> int | None:
    """The highest step up to `highest` within the week's limit of hard minutes; None if none is."""
    steps = EFFORT_STEPS[session_type][: highest + 1]
    within = [index for index, (reps, minutes) in enumerate(steps) if reps * minutes <= limit_minutes]
    return within[-1] if within else None


def effort_session(session_type: SessionType, step: int) -> Session:
    reps, minutes = EFFORT_STEPS[session_type][step]
    return Session(session_type, reps=reps, minutes=minutes)
