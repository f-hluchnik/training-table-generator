"""Render a `plan.json` document to the printable PDF with the Typst template.

The template (`templates/plan.typ`) only lays out what the plan contains (D-012).
"""

import json
from pathlib import Path

import typst

# The template sits in the repository next to the package sources (PLAN §3). Installing the
# package as a wheel would need it moved into the package; that is a T-09 concern.
TEMPLATE = Path(__file__).resolve().parents[2] / "templates" / "plan.typ"
PLAN_INPUT = "plan"  # name of the Typst input that carries the plan's JSON text


def render_pdf(plan: dict) -> bytes:
    """Return the PDF of `plan` (the plan.json structure of docs/PLAN.md §4)."""
    plan_text = json.dumps(plan, ensure_ascii=False)
    return typst.compile(TEMPLATE, sys_inputs={PLAN_INPUT: plan_text})


def render_file(plan_path: Path, pdf_path: Path) -> None:
    """Read `plan_path` (JSON) and write the PDF to `pdf_path`."""
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    pdf_path.write_bytes(render_pdf(plan))
