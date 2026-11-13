import pytest

from ttg.model import EasyRuns, Session, SessionType
from ttg.paces import Pace, TrainingPaces
from ttg.sessions import (
    MAX_HILL_MINUTES,
    MAX_HILL_REP_MINUTES,
    MAX_THRESHOLD_MINUTES,
    easy_run_kms,
    hill_session,
    interval_limit_km,
    interval_session,
    marathon_long_run_mp_km,
    marathon_pace_session,
    no_session,
    progression_session,
    round_km,
    session_km,
    strides_session,
    taper_session,
    threshold_session,
    work_km,
    work_minutes,
)

H, I, T, MP = (SessionType.HILLS, SessionType.INTERVALS, SessionType.THRESHOLD, SessionType.MARATHON_PACE)

# The paces of the 2026 season (seasons/2026.toml).
PACES_2026 = TrainingPaces(
    easy=Pace.parse("5:30"), mp=Pace.parse("4:58"), threshold=Pace.parse("4:30"), interval=Pace.parse("4:15")
)
EASY_RUN_KM_2026 = 12


def shape(session: Session) -> tuple[int, float]:
    return session.reps, session.minutes


def test_hills_add_a_rep_then_halve_the_reps_and_double_the_duration():
    assert [shape(hill_session(n)) for n in range(7)] == [
        (6, 1), (7, 1), (8, 1), (9, 1), (5, 2), (6, 2), (7, 2),
    ]  # fmt: skip


def test_hills_hold_at_nine_times_two_minutes_within_the_limits():
    assert [shape(hill_session(n)) for n in range(7, 11)] == [(8, 2), (9, 2), (9, 2), (9, 2)]
    for reps, minutes in map(shape, map(hill_session, range(60))):
        assert minutes <= MAX_HILL_REP_MINUTES and reps * minutes <= MAX_HILL_MINUTES


def test_intervals_alternate_a_rep_and_a_minute():
    assert [shape(interval_session(n)) for n in range(5)] == [(5, 3), (6, 3), (5, 4), (6, 4), (5, 5)]


def test_threshold_alternates_longer_reps_and_an_extra_rep():
    assert [shape(threshold_session(n)) for n in range(4)] == [(3, 8), (3, 10), (4, 8), (4, 10)]


@pytest.mark.parametrize("occurrence", range(20))
def test_threshold_never_exceeds_the_cap(occurrence):
    session = threshold_session(occurrence)
    assert session.reps * session.minutes <= MAX_THRESHOLD_MINUTES


def test_threshold_holds_at_the_last_step_under_the_cap():
    assert shape(threshold_session(4)) == (5, 8)  # 40′ exactly
    assert threshold_session(5) == threshold_session(4) == threshold_session(30)


def test_marathon_pace_repeats_add_a_rep_a_week_up_to_90_minutes_at_mp():
    sessions = [marathon_pace_session(n, PACES_2026.mp) for n in range(5)]
    # 6 × 3 km at 4:58 is 89.4′; a 7th rep would pass Daniels' 90′.
    assert [(s.reps, s.km) for s in sessions] == [(3, 3), (4, 3), (5, 3), (6, 3), (6, 3)]
    assert all(s.type is MP for s in sessions)


def test_long_run_mp_km_grows_by_two_up_to_90_minutes_at_mp():
    assert [marathon_long_run_mp_km(n, PACES_2026.mp) for n in range(8)] == [6, 8, 10, 12, 14, 16, 18, 18]


def progression(session_type, occurrence, other_week_km=60):
    return progression_session(session_type, occurrence, PACES_2026, EASY_RUN_KM_2026, other_week_km)


def test_progression_session_dispatches_by_type():
    assert progression(H, 2) == hill_session(2)
    assert progression(I, 2) == interval_session(2)
    assert progression(T, 2) == threshold_session(2)
    assert progression(MP, 2) == marathon_pace_session(2, PACES_2026.mp)
    with pytest.raises(ValueError):
        progression(SessionType.STRIDES, 0)


def test_intervals_hold_at_the_last_step_within_daniels_limit():
    # Other km 60: 6 × 4′ at 4:15 is 5.6 km (6 whole km); its week is 71 km, 8 % = 5.7 (6). Fits.
    assert progression(I, 3, other_week_km=60) == interval_session(3)
    # Other km 45: the week is about 55 km, 8 % = 4.4 (4): 6 × 4′ (6 km) and 5 × 4′ (5 km) don't
    # fit, 6 × 3′ (4 km) does …
    assert progression(I, 3, other_week_km=45) == interval_session(1)
    # … and a small week holds the first steps.
    assert progression(I, 5, other_week_km=20) == interval_session(0)


def test_interval_limit_is_the_lesser_of_10_km_and_8_percent_in_whole_km():
    assert [interval_limit_km(km) for km in (44, 59, 150)] == [4, 5, 10]


