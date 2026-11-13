"""Phase rules → weeks, then the `[overrides]` (TRAINING_MODEL.md §4, D-012).

The phases from `ttg.layout` are walked week by week. Progressions (the quality
rotation, the long run, the 3:1 cycle) carry over from week to week; an override
changes only its own week, never the progressions after it (D-030). Pure (D-013).
"""

from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from types import MappingProxyType

from ttg import long_run
from ttg.checks import check
from ttg.layout import Layout, lay_out
from ttg.model import (
    EasyRuns,
    LongRun,
    Phase,
    PhaseKind,
    Plan,
    PlanWarning,
    Race,
    RaceType,
    Season,
    SeasonError,
    Session,
    SessionType,
    WarningCode,
    Week,
    WeekKind,
    WeekOverride,
)
from ttg.paces import TrainingPaces
from ttg.sessions import (
    BUILD_ROTATION,
    easy_run_kms,
    marathon_long_run_mp_km,
    no_session,
    progression_session,
    round_km,
    session_km,
    strides_session,
    taper_session,
)

# The 3:1 cycle: three loading weeks, then a deload [2026, source 6]. The count
# restarts after every week that is not a loading week (D-030), so a deload never
# follows a taper, race or recovery week directly.
LOADING_WEEKS_PER_DELOAD = 3

# Quality runs of the race-specific block, in rotation (TRAINING_MODEL.md §4).
SPECIFIC_ROTATION: Mapping[RaceType, tuple[SessionType, ...]] = MappingProxyType(
    {
        RaceType.TEN_K: (SessionType.INTERVALS, SessionType.THRESHOLD),
        RaceType.HALF: (SessionType.THRESHOLD,),
        RaceType.MARATHON: (SessionType.MARATHON_PACE,),
        RaceType.ULTRA: BUILD_ROTATION,  # D-023
    }
)

# [default, D-041] A hilly race's race-specific block: every other quality run is hill repeats, the
# others are the race's own intensity, threshold instead of marathon pace (hills, not a steady pace,
# decide the effort on its course). Sources in TRAINING_MODEL.md §4.
HILLY_SPECIFIC_ROTATION: Mapping[RaceType, tuple[SessionType, ...]] = MappingProxyType(
    {
        RaceType.TEN_K: (SessionType.HILLS, SessionType.INTERVALS, SessionType.HILLS, SessionType.THRESHOLD),
        RaceType.HALF: (SessionType.HILLS, SessionType.THRESHOLD),
        RaceType.MARATHON: (SessionType.HILLS, SessionType.THRESHOLD),
        RaceType.ULTRA: (SessionType.HILLS, SessionType.INTERVALS, SessionType.HILLS, SessionType.THRESHOLD),
    }
)

# [default, owner S5] A C race up to 10 km replaces the quality run (D-017). From the half
# marathon up it is the week's long, hard effort: it replaces the long run, and the week has
# no other quality run.
SHORT_C_RACE = RaceType.TEN_K


def expand(season: Season, today: date) -> Plan:
    """The season's plan, overrides applied, with every warning. Raises SeasonError for invalid overrides."""
    layout = lay_out(season, today)
    expander = _Expander(season, layout, season.paces.resolve())
    weeks = tuple(expander.weeks())
    plan = Plan(
        season=season,
        paces=expander.paces,
        weeks=expander.with_overrides(weeks),
        warnings=layout.warnings + expander.warnings(weeks),
    )
    return replace(plan, warnings=_by_week((*plan.warnings, *check(plan))))


def _by_week(warnings: Iterable[PlanWarning]) -> tuple[PlanWarning, ...]:
    """Ordered by week; warnings about the whole plan first."""
    return tuple(sorted(warnings, key=lambda warning: (warning.week or 0, warning.code)))


@dataclass
class _Progress:
    """What carries over from one week to the next."""

    rotation_positions: Counter[tuple[SessionType, ...]] = field(default_factory=Counter)
    occurrences: Counter[SessionType] = field(default_factory=Counter)
    loading_streak: int = 0
    long_run_km: int | None = None  # the last loading week's long run since the last race
    peak_km: int | None = None  # the longest loading long run since the last race
    previous_peak_km: int | None = None  # the peak before the last race
    mp_long_runs: int = 0  # marathon-specific long runs with MP km so far
    last_specific_long_run_had_mp: bool = False  # for the alternation (D-033)


