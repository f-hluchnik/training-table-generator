"""
Minimal web front end. Two routes:
  GET  /          - the form
  POST /generate  - builds a plan from the submitted form and returns the
                     rendered plan.html directly as the response - this is
                     the "one endpoint that does python my_plan.py".

Run with:
    python3 app.py
then open http://127.0.0.1:5000
"""

from datetime import date

from flask import Flask, Response, render_template, request

from build import build_plan
from config import Inputs
from plan_table import render_html

app = Flask(__name__)

DEFAULTS = Inputs()  # source of truth for pre-filled form values


def _str_or_none(form, name):
    v = (form.get(name) or "").strip()
    return v or None


def _int_or_none(form, name):
    v = (form.get(name) or "").strip()
    return int(v) if v else None


def _float_or_none(form, name):
    v = (form.get(name) or "").strip()
    return float(v) if v else None


def _float(form, name, default):
    v = (form.get(name) or "").strip()
    return float(v) if v else default


def _int(form, name, default):
    v = (form.get(name) or "").strip()
    return int(v) if v else default


def _date_or_none(form, name):
    v = (form.get(name) or "").strip()
    return date.fromisoformat(v) if v else None


def _dates_list(form, name):
    raw = (form.get(name) or "").strip()
    if not raw:
        return []
    parts = [p.strip() for p in raw.replace(",", "\n").splitlines() if p.strip()]
    return [date.fromisoformat(p) for p in parts]


def _bool(form, name):
    return form.get(name) == "on"


def inputs_from_form(form) -> Inputs:
    """Every Inputs field, explicitly. Verbose on purpose - it's meant to be
    obvious which form field feeds which config value, and adding a new
    config field means adding one line here plus one field in the template."""
    return Inputs(
        z2_pace=(form.get("z2_pace") or DEFAULTS.z2_pace).strip(),
        threshold_pace=_str_or_none(form, "threshold_pace"),
        vo2max_pace=_str_or_none(form, "vo2max_pace"),

        current_weekly_km=_int(form, "current_weekly_km", DEFAULTS.current_weekly_km),
        training_distance_km=_float_or_none(form, "training_distance_km"),
        weeks=_int_or_none(form, "weeks"),
        start_date=_date_or_none(form, "start_date"),

        race_date=_date_or_none(form, "race_date"),
        additional_race_dates=_dates_list(form, "additional_race_dates"),
        taper_weeks=_int(form, "taper_weeks", DEFAULTS.taper_weeks),
        recovery_weeks=_int(form, "recovery_weeks", DEFAULTS.recovery_weeks),

        hill_start=(
            _int(form, "hill_reps", DEFAULTS.hill_start[0]),
            _float(form, "hill_min", DEFAULTS.hill_start[1]),
        ),
        vo2max_start=(
            _int(form, "vo2max_reps", DEFAULTS.vo2max_start[0]),
            _float(form, "vo2max_min", DEFAULTS.vo2max_start[1]),
        ),
        threshold_start=(
            _int(form, "threshold_reps", DEFAULTS.threshold_start[0]),
            _float(form, "threshold_min", DEFAULTS.threshold_start[1]),
        ),

        use_color=_bool(form, "use_color"),

        max_growth_rate=_float(form, "max_growth_rate", DEFAULTS.max_growth_rate),
        deload_factor=_float(form, "deload_factor", DEFAULTS.deload_factor),
        long_run_fraction=_float(form, "long_run_fraction", DEFAULTS.long_run_fraction),
        long_run_build_factor=_float(form, "long_run_build_factor", DEFAULTS.long_run_build_factor),
        long_run_min_increment=_float(form, "long_run_min_increment", DEFAULTS.long_run_min_increment),
        taper_long_run_floor=_float(form, "taper_long_run_floor", DEFAULTS.taper_long_run_floor),
        over_target_tolerance=_float(form, "over_target_tolerance", DEFAULTS.over_target_tolerance),

        warmup_min=_float(form, "warmup_min", DEFAULTS.warmup_min),
        cooldown_min=_float(form, "cooldown_min", DEFAULTS.cooldown_min),
        pause_min_default=_float(form, "pause_min_default", DEFAULTS.pause_min_default),

        min_easy_km=_float(form, "min_easy_km", DEFAULTS.min_easy_km),
        max_easy_km=_float(form, "max_easy_km", DEFAULTS.max_easy_km),
        max_long_run_km=_float_or_none(form, "max_long_run_km"),

        segment_km=_float(form, "segment_km", DEFAULTS.segment_km),
    )


@app.route("/")
def index():
    return render_template("index.html", d=DEFAULTS)


@app.route("/generate", methods=["POST"])
def generate():
    try:
        inputs = inputs_from_form(request.form)
        plan, warnings = build_plan(inputs)
    except (ValueError, TypeError) as e:
        return Response(
            "<!DOCTYPE html><html><body style='font:14px sans-serif;padding:40px;'>"
            f"<p><strong>Couldn't generate a plan:</strong> {e}</p>"
            "<p><a href='/'>&larr; back to the form</a></p></body></html>",
            status=400, mimetype="text/html",
        )

    html = render_html(plan, use_color=inputs.use_color)

    if warnings:
        banner = "".join(
            '<p style="margin:0;padding:6px 10px;background:#FFF3CD;'
            'border-bottom:1px solid #E0C36B;font:13px sans-serif;color:#5C4A10;">'
            f"&#9888; {w}</p>"
            for w in warnings
        )
        html = html.replace("<body>", f"<body>{banner}", 1)

    return Response(html, mimetype="text/html")


if __name__ == "__main__":
    app.run(debug=True)