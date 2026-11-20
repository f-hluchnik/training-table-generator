"""Warnings C3–C12 (TRAINING_MODEL.md §7, D-031, D-043, D-054).

Each check is a small function of the plan with a named threshold. C1 and C2
come from the layout (D-029) and the expansion; `ttg.expand` merges them with these.
Warnings never stop the build (D-001) and are not printed on the sheet (D-027).
Pure (D-013).
"""

from collections.abc import Callable, Iterator, Mapping
from dataclasses import replace
from itertools import pairwise
from types import MappingProxyType

from ttg import long_run
from ttg.model import LongRun, Plan, PlanWarning, RaceType, Session, SessionType, WarningCode, Week, WeekKind
from ttg.paces import derive_paces
from ttg.sessions import (
    MAX_HILL_MINUTES,
    MAX_HILL_REP_MINUTES,
    MAX_INTERVAL_KM,
    MAX_INTERVAL_SHARE_OF_WEEK,
    MAX_THRESHOLD_MINUTES,
    interval_limit_km,
    round_km,
    work_km,
    work_minutes,
)

# C3: planned km more than 10 % above the previous loading week. A common heuristic
# with weak evidence [source 21]. It compares the easy runs and the long run only: the
# quality km are an estimate that swings with the session type (owner, S5, D-031).
MAX_WEEKLY_RAMP = 0.10
# C4 [default]: 40–50 % is normal with 4 runs a week; 2026 peaked at 54 %.
MAX_LONG_RUN_SHARE = 0.50
# C6: at most 40′ at threshold in one session [source 5]; the same cap holds the T progression.
MAX_THRESHOLD_SESSION_MINUTES = MAX_THRESHOLD_MINUTES
# C7: Daniels' limit for I pace in one session, the one the I progression holds within
# (`ttg.sessions`, D-030); only an override can pass it. Compared in whole km (D-031).
# C8 [default]: an overridden threshold pace this far from the derived one.
MAX_THRESHOLD_DEVIATION_SECONDS = 10
# C9: the hill limits the H progression keeps (`ttg.sessions`, D-043): reps of at most 2′ [owner],
# at most 20′ of effort [source 31, 32]. Only an override can pass them. Reps given in km are timed
# at easy pace, as the km estimate counts hill efforts (TRAINING_MODEL.md §3).
# C10 [default, coach S11]: in a loading or bridge week, a quality run longer than the long run means
# the starting load is too small for the session; a taper's short threshold run may be longer.
QUALITY_CHECKED_WEEKS = (WeekKind.BUILD, WeekKind.SPECIFIC, WeekKind.BRIDGE)
# C11: the first long run that novice plans start from, below which the beginner mode fits better
# (D-054): Higdon's novice 10K about 4.8 km [source 35], novice half 6.4 km [source 36], and a
# comfortable 10 km before a marathon plan [source 39]; the ultra as the marathon [default].
STARTING_LONG_RUN_KM: Mapping[RaceType, int] = MappingProxyType(
    {RaceType.TEN_K: 5, RaceType.HALF: 6, RaceType.MARATHON: 10, RaceType.ULTRA: 10}
)
# C12: marathoners who ran under 30 km a week had about twice the injury risk, a retrospective
# association [source 43]. The beginner's only warning, worded to encourage (owner, S11).
MARATHON_BASE_WEEK_KM = 30


def check(plan: Plan) -> tuple[PlanWarning, ...]:
    """Warnings C3–C11 of the plan's weeks and paces (not C1 and C2, which come with the plan)."""
    warnings: list[PlanWarning] = []
    for weekly_check in _WEEKLY_CHECKS:
        warnings += weekly_check(plan)
    warnings += pace_consistency(plan)
    warnings += below_starting_level(plan)
    return tuple(warnings)


def check_beginner(plan: Plan) -> tuple[PlanWarning, ...]:
    """A beginner's plan gets only C12, an encouragement rather than a correction (owner, S11, D-054)."""
    return tuple(marathon_base(plan))