class _Expander:
    def __init__(self, season: Season, layout: Layout, paces: TrainingPaces) -> None:
        self.season = season
        self.layout = layout
        self.paces = paces
        self._progress = _Progress()
        self._race_weeks = _race_weeks(layout.phases)
        self._c_races = _c_races_by_week(season, layout)

    # --- weeks from the phase rules -------------------------------------------

    def weeks(self) -> Iterator[Week]:
        for phase in self.layout.phases:
            for number in range(phase.first_week, phase.last_week + 1):
                yield self._week(number, phase)

    def _week(self, number: int, phase: Phase) -> Week:
        kind = self._kind(number, phase)
        target = self._target(number)
        c_race = self._c_race(number)
        # Easy runs are reduced in every week that is not a loading week (D-022).
        easy = self._easy_runs(EasyRuns.REGULAR if kind.is_loading else EasyRuns.REDUCED)
        # Order matters: both calls advance the progressions, and the I cap needs the long run's km.
        long = self._long_run(kind, number, phase, target, c_race)
        long_km = self._long_run_km(long)
        quality = self._quality(kind, target, c_race, other_week_km=sum(easy) + long_km)
        self._progress.loading_streak = self._progress.loading_streak + 1 if kind.is_loading else 0
        calendar = self.layout.calendar
        return Week(
            number=number,
            days=calendar.days(number),
            month=calendar.month(number),
            kind=kind,
            phase=phase,
            target=target,
            easy=easy,
            quality=quality,
            quality_km=self._quality_km(quality),
            long_run=long,
            long_run_km=long_km,
        )

    def _kind(self, number: int, phase: Phase) -> WeekKind:
        match phase.kind:
            case PhaseKind.BUILD | PhaseKind.SPECIFIC if self._progress.loading_streak == LOADING_WEEKS_PER_DELOAD:
                return WeekKind.DELOAD
            case PhaseKind.BUILD:
                return WeekKind.BUILD
            case PhaseKind.SPECIFIC:
                return WeekKind.SPECIFIC
            case PhaseKind.TAPER:
                return WeekKind.RACE if number == phase.last_week else WeekKind.TAPER
            case PhaseKind.RECOVERY:
                return WeekKind.RECOVERY
        raise ValueError(f"unknown phase kind {phase.kind}")

    def _long_run(
        self, kind: WeekKind, number: int, phase: Phase, target: Race, c_race: Race | None
    ) -> LongRun | Race | None:
        """The week's long run; advances the long-run progression unless a C race takes its place."""
        if kind is WeekKind.RACE:
            assert phase.race is not None  # a taper belongs to its race
            self._finish_race()
            return phase.race
        if c_race is not None and _replaces_long_run(c_race):
            return c_race
        easy_run_km = self.season.load.easy_run_km
        match kind:
            case WeekKind.BUILD | WeekKind.SPECIFIC:
                return self._loading_long_run(kind, target, tune_up_week=c_race is not None)
            case WeekKind.DELOAD:
                # Long C races can have taken the place of every loading long run since the last race.
                last_km = self._progress.long_run_km or self._first_long_run_km(target)
                return LongRun(long_run.deload(last_km, easy_run_km))
            case WeekKind.TAPER:
                weeks_to_race_week = phase.last_week - number
                return LongRun(long_run.taper(self._taper_peak(), weeks_to_race_week, easy_run_km))
            case WeekKind.RECOVERY:
                first_week = number == phase.first_week  # easy runs only (TRAINING_MODEL.md §4)
                return None if first_week else LongRun(easy_run_km)
        raise ValueError(f"unknown week kind {kind}")

    def _quality(self, kind: WeekKind, target: Race, c_race: Race | None, other_week_km: int) -> Session | Race:
        """The week's quality run; advances the rotation unless a C race takes its place."""
        if c_race is not None:
            # A long C race took the long run's place; one hard effort a week is enough.
            return no_session() if _replaces_long_run(c_race) and kind is not WeekKind.RACE else c_race
        match kind:
            case WeekKind.BUILD:
                return self._next_quality(BUILD_ROTATION, other_week_km)
            case WeekKind.SPECIFIC:
                return self._next_quality(_specific_rotation(target), other_week_km)
            case WeekKind.DELOAD:
                return strides_session()
            case WeekKind.TAPER:
                return taper_session()
            case WeekKind.RACE:
                return strides_session()  # keeps the legs sharp before the race (D-033)
            case WeekKind.RECOVERY:
                return no_session()
        raise ValueError(f"unknown week kind {kind}")

    def _next_quality(self, rotation: tuple[SessionType, ...], other_week_km: int) -> Session:
        """The next session of a rotation; each type progresses each time it occurs [2026]."""
        progress = self._progress
        session_type = rotation[progress.rotation_positions[rotation] % len(rotation)]
        progress.rotation_positions[rotation] += 1
        occurrence = progress.occurrences[session_type]
        progress.occurrences[session_type] += 1
        return progression_session(session_type, occurrence, self.paces, self.season.load.easy_run_km, other_week_km)

    def _loading_long_run(self, kind: WeekKind, target: Race, tune_up_week: bool) -> LongRun:
        """+2 km a loading week up to the cap; after a race, a restart (TRAINING_MODEL.md §4, §6)."""
        progress = self._progress
        if progress.long_run_km is not None:
            in_specific_block = kind is WeekKind.SPECIFIC
            cap = long_run.cap(target.type) if in_specific_block else long_run.build_cap(target.type)
            km = long_run.grow(progress.long_run_km, cap)
        else:
            km = self._first_long_run_km(target)
        progress.long_run_km = km
        progress.peak_km = max(km, progress.peak_km or 0)
        return LongRun(km, self._long_run_mp_km(kind, target, km, tune_up_week))

    def _first_long_run_km(self, target: Race) -> int:
        """The first loading long run of the plan (the starting load) or after a race (a restart)."""
        previous_peak_km = self._progress.previous_peak_km
        if previous_peak_km is None:
            return self.season.load.long_run_km
        return long_run.restart(previous_peak_km, target.type, self.season.load.easy_run_km)

    def _long_run_mp_km(self, kind: WeekKind, target: Race, km: int, tune_up_week: bool) -> int:
        """MP km in every other marathon-specific long run, none in a tune-up race's week (D-033)."""
        if kind is not WeekKind.SPECIFIC or target.type is not RaceType.MARATHON or target.hilly:
            return 0
        progress = self._progress
        with_mp = not progress.last_specific_long_run_had_mp and not tune_up_week
        progress.last_specific_long_run_had_mp = with_mp
        if not with_mp:
            return 0
        mp_km = marathon_long_run_mp_km(progress.mp_long_runs, self.paces.mp)
        progress.mp_long_runs += 1
        return min(mp_km, km)

    def _taper_peak(self) -> int:
        """The peak the taper reduces from: since the last race, else before it, else the starting long run."""
        progress = self._progress
        return progress.peak_km or progress.previous_peak_km or self.season.load.long_run_km

    def _finish_race(self) -> None:
        progress = self._progress
        progress.previous_peak_km = self._taper_peak()
        progress.peak_km = None
        progress.long_run_km = None

    def _target(self, number: int) -> Race:
        """The next A or B race; after the last one, the last one; without any, the longest race."""
        upcoming = [race for race, race_week in self._race_weeks if race_week >= number]
        if upcoming:
            return upcoming[0]
        if self._race_weeks:
            return self._race_weeks[-1][0]
        return max(self.season.races, key=lambda race: race.distance_km)

    def _c_race(self, number: int) -> Race | None:
        """The week's C race; of several, the first (`warnings` reports the others)."""
        races = self._c_races.get(number)
        return races[0] if races else None

    def _easy_runs(self, pattern: EasyRuns) -> tuple[int, ...]:
        load = self.season.load
        return easy_run_kms(load.easy_run_km, load.runs_per_week, pattern)

    def _quality_km(self, quality: Session | Race) -> int:
        if isinstance(quality, Race):
            return round_km(quality.distance_km)  # a C race counts (owner, S5)
        return round_km(session_km(quality, self.paces, self.season.load.easy_run_km))

    @staticmethod
    def _long_run_km(long: LongRun | Race | None) -> int:
        if isinstance(long, LongRun):
            return long.km
        if isinstance(long, Race) and not long.is_key:
            return round_km(long.distance_km)  # a C race counts, an A or B race does not (owner, S5)
        return 0

    def warnings(self, weeks: Sequence[Week]) -> tuple[PlanWarning, ...]:
        """C1 for C races that share a week or fall in a recovery block (TRAINING_MODEL.md §4)."""
        shared = (
            PlanWarning(
                WarningCode.RACES_TOO_CLOSE,
                number,
                f'"{races[0].name}" and "{races[1].name}" are in the same week: only "{races[0].name}" is on the sheet',
            )
            for number, races in self._c_races.items()
            if len(races) > 1
        )
        in_recovery = (
            PlanWarning(
                WarningCode.RACES_TOO_CLOSE,
                week.number,
                f'"{race.name}" falls in the recovery after "{week.phase.race.name}": racing returns sooner '
                "than the recovery block allows",
            )
            for week in weeks
            if week.kind is WeekKind.RECOVERY and week.phase.race and (race := self._c_race(week.number))
        )
        return (*shared, *in_recovery)

    # --- overrides ----------------------------------------------------------------

    def with_overrides(self, weeks: tuple[Week, ...]) -> tuple[Week, ...]:
        """Apply `[overrides]`: each changes only its own week (D-012, D-030)."""
        overrides = {override.week: override for override in self.season.overrides}
        past_end = [number for number in overrides if number > len(weeks)]
        if past_end:
            raise SeasonError(f"overrides.{past_end[0]}: the plan has only {len(weeks)} weeks")
        return tuple(
            self._overridden(week, overrides[week.number]) if week.number in overrides else week for week in weeks
        )

    def _overridden(self, week: Week, override: WeekOverride) -> Week:
        _check_no_race_overridden(week, override)
        quality = week.quality if override.quality is None else override.quality
        long = week.long_run if override.long_run_km is None else _long_run_override(week, override.long_run_km)
        return replace(
            week,
            easy=week.easy if override.easy is None else self._easy_runs(override.easy),
            quality=quality,
            quality_km=self._quality_km(quality),
            long_run=long,
            long_run_km=self._long_run_km(long),
            note=week.note if override.note is None else override.note,
        )


