"""The generator page's entry point (D-052): the form's texts become the season file's tree.

The form sends every value as the text the visitor typed. The page is checked against both reference
seasons: the same plan comes out whether it is read from the season file or from the form."""

import json
import re
import subprocess
import sys
import tomllib
from datetime import date

import pytest

from ttg.expand import expand
from ttg.model import SeasonError
from ttg.spec import load_season, parse_season
from ttg.web import MAX_WEEKS, generate, generate_json, season_data, season_toml

from support import FIXTURES, SEASONS, TODAY

MARATHON = {"name": "Marathon", "date": "2027-10-10", "distance_km": "42.195"}


def a_form(**changes):
    """The smallest form that builds: one marathon, its result and the starting load."""
    form = {
        "start": "2027-05-03",
        "race": [dict(MARATHON)],
        "paces": {"race_result": {"distance_km": "42.195", "time": "3:30:02"}},
        "load": {"easy_run_km": "12", "long_run_km": "15"},
    }
    return form | changes


# The season of seasons/2026.toml, as the form sends it: texts, with a decimal comma where a Czech keyboard has one.
FORM_2026 = {
    "start": "2026-05-04",
    "sheet": {"title": "marathon training plan", "rules": ""},
    "race": [
        {
            "name": "Beskydská sedmička",
            "date": "2026-08-28",
            "end": "2026-08-29",
            "distance_km": "101",
            "priority": "B",
            "taper_weeks": "3",
            "recovery_weeks": "2",
            "hilly": False,
        },
        {"name": "Běhej Lesy Lednice", "date": "2026-10-10", "distance_km": "42,195", "priority": "A"},
    ],
    "paces": {
        "race_result": {"distance_km": "42,195", "time": "3:30:02"},
        "easy": "5:30",
        "mp": "4:58",
        "threshold": "4:30",
        "interval": "4:15",
    },
    "load": {"easy_run_km": "12", "long_run_km": "15", "runs_per_week": "4"},
    "overrides": [
        {"week": "1", "easy": "reduced"},
        {"week": "2", "easy": "reduced"},
        {"week": "3", "easy": "reduced"},
        {"week": "13", "quality": {"type": "H", "reps": "10", "minutes": "1"}},
        {"week": "14", "long_run_km": "40"},
        {"week": "19", "note": "flush"},
        {"week": "20", "note": "check"},
        {"week": "21", "note": "peak"},
        {"week": "", "easy": "", "quality": {"type": "", "reps": "", "minutes": "", "km": ""}, "note": ""},
    ],
}


def as_json(plan):
    return json.loads(json.dumps(plan))


def test_the_form_of_the_2026_season_builds_its_snapshot():
    plan = generate(FORM_2026, TODAY).plan
    assert as_json(plan) == json.loads((FIXTURES / "plan-2026.json").read_text(encoding="utf-8"))


def test_the_season_file_written_from_the_form_is_the_2026_season():
    written = season_toml(season_data(FORM_2026))
    assert parse_season(tomllib.loads(written)) == load_season(SEASONS / "2026.toml")


def test_a_race_without_phase_lengths_or_priority_takes_the_defaults():
    plan = generate(a_form(), TODAY).plan
    assert plan["weeks"][-1]["days"][6]["date"] == "2027-10-10"


def test_a_start_date_or_a_length_or_neither_may_start_the_plan():
    form = a_form(start="")
    next_monday = generate(form, date(2027, 5, 1)).plan["weeks"][0]["days"][0]["date"]
    assert next_monday == "2027-05-03"
    assert len(generate(form | {"weeks": "20"}, TODAY).plan["weeks"]) == 20


def test_blanks_are_missing_fields_and_whitespace_is_ignored():
    form = a_form(race=[MARATHON | {"end": "  ", "priority": "", "taper_weeks": " 2 "}])
    race = season_data(form)["race"][0]
    assert race == {"name": "Marathon", "date": date(2027, 10, 10), "distance_km": 42.195, "taper_weeks": 2}


