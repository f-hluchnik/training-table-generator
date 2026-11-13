import copy
import tomllib
from datetime import date, timedelta

import pytest

from ttg.model import (
    DEFAULT_RULES,
    DEFAULT_RUNS_PER_WEEK,
    DEFAULT_TITLE,
    EasyRuns,
    Priority,
    Session,
    SessionType,
)
from ttg.paces import Pace
from ttg.spec import SeasonError, load_season, parse_season

from support import SEASONS

MINIMAL = tomllib.loads(
    """
    [[race]]
    name = "Marathon"
    date = 2027-10-10
    distance_km = 42.195

    [paces]
    race_result = { distance_km = 42.195, time = "3:30:02" }

    [load]
    easy_run_km = 12
    long_run_km = 15
    """
)


def season_with(**sections):
    """The minimal season with top-level keys or whole sections replaced."""
    data = copy.deepcopy(MINIMAL)
    data.update(copy.deepcopy(sections))
    return data


def race(**fields):
    return {"name": "Marathon", "date": date(2027, 10, 10), "distance_km": 42.195, **fields}


def load(**fields):
    return {"easy_run_km": 12, "long_run_km": 15, **fields}


def assert_error(data, field, fragment=""):
    with pytest.raises(SeasonError) as error:
        parse_season(data)
    message = str(error.value)
    assert message.startswith(f"{field}: "), message
    assert fragment in message


# --- the reference seasons ---------------------------------------------------


def test_2026_season_loads():
    season = load_season(SEASONS / "2026.toml")
    ultra, marathon = season.races
    assert season.start == date(2026, 5, 4)
    assert (ultra.name, ultra.priority, ultra.end) == ("Beskydská sedmička", Priority.B, date(2026, 8, 29))
    assert (ultra.taper_weeks, ultra.recovery_weeks) == (3, 2)
    assert (marathon.name, marathon.priority, marathon.distance_km) == ("Běhej Lesy Lednice", Priority.A, 42.195)
    assert season.paces.threshold == Pace.parse("4:30")
    assert season.overrides[3].quality == Session(SessionType.HILLS, reps=10, minutes=1)


def test_test_2027_season_loads():
    season = load_season(SEASONS / "test-2027.toml")
    assert [race.priority for race in season.races] == [Priority.C, Priority.C, Priority.A]


# --- defaults ------------------------------------------------------------------


def test_minimal_season_gets_defaults():
    season = parse_season(MINIMAL)
    assert season.start is None and season.weeks is None
    assert season.races[0].priority is Priority.A
    assert season.races[0].last_day == date(2027, 10, 10)
    assert season.load.runs_per_week == DEFAULT_RUNS_PER_WEEK
    assert (season.sheet.title, season.sheet.rules) == (DEFAULT_TITLE, DEFAULT_RULES)
    assert season.paces.easy is None
    assert season.paces.race_result.time == timedelta(hours=3, minutes=30, seconds=2)
    assert season.overrides == ()


def test_races_and_overrides_are_sorted():
    data = season_with(
        race=[race(name="Late"), race(name="Early", date=date(2027, 4, 4), priority="C")],
        overrides={"10": {"note": "b"}, "2": {"note": "a"}},
    )
    season = parse_season(data)
    assert [race.name for race in season.races] == ["Early", "Late"]
    assert [override.week for override in season.overrides] == [2, 10]


def test_a_race_is_flat_unless_marked_hilly():
    races = parse_season(season_with(race=[race(), race(name="Trail", hilly=True)])).races
    assert [race.hilly for race in races] == [False, True]


def test_override_fields():
    data = season_with(
        overrides={
            "5": {"easy": "reduced", "long_run_km": 0, "note": "holiday"},
            "6": {"quality": {"type": "MP", "reps": 3, "km": 3}},
            "7": {"quality": {"type": "S"}},
        }
    )
    reduced, marathon_pace, strides = parse_season(data).overrides
    assert (reduced.easy, reduced.long_run_km, reduced.note) == (EasyRuns.REDUCED, 0, "holiday")
    assert marathon_pace.quality == Session(SessionType.MARATHON_PACE, reps=3, km=3)
    assert strides.quality == Session(SessionType.STRIDES)


def test_weeks_instead_of_start():
    assert parse_season(season_with(weeks=20)).weeks == 20


@pytest.mark.parametrize(("text", "expected"), [("3:30:02", (3, 30, 2)), ("42:15", (0, 42, 15)), ("75:00", (0, 75, 0))])
def test_race_result_time(text, expected):
    hours, minutes, seconds = expected
    paces = {"race_result": {"distance_km": 10, "time": text}}
    season = parse_season(season_with(paces=paces))
    assert season.paces.race_result.time == timedelta(hours=hours, minutes=minutes, seconds=seconds)


# --- errors name the field ---------------------------------------------------


def test_bad_date_in_file_names_the_line(tmp_path):
    path = tmp_path / "season.toml"
    path.write_text("start = 2026-02-30\n", encoding="utf-8")
    with pytest.raises(SeasonError, match=r'line 1 "start = 2026-02-30": invalid TOML'):
        load_season(path)


