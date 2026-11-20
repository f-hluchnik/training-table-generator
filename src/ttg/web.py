"""The generator page's entry point (D-052): the form's values in, the sheet's data out.

The page runs this module in the browser under Pyodide, so it imports only the pure core, never
`render` (which needs the Typst compiler) or `cli`. The form sends the season file's tree with every
value as the text the visitor typed. This module turns the texts into typed values, hands the tree to
`parse_season`, which validates it exactly as it validates a season file, and writes the tree back as
the season file the visitor can download.
"""

import datetime as dt
import json
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from ttg.beginner import with_a_goal
from ttg.calendar import plan_calendar
from ttg.expand import expand
from ttg.export import export
from ttg.model import Season, SeasonError, WarningCode
from ttg.spec import parse_season

# Reads one typed value from the text of a form field; the second argument is the field's path, for errors.
Converter = Callable[[str, str], Any]

# The longest plan the page makes, two years (D-053). Our own default, not a training rule. The command
# line has no limit (D-001), but the work grows faster than the plan: a plan of 6,700 weeks took half
# a minute, and a mistyped year would freeze the visitor's browser.
MAX_WEEKS = 104

_TOML_DEL = "\x7f"  # a control character that TOML requires escaped and `json.dumps` leaves as it is


@dataclass(frozen=True)
class Generated:
    plan: dict[str, Any]
    season_toml: str
    beginner: bool  # the level the plan was built for, chosen or suggested (D-054)


def generate(form: Mapping[str, Any], today: dt.date) -> Generated:
    """Build the plan for a filled-in form. Raises `SeasonError` for an invalid form."""
    form = _with_level(form, today)
    data = season_data(form)
    season = parse_season(data)
    if season.load.beginner:
        season = with_a_goal(season, today)
    _check_length(season, today)
    return Generated(plan=export(expand(season, today)), season_toml=season_toml(data), beginner=season.load.beginner)


def _with_level(form: Mapping[str, Any], today: dt.date) -> Mapping[str, Any]:
    """The form with its level: the visitor's choice, or the beginner's when the visitor left it open
    and gave no race, no race time, or a first long run below where plans for the race start (C11, D-054)."""
    load = form.get("load", {})
    if load.get("beginner") in (True, False):
        return form
    return {**form, "load": {**load, "beginner": _suggests_beginner(form, today)}}


def _suggests_beginner(form: Mapping[str, Any], today: dt.date) -> bool:
    result = form.get("paces", {}).get("race_result", {})
    if not form.get("race") or not any(_field(result, key) for key in ("distance_km", "time")):
        return True
    standard = {**form, "load": {**form.get("load", {}), "beginner": False}}
    try:
        season = parse_season(season_data(standard))
        _check_length(season, today)
    except SeasonError:
        return False  # the standard form's own error is the one to show
    warnings = expand(season, today).warnings
    return any(warning.code is WarningCode.BELOW_STARTING_LEVEL for warning in warnings)


def _check_length(season: Season, today: dt.date) -> None:
    """Refuse a plan longer than the page makes; the calendar is cheap, the plan is not."""
    weeks = plan_calendar(season, today).weeks
    if weeks > MAX_WEEKS:
        field = "weeks" if season.weeks is not None else "start"
        raise SeasonError(
            f"{field}: the plan would be {weeks} weeks long; this page makes plans of up to {MAX_WEEKS} weeks"
            " (the command-line tool has no limit)"
        )


def generate_json(form_json: str, today: str) -> str:
    """`generate` for the page: a JSON form and an ISO date in, `{"plan", "season_toml", "beginner"}` or
    `{"error"}` out."""
    try:
        generated = generate(json.loads(form_json), dt.date.fromisoformat(today))
    except SeasonError as error:
        return json.dumps({"error": str(error)})
    return json.dumps({"plan": generated.plan, "season_toml": generated.season_toml, "beginner": generated.beginner})


# --- form → season file ------------------------------------------------------


def season_data(form: Mapping[str, Any]) -> dict[str, Any]:
    """The season file's tree, as `tomllib` would read it, from the form's texts.

    A blank field is a missing field. Nothing is validated here beyond the form's own shape and the
    type of each value; ranges, required fields and unknown combinations are `parse_season`'s job.
    """
    data = _convert(form, "", {"start": _date, "weeks": _integer})
    sheet = _sheet(form.get("sheet", {}))
    if sheet:
        data["sheet"] = sheet
    data["race"] = [_race(race, number) for number, race in enumerate(form.get("race", []), start=1)]
    load = _load(form.get("load", {}))
    # `paces` and `load` are present, so a missing field is reported by name, e.g. `load.easy_run_km`.
    # A beginner needs no race result, and then has no `[paces]` (D-054).
    paces = _paces(form.get("paces", {}), beginner=load.get("beginner", False))
    if paces:
        data["paces"] = paces
    data["load"] = load
    overrides = _overrides(form.get("overrides", []))
    if overrides:
        data["overrides"] = overrides
    return data


def _sheet(form: Mapping[str, Any]) -> dict[str, Any]:
    sheet = _convert(form, "sheet", {"title": _text})
    rules = [line.strip() for line in _field(form, "rules").splitlines() if line.strip()]
    if rules:
        sheet["rules"] = rules
    return sheet


