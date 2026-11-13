"""Snapshots of the plan.json of both reference seasons (D-020).

`plan-2026.json` is the golden season's output (its differences from the reference sheet are
in tests/test_golden_2026.py). `plan-test-2027.json` freezes the defaults once the owner has
reviewed them. After an intended change, regenerate both and review the diff:

    TTG_UPDATE_SNAPSHOTS=1 pytest tests/test_snapshots.py
"""

import json
import os

import pytest

from ttg.expand import expand
from ttg.export import export
from ttg.spec import load_season

from support import FIXTURES, SEASONS, TODAY

SNAPSHOTS = {"2026.toml": "plan-2026.json", "test-2027.toml": "plan-test-2027.json"}
UPDATE = os.environ.get("TTG_UPDATE_SNAPSHOTS") == "1"


def generate(season_file: str) -> dict:
    plan = expand(load_season(SEASONS / season_file), TODAY)
    return export(plan)


@pytest.mark.parametrize(("season_file", "snapshot"), SNAPSHOTS.items())
def test_season_matches_its_snapshot(season_file, snapshot):
    path = FIXTURES / snapshot
    document = generate(season_file)
    if UPDATE:
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert document == json.loads(path.read_text(encoding="utf-8"))
