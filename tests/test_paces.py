import pytest

from ttg.paces import Pace


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
