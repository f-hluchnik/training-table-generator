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

from ttg import beginner, long_run
from ttg.checks import check, check_beginner
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
    bridge_session,
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
    """The season's plan, overrides applied, with every warning. Raises SeasonError for invalid overrides.

    A beginner's plan has only the encouraging C12; its sheet is meant to motivate (owner, S11, D-054).
    """
    if season.load.beginner:
        season = beginner.with_a_goal(season, today)  # "just start running": 5 km in 9 weeks
    layout = lay_out(season, today)
    expander_class = _BeginnerExpander if season.load.beginner else _Expander
    expander = expander_class(season, layout, season.paces.resolve())
    weeks = tuple(expander.weeks())
    plan = Plan(season=season, paces=expander.paces, weeks=expander.with_overrides(weeks), warnings=())
    if season.load.beginner:
        return replace(plan, warnings=_by_week(check_beginner(plan)))
    warnings = (*layout.warnings, *expander.warnings(weeks), *check(plan))
    return replace(plan, warnings=_by_week(warnings))


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
    previous_kind: WeekKind | None = None  # a bridge week follows a recovery block (D-050)


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
        # Order matters: both calls advance the progressions, and the I cap needs the long run's km.
        long = self._long_run(kind, number, phase, target, c_race)
        long_km = self._long_run_km(long)
        easy, quality = self._easy_and_quality(kind, number, phase, target, c_race, long_km)
        self._progress.loading_streak = self._progress.loading_streak + 1 if kind.is_loading else 0
        self._progress.previous_kind = kind
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
            quality_km=self._quality_km(quality, number),
            long_run=long,
            long_run_km=long_km,
        )

    def _easy_and_quality(
        self, kind: WeekKind, number: int, phase: Phase, target: Race, c_race: Race | None, long_km: int
    ) -> tuple[tuple[int, ...], Session | Race]:
        """The week's easy runs and quality run; advances the rotation."""
        # Easy runs are reduced in every week that is not a loading or bridge week (D-022, D-050).
        easy = self._easy_runs(EasyRuns.REGULAR if kind.has_regular_easy_runs else EasyRuns.REDUCED)
        return easy, self._quality(kind, phase, target, c_race, other_week_km=sum(easy) + long_km)

    def _kind(self, number: int, phase: Phase) -> WeekKind:
        match phase.kind:
            case PhaseKind.BUILD | PhaseKind.SPECIFIC if self._progress.previous_kind is WeekKind.RECOVERY:
                return WeekKind.BRIDGE
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
        easy_run_km = self._easy_run_km()
        match kind:
            case WeekKind.BUILD | WeekKind.SPECIFIC | WeekKind.BRIDGE:
                # The bridge's long run is the restart after the race, without MP km (D-050).
                return self._loading_long_run(kind, target, tune_up_week=c_race is not None)
            case WeekKind.DELOAD:
                # Long C races can have taken the place of every loading long run since the last race.
                last_km = self._progress.long_run_km or self._first_long_run_km(target)
                return LongRun(self._deload_long_run(last_km))
            case WeekKind.TAPER:
                weeks_to_race_week = phase.last_week - number
                return LongRun(long_run.taper(self._taper_peak(), weeks_to_race_week, easy_run_km))
            case WeekKind.RECOVERY:
                first_week = number == phase.first_week  # easy runs only (TRAINING_MODEL.md §4)
                return None if first_week else LongRun(easy_run_km)
        raise ValueError(f"unknown week kind {kind}")

    def _quality(
        self, kind: WeekKind, phase: Phase, target: Race, c_race: Race | None, other_week_km: int
    ) -> Session | Race:
        """The week's quality run; advances the rotation unless a C race takes its place."""
        if c_race is not None:
            return _quality_beside(c_race, kind)
        match kind:
            case WeekKind.BUILD | WeekKind.SPECIFIC:
                return self._next_quality(_rotation(phase, target), other_week_km)
            case WeekKind.BRIDGE:
                # The rotation advances as in any week of the phase, at half the volume (D-050).
                return bridge_session(self._next_quality(_rotation(phase, target), other_week_km))
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
        return long_run.restart(previous_peak_km, target.type, self._easy_run_km())

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

    def _overridden_easy_runs(self, week: Week, pattern: EasyRuns) -> tuple[int, ...]:
        return self._easy_runs(pattern)

    def _easy_run_km(self) -> int:
        """An easy run's length now: the floor of a reduced long run, and the recovery's long run."""
        return self.season.load.easy_run_km

    def _deload_long_run(self, last_loading_km: int) -> int:
        return long_run.deload(last_loading_km, self._easy_run_km())

    def _quality_km(self, quality: Session | Race, week_number: int) -> int:
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
        easy = week.easy if override.easy is None else self._overridden_easy_runs(week, override.easy)
        return replace(
            week,
            easy=easy,
            quality=quality,
            quality_km=self._quality_km(quality, week.number),
            long_run=long,
            long_run_km=self._long_run_km(long),
            note=week.note if override.note is None else override.note,
        )


