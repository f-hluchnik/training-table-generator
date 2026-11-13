"""The Typst template renders every sample plan to a PDF.

What the sheet looks like is checked by eye against docs/reference (CLAUDE.md §4); these tests
only guard that the template accepts the plan.json contract and does not crash.
"""

import copy
import json
from pathlib import Path

import pytest
import typst

from ttg.render import TEMPLATE, render_file, render_pdf

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLES = [FIXTURES / "sample-plan-2026-weeks-1-4.json", FIXTURES / "sample-plan-2026-full.json"]
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


def test_render_file_writes_the_pdf(tmp_path):
    pdf_path = tmp_path / "plan.pdf"
    render_file(SAMPLES[0], pdf_path)
    assert pdf_path.read_bytes().startswith(b"%PDF-")


def test_template_exists():
    assert TEMPLATE.is_file()
