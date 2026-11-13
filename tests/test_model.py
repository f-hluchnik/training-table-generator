import pytest

from ttg.model import RaceType


@pytest.mark.parametrize(
    ("distance_km", "race_type"),
    [
        (5, RaceType.TEN_K),
        (10, RaceType.TEN_K),
        (15, RaceType.HALF),
        (21.0975, RaceType.HALF),
        (21.1, RaceType.HALF),  # rounded distances count as the standard one
        (30, RaceType.MARATHON),
        (42.2, RaceType.MARATHON),
        (50, RaceType.ULTRA),
        (101, RaceType.ULTRA),
    ],
)
def test_race_type_by_distance(distance_km, race_type):
    assert RaceType.of(distance_km) is race_type
