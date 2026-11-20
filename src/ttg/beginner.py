"""The beginner's rules (TRAINING_MODEL.md §11, D-054): gentle growth, little intensity, no warnings.

The phase layout, the 3:1 cycle and the long-run reductions (deload, taper, restart) are the
standard ones; what differs is here: how a week's runs grow, the long-run caps, the easy runs, and
which quality run a week gets. `ttg.expand` applies them. Pure (D-013).

Studies give novices no progression numbers: a 10 % rule did not prevent injuries [source 21], and
the evidence on load changes is very limited [source 42]. The numbers follow established beginner
plans (NHS Couch to 5K, Higdon's novice plans) or are our own defaults, as tagged.
"""

from collections.abc import Mapping
from types import MappingProxyType

from ttg.model import Race, RaceType, Session, SessionType, WeekKind
from ttg.paces import Pace
from ttg.sessions import round_km

# --- the runs of a week -----------------------------------------------------

# [default, fitted to Higdon] A week grows by 1 km a loading week, in turn the long run's and the
# shortest easy run's. Higdon's novice 10K adds about 0.8 km a week to the long run [source 35];
# his novice half adds 1.6 km every other week [source 36]. An absolute step: at 3–10 km a share
# of the run is not a step in whole km.
STEP_KM = 1

# [default, fitted to Higdon] Without `easy_run_km`, an easy run is ¾ of the first long run:
# Higdon's novice plans start with weekday runs of 2.5 mi to a 3 mi long run (10K) and 3 mi to
# 4 mi (half) [source 35, 36].
DEFAULT_EASY_SHARE_OF_LONG_RUN = 0.75
MIN_DEFAULT_EASY_RUN_KM = 1

# [default] An easy run grows up to these lengths; Higdon's weekday runs top out at 3 mi (10K) and
# 5 mi (half) [source 35, 36]. It also stays at least 1 km shorter than the long run.
EASY_RUN_CAP_KM: Mapping[RaceType, int] = MappingProxyType(
    {RaceType.TEN_K: 5, RaceType.HALF: 8, RaceType.MARATHON: 8, RaceType.ULTRA: 8}
)
EASY_RUN_BELOW_LONG_RUN_KM = 1

# [default] A reduced week (deload, taper, race, recovery) takes 1 km off each easy run, but does not
# shorten a run below 2 km, about a Couch to 5K week-1 session [source 33].
REDUCTION_KM = 1
MIN_REDUCED_EASY_RUN_KM = 2

# --- the long run -----------------------------------------------------------

# Higdon's novice plans peak at 4.8 km for a 5 km and 8.9 km for a 10 km [source 34, 35]: about
# 90 % of the race distance, which is the cap for races up to 10 km.
SHORT_RACE_CAP_SHARE = 0.9
# Higdon's novice half peaks at 10 mi [source 36].
HALF_CAP_KM = 16
# A marathon or longer: 20 mi in Higdon's novice plan [source 37], and at most 3 h at easy pace
# [default], looser than Daniels' 150 min for trained runners [source 25], since a beginner runs slower.
LONG_RACE_CAP_KM = 32
LONG_RACE_CAP_MINUTES = 180

# --- the quality run ----------------------------------------------------------

# Higdon's novice plans have no speed work [source 34–37]. Strides come first, then short hills
# [source 44, 45]; intervals and threshold runs are for later [source 45].
# [default] No quality run in weeks 1–4; strides from week 5; from week 9 (after a month of
# strides, source 44 says 2–3 weeks) hill repeats every other loading week, strides in between.
STRIDES_FROM_WEEK = 5
HILLS_FROM_WEEK = 9
# [default] Hill repeats 4 × 1′, one more each time, held at 6 × 1′; walk or jog down.
HILL_START_REPS = 4
HILL_MAX_REPS = 6
HILL_REP_MINUTES = 1

# With fewer runs a week there is no quality run: a beginner keeps the long run first (owner, S11).
MIN_RUNS_FOR_A_QUALITY_RUN = 3

# [default, coach S11] Rest before the race: the race week has no quality run and one easy run fewer,
# as in Higdon's novice race weeks [source 35, 36].
RACE_WEEK_RUNS_LEFT_OUT = 1


def default_easy_run_km(long_run_km: int) -> int:
    return max(MIN_DEFAULT_EASY_RUN_KM, round_km(DEFAULT_EASY_SHARE_OF_LONG_RUN * long_run_km))


def long_run_cap(race: Race, easy: Pace) -> int:
    """The beginner's long-run cap for a race; reached in the race-specific block, as for anyone."""
    match race.type:
        case RaceType.TEN_K:
            return round_km(SHORT_RACE_CAP_SHARE * race.distance_km)
        case RaceType.HALF:
            return HALF_CAP_KM
    three_hours_km = round_km(LONG_RACE_CAP_MINUTES * 60 / easy.seconds_per_km)
    return min(LONG_RACE_CAP_KM, three_hours_km)


def easy_run_cap(race: Race, long_run_km: int) -> int:
    return min(EASY_RUN_CAP_KM[race.type], long_run_km - EASY_RUN_BELOW_LONG_RUN_KM)


def reduced(easy_kms: tuple[int, ...]) -> tuple[int, ...]:
    """A reduced week's easy runs: each 1 km shorter, but not below 2 km by the cut."""
    return tuple(max(km - REDUCTION_KM, min(km, MIN_REDUCED_EASY_RUN_KM)) for km in easy_kms)


def grown(easy_kms: tuple[int, ...], cap_km: int) -> tuple[int, ...] | None:
    """The easy runs with the shortest one 1 km longer, longest first; None when it is at the cap."""
    shortest = min(easy_kms)
    if shortest + STEP_KM > cap_km:
        return None
    runs = list(easy_kms)
    runs[runs.index(shortest)] += STEP_KM
    return tuple(sorted(runs, reverse=True))


def has_quality_run(runs_per_week: int) -> bool:
    return runs_per_week >= MIN_RUNS_FOR_A_QUALITY_RUN


def quality_type(kind: WeekKind, number: int, hill_week: bool) -> SessionType:
    """The kind of quality run a week gets; `hill_week` alternates in the loading weeks."""
    if kind in (WeekKind.RACE, WeekKind.RECOVERY) or number < STRIDES_FROM_WEEK:
        return SessionType.NONE
    if kind.is_loading and number >= HILLS_FROM_WEEK and hill_week:
        return SessionType.HILLS
    return SessionType.STRIDES


def hill_session(occurrence: int) -> Session:
    """The `occurrence`-th (from 0) beginner hill session: 4 × 1′, 5 × 1′, then 6 × 1′."""
    reps = min(HILL_START_REPS + occurrence, HILL_MAX_REPS)
    return Session(SessionType.HILLS, reps=reps, minutes=HILL_REP_MINUTES)
