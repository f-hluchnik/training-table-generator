"""Read and validate season.toml (schema: docs/PLAN.md §4, D-025).

Invalid input is an error and nothing is built (PLAN §3); every message names
the offending field, e.g. `race[2].date: ...`. Questionable but valid input is
left to the checks, which only warn (D-001).
"""

import re
import tomllib
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, NoReturn, TypeVar

from ttg.model import (
    DEFAULT_RULES,
    DEFAULT_RUNS_PER_WEEK,
    DEFAULT_TITLE,
    MAX_RUNS_PER_WEEK,
    MIN_RUNS_PER_WEEK,
    EasyRuns,
    Load,
    Paces,
    Priority,
    Race,
    RaceResult,
    Season,
    SeasonError,
    Session,
    SessionType,
    Sheet,
    WeekOverride,
)
from ttg.paces import Pace

_TOML_LINE_PATTERN = re.compile(r"at line (\d+)")
_DURATION_PATTERN = re.compile(r"(?:(\d+):([0-5]\d)|(\d+)):([0-5]\d)")

_Choice = TypeVar("_Choice", bound=StrEnum)

# Fields of `Race` that override a phase length (D-009), and of `Session` that
# describe its repetitions.
_PHASE_LENGTH_FIELDS = ("taper_weeks", "specific_weeks", "recovery_weeks")
_REPETITION_FIELDS = ("reps", "minutes", "km")


def load_season(path: Path) -> Season:
    """Read and validate a season file."""
    text = path.read_text(encoding="utf-8")
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise SeasonError(f"{path}: {_describe_toml_error(text, error)}") from None
    try:
        return parse_season(data)
    except SeasonError as error:
        raise SeasonError(f"{path}: {error}") from None


def parse_season(data: dict[str, Any]) -> Season:
    """Validate parsed TOML and build the `Season`."""
    root = _Table(data, "")
    start = root.date("start")
    weeks = root.integer("weeks", minimum=1)
    if start is not None and weeks is not None:
        _fail("weeks", "give either start or weeks, not both")
    races = _parse_races(root.tables("race", required=True))
    season = Season(
        races=races,
        paces=_parse_paces(root.table("paces", required=True)),
        load=_parse_load(root.table("load", required=True)),
        start=start,
        weeks=weeks,
        sheet=_parse_sheet(root.table("sheet")),
        overrides=_parse_overrides(root.table("overrides")),
    )
    root.close()
    _check_races_not_before_start(races, start)
    return season


# --- sections ----------------------------------------------------------------


def _parse_races(tables: list["_Table"]) -> tuple[Race, ...]:
    if not tables:
        _fail("race", "at least one [[race]] is required")
    races = [_parse_race(table) for table in tables]
    _check_unique_names(races, tables)
    return tuple(sorted(races, key=lambda race: race.date))


def _parse_race(table: "_Table") -> Race:
    race_date = table.date("date", required=True)
    end = table.date("end")
    if end is not None and end < race_date:
        _fail(table.path_of("end"), f"{end} is before the race date {race_date}")
    race = Race(
        name=table.text("name", required=True),
        date=race_date,
        end=end,
        distance_km=table.positive_number("distance_km", required=True),
        priority=table.choice("priority", Priority, default=Priority.A),
        taper_weeks=table.integer("taper_weeks", minimum=1),
        specific_weeks=table.integer("specific_weeks", minimum=0),
        recovery_weeks=table.integer("recovery_weeks", minimum=0),
    )
    table.close()
    _check_phase_lengths_allowed(race, table)
    return race


def _check_phase_lengths_allowed(race: Race, table: "_Table") -> None:
    """C races get no taper, specific or recovery block (D-017)."""
    if race.is_key:
        return
    for key in _PHASE_LENGTH_FIELDS:
        if getattr(race, key) is not None:
            _fail(table.path_of(key), "a C race has no taper, specific or recovery block (D-017)")


def _check_unique_names(races: list[Race], tables: list["_Table"]) -> None:
    seen: set[str] = set()
    for race, table in zip(races, tables, strict=True):
        if race.name in seen:
            _fail(table.path_of("name"), f'"{race.name}" is used by another race')
        seen.add(race.name)


def _check_races_not_before_start(races: Iterable[Race], start: date | None) -> None:
    if start is None:
        return
    for race in races:
        if race.last_day < start:
            _fail("start", f'{start} is after the race "{race.name}" on {race.last_day}')