def _race(form: Mapping[str, Any], number: int) -> dict[str, Any]:
    race = _convert(
        form,
        f"race[{number}]",
        {
            "name": _text,
            "date": _date,
            "end": _date,
            "distance_km": _number,
            "priority": _text,
            "taper_weeks": _integer,
            "specific_weeks": _integer,
            "recovery_weeks": _integer,
        },
    )
    for flag in ("hilly", "goal"):
        if form.get(flag) is True:
            race[flag] = True
    return race


def _load(form: Mapping[str, Any]) -> dict[str, Any]:
    load = _convert(form, "load", {"easy_run_km": _integer, "long_run_km": _integer, "runs_per_week": _integer})
    if form.get("beginner") is True:
        load = {"beginner": True, **load}
    return load


def _paces(form: Mapping[str, Any], beginner: bool) -> dict[str, Any]:
    paces = _convert(form, "paces", {"easy": _text, "mp": _text, "threshold": _text, "interval": _text})
    result = _convert(form.get("race_result", {}), "paces.race_result", {"distance_km": _number, "time": _text})
    if beginner and not result:
        return paces
    return {"race_result": result, **paces}


def _overrides(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    """The `[overrides]` table, keyed by week number; a row with nothing in it is skipped."""
    overrides: dict[str, Any] = {}
    for number, row in enumerate(rows, start=1):
        if not _has_content(row):
            continue
        week = _integer(_required(row, "week", f"overrides[{number}]"), f"overrides[{number}].week")
        path = f"overrides.{week}"
        if str(week) in overrides:
            raise SeasonError(f"{path}: week {week} is overridden twice")
        override = _convert(row, path, {"easy": _text, "long_run_km": _integer, "note": _text})
        quality = _convert(
            row.get("quality", {}),
            f"{path}.quality",
            {"type": _text, "reps": _integer, "minutes": _number, "km": _number},
        )
        if quality:
            override["quality"] = quality
        overrides[str(week)] = override
    return overrides


def _has_content(row: Mapping[str, Any]) -> bool:
    return any(
        _has_content(value) if isinstance(value, Mapping) else bool(str(value).strip()) for value in row.values()
    )


# --- the texts of the form ---------------------------------------------------


def _convert(form: Mapping[str, Any], path: str, converters: Mapping[str, Converter]) -> dict[str, Any]:
    """The fields of one table that are not blank, each read by its converter."""
    converted: dict[str, Any] = {}
    for key, convert in converters.items():
        text = _field(form, key)
        if text:
            converted[key] = convert(text, f"{path}.{key}" if path else key)
    return converted


def _field(form: Mapping[str, Any], key: str) -> str:
    value = form.get(key, "")
    return value.strip() if isinstance(value, str) else ""


def _required(form: Mapping[str, Any], key: str, path: str) -> str:
    text = _field(form, key)
    if not text:
        raise SeasonError(f"{path}.{key}: missing (required)")
    return text


def _text(text: str, path: str) -> str:
    return text


def _integer(text: str, path: str) -> int:
    try:
        return int(text)
    except ValueError:
        raise SeasonError(f'{path}: expected a whole number, got "{text}"') from None


def _number(text: str, path: str) -> int | float:
    """A number; the decimal comma of a Czech keyboard is accepted. A whole number stays an integer."""
    try:
        value = float(text.replace(",", "."))
    except ValueError:
        raise SeasonError(f'{path}: expected a number, got "{text}"') from None
    if not math.isfinite(value):
        raise SeasonError(f'{path}: expected a number, got "{text}"')
    return int(value) if value.is_integer() else value


def _date(text: str, path: str) -> dt.date:
    try:
        return dt.date.fromisoformat(text)
    except ValueError:
        raise SeasonError(f'{path}: expected a date like 2026-05-04, got "{text}"') from None


# --- season file → text ------------------------------------------------------


def season_toml(data: Mapping[str, Any]) -> str:
    """The season file for a tree: top-level values, then each table and each array of tables."""
    blocks = ["\n".join(f"{key} = {_value(value)}" for key, value in data.items() if _is_plain(value))]
    for key, value in data.items():
        if isinstance(value, Mapping):
            blocks.append(f"[{key}]\n" + _lines(value))
        elif isinstance(value, list) and all(isinstance(item, Mapping) for item in value):
            blocks.extend(f"[[{key}]]\n" + _lines(item) for item in value)
    return "\n\n".join(block for block in blocks if block) + "\n"


def _is_plain(value: Any) -> bool:
    """A value that is written as `key = value` at the top: not a table, not an array of tables."""
    return not isinstance(value, Mapping) and not (
        isinstance(value, list) and value and all(isinstance(item, Mapping) for item in value)
    )


def _lines(table: Mapping[str, Any]) -> str:
    return "\n".join(f"{key} = {_value(value)}" for key, value in table.items())


def _value(value: Any) -> str:
    """A TOML value: a date, a number, a boolean, a text, a list, or an inline table."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, int | float):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False).replace(_TOML_DEL, "\\u007f")
    if isinstance(value, Mapping):
        return "{ " + ", ".join(f"{key} = {_value(item)}" for key, item in value.items()) + " }"
    return "[" + ", ".join(_value(item) for item in value) + "]"
