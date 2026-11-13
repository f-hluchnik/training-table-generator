"""Phase rules → weeks, then the `[overrides]` (TRAINING_MODEL.md §4, D-012).

The phases from `ttg.layout` are walked week by week. Progressions (the quality
rotation, the long run, the 3:1 cycle) carry over from week to week; an override
changes only its own week, never the progressions after it (D-030). Pure (D-013).
"""

from collections import Counter, defaultdict
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from types import MappingProxyType

from ttg import long_run
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


def expand(season: Season, today: date) -> Plan:
    """The weeks of the season's plan, overrides applied. Raises SeasonError for an override past the end."""
    layout = lay_out(season, today)
    expander = _Expander(season, layout, season.paces.resolve())
    weeks = tuple(expander.weeks())
    return Plan(
        season=season,
        paces=expander.paces,
        weeks=expander.with_overrides(weeks),
        warnings=layout.warnings + expander.warnings(),
    )


@dataclass
class _Progress:
    """What carries over from one week to the next."""

    rotation_positions: Counter[tuple[SessionType, ...]] = field(default_factory=Counter)
    occurrences: Counter[SessionType] = field(default_factory=Counter)
    loading_streak: int = 0
    long_run_km: int | None = None  # the last loading week's long run since the last race
    peak_km: int | None = None  # the longest loading long run since the last race
    previous_peak_km: int | None = None  # the peak before the last race
    mp_long_runs: int = 0  # marathon-specific long runs so far


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
        make_quality, long = self._sessions(kind, number, phase, target)
        c_races = self._c_races.get(number)
        quality = c_races[0] if c_races else make_quality()  # a C race replaces the quality run (D-017)
        self._progress.loading_streak = self._progress.loading_streak + 1 if kind.is_loading else 0
        calendar = self.layout.calendar
        return Week(
            number=number,
            days=calendar.days(number),
            month=calendar.month(number),
            kind=kind,
            phase=phase,
            target=target,
            # Easy runs are reduced in every week that is not a loading week (D-022).
            easy=self._easy_runs(EasyRuns.REGULAR if kind.is_loading else EasyRuns.REDUCED),
            quality=quality,
            quality_km=self._quality_km(quality),
            long_run=long,
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

    def _sessions(
        self, kind: WeekKind, number: int, phase: Phase, target: Race
    ) -> tuple[Callable[[], Session], LongRun | Race | None]:
        """The week's quality run (made only if no C race replaces it) and long run.

        Advances the progressions: the long run, and the race bookkeeping in a race week.
        """
        easy_run_km = self.season.load.easy_run_km
        progress = self._progress
        match kind:
            case WeekKind.BUILD:
                return lambda: self._next_quality(BUILD_ROTATION), self._loading_long_run(kind, target)
            case WeekKind.SPECIFIC:
                rotation = SPECIFIC_ROTATION[target.type]
                return lambda: self._next_quality(rotation), self._loading_long_run(kind, target)
            case WeekKind.DELOAD:
                assert progress.long_run_km is not None  # a deload follows three loading weeks
                return strides_session, LongRun(long_run.deload(progress.long_run_km, easy_run_km))
            case WeekKind.TAPER:
                weeks_to_race_week = phase.last_week - number
                return taper_session, LongRun(long_run.taper(self._taper_peak(), weeks_to_race_week, easy_run_km))
            case WeekKind.RACE:
                assert phase.race is not None  # a taper belongs to its race
                self._finish_race()
                return no_session, phase.race
            case WeekKind.RECOVERY:
                first_week = number == phase.first_week  # easy runs only (TRAINING_MODEL.md §4)
                return no_session, None if first_week else LongRun(easy_run_km)
        raise ValueError(f"unknown week kind {kind}")

    def _next_quality(self, rotation: tuple[SessionType, ...]) -> Session:
        """The next session of a rotation; each type progresses each time it occurs [2026]."""
        progress = self._progress
        session_type = rotation[progress.rotation_positions[rotation] % len(rotation)]
        progress.rotation_positions[rotation] += 1
        session = progression_session(session_type, progress.occurrences[session_type], self.paces)
        progress.occurrences[session_type] += 1
        return session

    def _loading_long_run(self, kind: WeekKind, target: Race) -> LongRun:
        """+2 km a loading week up to the cap; after a race, a restart (TRAINING_MODEL.md §4, §6)."""
        progress = self._progress
        if progress.long_run_km is not None:
            in_specific_block = kind is WeekKind.SPECIFIC
            cap = long_run.cap(target.type) if in_specific_block else long_run.build_cap(target.type)
            km = long_run.grow(progress.long_run_km, cap)
        elif progress.previous_peak_km is not None:
            km = long_run.restart(progress.previous_peak_km, target.type, self.season.load.easy_run_km)
        else:
            km = self.season.load.long_run_km
        progress.long_run_km = km
        progress.peak_km = max(km, progress.peak_km or 0)
        return LongRun(km, self._long_run_mp_km(kind, target, km))

    def _long_run_mp_km(self, kind: WeekKind, target: Race, km: int) -> int:
        if kind is not WeekKind.SPECIFIC or target.type is not RaceType.MARATHON:
            return 0
        mp_km = marathon_long_run_mp_km(self._progress.mp_long_runs, self.paces.mp)
        self._progress.mp_long_runs += 1
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

    def _easy_runs(self, pattern: EasyRuns) -> tuple[int, ...]:
        load = self.season.load
        return easy_run_kms(load.easy_run_km, load.runs_per_week, pattern)

    def _quality_km(self, quality: Session | Race) -> int:
        if isinstance(quality, Race):
            return round_km(quality.distance_km)  # a C race counts (owner, S5)
        return round_km(session_km(quality, self.paces, self.season.load.easy_run_km))

    def warnings(self) -> tuple[PlanWarning, ...]:
        """C1 for C races that share a week: only the first replaces the quality run."""
        return tuple(
            PlanWarning(
                WarningCode.RACES_TOO_CLOSE,
                number,
                f'"{races[0].name}" and "{races[1].name}" are in the same week: '
                f'only "{races[0].name}" replaces the quality run',
            )
            for number, races in self._c_races.items()
            if len(races) > 1
        )

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
        quality = week.quality if override.quality is None else override.quality
        return replace(
            week,
            easy=week.easy if override.easy is None else self._easy_runs(override.easy),
            quality=quality,
            quality_km=self._quality_km(quality),
            long_run=week.long_run if override.long_run_km is None else _long_run_override(week, override.long_run_km),
            note=week.note if override.note is None else override.note,
        )


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
