"""
Wires config.Inputs -> generator -> plan_table.Plan. This is the "engine";
for an actual runnable example with values to edit, see my_plan.py.
"""

from dataclasses import replace
from datetime import timedelta

from config import Inputs
from generator import (
    all_race_dates, format_quality_detail, generate_weeks,
    resolve_paces, resolve_plan_length, resolve_start_date,
)
from plan_table import LegendItem, Plan, Week, render_html


def build_plan(inputs: Inputs) -> tuple[Plan, list[str]]:
    start_date = resolve_start_date(inputs)
    weeks_count, warnings = resolve_plan_length(inputs, start_date)
    resolved = replace(inputs, weeks=weeks_count)

    generated = generate_weeks(resolved, start_date)
    paces = resolve_paces(resolved)

    weeks = [
        Week(
            week_num=gw.week_num,
            start_date=start_date + timedelta(weeks=gw.week_num - 1),
            easy_runs=gw.easy_runs_km,
            quality_type=gw.quality_type,
            quality_detail=format_quality_detail(gw.quality_reps, gw.quality_duration_min),
            long_run_km=gw.long_run_km,
            total_km=gw.total_km,
            over_target=gw.over_target,
        )
        for gw in generated
    ]

    # One legend, each code appearing exactly once.
    legend = [
        LegendItem("H",  "Uphill",     paces["Z2"].format() + " /km"),
        LegendItem("I",  "VO2max",     paces["I"].format() + " /km"),
        LegendItem("T",  "Threshold",  paces["T"].format() + " /km"),
        LegendItem("R",  "Rest",       None),
        LegendItem("Z2", "Easy/Long",  paces["Z2"].format() + " /km"),
    ]

    races = all_race_dates(resolved)
    subtitle = f"{resolved.weeks} weeks - starting at {resolved.current_weekly_km:g} km/week"
    if races:
        race_list = ", ".join(f"{d:%d %b %Y}" for d in sorted(races))
        subtitle += f" - race day(s): {race_list}"

    plan = Plan(
        title="Training Plan",
        subtitle=subtitle,
        weeks=weeks,
        legend=legend,
        segment_km=resolved.segment_km,
        race_dates=races,
    )
    return plan, warnings


def write_plan_html(inputs: Inputs, path: str = "plan.html") -> list[str]:
    """Convenience wrapper: build, render, write to disk, return warnings."""
    plan, warnings = build_plan(inputs)
    html = render_html(plan, use_color=inputs.use_color)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return warnings