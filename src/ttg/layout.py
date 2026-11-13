"""Backward phase layout (TRAINING_MODEL.md §5, D-009).

Each A or B race gets a taper (ending with its race week), a race-specific
block before it and a recovery block after it; build weeks fill whatever room
is left. When the weeks before a race are too few, blocks give way in a fixed
order, each with a warning (D-001). C races get no phases (D-017). Pure
(D-013).
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import Enum
from types import MappingProxyType

from ttg.calendar import Calendar, plan_calendar
from ttg.model import Phase, PhaseKind, PlanWarning, Priority, Race, RaceType, Season, WarningCode


@dataclass(frozen=True)
class PhaseLengths:
    """Phase lengths of one race, in weeks."""

    taper: int  # including the race week
    specific: int
    recovery: int


# [default, calibrated in T-04] Sources per row in TRAINING_MODEL.md §5.
DEFAULT_PHASE_LENGTHS: Mapping[RaceType, PhaseLengths] = MappingProxyType(
    {
        RaceType.TEN_K: PhaseLengths(taper=1, specific=3, recovery=1),
        RaceType.HALF: PhaseLengths(taper=2, specific=4, recovery=2),
        RaceType.MARATHON: PhaseLengths(taper=2, specific=6, recovery=2),
        RaceType.ULTRA: PhaseLengths(taper=3, specific=6, recovery=3),
    }
)

# D-017: a B race's default taper is one week shorter.
B_RACE_TAPER_CUT_WEEKS = 1
# A taper always keeps the race week.
RACE_WEEK = 1


class _Block(Enum):
    """The blocks that can give way in the weeks before a race week."""

    RECOVERY = "recovery"  # after the previous race
    SPECIFIC = "specific block"
    TAPER = "taper"  # including the race week


# TRAINING_MODEL.md §5 (owner, S3): what gives way, in order, and down to how
# many weeks. Build weeks are only filler, so they give way first, silently.
_BEFORE_FIRST_RACE: Sequence[tuple[_Block, int]] = (
    (_Block.SPECIFIC, 0),
    (_Block.TAPER, RACE_WEEK),
)
_BETWEEN_RACES: Sequence[tuple[_Block, int]] = (
    (_Block.SPECIFIC, 0),
    (_Block.RECOVERY, 1),
    (_Block.TAPER, RACE_WEEK),
    (_Block.RECOVERY, 0),
)


@dataclass(frozen=True)
class Layout:
    calendar: Calendar
    phases: tuple[Phase, ...]  # consecutive, covering every week of the plan
    warnings: tuple[PlanWarning, ...]


def lay_out(season: Season, today: date) -> Layout:
    """Place the phases of the season. Raises SeasonError if a race falls before week 1."""
    calendar = plan_calendar(season, today)
    races, warnings = _key_races(season.races, calendar)
    phases: list[Phase] = []
    previous: Race | None = None
    first_week = 1
    for race in races:
        race_week = calendar.week_of(race.date)
        gap_phases, gap_warnings = _phases_up_to(race, previous, first_week, race_week)
        phases += gap_phases
        warnings += gap_warnings
        previous, first_week = race, race_week + 1
    phases += _phases_after(previous, first_week, calendar.weeks)
    return Layout(calendar, tuple(phases), tuple(warnings))


def phase_lengths(race: Race) -> PhaseLengths:
    """The race's phase lengths: its overrides, else the defaults for its type (D-009, D-017)."""
    default = DEFAULT_PHASE_LENGTHS[race.type]
    taper = default.taper
    if race.priority is Priority.B:
        taper = max(RACE_WEEK, taper - B_RACE_TAPER_CUT_WEEKS)
    return PhaseLengths(
        taper=_override(race.taper_weeks, taper),
        specific=_override(race.specific_weeks, default.specific),
        recovery=_override(race.recovery_weeks, default.recovery),
    )


def _override(value: int | None, default: int) -> int:
    return default if value is None else value


