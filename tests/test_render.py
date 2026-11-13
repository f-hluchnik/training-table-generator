"""The Typst template renders every sample plan to a PDF.

What the sheet looks like is checked by eye against docs/reference (CLAUDE.md §4); these tests
only guard that the template accepts the plan.json contract and does not crash.
"""

import copy
import json
import re
from datetime import date, timedelta
from pathlib import Path

import pytest
import typst

from ttg.expand import expand
from ttg.export import export
from ttg.model import Load, Paces, Race, RaceResult, Season
from ttg.render import TEMPLATE, render_pdf

TODAY = date(2026, 11, 13)

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLES = [
    FIXTURES / "sample-plan-2026-weeks-1-4.json",
    FIXTURES / "plan-2026.json",
    FIXTURES / "plan-test-2027.json",
]
FOUR_EASY_RUNS = {"km": [12, 12, 12, 12], "text": "12+12+12+12"}  # D-016: 6 runs a week


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda path: path.stem)
def test_sample_plan_renders_to_a_pdf(sample):
    assert render_pdf(_load(sample)).startswith(b"%PDF-")


def test_plan_with_four_easy_runs_renders():
    plan = _load(SAMPLES[1])
    for week in plan["weeks"]:
        week["easy"] = FOUR_EASY_RUNS
    assert render_pdf(plan).startswith(b"%PDF-")


def test_plan_without_pace_details_renders():
    plan = copy.deepcopy(_load(SAMPLES[0]))
    plan["paces"] = [{"code": "ER", "pace": "", "label": ""}]
    assert render_pdf(plan).startswith(b"%PDF-")


def test_a_plan_missing_a_field_is_rejected():
    plan = _load(SAMPLES[0])
    del plan["footer"]
    with pytest.raises(typst.TypstError):
        render_pdf(plan)


def test_template_exists():
    assert TEMPLATE.is_file()


def _page_count(pdf: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page(?![s\w])", pdf))


def _plan_of_weeks(count: int) -> dict:
    """The full 2026 sample stretched to `count` weeks (repeated rows suffice for the layout)."""
    plan = _load(SAMPLES[1])
    plan["weeks"] = (plan["weeks"] * (count // len(plan["weeks"]) + 1))[:count]
    return plan


def test_a_40_week_plan_fits_one_page():
    assert _page_count(render_pdf(_plan_of_weeks(40))) == 1


def test_a_longer_plan_continues_on_a_second_page_at_the_minimum_row_height():
    assert _page_count(render_pdf(_plan_of_weeks(52))) == 2


def test_a_month_or_phase_band_longer_than_a_page_breaks_across_pages():
    """A generated 60-week plan has a build band of about 50 weeks. Unbreakable bands pushed the
    whole table to page 2, left page 1 with only the title and cut off the last weeks."""
    marathon = Race("Marathon", date(2027, 10, 10), 42.195)
    season = Season(
        races=(marathon,),
        paces=Paces(RaceResult(42.195, timedelta(hours=3, minutes=30, seconds=2))),
        load=Load(easy_run_km=12, long_run_km=15),
        weeks=60,
    )
    plan = expand(season, TODAY)
    assert _page_count(render_pdf(export(plan, ()))) == 2
