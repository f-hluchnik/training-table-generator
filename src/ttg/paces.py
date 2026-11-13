"""Running paces.

`Pace` is salvaged from the prototype (D-014). The default paces are derived
from one race result with Jack Daniels' VDOT model (D-015); the numbered
sources are in docs/TRAINING_MODEL.md §10.
"""

import math
import re
from dataclasses import dataclass
from datetime import timedelta

SECONDS_PER_MINUTE = 60
METRES_PER_KM = 1000

# Daniels–Gilbert oxygen-cost equation: VO2 (ml/kg/min) at a speed in m/min [source 2].
_VO2_INTERCEPT = -4.60
_VO2_PER_SPEED = 0.182258
_VO2_PER_SPEED_SQUARED = 0.000104

# Daniels–Gilbert fraction of VO2max a runner can sustain for t minutes [source 2].
_SUSTAINABLE_FLOOR = 0.8
_SUSTAINABLE_SLOW_AMPLITUDE, _SUSTAINABLE_SLOW_DECAY = 0.1894393, 0.012778
_SUSTAINABLE_FAST_AMPLITUDE, _SUSTAINABLE_FAST_DECAY = 0.2989558, 0.1932605

# Training paces as a fraction of VDOT (the oxygen cost of the pace relative to VDOT).
# Threshold: Daniels' 88 % [source 1, 2]. Reproduces the book's T pace within 0.3 s/km at
# VDOT 50–58 (tests/test_paces.py).
THRESHOLD_FRACTION_OF_VDOT = 0.88
# Interval: Daniels gives 95–100 %; 97.5 % is our fit to the book's I pace (3:51/km at
# VDOT 51, within 2.5 s/km at VDOT 50–57, the resolution of the 2nd edition's table).
INTERVAL_FRACTION_OF_VDOT = 0.975
# Easy: Daniels' range is 59–74 % [source 2]; the book's range at VDOT 51 is 63–73 %.
# 70 % is our own default, inside both (≈ 5:37 at VDOT 44.5; override it freely).
EASY_FRACTION_OF_VDOT = 0.70
# Marathon pace is not a fraction: it is the pace of the race-equivalent marathon (D-015).
MARATHON_KM = 42.195

# Bisection bounds for the race-equivalent marathon time (minutes) and iteration count.
_MARATHON_SEARCH_MINUTES = (60.0, 600.0)
_SEARCH_ITERATIONS = 60

_PACE_PATTERN = re.compile(r"(\d+):([0-5]\d)")


@dataclass(frozen=True, order=True)
class Pace:
    """A running pace in seconds per kilometre."""

    seconds_per_km: float

    @classmethod
    def parse(cls, text: str) -> "Pace":
        """Parse "m:ss" (per km), e.g. "4:58"."""
        match = _PACE_PATTERN.fullmatch(text.strip())
        if match is None:
            raise ValueError(f'expected a pace like "4:58" (minutes:seconds per km), got "{text}"')
        minutes, seconds = (int(group) for group in match.groups())
        pace = cls(float(minutes * SECONDS_PER_MINUTE + seconds))
        if pace.seconds_per_km == 0:
            raise ValueError("a pace must be greater than 0:00")
        return pace

    def format(self) -> str:
        """Format as "m:ss", rounded to whole seconds."""
        minutes, seconds = divmod(round(self.seconds_per_km), SECONDS_PER_MINUTE)
        return f"{minutes}:{seconds:02d}"


@dataclass(frozen=True)
class TrainingPaces:
    """The four paces the sheet uses, with any overrides already applied."""

    easy: Pace
    mp: Pace
    threshold: Pace
    interval: Pace


def vdot(distance_km: float, time: timedelta) -> float:
    """Daniels' VDOT for a race result [source 1, 2]."""
    minutes = time.total_seconds() / SECONDS_PER_MINUTE
    speed = distance_km * METRES_PER_KM / minutes  # m/min
    return _oxygen_cost(speed) / _sustainable_fraction(minutes)


def derive_paces(distance_km: float, time: timedelta) -> TrainingPaces:
    """Default paces for a race result (D-015)."""
    return paces_for_vdot(vdot(distance_km, time))


def paces_for_vdot(fitness: float) -> TrainingPaces:
    """The default paces of a runner with this VDOT."""
    return TrainingPaces(
        easy=_pace_at_fraction(fitness, EASY_FRACTION_OF_VDOT),
        mp=_marathon_equivalent_pace(fitness),
        threshold=_pace_at_fraction(fitness, THRESHOLD_FRACTION_OF_VDOT),
        interval=_pace_at_fraction(fitness, INTERVAL_FRACTION_OF_VDOT),
    )


def _oxygen_cost(speed: float) -> float:
    return _VO2_INTERCEPT + _VO2_PER_SPEED * speed + _VO2_PER_SPEED_SQUARED * speed**2


def _speed_for_oxygen_cost(oxygen_cost: float) -> float:
    """Inverse of `_oxygen_cost` (the positive root of the quadratic)."""
    c = _VO2_INTERCEPT - oxygen_cost
    discriminant = _VO2_PER_SPEED**2 - 4 * _VO2_PER_SPEED_SQUARED * c
    return (-_VO2_PER_SPEED + math.sqrt(discriminant)) / (2 * _VO2_PER_SPEED_SQUARED)


def _sustainable_fraction(minutes: float) -> float:
    return (
        _SUSTAINABLE_FLOOR
        + _SUSTAINABLE_SLOW_AMPLITUDE * math.exp(-_SUSTAINABLE_SLOW_DECAY * minutes)
        + _SUSTAINABLE_FAST_AMPLITUDE * math.exp(-_SUSTAINABLE_FAST_DECAY * minutes)
    )


def _pace_at_speed(speed: float) -> Pace:
    return Pace(METRES_PER_KM / speed * SECONDS_PER_MINUTE)


def _pace_at_fraction(fitness: float, fraction: float) -> Pace:
    return _pace_at_speed(_speed_for_oxygen_cost(fitness * fraction))


def _marathon_equivalent_pace(fitness: float) -> Pace:
    """The pace of the marathon time that gives exactly this VDOT (bisection)."""
    shortest, longest = _MARATHON_SEARCH_MINUTES
    for _ in range(_SEARCH_ITERATIONS):
        minutes = (shortest + longest) / 2
        speed = MARATHON_KM * METRES_PER_KM / minutes
        if _oxygen_cost(speed) / _sustainable_fraction(minutes) > fitness:
            shortest = minutes  # this time is too fast for the fitness
        else:
            longest = minutes
    return Pace(minutes * SECONDS_PER_MINUTE / MARATHON_KM)