def test_a_whole_number_of_km_stays_an_integer():
    assert season_data(a_form(race=[MARATHON | {"distance_km": "10,0"}]))["race"][0]["distance_km"] == 10


@pytest.mark.parametrize(
    ("form", "message"),
    [
        ({"load": {"beginner": False}}, "race: at least one [[race]] is required"),
        (a_form(race=[{}]), "race[1].date: missing (required)"),
        (
            a_form(race=[MARATHON | {"date": "10.10.2027"}]),
            'race[1].date: expected a date like 2026-05-04, got "10.10.2027"',
        ),
        (a_form(race=[MARATHON | {"taper_weeks": "two"}]), 'race[1].taper_weeks: expected a whole number, got "two"'),
        (a_form(race=[MARATHON | {"distance_km": "far"}]), 'race[1].distance_km: expected a number, got "far"'),
        (a_form(race=[MARATHON | {"distance_km": "nan"}]), 'race[1].distance_km: expected a number, got "nan"'),
        (a_form(race=[MARATHON, MARATHON | {"date": "xx"}]), "race[2].date: expected a date"),
        (
            a_form(paces={}, load={"beginner": False, "easy_run_km": "12", "long_run_km": "15"}),
            "paces.race_result.distance_km: missing (required)",
        ),
        (
            a_form(paces={"race_result": {"distance_km": "42,195", "time": "fast"}}),
            "paces.race_result.time: expected a time",
        ),
        (a_form(load={}), "load.easy_run_km: missing (required)"),
        (
            a_form(load={"easy_run_km": "12", "long_run_km": "15", "runs_per_week": "9"}),
            "load.runs_per_week: must be at most 6",
        ),
        (a_form(weeks="20"), "weeks: give either start or weeks, not both"),
        (a_form(race=[MARATHON | {"priority": "C", "hilly": True}]), "race[1].hilly"),
        (a_form(overrides=[{"week": "x", "note": "n"}]), 'overrides[1].week: expected a whole number, got "x"'),
        (a_form(overrides=[{"note": "no week"}]), "overrides[1].week: missing (required)"),
        (
            a_form(overrides=[{"week": "3", "note": "a"}, {"week": "03", "note": "b"}]),
            "overrides.3: week 3 is overridden twice",
        ),
        (
            a_form(overrides=[{"week": "3", "quality": {"type": "H", "reps": "5"}}]),
            "overrides.3.quality: give exactly one of minutes or km",
        ),
        (
            a_form(overrides=[{"week": "3", "quality": {"reps": "5", "km": "3"}}]),
            "overrides.3.quality.type: missing (required)",
        ),
    ],
)
def test_an_invalid_form_names_its_field(form, message):
    with pytest.raises(SeasonError, match=re.escape(message)):
        generate(form, TODAY)


def test_an_override_row_with_nothing_in_it_is_skipped():
    row = {
        "week": "",
        "easy": "",
        "quality": {"type": "", "reps": "", "minutes": "", "km": ""},
        "long_run_km": "",
        "note": "",
    }
    assert "overrides" not in season_data(a_form(overrides=[row]))


def test_the_sheet_rules_are_the_lines_of_the_text():
    data = season_data(a_form(sheet={"title": "", "rules": " Drop intensity first.\n\n Then the long run. "}))
    assert data["sheet"] == {"rules": ["Drop intensity first.", "Then the long run."]}


@pytest.mark.parametrize(
    "text",
    ['say "hi"', "back\\slash", "tab\there", "Běhej, Lesy: Lednice ½", "del\x7fchar", "multi\nline", "# not a comment"],
)
def test_any_text_survives_the_season_file(text):
    data = season_data(a_form(sheet={"title": text, "rules": ""}))
    assert tomllib.loads(season_toml(data))["sheet"]["title"] == text


def test_the_season_file_reads_back_as_the_tree_it_was_written_from():
    data = season_data(FORM_2026)
    assert tomllib.loads(season_toml(data)) == data


