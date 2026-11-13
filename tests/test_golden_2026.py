"""Golden test (D-020, T-06): seasons/2026.toml reproduces the reference table week for week,
except for the differences listed here, each with its reason.

The season uses only general features; no override was added just to copy the reference
(owner, S5). Every remaining difference is a rule of the new defaults or of the notation.
"""

import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import pytest

from ttg.expand import expand
from ttg.export import export
from ttg.spec import load_season

from support import TODAY

SEASON = Path(__file__).parents[1] / "seasons" / "2026.toml"
COLUMNS = ("phase", "easy", "quality", "long", "note")

# docs/reference/2026-marathon-training.pdf, page 1, transcribed in D-018 notation: the sheet's
# "R" is "–" (no session) or "RACE" (weeks 17 and 23, long run).
REFERENCE: Mapping[int, tuple[str, str, str, str, str]] = {
    1: ("base", "12+6", "H: 6x1'", "15 km", "38"),
    2: ("base", "12+6", "I: 5x3'", "18 km", "42"),
    3: ("base", "12+6", "T: 3x8'", "20 km", "46"),
    4: ("base", "12+6", "–", "12 km", "30"),
    5: ("strength", "12+12", "H: 7x1'", "22 km", "52"),
    6: ("strength", "12+12", "I: 6x3'", "24 km", "56"),
    7: ("strength", "12+12", "T: 3x10'", "26 km", "60"),
    8: ("strength", "12+6", "–", "15 km", "33"),
    9: ("volume", "12+12", "H: 8x1'", "28 km", "62"),
    10: ("volume", "12+12", "I: 5x4'", "30 km", "64"),
    11: ("volume", "12+12", "T: 4x8'", "32 km", "66"),
    12: ("volume", "12+6", "–", "15 km", "33"),
    13: ("volume", "12+12", "H: 10x1'", "35 km", "68"),
    14: ("volume", "12+12", "I: 6x4'", "40 km", "70"),
    15: ("ultra", "12+12", "T: 4x10'", "20 km", "taper"),
    16: ("ultra", "12+6", "–", "12 km", "taper"),
    17: ("ultra", "12+6", "–", "RACE", "race"),
    18: ("pivot", "12+6", "–", "–", "recovery"),
    19: ("pivot", "12+6", "–", "12 km", "flush"),
    20: ("pivot", "12+12", "MP 3x3 km", "20 km w MP", "check"),
    21: ("pivot", "12+12", "MP 4x3 km", "28 km w MP", "peak"),
    22: ("race", "12+6", "T: 6x1 km", "18 km w MP", "taper"),
    23: ("race", "12+6", "–", "RACE", "race"),
}


@dataclass(frozen=True)
class Difference:
    column: str
    generated: Mapping[int, str]  # week → what the compiler prints instead
    reason: str


# fmt: off
DIFFERENCES = (
    Difference(
        "phase",
        {
            **dict.fromkeys(range(1, 9), "build"),
            **dict.fromkeys(range(9, 15), "ultra"),
            **dict.fromkeys(range(15, 18), "taper"),
            **dict.fromkeys(range(18, 20), "recovery"),
            **dict.fromkeys(range(20, 22), "marathon"),
            **dict.fromkeys(range(22, 24), "taper"),
        },
        "Labels are derived from the phases (D-026); the blocks themselves match the reference.",
    ),
    Difference(
        "note",
        {1: "39", 2: "44", 3: "47", 4: "38", 5: "51", 6: "57",
         8: "43", 9: "57", 10: "63", 11: "67", 12: "47", 13: "64", 14: "75"},
        "Planned km are the sum of the sessions (D-006); the reference subtracted hand corrections "
        "(D-020). The quality-km estimate also differs from the owner's (TRAINING_MODEL.md §3).",
    ),
    Difference(
        "long",
        {2: "17 km", 3: "19 km", 5: "21 km", 6: "23 km", 7: "25 km", 9: "27 km", 10: "29 km",
         11: "31 km", 13: "33 km"},
        "The long run grows +2 km a loading week (D-030); 2026 grew +2–3 km.",
    ),
    Difference(
        "long",
        {4: "14 km", 8: "19 km", 12: "23 km"},
        "Deload long run: 75 % of the last loading week (TRAINING_MODEL.md §4); 2026 cut deeper.",
    ),
    Difference(
        "quality",
        {4: "S", 8: "S", 12: "S"},
        "Deloads keep strides instead of intensity (TRAINING_MODEL.md §4); 2026 had no quality run.",
    ),
    Difference(
        "easy",
        {15: "12+6"},
        "Taper weeks use the reduced easy pair (D-022); 2026 kept 12+12 in its first taper week.",
    ),
    Difference(
        "quality",
        {15: "T: 6×1 km", 16: "T: 6×1 km"},
        "Taper weeks before the race week get short T work (D-030); 2026 continued the rotation, "
        "then rested.",
    ),
    Difference(
        "long",
        {15: "26 km", 16: "21 km"},
        "Taper long runs: 75 %, then 60 % of the peak since the last race (D-030). The peak is "
        "the computed 35 km: the 40 km of week 14 is an override and changes only its own week.",
    ),
    Difference(
        "quality",
        {17: "S", 23: "S"},
        "Race weeks keep strides before the race (D-033); 2026 had no quality run.",
    ),
    Difference(
        "quality",
        {20: "MP: 3×3 km", 21: "MP: 4×3 km"},
        "Notation: a colon after the type, as for every other session (D-018).",
    ),
    Difference(
        "long",
        {20: "24 km (6 MP)", 21: "26 km"},
        "After a race the long run restarts at 75 % of the previous peak, at most the next race's "
        "build cap (24 km for a marathon), then +2 km (D-030). MP km in every other marathon long "
        "run (D-033), printed per D-018.",
    ),
    Difference(
        "long",
        {17: "RACE 101 km", 23: "RACE 42 km"},
        "A race prints its distance; the footer lists the races by name (owner, S5).",
    ),
    Difference(
        "long",
        {22: "16 km"},
        "The last taper long run is 60 % of the peak (26 km) and has no MP km (D-030).",
    ),
)
# fmt: on


def typeset(reference_text: str) -> str:
    """The reference's `6x1'` in the sheet's typography, `6×1′` (D-048): a notation, not a difference."""
    return re.sub(r"(\d)x(\d)", r"\1×\2", reference_text).replace("'", "′")


def expected() -> dict[int, dict[str, str]]:
    rows = {week: dict(zip(COLUMNS, map(typeset, row), strict=True)) for week, row in REFERENCE.items()}
    for difference in DIFFERENCES:
        for week, text in difference.generated.items():
            rows[week][difference.column] = text
    return rows


@pytest.fixture(scope="module")
def generated() -> dict[int, dict[str, str]]:
    plan = expand(load_season(SEASON), TODAY)
    weeks = export(plan)["weeks"]
    return {
        week["number"]: {
            "phase": week["phase_label"],
            "easy": week["easy"]["text"],
            "quality": week["quality"]["text"],
            "long": week["long"]["text"],
            "note": week["note"],
        }
        for week in weeks
    }


def test_2026_reproduces_the_reference_except_the_listed_differences(generated):
    assert generated == expected()


def test_every_listed_difference_is_a_real_difference():
    for difference in DIFFERENCES:
        column = COLUMNS.index(difference.column)
        for week, text in difference.generated.items():
            assert REFERENCE[week][column] != text, (week, difference.column)


def test_no_cell_is_listed_twice():
    cells = Counter((week, d.column) for d in DIFFERENCES for week in d.generated)
    assert [cell for cell, count in cells.items() if count > 1] == []