def _key_races(races: Iterable[Race], calendar: Calendar) -> tuple[list[Race], list[PlanWarning]]:
    """The A and B races in date order; of two in the same week only the later one (owner, S3)."""
    kept: list[Race] = []
    warnings: list[PlanWarning] = []
    for race in (race for race in races if race.is_key):
        if kept and calendar.week_of(kept[-1].date) == calendar.week_of(race.date):
            earlier = kept.pop()
            warnings.append(
                PlanWarning(
                    WarningCode.RACES_TOO_CLOSE,
                    calendar.week_of(race.date),
                    f'"{earlier.name}" and "{race.name}" are in the same week: '
                    f'one race week, no recovery after "{earlier.name}"',
                )
            )
        kept.append(race)
    return kept, warnings


def _phases_up_to(
    race: Race, previous: Race | None, first_week: int, race_week: int
) -> tuple[list[Phase], list[PlanWarning]]:
    """The phases from `first_week` to the race week: recovery, build, specific, taper."""
    lengths = phase_lengths(race)
    wanted = {
        _Block.RECOVERY: phase_lengths(previous).recovery if previous else 0,
        _Block.SPECIFIC: lengths.specific,
        _Block.TAPER: lengths.taper,
    }
    available = race_week - first_week + 1
    fitted = _fit(wanted, available, _BETWEEN_RACES if previous else _BEFORE_FIRST_RACE)
    phases = _consecutive(
        first_week,
        (
            (PhaseKind.RECOVERY, fitted[_Block.RECOVERY], previous),
            (PhaseKind.BUILD, available - sum(fitted.values()), None),
            (PhaseKind.SPECIFIC, fitted[_Block.SPECIFIC], race),
            (PhaseKind.TAPER, fitted[_Block.TAPER], race),
        ),
    )
    warnings = [
        _shortened(block, wanted[block], fitted[block], race, previous, race_week)
        for block in _Block
        if fitted[block] < wanted[block]
    ]
    return phases, warnings


def _phases_after(last_race: Race | None, first_week: int, last_week: int) -> list[Phase]:
    """After the last A or B race (C races, a multi-day race): recovery, then build."""
    remaining = last_week - first_week + 1
    recovery = min(phase_lengths(last_race).recovery, remaining) if last_race else 0
    return _consecutive(
        first_week,
        (
            (PhaseKind.RECOVERY, recovery, last_race),
            (PhaseKind.BUILD, remaining - recovery, None),
        ),
    )


def _fit(wanted: Mapping[_Block, int], available: int, order: Sequence[tuple[_Block, int]]) -> dict[_Block, int]:
    """Shorten blocks in `order`, each only as far as needed, until they fit `available` weeks."""
    fitted = dict(wanted)
    excess = sum(fitted.values()) - available
    for block, minimum in order:
        cut = max(0, min(excess, fitted[block] - minimum))
        fitted[block] -= cut
        excess -= cut
    return fitted


def _consecutive(first_week: int, parts: Iterable[tuple[PhaseKind, int, Race | None]]) -> list[Phase]:
    """Phases placed one after another from `first_week`; empty ones are left out."""
    phases = []
    for kind, weeks, race in parts:
        if weeks > 0:
            phases.append(Phase(kind, first_week, weeks, race))
            first_week += weeks
    return phases


def _shortened(
    block: _Block, wanted: int, fitted: int, race: Race, previous: Race | None, race_week: int
) -> PlanWarning:
    owner = previous if block is _Block.RECOVERY else race
    assert owner is not None  # a recovery is wanted only after a previous race
    if previous is None:
        code, reason = WarningCode.PLAN_TOO_SHORT, "the plan starts too late"
    else:
        code, reason = WarningCode.RACES_TOO_CLOSE, f'"{previous.name}" and "{race.name}" are too close'
    return PlanWarning(
        code,
        race_week,
        f'"{owner.name}": {block.value} shortened from {wanted} to {_weeks(fitted)} ({reason})',
    )


def _weeks(count: int) -> str:
    return f"{count} week" if count == 1 else f"{count} weeks"
