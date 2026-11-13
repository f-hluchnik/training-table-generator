"""The sample plans follow the plan.json contract in docs/PLAN.md §4 and are internally consistent.

`sample-plan-2026-weeks-1-4` is hand-made (T-02, the renderer's first input in T-08); `plan-2026`
and `plan-test-2027` are the generated snapshots (tests/test_snapshots.py)."""

import json
import math
from datetime import date, timedelta

import pytest

from support import FIXTURES

SAMPLES = [
    FIXTURES / "sample-plan-2026-weeks-1-4.json",
    FIXTURES / "plan-2026.json",
    FIXTURES / "plan-test-2027.json",
]
DAYS_PER_WEEK = 7

PLAN_KEYS = {"schema_version", "title", "paces", "gauge", "weeks", "footer", "warnings"}
WEEK_KEYS = {
    "number", "days", "month", "kind", "phase", "phase_label", "phase_short", "easy", "quality", "long",
    "planned_km", "note",
}  # fmt: skip


@pytest.fixture(scope="module", params=SAMPLES, ids=lambda path: path.stem)
def plan(request):
    return json.loads(request.param.read_text(encoding="utf-8"))


def test_top_level_keys(plan):
    assert set(plan) == PLAN_KEYS
    assert plan["schema_version"] == 4


def test_week_keys(plan):
    for week in plan["weeks"]:
        assert set(week) == WEEK_KEYS


def test_days_are_a_monday_based_week(plan):
    for week in plan["weeks"]:
        days = week["days"]
        assert len(days) == DAYS_PER_WEEK
        first_index, first = next((i, day) for i, day in enumerate(days) if day)
        monday = date.fromisoformat(first["date"]) - timedelta(days=first_index)
        assert monday.weekday() == 0
        for offset, day in enumerate(days):
            if day is not None:
                expected = monday + timedelta(days=offset)
                assert day["date"] == expected.isoformat()
                assert day["text"] == str(expected.day)


def test_days_after_the_last_race_are_null(plan):
    days = [day for week in plan["weeks"] for day in week["days"]]
    first_null = days.index(None) if None in days else len(days)
    assert all(day is None for day in days[first_null:])


def test_planned_km_is_the_sum_of_the_sessions(plan):
    for week in plan["weeks"]:
        sessions = sum(week["easy"]["km"]) + week["quality"]["km"] + week["long"]["km"]
        assert week["planned_km"] == sessions


def test_gauge_covers_the_highest_week(plan):
    gauge = plan["gauge"]
    highest = max(week["planned_km"] for week in plan["weeks"])
    assert gauge["boxes"] == math.ceil(highest / gauge["label_every_km"]) * gauge["label_every_km"]
