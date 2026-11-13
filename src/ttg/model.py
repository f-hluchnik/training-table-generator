"""The season: what the runner writes in season.toml, as immutable values.

The schema is documented in docs/PLAN.md §4 (D-025). Validation lives in
`ttg.spec`; these classes only hold already-validated data. The plan-side
classes (phases, weeks, the plan) are added with the tickets that build them
(T-04, T-06).
"""

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from ttg.paces import Pace

# D-016: 3–6 runs a week, default 4 (one quality run, one long run, the rest easy).
MIN_RUNS_PER_WEEK = 3
MAX_RUNS_PER_WEEK = 6
DEFAULT_RUNS_PER_WEEK = 4

DEFAULT_TITLE = "training plan"

# D-008, TRAINING_MODEL.md §8: the standard order in which sessions are dropped.
DEFAULT_RULES = (
    "Short on time: drop an easy run → intensity → long run.",
    "Tired or ill: drop intensity first.",
)


class Priority(StrEnum):
    """Race priority (D-017)."""

    A = "A"  # full taper and recovery
    B = "B"  # taper shortened by one week
    C = "C"  # tune-up: replaces one quality run; no taper, specific or recovery block


class SessionType(StrEnum):
    """Quality-run types (TRAINING_MODEL.md §1)."""

    HILLS = "H"
    INTERVALS = "I"
    THRESHOLD = "T"
    MARATHON_PACE = "MP"
    STRIDES = "S"
    NONE = "none"

    @property
    def has_repetitions(self) -> bool:
        return self not in (SessionType.STRIDES, SessionType.NONE)


class EasyRuns(StrEnum):
    """The easy-run pattern of a week (D-022)."""

    REGULAR = "regular"  # every easy run is the full length
    REDUCED = "reduced"  # the last easy run is halved


@dataclass(frozen=True)
class Race:
    name: str
    date: date
    distance_km: float
    priority: Priority = Priority.A
    end: date | None = None  # last day of a multi-day race
    # Phase-length overrides in weeks (D-009, D-025); None = the default for the distance.
    taper_weeks: int | None = None  # includes the race week
    specific_weeks: int | None = None
    recovery_weeks: int | None = None

    @property
    def last_day(self) -> date:
        return self.end or self.date


@dataclass(frozen=True)
class RaceResult:
    """A recent race result: the anchor for the default paces (D-015)."""

    distance_km: float
    time: timedelta


@dataclass(frozen=True)
class Paces:
    """The pace anchor and the optional overrides (D-005)."""

    race_result: RaceResult
    easy: Pace | None = None
    mp: Pace | None = None
    threshold: Pace | None = None
    interval: Pace | None = None


@dataclass(frozen=True)
class Load:
    """What the runner runs now (PLAN §4)."""

    easy_run_km: int
    long_run_km: int  # the long run of the first week
    runs_per_week: int = DEFAULT_RUNS_PER_WEEK


@dataclass(frozen=True)
class Session:
    """A quality session: `reps` × (`minutes` or `km`), or a type without repetitions."""

    type: SessionType
    reps: int | None = None
    minutes: float | None = None
    km: float | None = None


@dataclass(frozen=True)
class WeekOverride:
    """Manual changes to one week (D-012); unset fields keep the computed value."""

    week: int
    easy: EasyRuns | None = None
    quality: Session | None = None
    long_run_km: int | None = None
    note: str | None = None


@dataclass(frozen=True)
class Sheet:
    """Display-only settings."""

    title: str = DEFAULT_TITLE
    rules: tuple[str, ...] = DEFAULT_RULES


@dataclass(frozen=True)
class Season:
    races: tuple[Race, ...]  # sorted by date
    paces: Paces
    load: Load
    start: date | None = None  # at most one of start and weeks (D-004)
    weeks: int | None = None
    sheet: Sheet = Sheet()
    overrides: tuple[WeekOverride, ...] = ()  # sorted by week
