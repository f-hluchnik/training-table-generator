"""The session catalogue: quality sessions and their progressions, long runs, easy runs.

Salvaged from the prototype (D-014): the H/I/T progressions and the quality-km
estimate, which reproduce the 2026 sessions (docs/TRAINING_MODEL.md §1, §3, §4).
Everything here is a pure function of an occurrence index; which week gets which
session is decided by `expand` (T-06).
"""

import math

from ttg.model import EasyRuns, Session, SessionType
from ttg.paces import SECONDS_PER_MINUTE, Pace, TrainingPaces

# A week has one quality run and one long run; the rest are easy runs (D-016).
RUNS_THAT_ARE_NOT_EASY = 2

# Quality-km estimate: warm-up + work + recoveries + cool-down [2026, prototype].
WARMUP_MINUTES = 10
COOLDOWN_MINUTES = 10
RECOVERY_JOG_MINUTES = 2  # between reps of I, T and MP; hill recovery lasts as long as the effort

# Where each progression starts [2026].
HILL_START_REPS, HILL_START_MINUTES = 6, 1
HILL_REPS_BEFORE_SPLIT = 10  # at this many reps: halve the reps, double the duration
INTERVAL_START_REPS, INTERVAL_START_MINUTES = 5, 3
THRESHOLD_START_REPS, THRESHOLD_START_MINUTES = 3, 8
THRESHOLD_LONGER_REP_EXTRA_MINUTES = 2  # 8′ → 10′ [2026]
# Tempo work is 15–40 min [source 5]: no more than 40′ at T in one session.
MAX_THRESHOLD_MINUTES = 40
MP_START_REPS, MP_REP_KM = 3, 3  # marathon-pace repeats, +1 rep a week [2026]
# The last MP km of a marathon-specific long run: 6, 8, 10, … [default].
LONG_RUN_MP_START_KM, LONG_RUN_MP_STEP_KM = 6, 2
# Daniels: running at I pace in one session is at most the lesser of 10 km and 8 % of the
# week [source 11]. The I progression holds at the last step within it (owner, S5); compared in
# whole km, the sheet's precision (D-025).
MAX_INTERVAL_KM = 10
MAX_INTERVAL_SHARE_OF_WEEK = 0.08
# Daniels: one session holds at most the lesser of 90 min or 16 miles at M pace [source 20].
# The 16 miles (25.7 km) only binds below 3:21/km, so the minutes are the cap here.
MAX_MARATHON_PACE_MINUTES = 90
# The quality run of the taper weeks before the race week: short threshold work,
# T 6 × 1 km [2026; "intensity is kept short", source 8].
TAPER_THRESHOLD_REPS, TAPER_THRESHOLD_REP_KM = 6, 1

# A strides run (S): an easy run of e/2 km with short, fast, relaxed strides
# (TRAINING_MODEL.md §1) [default]. Only printed in the legend; the km are e/2.
STRIDES_COUNT, STRIDES_SECONDS = 6, 20

# Quality rotation of the build phase [2026]: each type progresses each time it occurs.
BUILD_ROTATION = (SessionType.HILLS, SessionType.INTERVALS, SessionType.THRESHOLD)


def hill_session(occurrence: int) -> Session:
    """6×1′, +1 rep each time; at 10 reps: halve the reps, double the duration."""
    reps, minutes = HILL_START_REPS, HILL_START_MINUTES
    for _ in range(occurrence):
        reps += 1
        if reps >= HILL_REPS_BEFORE_SPLIT:
            reps //= 2
            minutes *= 2
    return Session(SessionType.HILLS, reps=reps, minutes=minutes)


def interval_session(occurrence: int) -> Session:
    """5×3′ → 6×3′ → 5×4′ → 6×4′ → 5×5′ …"""
    return Session(
        SessionType.INTERVALS,
        reps=INTERVAL_START_REPS + occurrence % 2,
        minutes=INTERVAL_START_MINUTES + occurrence // 2,
    )


def capped_interval_session(occurrence: int, paces: TrainingPaces, easy_run_km: int, other_week_km: int) -> Session:
    """`interval_session`, held at the last step within Daniels' limit for its week.

    `other_week_km` are the week's km without this session (easy runs and long run).
    """
    for step in range(occurrence, 0, -1):
        session = interval_session(step)
        week_km = other_week_km + round_km(session_km(session, paces, easy_run_km))
        if round_km(work_km(session, paces.interval)) <= interval_limit_km(week_km):
            return session
    return interval_session(0)


def interval_limit_km(week_km: int) -> int:
    """The most km at I pace one session of a `week_km` week should hold, in whole km."""
    return round_km(min(MAX_INTERVAL_KM, MAX_INTERVAL_SHARE_OF_WEEK * week_km))


def threshold_session(occurrence: int) -> Session:
    """3×8′ → 3×10′ → 4×8′ → 4×10′ → 5×8′, held there by the cap on minutes at T."""
    reps, minutes = _uncapped_threshold_shape(occurrence)
    while reps * minutes > MAX_THRESHOLD_MINUTES:
        occurrence -= 1
        reps, minutes = _uncapped_threshold_shape(occurrence)
    return Session(SessionType.THRESHOLD, reps=reps, minutes=minutes)


