"""
Training plan generator.

Pure computation (well - almost pure; it needs a start_date to know which
calendar week each race falls in). Everything that's likely to change later
(progression formulas, deload sizing, warm-up/cool-down assumptions) is
isolated into its own small function so it can be swapped without touching
the rest of the pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable

from config import Inputs


# ---------------------------------------------------------------------------
# Pace
# ---------------------------------------------------------------------------

@dataclass
class Pace:
    """A running pace, stored as minutes-per-km (float)."""
    minutes_per_km: float

    @classmethod
    def parse(cls, s: str) -> "Pace":
        """Parse 'mm:ss' -> Pace."""
        m, sec = s.split(":")
        return cls(int(m) + int(sec) / 60)

    def minus_seconds(self, seconds: float) -> "Pace":
        return Pace(self.minutes_per_km - seconds / 60)

    def distance_for(self, duration_min: float) -> float:
        """km covered running this pace for duration_min minutes."""
        return duration_min / self.minutes_per_km

    def format(self) -> str:
        total_seconds = round(self.minutes_per_km * 60)
        m, s = divmod(total_seconds, 60)
        return f"{m}:{s:02d}"


def resolve_paces(inputs: Inputs) -> dict[str, Pace]:
    z2 = Pace.parse(inputs.z2_pace)
    threshold = (
        Pace.parse(inputs.threshold_pace)
        if inputs.threshold_pace
        else z2.minus_seconds(60)
    )
    vo2max = (
        Pace.parse(inputs.vo2max_pace)
        if inputs.vo2max_pace
        else threshold.minus_seconds(15)
    )
    return {"Z2": z2, "T": threshold, "I": vo2max}


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------

def resolve_start_date(inputs: Inputs) -> date:
    """
    Always a Monday. An explicit start_date is snapped back to that week's
    Monday; otherwise it's the next Monday (today itself, if today already
    is one) - not a hardcoded date.
    """
    if inputs.start_date is not None:
        return inputs.start_date - timedelta(days=inputs.start_date.weekday())
    today = date.today()
    return today + timedelta(days=(7 - today.weekday()) % 7)


def week_number_for_date(d: date, start_date: date) -> int:
    return (d - start_date).days // 7 + 1


def all_race_dates(inputs: Inputs) -> list[date]:
    """race_date is the clear single-race entrypoint; additional_race_dates
    covers training through more than one. Combine them for anything that
    needs to treat races uniformly."""
    dates = list(inputs.additional_race_dates)
    if inputs.race_date is not None:
        dates.append(inputs.race_date)
    return dates


DEFAULT_WEEKS = 10


def resolve_plan_length(inputs: Inputs, start_date: date) -> tuple[int, list[str]]:
    """
    The plan always ends on the latest race's week, when a race is given -
    `weeks` only determines the length directly when there's no race to
    anchor to. If both are set and disagree, the race wins but a warning
    explains why, rather than silently overriding what was typed in.
    """
    warnings: list[str] = []
    races = all_race_dates(inputs)

    if races:
        race_week = week_number_for_date(max(races), start_date)
        if race_week >= 1:
            if inputs.weeks is not None and inputs.weeks != race_week:
                direction = "sooner" if race_week < inputs.weeks else "later"
                warnings.append(
                    f"latest race date falls in week {race_week}, {direction} than "
                    f"the {inputs.weeks}-week plan length you set - using {race_week} "
                    f"weeks instead (the plan always ends on the latest race)."
                )
            return race_week, warnings
        warnings.append("latest race date is before the plan's start date; ignoring it for plan length.")

    return (inputs.weeks if inputs.weeks is not None else DEFAULT_WEEKS), warnings


# ---------------------------------------------------------------------------
# Quality-session progression rules
#
# Each function maps an *occurrence index* n (0 = first time this session
# type appears, 1 = second time, ...) to (reps, duration_minutes). Swap any
# of these out independently; nothing else in the file depends on how they
# work internally.
# ---------------------------------------------------------------------------

def hill_progression(n: int, base_reps: int, base_dur: float) -> tuple[int, float]:
    """+1 rep each occurrence; at 10 reps, halve reps and double duration."""
    reps, dur = base_reps, base_dur
    for _ in range(n):
        reps += 1
        if reps >= 10:
            reps //= 2
            dur *= 2
    return reps, dur


def vo2max_progression(n: int, base_reps: int, base_dur: float) -> tuple[int, float]:
    """Alternate bumping reps and duration: (5,3)(6,3)(5,4)(6,4)(5,5)..."""
    reps = base_reps + (1 if n % 2 == 1 else 0)
    dur = base_dur + n // 2
    return reps, dur


def threshold_progression(n: int, base_reps: int, base_dur: float) -> tuple[int, float]:
    """Alternate +25% duration and +1 rep: (3,8)(3,10)(4,8)(4,10)..."""
    reps = base_reps + n // 2
    dur = base_dur * 1.25 if n % 2 == 1 else base_dur
    return reps, dur


QUALITY_PROGRESSIONS: dict[str, Callable[[int, int, float], tuple[int, float]]] = {
    "H": hill_progression,
    "I": vo2max_progression,
    "T": threshold_progression,
}

QUALITY_LABEL = {"H": "Uphill", "I": "VO2max", "T": "Threshold", "R": "Rest"}


def format_duration(minutes: float) -> str:
    if abs(minutes - round(minutes)) < 1e-6:
        return f"{int(round(minutes))}'"
    return f"{minutes:.1f}'"


def format_quality_detail(reps: int | None, duration_min: float | None) -> str | None:
    if reps is None or duration_min is None:
        return None
    return f"{reps} x {format_duration(duration_min)}"

# Rotation order for the three build weeks in each 4-week cycle.
ROTATION_ORDER = ["H", "I", "T"]


# ---------------------------------------------------------------------------
# Distance estimation
# ---------------------------------------------------------------------------

def hill_pause_min(duration_min: float, _inputs: Inputs) -> float:
    """Assumption: jog back down takes about as long as the effort up."""
    return duration_min


def pause_minutes(qtype: str, duration_min: float, inputs: Inputs) -> float:
    if qtype == "H":
        return hill_pause_min(duration_min, inputs)
    return inputs.pause_min_default


def quality_distance_km(
    qtype: str, reps: int, duration_min: float,
    paces: dict[str, Pace], inputs: Inputs,
) -> float:
    """
    warm-up + reps x interval + (reps-1) x pause + cool-down, all converted
    to distance via the relevant pace. Hill intervals use Z2 pace for the
    effort itself (there's no flat-pace equivalent for a hill).
    """
    z2 = paces["Z2"]
    effort_pace = z2 if qtype == "H" else paces[qtype]

    warmup_km = z2.distance_for(inputs.warmup_min)
    cooldown_km = z2.distance_for(inputs.cooldown_min)
    interval_km = reps * effort_pace.distance_for(duration_min)
    pause_km = max(reps - 1, 0) * z2.distance_for(pause_minutes(qtype, duration_min, inputs))

    return warmup_km + interval_km + pause_km + cooldown_km


# ---------------------------------------------------------------------------
# Weekly mileage / long-run progression
# ---------------------------------------------------------------------------

def is_deload(week_num: int) -> bool:
    return week_num % 4 == 0


def _capped_progression(
    start_value: float, weeks: int, growth_cap: float, deload_factor: float,
    min_increment: float = 0.0,
) -> list[float]:
    """
    Shared shape for any "grows up to growth_cap per build week, dips on
    deload weeks, resumes from the pre-deload peak" sequence. Used for both
    the overall mileage target and (independently) the long-run baseline.

    min_increment guarantees each build week beats the last by at least
    that much even where growth_cap alone would round to the same number
    as before (a real issue at lower mileages, where 10% of a small long
    run rounds to nothing) - whichever of the two produces the bigger step
    wins.
    """
    totals: list[float] = []
    last_build_total = start_value

    for w in range(1, weeks + 1):
        if w == 1:
            t = start_value
        elif is_deload(w):
            t = last_build_total * deload_factor
        else:
            base = last_build_total if is_deload(w - 1) else totals[-1]
            t = max(base * (1 + growth_cap), base + min_increment)

        totals.append(t)
        if not is_deload(w):
            last_build_total = t

    return totals


def weekly_targets(inputs: Inputs) -> list[float]:
    """Overall weekly mileage target - used to size the easy-run remainder
    and for the over_target check. Week 1 = current mileage."""
    return _capped_progression(inputs.current_weekly_km, inputs.weeks, inputs.max_growth_rate, inputs.deload_factor)


def resolve_max_long_run_km(inputs: Inputs) -> float:
    """
    Long run cap. If max_long_run_km isn't set explicitly, derive it from
    training_distance_km: the long run can reach full race distance up
    through half-marathon; beyond that, cap around 80% of race distance
    (flat ceiling too) since a full-distance long run at marathon length or
    beyond carries more injury/fatigue risk than benefit. This is a
    judgment call, not a settled rule - swap it out if you disagree.
    """
    if inputs.max_long_run_km is not None:
        return inputs.max_long_run_km
    if inputs.training_distance_km is None:
        return 32.0  # no signal to derive from - same flat fallback as before
    if inputs.training_distance_km <= 21.1:
        return inputs.training_distance_km
    return min(inputs.training_distance_km * 0.8, 34.0)


def long_run_baseline(inputs: Inputs) -> list[float]:
    """
    Long runs grow at their own capped rate, independently of the overall
    weekly target - per explicit request, long runs should keep growing at
    up to max_growth_rate even though easy runs are clamped to a fixed
    range (which would otherwise indirectly cap how much room is left for
    the long run too) - and never by less than long_run_min_increment,
    so consecutive weeks don't round to the same displayed number.
    """
    start = inputs.current_weekly_km * inputs.long_run_fraction
    return _capped_progression(
        start, inputs.weeks, inputs.max_growth_rate, inputs.deload_factor,
        min_increment=inputs.long_run_min_increment,
    )


# ---------------------------------------------------------------------------
# Race weeks: taper before, nothing planned that week, recovery after
# ---------------------------------------------------------------------------

def _special_weeks(inputs: Inputs, start_date: date) -> dict[int, tuple]:
    """
    Maps week_num -> ("taper", race_idx, taper_index) | ("race", race_idx)
    | ("recovery", race_idx, recovery_index), for every week touched by a
    race's taper or recovery window.

    Simplification, flagged rather than hidden: if two races are close
    enough that their windows overlap, whichever assignment happens to be
    written last wins - there's no real conflict resolution here yet. Fine
    for the single-race case this is mainly tested against; multi-race
    scheduling will need real thought before this matters.
    """
    special: dict[int, tuple] = {}

    for ridx, race_date in enumerate(sorted(all_race_dates(inputs))):
        race_week = week_number_for_date(race_date, start_date)
        if not (1 <= race_week <= inputs.weeks):
            continue  # race falls outside the generated plan; ignore it

        for k in range(1, inputs.taper_weeks + 1):
            wk = race_week - inputs.taper_weeks + k
            if wk < 1:
                continue
            special[wk] = ("race", ridx) if wk == race_week else ("taper", ridx, k)

        for rk in range(1, inputs.recovery_weeks + 1):
            wk = race_week + rk
            if 1 <= wk <= inputs.weeks:
                special.setdefault(wk, ("recovery", ridx, rk))

    return special


# ---------------------------------------------------------------------------
# Assembling a week
# ---------------------------------------------------------------------------

@dataclass
class GeneratedWeek:
    week_num: int
    target_km: float
    quality_type: str                 # 'H' | 'I' | 'T' | 'R'
    quality_reps: int | None
    quality_duration_min: float | None
    quality_km: float
    long_run_km: float | None         # None on race weeks / first recovery week
    easy_runs_km: list[float]
    total_km: float
    over_target: bool                 # True if the prescribed total exceeds
                                       # target_km by more than the tolerance


def generate_weeks(inputs: Inputs, start_date: date) -> list[GeneratedWeek]:
    paces = resolve_paces(inputs)
    targets = weekly_targets(inputs)
    long_targets = long_run_baseline(inputs)
    max_long_run_km = resolve_max_long_run_km(inputs)
    base_params = {
        "H": inputs.hill_start,
        "I": inputs.vo2max_start,
        "T": inputs.threshold_start,
    }

    special = _special_weeks(inputs, start_date)

    # "Peak" values only update on ordinary build/deload weeks, so taper and
    # recovery weeks always reference the last normal week's numbers rather
    # than each other.
    peak_easy_km = inputs.min_easy_km
    peak_long_run_km = long_targets[0] if long_targets else inputs.current_weekly_km * inputs.long_run_fraction
    prev_build_long_km: float | None = None  # last true build (non-deload) week's
                                              # *displayed* long run, so the min
                                              # increment holds after clamping too,
                                              # not just in the raw progression

    weeks: list[GeneratedWeek] = []
    for w, target, long_target in zip(range(1, inputs.weeks + 1), targets, long_targets):
        role = special.get(w)

        if role is not None and role[0] == "taper":
            _, _ridx, taper_index = role
            qtype, reps, dur, quality_km = "R", None, None, 0.0
            factor = 1 - (1 - inputs.taper_long_run_floor) * (taper_index / inputs.taper_weeks)
            easy_km = round(peak_easy_km)
            long_run_km = round(peak_long_run_km * factor)
            total_km = round(2 * easy_km + long_run_km)
            over_target = False  # "target" isn't a meaningful concept in taper

        elif role is not None and role[0] == "race":
            qtype, reps, dur, quality_km = "R", None, None, 0.0
            easy_km = round(peak_easy_km)
            long_run_km = None  # the race itself replaces the long run
            total_km = round(2 * easy_km)
            over_target = False

        elif role is not None and role[0] == "recovery":
            _, _ridx, recovery_index = role
            qtype, reps, dur, quality_km = "R", None, None, 0.0
            easy_km = round(inputs.min_easy_km)  # deliberately gentle, not "hold at peak"
            if recovery_index == 1:
                long_run_km = None
                total_km = round(2 * easy_km)
            else:
                long_run_km = round(easy_km)  # same floor as any other rest week
                total_km = round(2 * easy_km + long_run_km)
            over_target = False

        else:
            if is_deload(w):
                qtype, reps, dur, quality_km = "R", None, None, 0.0
            else:
                pos = (w - 1) % 4                 # 0, 1, 2 -> H, I, T
                occurrence = (w - 1) // 4
                qtype = ROTATION_ORDER[pos]
                base_reps, base_dur = base_params[qtype]
                reps, dur = QUALITY_PROGRESSIONS[qtype](occurrence, base_reps, base_dur)
                quality_km = quality_distance_km(qtype, reps, dur, paces, inputs)

            # Easy runs are bounded to a sane range rather than left to soak
            # up whatever mileage is "left over". The long run has its own
            # independent growth (long_target, capped the same way as
            # overall mileage) and a floor relative to the easy run (1.5x in
            # build weeks, 1x in rest weeks), capped at max_long_run_km. If
            # the resulting prescription adds up to noticeably more than the
            # week's target, that's flagged rather than silently shrunk -
            # reconciling it is a job for the "make this week easier" rules,
            # which don't exist yet.
            raw_long = long_target
            raw_easy = (target - quality_km - raw_long) / 2

            easy_km = round(min(max(raw_easy, inputs.min_easy_km), inputs.max_easy_km))
            long_floor_factor = 1.0 if qtype == "R" else inputs.long_run_build_factor
            long_run_km = round(min(max(raw_long, long_floor_factor * easy_km), max_long_run_km))

            if not is_deload(w):
                # The floor-vs-easy clamp above can coincidentally land two
                # consecutive build weeks on the same rounded number even
                # though the raw progression increased - enforce the floor
                # on the actual displayed value too, then re-cap so this
                # can't push past max_long_run_km.
                if prev_build_long_km is not None:
                    long_run_km = max(long_run_km, round(prev_build_long_km + inputs.long_run_min_increment))
                long_run_km = min(long_run_km, round(max_long_run_km))
                prev_build_long_km = long_run_km

            total_km = round(2 * easy_km + long_run_km + quality_km)
            over_target = total_km > target * (1 + inputs.over_target_tolerance)

            peak_easy_km = easy_km
            peak_long_run_km = long_run_km

        weeks.append(GeneratedWeek(
            week_num=w,
            target_km=target,
            quality_type=qtype,
            quality_reps=reps,
            quality_duration_min=dur,
            quality_km=quality_km,
            long_run_km=long_run_km,
            easy_runs_km=[easy_km, easy_km],
            total_km=total_km,
            over_target=over_target,
        ))

    return weeks