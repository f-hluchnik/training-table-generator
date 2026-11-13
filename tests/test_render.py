"""The Typst template renders every sample plan to a PDF.

What the sheet looks like is checked by eye against docs/reference (CLAUDE.md §4); these tests
only guard that the template accepts the plan.json contract and does not crash.
"""

import copy
import json
import re
from datetime import date
from pathlib import Path

import pytest
import typst

from ttg.expand import expand
from ttg.export import export
from ttg.model import Priority, Race
from ttg.render import PLAN_INPUT, TEMPLATE, render_pdf

from support import FIXTURES, TODAY, season

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
    """Unbreakable bands pushed the whole table to page 2, left page 1 with only the title and cut
    off the last weeks."""
    assert _page_count(render_pdf(_sixty_week_plan())) == 2


def test_a_band_continued_on_the_next_page_is_labelled_on_both():
    """Weeks 1–47 fit page 1: the build band (weeks 1–50) and July (46–50) are cut at the break."""
    plan_text = json.dumps(_sixty_week_plan())
    labels = json.loads(typst.query(TEMPLATE, "<ttg-band>", field="value", sys_inputs={PLAN_INPUT: plan_text}))
    assert labels.count("build") == 2
    assert labels.count("jul") == 2
    assert labels.count("marathon") == 1


def _sixty_week_plan() -> dict:
    """A generated plan whose build band is about 50 weeks: longer than a page."""
    return export(expand(season(Race("Marathon", date(2027, 10, 10), 42.195), weeks=60), TODAY))


# --- band labels fit their bands (D-044) -------------------------------------------------------

READABLE_PT = 5  # the template's min-band-label-size


def _band_fits(plan: dict) -> list[dict]:
    plan_text = json.dumps(plan)
    return json.loads(typst.query(TEMPLATE, "<ttg-band-fit>", field="value", sys_inputs={PLAN_INPUT: plan_text}))


def _tight_plan() -> dict:
    """38 weeks (rows of 3.9 mm): a 10 km race gets a one-week taper and a one-week recovery."""
    ten_k = Race("Spring 10", date(2027, 4, 18), 10)
    marathon = Race("Autumn marathon", date(2027, 8, 29), 42.195, recovery_weeks=0)
    late = Race("Late 18", date(2027, 9, 26), 18, Priority.B)
    return export(expand(season(ten_k, marathon, late, start=date(2027, 1, 4)), TODAY))


def test_every_band_label_fits_inside_its_band():
    for fit in _band_fits(_tight_plan()):
        assert fit["along-mm"] <= fit["along-available-mm"] + 1e-6
        assert fit["across-mm"] <= fit["across-available-mm"] + 1e-6


def test_a_one_week_band_shows_its_short_form_horizontally_at_a_readable_size():
    """D-048: in the mono, `rec.` rotated in a one-week band would be about 3 pt; across, 5.6 pt."""
    fits = {fit["label"]: fit for fit in _band_fits(_tight_plan())}
    assert "recovery" not in fits
    for short in ("rec.", "tap."):
        assert fits[short]["size-pt"] >= READABLE_PT and not fits[short]["rotated"]


def test_longer_bands_keep_their_word_rotated():
    fits = _band_fits(_load(SAMPLES[1]))  # the 2026 plan: no band shorter than two weeks
    assert all(fit["rotated"] and fit["size-pt"] >= READABLE_PT for fit in fits)
    assert {fit["label"] for fit in fits} >= {"build", "ultra", "taper", "recovery", "marathon"}
    assert {fit["size-pt"] for fit in fits if fit["label"] in ("build", "ultra", "taper")} == {8}