class _BeginnerExpander(_Expander):
    """The beginner's weeks (TRAINING_MODEL.md §11, D-054); the phases and their kinds are the standard ones.

    Every run but the long run has a slot of its own length (`_slots`, longest first). A loading week
    grows by one step, to the long run or the shortest slot, or holds (`beginner`'s growth rule). The
    quality run is done inside the shortest slot's run, so it counts that run's km.
    """

    def __init__(self, season: Season, layout: Layout, paces: TrainingPaces) -> None:
        super().__init__(season, layout, paces)
        load = season.load
        self._slots = (load.easy_run_km,) * (load.runs_per_week - 1)
        self._long_run_weeks_held = 0  # loading weeks at the current long run's distance
        self._efforts = 0  # fartlek and hill sessions so far, for their rotation
        self._effort_steps: dict[SessionType, int] = {}  # each type's last step given
        # Each week's slots: as built (for overrides) and as run (regular or reduced).
        self._built_slots: dict[int, tuple[int, ...]] = {}
        self._run_slots: dict[int, tuple[int, ...]] = {}

    def _loading_long_run(self, kind: WeekKind, target: Race, tune_up_week: bool) -> LongRun:
        progress = self._progress
        last_km = progress.long_run_km
        km = self._first_long_run_km(target) if last_km is None else self._step(kind, target, last_km)
        self._long_run_weeks_held = self._long_run_weeks_held + 1 if km == last_km else 1
        progress.long_run_km = km
        progress.peak_km = max(km, progress.peak_km or 0)
        return LongRun(km)  # no marathon-pace km: a beginner has no MP work

    def _step(self, kind: WeekKind, target: Race, last_km: int) -> int:
        """One step of growth; returns the long run, which may stay as it was."""
        cap = beginner.long_run_cap(target, self.paces.easy)
        specific = kind is WeekKind.SPECIFIC
        if not specific:
            cap = round_km(long_run.BUILD_CAP_SHARE * cap)
        longer_km = last_km + beginner.STEP_KM if last_km + beginner.STEP_KM <= cap else None
        longer_slots = beginner.grown(self._slots, beginner.easy_run_cap(target, last_km))
        long_run_may_grow = specific or beginner.long_run_may_grow(last_km, self._long_run_weeks_held)
        easy_runs_first = not specific and beginner.easy_runs_catch_up(last_km, min(self._slots))
        if longer_slots is not None and (easy_runs_first or not long_run_may_grow or longer_km is None):
            self._slots = longer_slots
            return last_km
        return longer_km if longer_km is not None and long_run_may_grow else last_km

    def _deload_long_run(self, last_loading_km: int) -> int:
        return last_loading_km  # a beginner's deload holds: no step, strides only (§11)

    def _easy_and_quality(
        self, kind: WeekKind, number: int, phase: Phase, target: Race, c_race: Race | None, long_km: int
    ) -> tuple[tuple[int, ...], Session | Race]:
        slots = beginner.reduced(self._slots) if kind in beginner.REDUCED_KINDS else self._slots
        self._built_slots[number], self._run_slots[number] = self._slots, slots
        if c_race is not None:
            quality: Session | Race = _quality_beside(c_race, kind)
        else:
            quality = self._beginner_quality(kind, number, week_km=sum(slots) + long_km)
        if kind is WeekKind.RACE:
            kept = max(beginner.MIN_RACE_WEEK_EASY_RUNS, len(slots) - beginner.RACE_WEEK_RUNS_LEFT_OUT)
            return slots[:kept], quality
        # The quality run is done in the shortest slot's run; without one, that run is easy.
        return (slots[:-1] if _takes_a_slot(quality) else slots), quality

    def _beginner_quality(self, kind: WeekKind, number: int, week_km: int) -> Session:
        match beginner.quality_of(kind, number):
            case beginner.Quality.NONE:
                return no_session()
            case beginner.Quality.EFFORT:
                session = self._next_effort(beginner.hard_minutes_limit(week_km, self.paces.easy))
                if session is not None:
                    return session
        return strides_session()

    def _next_effort(self, limit_minutes: float) -> Session | None:
        """Fartlek and hills in turn; None (strides instead) when even the first step is too much."""
        rotation = beginner.EFFORT_ROTATION
        session_type = rotation[self._efforts % len(rotation)]
        self._efforts += 1
        # One step further than last time, unless the week's limit holds it (it never skips a step).
        step = beginner.effort_step(session_type, self._effort_steps.get(session_type, -1) + 1, limit_minutes)
        if step is None:
            return None
        self._effort_steps[session_type] = step
        return beginner.effort_session(session_type, step)

    def _overridden_easy_runs(self, week: Week, pattern: EasyRuns) -> tuple[int, ...]:
        """As many easy runs as the week has, from the week's slots as built; reduced as in a reduced week."""
        slots = self._built_slots[week.number]
        runs = slots if pattern is EasyRuns.REGULAR else beginner.reduced(slots)
        return runs[: len(week.easy)]

    def _easy_run_km(self) -> int:
        return self._slots[0]

    def _quality_km(self, quality: Session | Race, week_number: int) -> int:
        """A beginner's quality run is done inside a run: the shortest slot's (§11)."""
        if isinstance(quality, Session) and quality.type is not SessionType.NONE:
            return min(self._run_slots[week_number])
        return super()._quality_km(quality, week_number)


def _quality_beside(c_race: Race, kind: WeekKind) -> Session | Race:
    """A C race's week: a short one is the quality run; a long one took the long run's place, and one
    hard effort a week is enough (D-017, D-030)."""
    return no_session() if _replaces_long_run(c_race) and kind is not WeekKind.RACE else c_race


def _takes_a_slot(quality: Session | Race) -> bool:
    return isinstance(quality, Race) or quality.type is not SessionType.NONE


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


def _rotation(phase: Phase, target: Race) -> tuple[SessionType, ...]:
    """The quality rotation of a build or specific phase."""
    return _specific_rotation(target) if phase.kind is PhaseKind.SPECIFIC else BUILD_ROTATION


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
