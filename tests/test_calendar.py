from dataclasses import replace
from datetime import date

import pytest

from ttg.calendar import Calendar, monday_of, monday_on_or_after, plan_calendar
from ttg.model import Race, SeasonError

from support import TODAY, season

MARATHON = Race("Marathon", date(2027, 10, 10), 42.195)  # a Sunday


@pytest.mark.parametrize(
    ("day", "monday"),
    [
        (date(2026, 5, 4), date(2026, 5, 4)),  # Monday
        (date(2026, 5, 6), date(2026, 5, 4)),  # Wednesday
        (date(2026, 5, 10), date(2026, 5, 4)),  # Sunday
    ],
)
def test_monday_of(day, monday):
    assert monday_of(day) == monday


@pytest.mark.parametrize(
    ("day", "monday"),
    [
        (date(2027, 8, 30), date(2027, 8, 30)),  # a Monday is its own next Monday (owner, S3)
        (date(2027, 8, 31), date(2027, 9, 6)),
        (date(2027, 9, 5), date(2027, 9, 6)),
    ],
)
def test_monday_on_or_after(day, monday):
    assert monday_on_or_after(day) == monday


def test_reference_2026_months_follow_the_thursday():
    calendar = Calendar(date(2026, 5, 4), date(2026, 10, 10))
    months = [calendar.month(week) for week in range(1, calendar.weeks + 1)]
    # As in docs/reference/2026-marathon-training.pdf, e.g. week 9 (29 Jun – 5 Jul) is July.
    assert months == [5] * 4 + [6] * 4 + [7] * 5 + [8] * 4 + [9] * 4 + [10] * 2


def test_days_end_with_the_plan():
    calendar = Calendar(date(2026, 5, 4), date(2026, 10, 10))
    assert calendar.weeks == 23
    assert calendar.days(17)[-1] == date(2026, 8, 30)  # a race inside the plan does not cut its week
    assert calendar.days(23) == (*(date(2026, 10, day) for day in range(5, 11)), None)


def test_week_of():
    calendar = Calendar(date(2026, 5, 4), date(2026, 10, 10))
    assert calendar.week_of(date(2026, 5, 4)) == 1
    assert calendar.week_of(date(2026, 8, 29)) == 17
    assert calendar.week_of(date(2026, 5, 3)) == 0
    assert calendar.monday(17) == date(2026, 8, 24)


def test_start_mid_week_starts_on_its_monday():
    calendar = plan_calendar(season(MARATHON, start=date(2027, 5, 5)), TODAY)
    assert calendar.first_monday == date(2027, 5, 3)
    assert calendar.weeks == 23


def test_weeks_count_back_from_the_last_week():
    calendar = plan_calendar(season(MARATHON, weeks=6), TODAY)
    assert calendar.first_monday == date(2027, 8, 30)
    assert calendar.weeks == 6


def test_without_start_or_weeks_the_plan_starts_next_monday():
    assert plan_calendar(season(MARATHON), date(2027, 8, 30)).first_monday == date(2027, 8, 30)
    assert plan_calendar(season(MARATHON), date(2027, 8, 31)).first_monday == date(2027, 9, 6)


def test_plan_ends_on_the_last_day_of_a_multi_day_race():
    sunday_to_monday = replace(MARATHON, end=date(2027, 10, 11))
    calendar = plan_calendar(season(sunday_to_monday, start=date(2027, 5, 3)), TODAY)
    assert calendar.weeks == 24
    assert calendar.days(24) == (date(2027, 10, 11), *[None] * 6)


@pytest.mark.parametrize(
    ("data", "field", "fragment"),
    [
        (
            season(Race("Half", date(2027, 5, 9), 21.0975), MARATHON, weeks=4),
            "weeks",
            '4 weeks start on 2027-09-13, after the race "Half"',
        ),
        (season(MARATHON), "start", "without start or weeks the plan starts on 2027-10-11"),
        (
            season(MARATHON, start=date(2027, 10, 18)),
            "start",
            'the plan starts on 2027-10-18, after the race "Marathon"',
        ),
    ],
)
def test_race_before_the_first_week_is_an_error(data, field, fragment):
    today = date(2027, 10, 11)
    with pytest.raises(SeasonError, match=f"^{field}: ") as error:
        plan_calendar(data, today)
    assert fragment in str(error.value)
