"""Render a `plan.json` document to the printable PDF with the Typst template.

The template (`plan.typ`, shipped inside the package) only lays out what the plan contains
(D-012).
"""

import json
from pathlib import Path

import typst

TEMPLATE = Path(__file__).with_name("plan.typ")
PLAN_INPUT = "plan"  # name of the Typst input that carries the plan's JSON text
PLAN_JSON = "plan.json"
PLAN_PDF = "plan.pdf"
JSON_INDENT = 2


def render_pdf(plan: dict) -> bytes:
    """Return the PDF of `plan` (the plan.json structure of docs/PLAN.md §4)."""
    plan_text = json.dumps(plan, ensure_ascii=False)
    return typst.compile(TEMPLATE, sys_inputs={PLAN_INPUT: plan_text})


def write_outputs(plan: dict, directory: Path) -> tuple[Path, Path]:
    """Write `plan.json` and `plan.pdf` of `plan` into `directory`, created if missing.

    Returns the two paths. The PDF is rendered first, so a failed render leaves no half-written
    output behind.
    """
    pdf = render_pdf(plan)
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / PLAN_JSON
    pdf_path = directory / PLAN_PDF
    json_path.write_text(json.dumps(plan, ensure_ascii=False, indent=JSON_INDENT) + "\n", encoding="utf-8")
    pdf_path.write_bytes(pdf)
    return json_path, pdf_path
