"""Monday-based plan weeks (PLAN §3).

Week 1 is the week the plan starts in. The plan ends on the last day of the
last race (D-004), so its last week may be cut short. Pure (D-013): "today"
is passed in.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from ttg.model import Race, Season, SeasonError

DAYS_PER_WEEK = 7
ONE_WEEK = timedelta(weeks=1)
# ISO 8601: a week that spans two months belongs to the month holding at least
# four of its days, which is the month of its Thursday.
_THURSDAY_OFFSET = timedelta(days=3)


def monday_of(day: date) -> date:
    """The Monday of the week containing `day`."""
    return day - timedelta(days=day.weekday())


def monday_on_or_after(day: date) -> date:
    """`day` if it is a Monday, otherwise the next Monday (owner, S3)."""
    return monday_of(day + timedelta(days=DAYS_PER_WEEK - 1))


@dataclass(frozen=True)
class Calendar:
    first_monday: date
    last_day: date  # the plan's last day: the last race's last day (D-004)

    @property
    def weeks(self) -> int:
        return self.week_of(self.last_day)

    def week_of(self, day: date) -> int:
        """The week number of `day`: 1 for the first week, 0 or less before it."""
        return (day - self.first_monday).days // DAYS_PER_WEEK + 1

    def monday(self, week: int) -> date:
        return self.first_monday + (week - 1) * ONE_WEEK

    def days(self, week: int) -> tuple[date | None, ...]:
        """The 7 days of a week, Monday to Sunday; None after the plan ends."""
        monday = self.monday(week)
        days = (monday + timedelta(days=offset) for offset in range(DAYS_PER_WEEK))
        return tuple(day if day <= self.last_day else None for day in days)

    def month(self, week: int) -> int:
        """The month (1–12) a week belongs to: the month of its Thursday."""
        return (self.monday(week) + _THURSDAY_OFFSET).month


def plan_calendar(season: Season, today: date) -> Calendar:
    """The plan's calendar. Raises SeasonError if a race falls before week 1."""
    last_day = max(race.last_day for race in season.races)
    calendar = Calendar(_first_monday(season, last_day, today), last_day)
    _check_no_race_before_start(season, calendar)
    return calendar


def _first_monday(season: Season, last_day: date, today: date) -> date:
    """From `start`, from `weeks` counted back from the last week, or next Monday (D-004)."""
    if season.start is not None:
        return monday_of(season.start)
    if season.weeks is not None:
        return monday_of(last_day) - (season.weeks - 1) * ONE_WEEK
    return monday_on_or_after(today)


def _check_no_race_before_start(season: Season, calendar: Calendar) -> None:
    """The loader checks an explicit `start`; this covers `weeks` and the default start."""
    early: Race | None = next((race for race in season.races if race.last_day < calendar.first_monday), None)
    if early is None:
        return
    if season.weeks is not None:
        field, start = "weeks", f"{season.weeks} weeks start on {calendar.first_monday}"
    elif season.start is not None:
        field, start = "start", f"the plan starts on {calendar.first_monday}"
    else:
        field, start = "start", f"without start or weeks the plan starts on {calendar.first_monday}"
    raise SeasonError(f'{field}: {start}, after the race "{early.name}" on {early.last_day}')
