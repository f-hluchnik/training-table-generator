"""The landing page describes every season-file field in both languages (D-051).

The fields are read from the parser itself, so a new field fails this test until the page
describes it."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
PAGES = [ROOT / "site" / "index.html", ROOT / "site" / "cs" / "index.html"]

# The parser reads each field with a typed accessor: `table.date("start")`, `root.tables("race")`, …
FIELD_READ = re.compile(r"\.\w+\(\s*\"([a-z_]+)\"")


def season_file_fields() -> set[str]:
    return set(FIELD_READ.findall((ROOT / "src" / "ttg" / "spec.py").read_text(encoding="utf-8")))


def code_words(page: Path) -> set[str]:
    """Every identifier inside a <code> element of the page."""
    snippets = re.findall(r"<code>(.*?)</code>", page.read_text(encoding="utf-8"), re.DOTALL)
    return {word for snippet in snippets for word in re.findall(r"[a-z_]+", snippet)}


def test_the_parser_reads_the_fields_this_test_expects():
    assert {"start", "race", "race_result", "runs_per_week", "overrides", "hilly"} <= season_file_fields()


@pytest.mark.parametrize("page", PAGES, ids=lambda page: page.parent.name)
def test_the_page_describes_every_season_file_field(page):
    assert season_file_fields() - code_words(page) == set()
