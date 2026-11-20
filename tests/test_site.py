"""The landing page describes every season-file field in both languages (D-051).

The fields are read from the parser itself, so a new field fails this test until the page
describes it."""

import json
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


# --- the generator page (D-052) ------------------------------------------------

SITE = ROOT / "site"
GENERATOR_PAGES = [SITE / "generator" / "index.html", SITE / "cs" / "generator" / "index.html"]
GENERATOR_SCRIPT = (SITE / "generator.js").read_text(encoding="utf-8")

# `[[race]]`, `[paces]`, ...: the parser reads these as tables, so the form has a group for each, not a control.
TABLE_READ = re.compile(r"\.tables?\(\s*\"([a-z_]+)\"")
CONTROL_NAME = re.compile(r'<(?:input|select|textarea)\b[^>]*\bname="([\w.]+)"')
ELEMENT_ID = re.compile(r'\bid="([\w-]+)"')
CLASS_TOKENS = re.compile(r'\bclass="([^"]*)"')


def page_text(page: Path) -> str:
    return page.read_text(encoding="utf-8")


def control_names(page: Path) -> set[str]:
    return set(CONTROL_NAME.findall(page_text(page)))


def page_words(page: Path) -> set[str]:
    """Every class and every id on the page."""
    text = page_text(page)
    classes = {word for value in CLASS_TOKENS.findall(text) for word in value.split()}
    return classes | set(ELEMENT_ID.findall(text))


@pytest.mark.parametrize("page", GENERATOR_PAGES, ids=lambda page: page.parent.name)
def test_the_form_has_a_control_for_every_season_file_field(page):
    parser = (ROOT / "src" / "ttg" / "spec.py").read_text(encoding="utf-8")
    fields = season_file_fields() - set(TABLE_READ.findall(parser))
    assert fields - {name.rsplit(".", 1)[-1] for name in control_names(page)} == set()


def test_both_languages_have_the_same_controls():
    english, czech = (control_names(page) for page in GENERATOR_PAGES)
    assert english == czech


def collected_fields() -> set[str]:
    """The names in the script's FIELDS and ROW_FIELDS lists: what it reads from the form."""
    blocks = re.findall(r"const (?:ROW_)?FIELDS = .*?\n[\]}];", GENERATOR_SCRIPT, re.DOTALL)
    assert len(blocks) == 2
    return set(re.findall(r'"([\w.]+)"', "".join(blocks)))


@pytest.mark.parametrize("page", GENERATOR_PAGES, ids=lambda page: page.parent.name)
def test_the_script_collects_exactly_the_controls_of_the_form(page):
    assert control_names(page) == collected_fields()


@pytest.mark.parametrize("page", GENERATOR_PAGES, ids=lambda page: page.parent.name)
def test_the_script_finds_everything_it_looks_for_on_the_page(page):
    words = page_words(page)
    ids = set(re.findall(r'getElementById\("([\w-]+)"\)', GENERATOR_SCRIPT))
    selectors = re.findall(r'(?:result|form)\.querySelector(?:All)?\("([^"]+)"\)', GENERATOR_SCRIPT)
    classes = {word for selector in selectors for word in re.findall(r"\.([\w-]+)", selector)}
    assert (ids | classes) - words == set()


@pytest.mark.parametrize("page", GENERATOR_PAGES, ids=lambda page: page.parent.name)
def test_the_page_points_at_the_wheel_and_the_landing_page(page):
    text = page_text(page)
    wheel = re.search(r'data-wheel="([^"]+)"', text).group(1)
    reference = re.search(r'data-reference="([^"]+)"', text).group(1)
    assert (page.parent / wheel).resolve() == SITE / "ttg.whl"
    assert (page.parent / reference / "index.html").resolve() in PAGES


def test_both_languages_word_the_same_labels():
    def words(page: Path) -> set[str]:
        block = re.search(r'id="generator-text">(.*?)</script>', page_text(page), re.DOTALL).group(1)
        return set(json.loads(block))

    english, czech = (words(page) for page in GENERATOR_PAGES)
    assert english == czech
    assert {"race", "override", "loading", "building", "week", "weekdays", "kmText", "gaugeText"} <= english
    assert {name for name in re.findall(r"text\.(\w+)", GENERATOR_SCRIPT)} - {"km", "gauge"} <= english


def test_each_landing_page_links_to_its_generator():
    assert 'href="generator/"' in page_text(PAGES[0])
    assert 'href="generator/"' in page_text(PAGES[1])


def content_security_policy(page: Path) -> dict[str, list[str]]:
    policy = re.search(r'http-equiv="Content-Security-Policy"\s+content="([^"]+)"', page_text(page)).group(1)
    directives = (part.split() for part in policy.split(";"))
    return {name: sources for name, *sources in directives}


@pytest.mark.parametrize("page", GENERATOR_PAGES, ids=lambda page: page.parent.name)
def test_the_page_allows_only_its_own_files_and_the_pyodide_cdn(page):
    policy = content_security_policy(page)
    assert policy["default-src"] == ["'none'"]
    cdn = re.search(r'PYODIDE_URL = "(https://[^/]+)/', GENERATOR_SCRIPT).group(1)
    assert policy["script-src"] == ["'self'", cdn, "'wasm-unsafe-eval'"]
    assert policy["connect-src"] == ["'self'", cdn]
    assert policy["worker-src"] == ["'self'"]
    assert "'unsafe-inline'" not in str(policy) and "'unsafe-eval'" not in str(policy)


def test_both_languages_have_the_same_policy():
    english, czech = (content_security_policy(page) for page in GENERATOR_PAGES)
    assert english == czech


def test_the_page_builds_in_a_worker_so_a_runaway_build_can_be_stopped():
    assert "generator-worker.js" in GENERATOR_SCRIPT
    assert "worker?.terminate()" in GENERATOR_SCRIPT
    assert (SITE / "generator-worker.js").is_file()
