"""Warnings C3–C8 (TRAINING_MODEL.md §7, D-031).

Each check is a small function of the plan with a named threshold. C1 and C2
come from the layout (D-029) and the expansion; `check` only merges them.
Warnings never stop the build (D-001) and are not printed on the sheet (D-027).
Pure (D-013).
"""

from collections.abc import Callable, Iterator
from itertools import pairwise

from ttg import long_run
from ttg.model import Plan, PlanWarning, Session, SessionType, WarningCode, Week
from ttg.paces import SECONDS_PER_MINUTE, Pace, derive_paces
from ttg.sessions import MAX_THRESHOLD_MINUTES, round_km

# C3: planned km more than 10 % above the previous loading week. A common heuristic
# with weak evidence [source 21]. It compares the easy runs and the long run only: the
# quality km are an estimate that swings with the session type (owner, S5, D-031).
MAX_WEEKLY_RAMP = 0.10
# C4 [default]: 40–50 % is normal with 4 runs a week; 2026 peaked at 54 %.
MAX_LONG_RUN_SHARE = 0.50
# C6: at most 40′ at threshold in one session [source 5]; the same cap holds the T progression.
MAX_THRESHOLD_SESSION_MINUTES = MAX_THRESHOLD_MINUTES
# C7: running at I pace in one session, at most the lesser of 10 km and 8 % of the week
# [source 11]. Compared in whole km, the sheet's precision (D-025, D-031).
MAX_INTERVAL_KM = 10
MAX_INTERVAL_SHARE = 0.08
# C8 [default]: an overridden threshold pace this far from the derived one.
MAX_THRESHOLD_DEVIATION_SECONDS = 10


def check(plan: Plan) -> tuple[PlanWarning, ...]:
    """All warnings of the plan, ordered by week; warnings about the whole plan first."""
    warnings = [*plan.warnings]
    for weekly_check in _WEEKLY_CHECKS:
        warnings += weekly_check(plan)
    warnings += pace_consistency(plan)
    return tuple(sorted(warnings, key=lambda warning: (warning.week or 0, warning.code)))


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
    """C4."""
    for week in plan.weeks:
        if week.long_run_km > MAX_LONG_RUN_SHARE * week.planned_km:
            yield PlanWarning(
                WarningCode.LONG_RUN_SHARE,
                week.number,
                f"the long run is {_percent(week.long_run_km / week.planned_km)} of the week's "
                f"{week.planned_km} km (more than {_percent(MAX_LONG_RUN_SHARE)})",
            )


def long_run_above_cap(plan: Plan) -> Iterator[PlanWarning]:
    """C5: only an override or a long starting long run can pass the cap of the target race."""
    for week in plan.weeks:
        cap = long_run.cap(week.target.type)
        if week.long_run_km > cap:
            yield PlanWarning(
                WarningCode.LONG_RUN_ABOVE_CAP,
                week.number,
                f"the long run of {week.long_run_km} km is above the {cap} km cap for "
                f'"{week.target.name}" ({week.target.type})',
            )


def threshold_volume(plan: Plan) -> Iterator[PlanWarning]:
    """C6."""
    for week, session in _sessions_of(plan, SessionType.THRESHOLD):
        minutes = _minutes_at(session, plan.paces.threshold)
        if minutes > MAX_THRESHOLD_SESSION_MINUTES:
            yield PlanWarning(
                WarningCode.THRESHOLD_VOLUME,
                week.number,
                f"{minutes:.0f}′ at threshold in one session (more than {MAX_THRESHOLD_SESSION_MINUTES}′)",
            )


def interval_volume(plan: Plan) -> Iterator[PlanWarning]:
    """C7."""
    for week, session in _sessions_of(plan, SessionType.INTERVALS):
        km = round_km(_km_at(session, plan.paces.interval))
        limit = round_km(min(MAX_INTERVAL_KM, MAX_INTERVAL_SHARE * week.planned_km))
        if km > limit:
            yield PlanWarning(
                WarningCode.INTERVAL_VOLUME,
                week.number,
                f"{km} km at interval pace in one session (at most {limit}: the lesser of "
                f"{MAX_INTERVAL_KM} km and {_percent(MAX_INTERVAL_SHARE)} of the week's {week.planned_km} km)",
            )


def pace_consistency(plan: Plan) -> Iterator[PlanWarning]:
    """C8: compares an overridden threshold pace with the one derived from the race result."""
    paces = plan.season.paces
    if paces.threshold is None:
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
)


def _percent(share: float, sign: bool = False) -> str:
    """0.12 → "12 %" (or "+12 %"), as the sheet writes percentages."""
    return f"{'+' if sign else ''}{round(share * 100)} %"


def _easy_and_long_km(week: Week) -> int:
    return sum(week.easy) + week.long_run_km


def _sessions_of(plan: Plan, session_type: SessionType) -> Iterator[tuple[Week, Session]]:
    for week in plan.weeks:
        if isinstance(week.quality, Session) and week.quality.type is session_type:
            yield week, week.quality


def _minutes_at(session: Session, pace: Pace) -> float:
    """Minutes of work in a session given in minutes or in km."""
    per_rep = session.minutes if session.km is None else session.km * pace.seconds_per_km / SECONDS_PER_MINUTE
    return session.reps * per_rep


def _km_at(session: Session, pace: Pace) -> float:
    """Km of work in a session given in minutes or in km."""
    per_rep = session.km if session.km is not None else session.minutes * SECONDS_PER_MINUTE / pace.seconds_per_km
    return session.reps * per_rep
