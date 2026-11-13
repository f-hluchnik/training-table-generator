"""The session catalogue: quality sessions and their progressions, long runs, easy runs.

Salvaged from the prototype (D-014): the H/I/T progressions and the quality-km
estimate, which reproduce the 2026 sessions (docs/TRAINING_MODEL.md §1, §3, §4).
Everything here is a pure function of an occurrence index; which week gets which
session is decided by `expand` (T-06).
"""

from collections.abc import Callable

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


def threshold_session(occurrence: int) -> Session:
    """3×8′ → 3×10′ → 4×8′ → 4×10′ → 5×8′, held there by the cap on minutes at T."""
    session = _uncapped_threshold_session(occurrence)
    while session.reps * session.minutes > MAX_THRESHOLD_MINUTES:
        occurrence -= 1
        session = _uncapped_threshold_session(occurrence)
    return session


def _uncapped_threshold_session(occurrence: int) -> Session:
    return Session(
        SessionType.THRESHOLD,
        reps=THRESHOLD_START_REPS + occurrence // 2,
        minutes=THRESHOLD_START_MINUTES + THRESHOLD_LONGER_REP_EXTRA_MINUTES * (occurrence % 2),
    )


def marathon_pace_session(occurrence: int) -> Session:
    """3×3 km at MP, +1 rep a week."""
    return Session(SessionType.MARATHON_PACE, reps=MP_START_REPS + occurrence, km=MP_REP_KM)


def marathon_long_run_mp_km(occurrence: int) -> int:
    """The MP km at the end of the long run of the `occurrence`-th marathon-specific week."""
    return LONG_RUN_MP_START_KM + LONG_RUN_MP_STEP_KM * occurrence


def strides_session() -> Session:
    return Session(SessionType.STRIDES)


def no_session() -> Session:
    return Session(SessionType.NONE)


def build_session(build_week_index: int) -> Session:
    """The quality session of the `build_week_index`-th build week that is not a deload (from 0)."""
    occurrence, position = divmod(build_week_index, len(BUILD_ROTATION))
    return PROGRESSIONS[BUILD_ROTATION[position]](occurrence)


PROGRESSIONS: dict[SessionType, Callable[[int], Session]] = {
    SessionType.HILLS: hill_session,
    SessionType.INTERVALS: interval_session,
    SessionType.THRESHOLD: threshold_session,
    SessionType.MARATHON_PACE: marathon_pace_session,
}


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
    work_km = session.reps * (session.km or _work_km(session, paces))
    recoveries = (session.reps - 1) * _recovery_minutes(session)
    easy_minutes = WARMUP_MINUTES + COOLDOWN_MINUTES + recoveries
    return work_km + easy_minutes * easy_km_per_minute


def _work_km(session: Session, paces: TrainingPaces) -> float:
    """Km of one repetition given in minutes; hill efforts count at easy pace."""
    return session.minutes * _km_per_minute(_effort_pace(session.type, paces))


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
