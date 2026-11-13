"""The domain model as immutable values.

The season is what the runner writes in season.toml; the schema is documented
in docs/PLAN.md §4 (D-025). Validation lives in `ttg.spec`; these classes only
hold already-validated data. The plan side (phases, weeks, the plan) is built by
`ttg.layout` and `ttg.expand`.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from ttg.paces import Pace, TrainingPaces, derive_paces

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


# Standard race distances.
TEN_K_KM = 10.0
HALF_MARATHON_KM = 21.0975
MARATHON_KM = 42.195
# [default] Tolerance when classifying a race by distance, so that rounded
# distances such as 21.1 or 42.2 still count as a half or a full marathon.
RACE_DISTANCE_SLACK_KM = 0.1


class SeasonError(ValueError):
    """The season is invalid and nothing is built. The message names the field."""


class Priority(StrEnum):
    """Race priority (D-017)."""

    A = "A"  # full taper and recovery
    B = "B"  # taper shortened by one week
    C = "C"  # tune-up: replaces one quality run; no taper, specific or recovery block


class RaceType(StrEnum):
    """The race type decides phase lengths and the specific block (TRAINING_MODEL.md §4–§6).

    The values are the phase labels of the race-specific block (D-026).
    """

    TEN_K = "10 km"  # up to 10 km
    HALF = "half"  # up to a half marathon
    MARATHON = "marathon"  # up to a marathon
    ULTRA = "ultra"  # longer

    @classmethod
    def of(cls, distance_km: float) -> "RaceType":
        if distance_km <= TEN_K_KM + RACE_DISTANCE_SLACK_KM:
            return cls.TEN_K
        if distance_km <= HALF_MARATHON_KM + RACE_DISTANCE_SLACK_KM:
            return cls.HALF
        if distance_km <= MARATHON_KM + RACE_DISTANCE_SLACK_KM:
            return cls.MARATHON
        return cls.ULTRA


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

    @property
    def type(self) -> RaceType:
        return RaceType.of(self.distance_km)

    @property
    def is_key(self) -> bool:
        """A and B races get their own phases; C races only replace a quality run (D-017)."""
        return self.priority is not Priority.C


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

    def resolve(self) -> TrainingPaces:
        """The paces to use: each override where given, otherwise the derived default (D-005, D-015)."""
        derived = derive_paces(self.race_result.distance_km, self.race_result.time)
        return TrainingPaces(
            easy=derived.easy if self.easy is None else self.easy,
            mp=derived.mp if self.mp is None else self.mp,
            threshold=derived.threshold if self.threshold is None else self.threshold,
            interval=derived.interval if self.interval is None else self.interval,
        )


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


# --- plan side -----------------------------------------------------------------


class PhaseKind(StrEnum):
    """The phases the layout places (TRAINING_MODEL.md §4–§5).

    Deload and race weeks are week kinds inside these phases (`WeekKind`).
    """

    BUILD = "build"  # general preparation
    SPECIFIC = "specific"  # race-specific preparation
    TAPER = "taper"  # ends with the race week
    RECOVERY = "recovery"  # after a race


@dataclass(frozen=True)
class Phase:
    kind: PhaseKind
    first_week: int  # 1-based week number
    weeks: int
    race: Race | None = None  # the race prepared for or recovered from; None for build

    @property
    def last_week(self) -> int:
        return self.first_week + self.weeks - 1


class WeekKind(StrEnum):
    """What a week is for (PLAN §4 `weeks[].kind`).

    Build and specific weeks are the loading weeks of the 3:1 cycle; a deload can
    fall inside either phase. The race week is the last week of a taper.
    """

    BUILD = "build"
    DELOAD = "deload"
    SPECIFIC = "specific"
    TAPER = "taper"
    RACE = "race"
    RECOVERY = "recovery"

    @property
    def is_loading(self) -> bool:
        return self in (WeekKind.BUILD, WeekKind.SPECIFIC)


@dataclass(frozen=True)
class LongRun:
    km: int
    mp_km: int = 0  # the last km at marathon pace, printed `28 km (10 MP)` (D-018)


@dataclass(frozen=True)
class Week:
    number: int  # 1-based
    days: tuple[date | None, ...]  # Monday to Sunday; None after the plan ends
    month: int  # 1–12, the month of the week's Thursday
    kind: WeekKind
    phase: Phase
    target: Race  # the A or B race the week works toward; decides the long-run cap
    easy: tuple[int, ...]  # km of each easy run
    quality: Session | Race  # a C race up to 10 km replaces the quality run (D-017, D-030)
    quality_km: int  # estimate (TRAINING_MODEL.md §3); a C race counts its distance
    # A race replaces the long run: the A or B race of the week, or a C race from the half
    # marathon up (D-030). None: no long run.
    long_run: LongRun | Race | None
    long_run_km: int  # a C race counts its distance, an A or B race does not (D-030)
    note: str | None = None  # override text for the last column (D-025)

    @property
    def planned_km(self) -> int:
        """The sum of all runs (D-006)."""
        return sum(self.easy) + self.quality_km + self.long_run_km


class WarningCode(StrEnum):
    """Check codes (TRAINING_MODEL.md §7)."""

    RACES_TOO_CLOSE = "C1"
    PLAN_TOO_SHORT = "C2"
    WEEKLY_RAMP = "C3"
    LONG_RUN_SHARE = "C4"
    LONG_RUN_ABOVE_CAP = "C5"
    THRESHOLD_VOLUME = "C6"
    INTERVAL_VOLUME = "C7"
    PACE_CONSISTENCY = "C8"


@dataclass(frozen=True)
class PlanWarning:
    """Questionable input: the plan is still built (D-001). Not printed on the sheet (D-027)."""

    code: WarningCode
    week: int | None
    message: str


@dataclass(frozen=True)
class Plan:
    season: Season
    paces: TrainingPaces  # overrides applied
    weeks: tuple[Week, ...]
    warnings: tuple[PlanWarning, ...]  # from the layout and the expansion; the checks add theirs (T-07)
