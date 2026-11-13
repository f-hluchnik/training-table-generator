"""Long-run rules: growth, caps, deload, taper and the restart after a race.

Sources and tags in docs/TRAINING_MODEL.md §4 and §6. Km are whole numbers, as
printed (D-025). Pure (D-013).
"""

from collections.abc import Mapping
from types import MappingProxyType

from ttg.model import RaceType
from ttg.sessions import round_km

# +2 km per loading week [2026: +2–3 km]. Long-run guidance is usually an absolute
# step of 1–2 miles a week [source 22]; the 10 % rule is about weekly volume and has
# weak evidence [source 21], so it is only a warning (C3).
GROWTH_KM = 2

# TRAINING_MODEL.md §6: the long run of the race-specific block grows up to this cap.
CAP_KM: Mapping[RaceType, int] = MappingProxyType(
    {
        RaceType.TEN_K: 16,  # [default]
        RaceType.HALF: 21,  # [default]
        RaceType.MARATHON: 32,  # Daniels' long-run cap [source 10]
        RaceType.ULTRA: 40,  # [2026]
    }
)
# [default, owner S5] Build weeks stop at 75 % of the cap, so the peak comes in the
# race-specific block and long plans don't hold the full cap for months.
BUILD_CAP_SHARE = 0.75

# [default] A deload's long run: 75 % of the last loading week's (TRAINING_MODEL.md §4).
DELOAD_SHARE = 0.75
# Taper: the long run of the week before the race week is about 60 % of the peak
# [source 8]; earlier taper weeks use the deload depth [default].
LAST_TAPER_SHARE = 0.60
EARLY_TAPER_SHARE = DELOAD_SHARE
# [default, owner S5] After a race, the long run restarts at the deload depth of the
# previous peak, but never above the next race's build cap: after a big race
# (an ultra before a marathon) the restart follows the smaller next race.
RESTART_SHARE = DELOAD_SHARE


def cap(race_type: RaceType) -> int:
    return CAP_KM[race_type]


def build_cap(race_type: RaceType) -> int:
    return round_km(BUILD_CAP_SHARE * CAP_KM[race_type])


def grow(previous_km: int, cap_km: int) -> int:
    """Next loading week: +2 km up to the cap. The cap stops growth; it never cuts a longer run."""
    return max(previous_km, min(previous_km + GROWTH_KM, cap_km))


def deload(last_loading_km: int, easy_run_km: int) -> int:
    return _reduced(DELOAD_SHARE, last_loading_km, easy_run_km)


def taper(peak_km: int, weeks_to_race_week: int, easy_run_km: int) -> int:
    """A taper week's long run; `weeks_to_race_week` is 1 for the week just before the race week."""
    share = LAST_TAPER_SHARE if weeks_to_race_week == 1 else EARLY_TAPER_SHARE
    return _reduced(share, peak_km, easy_run_km)


def restart(previous_peak_km: int, next_race: RaceType, easy_run_km: int) -> int:
    """The first loading week's long run after a race."""
    return min(_reduced(RESTART_SHARE, previous_peak_km, easy_run_km), max(build_cap(next_race), easy_run_km))


def _reduced(share: float, km: int, easy_run_km: int) -> int:
    """A share of `km`, but a long run is never shorter than an easy run [default]."""
    return max(round_km(share * km), easy_run_km)
