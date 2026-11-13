"""The hand-made sample plan.json (input of the renderer in T-08) follows the
plan.json contract in docs/PLAN.md §4 and is internally consistent."""

import json
import math
from datetime import date, timedelta
from pathlib import Path

import pytest

SAMPLE = Path(__file__).parent / "fixtures" / "sample-plan-2026-weeks-1-4.json"
DAYS_PER_WEEK = 7
SUCCESS_SHARE = 0.8  # D-006

PLAN_KEYS = {"schema_version", "title", "paces", "gauge", "weeks", "footer", "warnings"}
WEEK_KEYS = {
    "number", "days", "month", "kind", "phase_label", "easy", "quality", "long",
    "planned_km", "box_80pct", "note",
}  # fmt: skip


@pytest.fixture(scope="module")
def plan():
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


def test_top_level_keys(plan):
    assert set(plan) == PLAN_KEYS
    assert plan["schema_version"] == 1


def test_week_keys(plan):
    for week in plan["weeks"]:
        assert set(week) == WEEK_KEYS


def test_days_are_a_monday_based_week(plan):
    for week in plan["weeks"]:
        days = week["days"]
        assert len(days) == DAYS_PER_WEEK
        monday = date.fromisoformat(days[0]["date"])
        assert monday.weekday() == 0
        for offset, day in enumerate(days):
            expected = monday + timedelta(days=offset)
            assert day == {"date": expected.isoformat(), "text": str(expected.day), "race": False}


def test_planned_km_is_the_sum_of_the_sessions(plan):
    for week in plan["weeks"]:
        sessions = sum(week["easy"]["km"]) + week["quality"]["km"] + week["long"]["km"]
        assert week["planned_km"] == sessions
        assert week["box_80pct"] == math.ceil(SUCCESS_SHARE * week["planned_km"])


def test_gauge_covers_the_highest_week(plan):
    gauge = plan["gauge"]
    highest = max(week["planned_km"] for week in plan["weeks"])
    assert gauge["boxes"] == math.ceil(highest / gauge["label_every_km"]) * gauge["label_every_km"]