def weekly_ramp(plan: Plan) -> Iterator[PlanWarning]:
    """C3: not after a deload, taper, race or recovery week, which are meant to be lower."""
    for previous, week in pairwise(plan.weeks):
        if not (previous.kind.is_loading and week.kind.is_loading):
            continue
        before, after = _easy_and_long_km(previous), _easy_and_long_km(week)
        if after > before * (1 + MAX_WEEKLY_RAMP):
            yield PlanWarning(
                WarningCode.WEEKLY_RAMP,
                week.number,
                f"easy runs and long run: {after} km, {_percent(after / before - 1, sign=True)} on week "
                f"{previous.number}'s {before} km (more than {_percent(MAX_WEEKLY_RAMP)})",
            )


def long_run_share(plan: Plan) -> Iterator[PlanWarning]:
    """C4: not for a race in the long run's place, which is not a long run (D-039)."""
    for week in _weeks_with_a_long_run(plan):
        if week.long_run_km > MAX_LONG_RUN_SHARE * week.planned_km:
            yield PlanWarning(
                WarningCode.LONG_RUN_SHARE,
                week.number,
                f"the long run is {_percent(week.long_run_km / week.planned_km)} of the week's "
                f"{week.planned_km} km (more than {_percent(MAX_LONG_RUN_SHARE)})",
            )


def long_run_above_cap(plan: Plan) -> Iterator[PlanWarning]:
    """C5: only an override or a long starting long run can pass the cap of the target race.

    Not for a race in the long run's place: a long C race is not a long run (D-039).
    """
    for week in _weeks_with_a_long_run(plan):
        cap = long_run.cap(week.target.type)
        if week.long_run_km > cap:
            yield PlanWarning(
                WarningCode.LONG_RUN_ABOVE_CAP,
                week.number,
                f"the long run of {week.long_run_km} km is above the {cap} km cap for "
                f'"{week.target.name}" ({week.target.type})',
            )


def quality_longer_than_long_run(plan: Plan) -> Iterator[PlanWarning]:
    """C10: the quality run's estimate includes its warm-up and cool-down (TRAINING_MODEL.md §3)."""
    for week in _weeks_with_a_long_run(plan):
        if week.kind in QUALITY_CHECKED_WEEKS and week.quality_km > week.long_run_km:
            yield PlanWarning(
                WarningCode.QUALITY_LONGER_THAN_LONG_RUN,
                week.number,
                f"the quality run, about {week.quality_km} km with warm-up and cool-down, is longer than "
                f"the {week.long_run_km} km long run",
            )


def below_starting_level(plan: Plan) -> Iterator[PlanWarning]:
    """C11: compared with the first week's target race; the beginner mode builds up more gently."""
    first_long_run_km = plan.season.load.long_run_km
    target = plan.weeks[0].target
    starting_km = STARTING_LONG_RUN_KM[target.type]
    if first_long_run_km < starting_km:
        yield PlanWarning(
            WarningCode.BELOW_STARTING_LEVEL,
            None,
            f'a first long run of {first_long_run_km} km is short for "{target.name}" ({target.type}): '
            f"plans usually start from about {starting_km} km; the beginner mode (beginner = true in [load]) "
            "builds up more gently",
        )


def marathon_base(plan: Plan) -> Iterator[PlanWarning]:
    """C12: for a marathon or longer, the plan's biggest week."""
    long_races = [race for race in plan.season.races if race.is_key and race.type in _LONG_RACES]
    biggest_km = max(week.planned_km for week in plan.weeks)
    if long_races and biggest_km < MARATHON_BASE_WEEK_KM:
        yield PlanWarning(
            WarningCode.MARATHON_BASE,
            None,
            f"your biggest week is {biggest_km} km. A first marathon goes best from about "
            f"{MARATHON_BASE_WEEK_KM} km a week: a half marathon on the way, or a later date, gives your "
            "legs time to get there. Walk breaks in the race are fine.",
        )


