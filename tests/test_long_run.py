from ttg import long_run
from ttg.model import RaceType

EASY_RUN_KM = 12


def test_caps_per_race_type():
    caps = {race_type: long_run.cap(race_type) for race_type in RaceType}
    assert caps == {RaceType.TEN_K: 16, RaceType.HALF: 21, RaceType.MARATHON: 32, RaceType.ULTRA: 40}


def test_build_cap_is_three_quarters_of_the_cap_in_whole_km():
    builds = {race_type: long_run.build_cap(race_type) for race_type in RaceType}
    assert builds == {RaceType.TEN_K: 12, RaceType.HALF: 16, RaceType.MARATHON: 24, RaceType.ULTRA: 30}


def test_grows_two_km_up_to_the_cap():
    assert long_run.grow(15, 32) == 17
    assert long_run.grow(31, 32) == 32
    assert long_run.grow(32, 32) == 32


def test_the_cap_stops_growth_but_never_cuts_a_longer_run():
    assert long_run.grow(15, 12) == 15


def test_deload_is_three_quarters_of_the_last_loading_long_run():
    assert long_run.deload(20, EASY_RUN_KM) == 15
    assert long_run.deload(19, EASY_RUN_KM) == 14  # 14.25


def test_a_reduced_long_run_is_never_shorter_than_an_easy_run():
    assert long_run.deload(14, EASY_RUN_KM) == EASY_RUN_KM  # 10.5
    assert long_run.taper(16, 1, EASY_RUN_KM) == EASY_RUN_KM  # 9.6


def test_taper_is_60_percent_of_the_peak_just_before_the_race_week_75_earlier():
    assert long_run.taper(32, 1, EASY_RUN_KM) == 19  # 19.2
    assert long_run.taper(40, 2, EASY_RUN_KM) == 30
    assert long_run.taper(40, 3, EASY_RUN_KM) == 30


def test_restart_after_a_race_is_three_quarters_of_the_previous_peak():
    assert long_run.restart(21, RaceType.MARATHON, EASY_RUN_KM) == 16  # 15.75


def test_restart_after_a_big_race_follows_the_next_races_build_cap():
    # After a 40 km ultra peak, a marathon restarts at its build cap (24), not at 30.
    assert long_run.restart(40, RaceType.MARATHON, EASY_RUN_KM) == 24


def test_restart_is_never_shorter_than_an_easy_run():
    # A 10 km race's build cap (12) and 75 % of a 14 km peak (10.5) are both below 13.
    assert long_run.restart(14, RaceType.TEN_K, 13) == 13