def _uncapped_threshold_shape(occurrence: int) -> tuple[int, int]:
    """(reps, minutes per rep) of the `occurrence`-th T session, before the cap."""
    reps = THRESHOLD_START_REPS + occurrence // 2
    minutes = THRESHOLD_START_MINUTES + THRESHOLD_LONGER_REP_EXTRA_MINUTES * (occurrence % 2)
    return reps, minutes


def marathon_pace_session(occurrence: int, mp: Pace) -> Session:
    """3×3 km at MP, +1 rep a week, held at the most reps that fit the MP cap."""
    reps = min(MP_START_REPS + occurrence, max(1, _max_marathon_pace_km(mp) // MP_REP_KM))
    return Session(SessionType.MARATHON_PACE, reps=reps, km=MP_REP_KM)


def marathon_long_run_mp_km(occurrence: int, mp: Pace) -> int:
    """The MP km at the end of the `occurrence`-th marathon-specific long run: 6, 8, … up to the MP cap."""
    return min(LONG_RUN_MP_START_KM + LONG_RUN_MP_STEP_KM * occurrence, _max_marathon_pace_km(mp))


def _max_marathon_pace_km(mp: Pace) -> int:
    """Whole km that fit into the MP cap."""
    return math.floor(MAX_MARATHON_PACE_MINUTES * _km_per_minute(mp))


def taper_session() -> Session:
    return Session(SessionType.THRESHOLD, reps=TAPER_THRESHOLD_REPS, km=TAPER_THRESHOLD_REP_KM)


def strides_session() -> Session:
    return Session(SessionType.STRIDES)


def no_session() -> Session:
    return Session(SessionType.NONE)


def progression_session(
    session_type: SessionType, occurrence: int, paces: TrainingPaces, easy_run_km: int, other_week_km: int
) -> Session:
    """The `occurrence`-th session (from 0) of a progressing type: H, I, T or MP.

    `other_week_km` are the week's km without this session; the I cap depends on them.
    """
    match session_type:
        case SessionType.HILLS:
            return hill_session(occurrence)
        case SessionType.INTERVALS:
            return capped_interval_session(occurrence, paces, easy_run_km, other_week_km)
        case SessionType.THRESHOLD:
            return threshold_session(occurrence)
        case SessionType.MARATHON_PACE:
            return marathon_pace_session(occurrence, paces.mp)
    raise ValueError(f"{session_type} has no progression")


def round_km(km: float) -> int:
    """Whole km as printed on the sheet (D-025), halves rounded up."""
    return math.floor(km + 0.5)


def half_easy_run_km(easy_run_km: int) -> int:
    """e/2 rounded up to whole km (D-022); also the length of a strides run."""
    return (easy_run_km + 1) // 2


def easy_run_kms(easy_run_km: int, runs_per_week: int, pattern: EasyRuns) -> tuple[int, ...]:
    """The easy runs of a week: all `easy_run_km`, the last halved in a reduced week (D-016, D-022)."""
    runs = [easy_run_km] * (runs_per_week - RUNS_THAT_ARE_NOT_EASY)
    if pattern is EasyRuns.REDUCED:
        runs[-1] = half_easy_run_km(easy_run_km)
    return tuple(runs)


def session_km(session: Session, paces: TrainingPaces, easy_run_km: int) -> float:
    """Estimated km of a quality run, warm-up and cool-down included."""
    if session.type is SessionType.NONE:
        return 0.0
    if session.type is SessionType.STRIDES:
        return float(half_easy_run_km(easy_run_km))
    easy_km_per_minute = _km_per_minute(paces.easy)
    # Hill efforts count at easy pace.
    work = work_km(session, _effort_pace(session.type, paces))
    recoveries = (_reps(session) - 1) * _recovery_minutes(session)
    easy_minutes = WARMUP_MINUTES + COOLDOWN_MINUTES + recoveries
    return work + easy_minutes * easy_km_per_minute


def work_km(session: Session, pace: Pace) -> float:
    """Km of work (recoveries excluded) at `pace`, for repetitions given in minutes or in km."""
    if session.km is not None:
        return _reps(session) * session.km
    return _reps(session) * _rep_minutes(session) * _km_per_minute(pace)


def work_minutes(session: Session, pace: Pace) -> float:
    """Minutes of work (recoveries excluded) at `pace`, for repetitions given in minutes or in km."""
    if session.km is not None:
        return _reps(session) * session.km / _km_per_minute(pace)
    return _reps(session) * _rep_minutes(session)


def _reps(session: Session) -> int:
    if session.reps is None:
        raise ValueError(f"a {session.type} session has no repetitions")
    return session.reps


def _rep_minutes(session: Session) -> float:
    """Minutes per repetition of a session given in minutes (spec allows exactly one of minutes or km)."""
    if session.minutes is None:
        raise ValueError(f"this {session.type} session is given in km, not minutes")
    return session.minutes


def _effort_pace(session_type: SessionType, paces: TrainingPaces) -> Pace:
    return {
        SessionType.HILLS: paces.easy,
        SessionType.INTERVALS: paces.interval,
        SessionType.THRESHOLD: paces.threshold,
        SessionType.MARATHON_PACE: paces.mp,
    }[session_type]


def _recovery_minutes(session: Session) -> float:
    if session.type is SessionType.HILLS and session.minutes:
        return session.minutes  # the jog down takes as long as the effort up
    return RECOVERY_JOG_MINUTES


def _km_per_minute(pace: Pace) -> float:
    return SECONDS_PER_MINUTE / pace.seconds_per_km
