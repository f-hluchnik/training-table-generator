"""
YOUR TRAINING PLAN
===================
Edit the values below, then run:

    python3 my_plan.py

This writes plan.html in the current folder - open it in a browser (or
print it, it's laid out for A4 landscape).
"""

from datetime import date

from config import Inputs
from build import write_plan_html

inputs = Inputs(
    # --- Paces -----------------------------------------------------------
    z2_pace="5:30",             # your comfortable, all-day easy pace (mm:ss/km)
    threshold_pace=None,        # leave None to auto-set to z2_pace - 1:00
    vo2max_pace=None,           # leave None to auto-set to threshold - 0:15

    # --- Plan shape --------------------------------------------------------
    current_weekly_km=20,       # roughly what you're running per week now
    training_distance_km=42.2,  # your goal race distance
    weeks=None,                 # None = end automatically on race_date's week
                                 # (or set a number to force a fixed length)

    race_date=date(2026, 12, 6),   # <-- YOUR RACE DATE GOES HERE
    # additional_race_dates=[date(2026, 10, 18)],  # only if training through
                                                     # more than one race

    taper_weeks=2,               # per race, 1-3
    recovery_weeks=2,            # per race

    use_color=False,             # True for accent-colored quality sessions
)

warnings = write_plan_html(inputs, path="plan.html")
for w in warnings:
    print(f"WARNING: {w}")

print("Wrote plan.html")