def _parse_paces(table: "_Table") -> Paces:
    paces = Paces(
        race_result=_parse_race_result(table.table("race_result", required=True)),
        easy=table.pace("easy"),
        mp=table.pace("mp"),
        threshold=table.pace("threshold"),
        interval=table.pace("interval"),
    )
    table.close()
    return paces


def _parse_race_result(table: "_Table") -> RaceResult:
    result = RaceResult(
        distance_km=table.positive_number("distance_km", required=True),
        time=table.duration("time", required=True),
    )
    table.close()
    return result


def _parse_load(table: "_Table") -> Load:
    load = Load(
        easy_run_km=table.integer("easy_run_km", required=True, minimum=1),
        long_run_km=table.integer("long_run_km", required=True, minimum=1),
        runs_per_week=table.integer(
            "runs_per_week", default=DEFAULT_RUNS_PER_WEEK, minimum=MIN_RUNS_PER_WEEK, maximum=MAX_RUNS_PER_WEEK
        ),
    )
    table.close()
    return load


def _parse_sheet(table: "_Table | None") -> Sheet:
    if table is None:
        return Sheet()
    sheet = Sheet(
        title=table.text("title", default=DEFAULT_TITLE),
        rules=table.texts("rules", default=DEFAULT_RULES),
    )
    table.close()
    return sheet


def _parse_overrides(table: "_Table | None") -> tuple[WeekOverride, ...]:
    if table is None:
        return ()
    overrides = [_parse_override(key, table) for key in table.keys()]
    return tuple(sorted(overrides, key=lambda override: override.week))


def _parse_override(key: str, parent: "_Table") -> WeekOverride:
    if not key.isdigit() or int(key) < 1:
        _fail(parent.path_of(key), "expected a week number (1, 2, ...)")
    table = parent.table(key, required=True)
    quality_table = table.table("quality")
    override = WeekOverride(
        week=int(key),
        easy=table.choice("easy", EasyRuns),
        quality=None if quality_table is None else _parse_session(quality_table),
        long_run_km=table.integer("long_run_km", minimum=0),
        note=table.text("note"),
    )
    table.close()
    return override


def _parse_session(table: "_Table") -> Session:
    session = Session(
        type=table.choice("type", SessionType, required=True),
        reps=table.integer("reps", minimum=1),
        minutes=table.positive_number("minutes"),
        km=table.positive_number("km"),
    )
    table.close()
    if session.type.has_repetitions:
        _check_repeated_session(session, table)
    else:
        _check_session_without_repetitions(session, table)
    return session


def _check_repeated_session(session: Session, table: "_Table") -> None:
    if session.reps is None:
        _fail(table.path_of("reps"), f"missing (required for type {session.type})")
    if (session.minutes is None) == (session.km is None):
        _fail(table.path, f"give exactly one of minutes or km for type {session.type}")


def _check_session_without_repetitions(session: Session, table: "_Table") -> None:
    for key in _REPETITION_FIELDS:
        if getattr(session, key) is not None:
            _fail(table.path_of(key), f'type "{session.type}" takes no {key}')


# --- field reading -----------------------------------------------------------