def test_the_season_file_is_the_file_a_runner_would_write():
    written = season_toml(
        season_data(a_form(overrides=[{"week": "13", "quality": {"type": "H", "reps": "10", "minutes": "1"}}]))
    )
    assert written == (
        "start = 2027-05-03\n\n"
        '[[race]]\nname = "Marathon"\ndate = 2027-10-10\ndistance_km = 42.195\n\n'
        '[paces]\nrace_result = { distance_km = 42.195, time = "3:30:02" }\n\n'
        "[load]\neasy_run_km = 12\nlong_run_km = 15\n\n"
        '[overrides]\n13 = { quality = { type = "H", reps = 10, minutes = 1 } }\n'
    )


def test_the_page_gets_the_plan_and_the_season_file_as_json():
    reply = json.loads(generate_json(json.dumps(a_form()), "2026-11-20"))
    assert reply["plan"]["schema_version"] == generate(a_form(), TODAY).plan["schema_version"]
    assert reply["season_toml"].startswith("start = 2027-05-03\n")


def test_the_page_gets_an_invalid_form_as_an_error_message():
    reply = json.loads(generate_json(json.dumps(a_form(load={})), "2026-11-20"))
    assert reply == {"error": "load.easy_run_km: missing (required)"}


def test_the_module_runs_without_the_typst_compiler():
    """The page loads this module in a browser, where Typst is not installed."""
    code = "import sys; sys.modules['typst'] = None; import ttg.web"
    subprocess.run([sys.executable, "-c", code], check=True)


# --- the page's limit on the length of a plan (D-053) -----------------------------


def test_a_plan_of_the_longest_length_builds():
    assert len(generate(a_form(start="", weeks=str(MAX_WEEKS)), TODAY).plan["weeks"]) == MAX_WEEKS


@pytest.mark.parametrize(
    ("form", "field"),
    [
        (a_form(start="", weeks=str(MAX_WEEKS + 1)), "weeks"),
        (a_form(start="1900-01-01"), "start"),
        (a_form(start="", race=[MARATHON | {"date": "2099-10-10"}]), "start"),
    ],
)
def test_a_longer_plan_is_refused_before_it_is_built(form, field):
    with pytest.raises(
        SeasonError, match=rf"^{field}: the plan would be \d+ weeks long; this page makes plans of up to {MAX_WEEKS}"
    ):
        generate(form, TODAY)


def test_the_limit_is_the_pages_and_not_the_cores():
    """The command line never refuses a plan (D-001)."""
    long_plan = parse_season(season_data(a_form(start="", weeks=str(MAX_WEEKS + 20))))
    assert len(expand(long_plan, TODAY).weeks) == MAX_WEEKS + 20


# --- the level: chosen, or suggested when left open (D-054) -------------------------------


def test_a_chosen_level_is_kept():
    regular = a_form(load={"beginner": False, "easy_run_km": "3", "long_run_km": "3"})
    assert generate(regular, TODAY).beginner is False
    beginner = a_form(load={"beginner": True, "easy_run_km": "12", "long_run_km": "15"})
    assert generate(beginner, TODAY).beginner is True


@pytest.mark.parametrize(
    ("changes", "is_beginner"),
    [
        ({}, False),
        ({"paces": {"race_result": {"distance_km": "", "time": ""}}}, True),  # no race time
        ({"race": []}, True),  # just start running
        ({"load": {"easy_run_km": "3", "long_run_km": "8"}}, True),  # below a marathon's 10 km (C11)
        ({"load": {"easy_run_km": "3", "long_run_km": "10"}}, False),
    ],
)
def test_a_level_left_open_is_suggested_by_the_race_time_and_the_long_run(changes, is_beginner):
    generated = generate(a_form(**changes), TODAY)
    assert generated.beginner is is_beginner
    assert ("beginner = true" in generated.season_toml) is is_beginner


def test_a_level_left_open_still_reports_the_regular_forms_error():
    with pytest.raises(SeasonError, match=r"^load.easy_run_km: missing"):
        generate(a_form(load={"long_run_km": "15"}), TODAY)