def _check_no_race_overridden(week: Week, override: WeekOverride) -> None:
    """A race is not a session: an override must not replace the race in its cell (D-038)."""
    cells = (
        ("quality", "quality run", override.quality, week.quality),
        ("long_run_km", "long run", override.long_run_km, week.long_run),
    )
    for field_name, cell, value, computed in cells:
        if value is not None and isinstance(computed, Race):
            raise SeasonError(
                f"overrides.{week.number}.{field_name}: the {cell} of week {week.number} is the race "
                f'"{computed.name}", which cannot be overridden'
            )


def _specific_rotation(race: Race) -> tuple[SessionType, ...]:
    """The quality runs of the race's specific block (TRAINING_MODEL.md §4, D-041)."""
    rotations = HILLY_SPECIFIC_ROTATION if race.hilly else SPECIFIC_ROTATION
    return rotations[race.type]


def _replaces_long_run(c_race: Race) -> bool:
    return c_race.type is not SHORT_C_RACE


def _long_run_override(week: Week, km: int) -> LongRun | None:
    """0 means no long run; the computed MP km stay, up to the new length."""
    if km == 0:
        return None
    mp_km = week.long_run.mp_km if isinstance(week.long_run, LongRun) else 0
    return LongRun(km, min(mp_km, km))


def _race_weeks(phases: Sequence[Phase]) -> list[tuple[Race, int]]:
    """The A and B races with their race weeks (the last week of each taper), in order."""
    return [(phase.race, phase.last_week) for phase in phases if phase.kind is PhaseKind.TAPER and phase.race]


def _c_races_by_week(season: Season, layout: Layout) -> dict[int, list[Race]]:
    by_week: defaultdict[int, list[Race]] = defaultdict(list)
    for race in season.races:
        if not race.is_key:
            by_week[layout.calendar.week_of(race.date)].append(race)
    return dict(by_week)
