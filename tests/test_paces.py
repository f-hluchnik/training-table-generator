from datetime import timedelta

import pytest

from ttg.model import Paces, RaceResult
from ttg.paces import Pace, derive_paces, paces_for_vdot, vdot


@pytest.mark.parametrize(("text", "seconds"), [("4:58", 298), ("5:30", 330), ("10:05", 605), (" 4:15 ", 255)])
def test_parse(text, seconds):
    assert Pace.parse(text) == Pace(seconds)


@pytest.mark.parametrize("text", ["4.58", "4:60", "4:5", "458", "", "0:00", "-4:58"])
def test_parse_rejects(text):
    with pytest.raises(ValueError):
        Pace.parse(text)


@pytest.mark.parametrize(("seconds", "text"), [(298, "4:58"), (298.4, "4:58"), (298.6, "4:59"), (605, "10:05")])
def test_format_rounds_to_whole_seconds(seconds, text):
    assert Pace(seconds).format() == text


def test_paces_order_by_speed():
    assert Pace.parse("4:15") < Pace.parse("4:30")


# --- Paces derived from a race result (T-03, D-015) -------------------------------------
#
# Reference values from Daniels' Running Formula, transcribed from secondary sources
# (the book itself was not available; docs/TRAINING_MODEL.md §10):
#   * 2nd ed., table 3.1 (VDOT → race times) and table 3.2 (VDOT → paces per mile),
#     as posted at runningahead.com (source 12);
#   * 4th ed., table 5.2 for VDOT 51 (paces per km), as summarised in source 1.
# Table values are rounded to whole seconds (per mile in the 2nd edition, per 400 m for I),
# so each comparison allows the rounding plus a small margin.
KM_PER_MILE = 1.609344
VDOT_TOLERANCE = 0.1  # race times in the table are whole seconds
MP_TOLERANCE_S = 1.0  # s/km
THRESHOLD_TOLERANCE_S = 1.0
INTERVAL_TOLERANCE_S = 3.0  # the 2nd edition gives I as whole seconds per 400 m (2.5 s/km)

MARATHON_KM = 42.195


def clock(text: str) -> timedelta:
    *hours, minutes, seconds = (int(part) for part in text.split(":"))
    return timedelta(hours=hours[0] if hours else 0, minutes=minutes, seconds=seconds)


def per_km(seconds_per_mile: str) -> float:
    minutes, seconds = (int(part) for part in seconds_per_mile.split(":"))
    return (minutes * 60 + seconds) / KM_PER_MILE


# (VDOT, 5 km, 10 km, marathon) — 2nd edition, table 3.1.
RACE_TIMES = [
    (50, "19:57", "41:21", "3:10:49"),
    (55, "18:22", "38:06", "2:56:01"),
    (58, "17:33", "36:24", "2:48:14"),
]


@pytest.mark.parametrize(("expected", "five_km", "ten_km", "marathon"), RACE_TIMES)
def test_vdot_matches_daniels_table(expected, five_km, ten_km, marathon):
    for distance_km, time in ((5, five_km), (10, ten_km), (MARATHON_KM, marathon)):
        assert vdot(distance_km, clock(time)) == pytest.approx(expected, abs=VDOT_TOLERANCE)


# (VDOT, M, T per mile, I per 400 m in seconds) — 2nd edition, table 3.2.
PACE_TABLE_2ND_EDITION = [
    (50, "7:17", "6:51", 93),
    (55, "6:43", "6:20", 87),
    (57, "6:31", "6:09", 85),
]


@pytest.mark.parametrize(("fitness", "marathon", "threshold", "interval_400"), PACE_TABLE_2ND_EDITION)
def test_paces_match_daniels_second_edition(fitness, marathon, threshold, interval_400):
    paces = paces_for_vdot(fitness)
    assert paces.mp.seconds_per_km == pytest.approx(per_km(marathon), abs=MP_TOLERANCE_S)
    assert paces.threshold.seconds_per_km == pytest.approx(per_km(threshold), abs=THRESHOLD_TOLERANCE_S)
    assert paces.interval.seconds_per_km == pytest.approx(interval_400 * 1000 / 400, abs=INTERVAL_TOLERANCE_S)


def test_paces_match_daniels_fourth_edition_vdot_51():
    paces = paces_for_vdot(51)
    assert paces.mp.seconds_per_km == pytest.approx(4 * 60 + 27, abs=MP_TOLERANCE_S)
    assert paces.threshold.seconds_per_km == pytest.approx(4 * 60 + 11, abs=THRESHOLD_TOLERANCE_S)
    assert paces.interval.seconds_per_km == pytest.approx(3 * 60 + 51, abs=1.0)
    # Daniels' E range at VDOT 51 is 4:52–5:29 per km; the default sits inside it.
    assert 4 * 60 + 52 <= paces.easy.seconds_per_km <= 5 * 60 + 29


def test_derived_paces_of_the_2026_marathon():
    """TRAINING_MODEL §2: 3:30:02 → VDOT 44.5."""
    result = clock("3:30:02")
    assert vdot(MARATHON_KM, result) == pytest.approx(44.5, abs=0.1)
    paces = derive_paces(MARATHON_KM, result)
    assert [p.format() for p in (paces.easy, paces.mp, paces.threshold, paces.interval)] == [
        "5:37", "4:59", "4:40", "4:18",
    ]


def test_faster_result_gives_faster_paces():
    slow, fast = derive_paces(10, clock("50:00")), derive_paces(10, clock("40:00"))
    assert all(f < s for f, s in zip(
        (fast.easy, fast.mp, fast.threshold, fast.interval),
        (slow.easy, slow.mp, slow.threshold, slow.interval),
    ))


def test_paces_are_ordered_by_intensity():
    paces = derive_paces(21.0975, clock("1:45:00"))
    assert paces.interval < paces.threshold < paces.mp < paces.easy


def test_resolve_uses_overrides_where_given():
    result = RaceResult(MARATHON_KM, clock("3:30:02"))
    paces = Paces(result, easy=Pace.parse("5:30"), threshold=Pace.parse("4:30")).resolve()
    derived = derive_paces(MARATHON_KM, result.time)
    assert (paces.easy, paces.threshold) == (Pace.parse("5:30"), Pace.parse("4:30"))
    assert (paces.mp, paces.interval) == (derived.mp, derived.interval)