def test_work_km_and_minutes_for_minute_and_km_repeats():
    assert work_km(Session(I, reps=5, minutes=3), PACES_2026.interval) == pytest.approx(15 / 4.25)
    assert work_km(Session(T, reps=6, km=1), PACES_2026.threshold) == 6
    assert work_minutes(Session(T, reps=6, km=1), PACES_2026.threshold) == pytest.approx(27)
    assert work_minutes(Session(T, reps=3, minutes=8), PACES_2026.threshold) == 24


def test_taper_session_is_short_threshold_work():
    assert taper_session() == Session(T, reps=6, km=1)


def test_round_km_rounds_halves_up():
    assert [round_km(km) for km in (14.25, 14.5, 19.5, 20.49)] == [14, 15, 20, 20]


# (type, reps, minutes) of the quality runs of the 2026 plan, weeks 1–3, 5–7, 9–11, 13–15
# (the build rotation H → I → T, so occurrence = index // 3; the rotation itself is tested in
# tests/test_expand.py),
# and the km the owner wrote for them (second page of docs/reference/2026-marathon-training.pdf).
# Week 13 is an override in seasons/2026.toml: the rule gives 9 × 1′, the owner wrote 10 × 1′.
REFERENCE_2026 = [
    (H, 6, 1, 8), (I, 5, 3, 8), (T, 3, 8, 10),
    (H, 7, 1, 8), (I, 6, 3, 9), (T, 3, 10, 11),
    (H, 8, 1, 9), (I, 5, 4, 9), (T, 4, 8, 11),
    (H, 9, 1, 9), (I, 6, 4, 10), (T, 4, 10, 11),
]  # fmt: skip
# The owner's km are hand estimates: they are not derivable from any one formula (hill runs are
# 2–3 km above the estimate, T 4 × 10′ is 2.6 km below). The estimate stays within this much.
REFERENCE_KM_TOLERANCE = 3.0
# What the estimate gives (the prototype's formula), pinned so a change is noticed.
ESTIMATED_KM_2026 = [5.64, 8.62, 9.70, 6.00, 9.69, 11.03, 6.36, 9.80, 11.84, 6.73, 11.10, 13.62]


@pytest.mark.parametrize(
    ("index", "reference", "estimated"), list(zip(range(12), REFERENCE_2026, ESTIMATED_KM_2026, strict=True))
)
def test_reproduces_the_2026_quality_sessions(index, reference, estimated):
    session_type, reps, minutes, reference_km = reference
    session = {H: hill_session, I: interval_session, T: threshold_session}[session_type](index // 3)
    assert (session.type, session.reps, session.minutes) == (session_type, reps, minutes)
    km = session_km(session, PACES_2026, EASY_RUN_KM_2026)
    assert km == pytest.approx(estimated, abs=0.01)
    assert km == pytest.approx(reference_km, abs=REFERENCE_KM_TOLERANCE)


def test_km_of_minute_based_session_by_hand():
    # T 3 × 8′: 10′ + 10′ easy, 2 recoveries of 2′ easy = 24′ at 5:30; 24′ at 4:30.
    expected = (10 + 10 + 2 * 2) / 5.5 + 24 / 4.5
    assert session_km(threshold_session(0), PACES_2026, EASY_RUN_KM_2026) == pytest.approx(expected)


def test_km_of_km_based_session_by_hand():
    # MP 3 × 3 km: 9 km at pace, plus 20′ + 2 recoveries of 2′ easy.
    expected = 9 + (10 + 10 + 2 * 2) / 5.5
    assert session_km(marathon_pace_session(0, PACES_2026.mp), PACES_2026, EASY_RUN_KM_2026) == pytest.approx(expected)


def test_taper_threshold_in_km():
    assert session_km(taper_session(), PACES_2026, EASY_RUN_KM_2026) == pytest.approx(6 + (20 + 5 * 2) / 5.5)


def test_strides_run_is_half_an_easy_run_and_no_session_is_zero():
    assert session_km(strides_session(), PACES_2026, 12) == 6
    assert session_km(strides_session(), PACES_2026, 15) == 8
    assert session_km(no_session(), PACES_2026, 12) == 0


@pytest.mark.parametrize(
    ("runs", "pattern", "expected"),
    [
        (4, EasyRuns.REGULAR, (12, 12)),
        (4, EasyRuns.REDUCED, (12, 6)),
        (3, EasyRuns.REGULAR, (12,)),
        (3, EasyRuns.REDUCED, (6,)),
        (6, EasyRuns.REGULAR, (12, 12, 12, 12)),
        (6, EasyRuns.REDUCED, (12, 12, 12, 6)),
    ],
)
def test_easy_runs(runs, pattern, expected):
    assert easy_run_kms(12, runs, pattern) == expected


def test_reduced_easy_run_rounds_up_to_whole_km():
    assert easy_run_kms(15, 4, EasyRuns.REDUCED) == (15, 8)
    assert easy_run_kms(1, 4, EasyRuns.REDUCED) == (1, 1)