class _Table:
    """One TOML table: typed access to its fields, and a check for unknown ones."""

    def __init__(self, data: dict[str, Any], path: str) -> None:
        self._data = data
        self._read: set[str] = set()
        self.path = path

    def path_of(self, key: str) -> str:
        return f"{self.path}.{key}" if self.path else key

    def keys(self) -> list[str]:
        return list(self._data)

    def close(self) -> None:
        """Fail on a field that no reader asked for."""
        for key in self._data:
            if key not in self._read:
                _fail(self.path_of(key), "unknown field")

    def text(self, key: str, *, required: bool = False, default: str | None = None) -> str | None:
        value = self._value(key, required)
        if value is None:
            return default
        if not isinstance(value, str) or not value.strip():
            self._wrong_type(key, "non-empty text in quotes", value)
        return value.strip()

    def texts(self, key: str, *, default: tuple[str, ...] | None = None) -> tuple[str, ...] | None:
        value = self._value(key, required=False)
        if value is None:
            return default
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            self._wrong_type(key, 'a list of texts, e.g. ["…", "…"]', value)
        return tuple(value)

    def integer(
        self,
        key: str,
        *,
        required: bool = False,
        default: int | None = None,
        minimum: int | None = None,
        maximum: int | None = None,
    ) -> int | None:
        value = self._value(key, required)
        if value is None:
            return default
        if not _is_integer(value):
            self._wrong_type(key, "a whole number", value)
        if minimum is not None and value < minimum:
            _fail(self.path_of(key), f"must be at least {minimum}, got {value}")
        if maximum is not None and value > maximum:
            _fail(self.path_of(key), f"must be at most {maximum}, got {value}")
        return value

    def positive_number(self, key: str, *, required: bool = False) -> float | None:
        """A number greater than 0; whole numbers are accepted too."""
        value = self._value(key, required)
        if value is None:
            return None
        if not (_is_integer(value) or isinstance(value, float)):
            self._wrong_type(key, "a number", value)
        if value <= 0:
            _fail(self.path_of(key), f"must be greater than 0, got {value}")
        return float(value)

    def date(self, key: str, *, required: bool = False) -> date | None:
        value = self._value(key, required)
        if value is None:
            return None
        if not isinstance(value, date) or isinstance(value, datetime):
            self._wrong_type(key, "a date like 2026-05-04 (without quotes)", value)
        return value

    def pace(self, key: str) -> Pace | None:
        text = self.text(key)
        if text is None:
            return None
        try:
            return Pace.parse(text)
        except ValueError as error:
            _fail(self.path_of(key), str(error))

    def duration(self, key: str, *, required: bool = False) -> timedelta | None:
        text = self.text(key, required=required)
        if text is None:
            return None
        try:
            return _parse_duration(text)
        except ValueError as error:
            _fail(self.path_of(key), str(error))

    def choice(
        self, key: str, choices: type[_Choice], *, required: bool = False, default: _Choice | None = None
    ) -> _Choice | None:
        text = self.text(key, required=required)
        if text is None:
            return default
        try:
            return choices(text)
        except ValueError:
            allowed = ", ".join(f'"{choice}"' for choice in choices)
            _fail(self.path_of(key), f'expected one of {allowed}, got "{text}"')

    def table(self, key: str, *, required: bool = False) -> "_Table | None":
        value = self._value(key, required)
        if value is None:
            return None
        if not isinstance(value, dict):
            self._wrong_type(key, "a table", value)
        return _Table(value, self.path_of(key))

    def tables(self, key: str, *, required: bool = False) -> list["_Table"]:
        """An array of tables, e.g. [[race]]; paths are numbered from 1."""
        value = self._value(key, required)
        if value is None:
            return []
        if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
            self._wrong_type(key, f"[[{key}]] tables", value)
        return [_Table(item, f"{self.path_of(key)}[{number}]") for number, item in enumerate(value, start=1)]

    def _value(self, key: str, required: bool) -> Any:
        self._read.add(key)
        if key not in self._data:
            if required:
                _fail(self.path_of(key), "missing (required)")
            return None
        return self._data[key]

    def _wrong_type(self, key: str, expected: str, value: Any) -> NoReturn:
        shown = f'"{value}"' if isinstance(value, str) else str(value)
        _fail(self.path_of(key), f"expected {expected}, got {shown}")


def _is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _parse_duration(text: str) -> timedelta:
    """Parse "h:mm:ss" or "m:ss", e.g. "3:30:02" or "42:15"."""
    match = _DURATION_PATTERN.fullmatch(text)
    if match is None:
        raise ValueError(f'expected a time like "3:30:02" or "42:15", got "{text}"')
    hours, minutes_after_hours, minutes_only, seconds = match.groups()
    duration = timedelta(
        hours=int(hours or 0),
        minutes=int(minutes_after_hours or minutes_only),
        seconds=int(seconds),
    )
    if not duration:
        raise ValueError("a time must be greater than 0:00")
    return duration


def _describe_toml_error(text: str, error: tomllib.TOMLDecodeError) -> str:
    """tomllib reports only a position; quote the line, which names the field."""
    match = _TOML_LINE_PATTERN.search(str(error))
    if match is None:
        return f"invalid TOML: {error}"
    line_number = int(match.group(1))
    lines = text.splitlines()
    line = lines[line_number - 1].strip() if line_number <= len(lines) else ""
    return f'line {line_number} "{line}": invalid TOML: {error}'


def _fail(path: str, message: str) -> NoReturn:
    raise SeasonError(f"{path}: {message}")