def test_file_errors_are_prefixed_with_the_path(tmp_path):
    path = tmp_path / "season.toml"
    path.write_text('start = "2026-05-04"\n', encoding="utf-8")
    with pytest.raises(SeasonError, match=rf"^{path}: start: expected a date"):
        load_season(path)


def test_a_file_that_is_not_utf_8_is_an_input_error(tmp_path):
    path = tmp_path / "season.toml"
    path.write_bytes("# Běhej Lesy\n".encode("cp1250"))
    with pytest.raises(SeasonError, match=rf"^{path}: not a UTF-8 text file"):
        load_season(path)


@pytest.mark.parametrize(
    ("data", "field", "fragment"),
    [
        (season_with(race=[race(distance_km=float("nan"))]), "race[1].distance_km", "expected a number"),
        (season_with(race=[race(distance_km=float("inf"))]), "race[1].distance_km", "expected a number"),
        (season_with(overrides={"²": {"note": "x"}}), "overrides.²", "week number"),
        (season_with(start="2027-01-04"), "start", "expected a date"),
        (season_with(start=date(2027, 10, 11)), "start", 'after the race "Marathon"'),
        (season_with(start=date(2027, 5, 3), weeks=20), "weeks", "not both"),
        (season_with(weeks=0), "weeks", "at least 1"),
        (season_with(title="x"), "title", "unknown field"),
        (season_with(race=[]), "race", "at least one"),
        (season_with(race={"name": "x"}), "race", "[[race]] tables"),
        (season_with(race=[race(), race()]), "race[2].name", "used by another race"),
        (season_with(race=[race(nmae="x")]), "race[1].nmae", "unknown field"),
        (season_with(race=[race(date="2027-10-10")]), "race[1].date", "expected a date"),
        (season_with(race=[race(end=date(2027, 10, 9))]), "race[1].end", "before the race date"),
        (season_with(race=[race(distance_km=0)]), "race[1].distance_km", "greater than 0"),
        (season_with(race=[race(priority="D")]), "race[1].priority", 'one of "A", "B", "C"'),
        (season_with(race=[race(priority="C", taper_weeks=1)]), "race[1].taper_weeks", "C race"),
        (season_with(race=[race(priority="C", hilly=True)]), "race[1].hilly", "C race"),
        (season_with(race=[race(hilly="yes")]), "race[1].hilly", "true or false"),
        (season_with(race=[race(taper_weeks=0)]), "race[1].taper_weeks", "at least 1"),
        (season_with(race=[race(recovery_weeks=-1)]), "race[1].recovery_weeks", "at least 0"),
        (season_with(paces={}), "paces.race_result", "missing"),
        (season_with(paces={"race_result": {"distance_km": 10, "time": "3h30"}}), "paces.race_result.time", "3:30:02"),
        (season_with(paces={"race_result": {"distance_km": 10, "time": "0:00"}}), "paces.race_result.time", "greater"),
        (
            season_with(paces={"race_result": {"distance_km": 10, "time": "40:00"}, "treshold": "4:30"}),
            "paces.treshold",
            "unknown field",
        ),
        (
            season_with(paces={"race_result": {"distance_km": 10, "time": "40:00"}, "mp": "4.58"}),
            "paces.mp",
            '"4:58"',
        ),
        (season_with(load={"long_run_km": 15}), "load.easy_run_km", "missing"),
        (season_with(load=load(easy_run_km=12.5)), "load.easy_run_km", "whole number"),
        (season_with(load=load(easy_run_km=True)), "load.easy_run_km", "whole number"),
        (season_with(load=load(runs_per_week=7)), "load.runs_per_week", "at most 6"),
        (season_with(load=load(runs_per_week=2)), "load.runs_per_week", "at least 3"),
        (season_with(sheet={"rules": "drop it"}), "sheet.rules", "list of texts"),
        (season_with(sheet={"phase_labels": ["base"]}), "sheet.phase_labels", "unknown field"),
        (season_with(overrides={"x": {}}), "overrides.x", "week number"),
        (season_with(overrides={"0": {}}), "overrides.0", "week number"),
        (season_with(overrides={"3": {"easy": "short"}}), "overrides.3.easy", '"regular", "reduced"'),
        (season_with(overrides={"3": {"label": "pivot"}}), "overrides.3.label", "unknown field"),
        (season_with(overrides={"3": {"quality": "H 10x1'"}}), "overrides.3.quality", "a table"),
        (season_with(overrides={"3": {"quality": {"type": "X"}}}), "overrides.3.quality.type", '"H"'),
        (season_with(overrides={"3": {"quality": {"type": "H", "minutes": 1}}}), "overrides.3.quality.reps", "missing"),
        (
            season_with(overrides={"3": {"quality": {"type": "T", "reps": 6, "minutes": 3, "km": 1}}}),
            "overrides.3.quality",
            "exactly one of minutes or km",
        ),
        (season_with(overrides={"3": {"quality": {"type": "I", "reps": 5}}}), "overrides.3.quality", "exactly one"),
        (season_with(overrides={"3": {"quality": {"type": "S", "reps": 6}}}), "overrides.3.quality.reps", "takes no"),
        (season_with(overrides={"3": {"long_run_km": -1}}), "overrides.3.long_run_km", "at least 0"),
    ],
)
def test_invalid_season(data, field, fragment):
    assert_error(data, field, fragment)