def threshold_volume(plan: Plan) -> Iterator[PlanWarning]:
    """C6."""
    for week, session in _sessions_of(plan, SessionType.THRESHOLD):
        minutes = work_minutes(session, plan.paces.threshold)
        if minutes > MAX_THRESHOLD_SESSION_MINUTES:
            yield PlanWarning(
                WarningCode.THRESHOLD_VOLUME,
                week.number,
                f"{minutes:.0f}′ at threshold in one session (more than {MAX_THRESHOLD_SESSION_MINUTES}′)",
            )


def interval_volume(plan: Plan) -> Iterator[PlanWarning]:
    """C7."""
    for week, session in _sessions_of(plan, SessionType.INTERVALS):
        km = round_km(work_km(session, plan.paces.interval))
        limit = interval_limit_km(week.planned_km)
        if km > limit:
            yield PlanWarning(
                WarningCode.INTERVAL_VOLUME,
                week.number,
                f"{km} km at interval pace in one session (at most {limit}: the lesser of "
                f"{MAX_INTERVAL_KM} km and {_percent(MAX_INTERVAL_SHARE_OF_WEEK)} of the week's {week.planned_km} km)",
            )


def hill_volume(plan: Plan) -> Iterator[PlanWarning]:
    """C9: one warning per session, naming each limit it passes."""
    for week, session in _sessions_of(plan, SessionType.HILLS):
        rep_minutes = work_minutes(replace(session, reps=1), plan.paces.easy)
        total_minutes = work_minutes(session, plan.paces.easy)
        passed = []
        if rep_minutes > MAX_HILL_REP_MINUTES:
            passed.append(f"reps of {rep_minutes:.0f}′ (at most {MAX_HILL_REP_MINUTES}′)")
        if total_minutes > MAX_HILL_MINUTES:
            passed.append(f"{total_minutes:.0f}′ in all (at most {MAX_HILL_MINUTES}′)")
        if passed:
            yield PlanWarning(WarningCode.HILL_VOLUME, week.number, f"hill repeats: {' and '.join(passed)}")


def pace_consistency(plan: Plan) -> Iterator[PlanWarning]:
    """C8: compares an overridden threshold pace with the one derived from the race result."""
    paces = plan.season.paces
    if paces.threshold is None or paces.race_result is None:
        return
    derived = derive_paces(paces.race_result.distance_km, paces.race_result.time).threshold
    deviation = paces.threshold.seconds_per_km - derived.seconds_per_km
    if abs(deviation) > MAX_THRESHOLD_DEVIATION_SECONDS:
        direction = "faster" if deviation < 0 else "slower"
        yield PlanWarning(
            WarningCode.PACE_CONSISTENCY,
            None,
            f"threshold pace {paces.threshold.format()} is {abs(deviation):.1f} s/km {direction} than "
            f"{derived.format()}, derived from the race result (more than {MAX_THRESHOLD_DEVIATION_SECONDS})",
        )


_WEEKLY_CHECKS: tuple[Callable[[Plan], Iterator[PlanWarning]], ...] = (
    weekly_ramp,
    long_run_share,
    long_run_above_cap,
    threshold_volume,
    interval_volume,
    hill_volume,
    quality_longer_than_long_run,
)
_LONG_RACES = (RaceType.MARATHON, RaceType.ULTRA)


def _percent(share: float, sign: bool = False) -> str:
    """0.12 → "12 %" (or "+12 %"), as the sheet writes percentages."""
    return f"{'+' if sign else ''}{round(share * 100)} %"


def _easy_and_long_km(week: Week) -> int:
    return sum(week.easy) + week.long_run_km


def _weeks_with_a_long_run(plan: Plan) -> Iterator[Week]:
    return (week for week in plan.weeks if isinstance(week.long_run, LongRun))


def _sessions_of(plan: Plan, session_type: SessionType) -> Iterator[tuple[Week, Session]]:
    for week in plan.weeks:
        if isinstance(week.quality, Session) and week.quality.type is session_type:
            yield week, week.quality
