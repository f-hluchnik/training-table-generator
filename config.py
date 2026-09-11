"""
All the knobs that define a single plan. This is deliberately separate from
generator.py: the idea is that Inputs eventually gets populated by a web
form rather than constructed in code, so it shouldn't be tangled up with
the computation itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class Inputs:
    # --- Paces -----------------------------------------------------------
    z2_pace: str = "5:30"
    threshold_pace: str | None = None   # default: z2 - 1:00
    vo2max_pace: str | None = None      # default: threshold - 0:15

    # --- Plan shape --------------------------------------------------------
    weeks: int | None = None            # None -> derived: the week of the
                                         # latest race date, or 10 if there's
                                         # no race date at all
    current_weekly_km: int = 20
    start_date: date | None = None      # if unset, next Monday (today, if
                                         # today is itself a Monday)

    race_date: date | None = None       # your race day, e.g.
                                         #   race_date=date(2026, 10, 12)
    training_distance_km: float | None = None   # your goal race distance;
                                         # drives max_long_run_km below if
                                         # that isn't set explicitly
    additional_race_dates: list[date] = field(default_factory=list)
                                         # rare case: training through more
                                         # than one race. Each race date
                                         # (race_date + these) gets its own
                                         # taper and recovery window.
    taper_weeks: int = 2                # weeks of taper before EACH race; 1-3
    recovery_weeks: int = 2             # weeks of recovery after EACH race

    # --- Quality session starting points -----------------------------------
    hill_start: tuple[int, float] = (6, 1)         # (reps, minutes)
    vo2max_start: tuple[int, float] = (5, 3)
    threshold_start: tuple[int, float] = (3, 8)

    # --- Display -------------------------------------------------------
    use_color: bool = False            # accent-color the quality-session strips

    # --- Tunables ------------------------------------------------------
    # Not exposed as user-facing inputs yet, but every one of these is a
    # candidate form field later. Kept here rather than as magic numbers
    # scattered through generator.py.

    max_growth_rate: float = 0.10      # CEILING on week-over-week mileage
                                        # increase - not a fixed rate. Today
                                        # nothing lowers it further, but the
                                        # generator treats it as a cap so a
                                        # future "desired growth" signal can
                                        # slot in without changing the shape
                                        # of that logic.
    deload_factor: float = 0.75        # deload week = this * last build peak
    long_run_fraction: float = 0.30    # long run's starting share of mileage
    long_run_build_factor: float = 1.5 # in build weeks, long run >= this * easy
    long_run_min_increment: float = 2.0  # build-week long run must grow by at
                                          # least this much vs. the last build
                                          # week (unless capped by max_long_run_km)
    taper_long_run_floor: float = 0.60 # long run eases down to this fraction
                                        # of the pre-taper peak by the last
                                        # taper week
    over_target_tolerance: float = 0.10  # only flag totals more than this
                                          # far above the computed target

    warmup_min: float = 10.0
    cooldown_min: float = 10.0
    pause_min_default: float = 2.0     # recovery jog between reps (I, T)
    # Hill recovery isn't given a fixed value in the brief; the working
    # assumption is "jog back down takes about as long as the effort up."
    # Swap out hill_pause_min() in generator.py if you want a fixed value.

    min_easy_km: float = 5.0           # an "easy run" is never shorter than this
    max_easy_km: float = 12.0          # ...or longer than this
    # Cap on the long run. None = derive from training_distance_km (see
    # resolve_max_long_run_km in generator.py); set this directly to
    # override that derivation.
    max_long_run_km: float | None = None

    segment_km: float = 2.0            # km represented by one "actual" gauge box