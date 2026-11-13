"""End-to-end tests of `ttg build` (T-09): both reference seasons, input errors, exit codes."""

import json

import pytest

from ttg.cli import EXIT_INPUT_ERROR, main
from ttg.render import PLAN_JSON, PLAN_PDF

from support import FIXTURES, ROOT

SEASONS = {"2026": "plan-2026.json", "test-2027": "plan-test-2027.json"}


@pytest.mark.parametrize(("season", "snapshot"), SEASONS.items())
def test_build_writes_the_plan_and_the_pdf(season, snapshot, tmp_path, capsys):
    assert main(["build", str(ROOT / "seasons" / f"{season}.toml"), "-o", str(tmp_path)]) == 0

    expected = json.loads((FIXTURES / snapshot).read_text(encoding="utf-8"))
    assert json.loads((tmp_path / PLAN_JSON).read_text(encoding="utf-8")) == expected
    assert (tmp_path / PLAN_PDF).read_bytes().startswith(b"%PDF-")
    assert f"wrote {tmp_path / PLAN_PDF}" in capsys.readouterr().out


def test_build_prints_the_warnings_and_still_succeeds(tmp_path, capsys):
    assert main(["build", str(ROOT / "seasons" / "2026.toml"), "-o", str(tmp_path)]) == 0

    stderr = capsys.readouterr().err
    assert "warning C4 (week 13):" in stderr
    assert "warning C8:" in stderr  # a warning without a week names no week


def test_build_creates_the_output_folder(tmp_path):
    folder = tmp_path / "a" / "b"
    assert main(["build", str(ROOT / "seasons" / "test-2027.toml"), "-o", str(folder)]) == 0
    assert (folder / PLAN_PDF).is_file()


def test_build_defaults_to_a_folder_per_season(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["build", str(ROOT / "seasons" / "test-2027.toml")]) == 0
    assert (tmp_path / "out" / "test-2027" / PLAN_PDF).is_file()


def test_invalid_season_is_an_error_and_writes_nothing(tmp_path, capsys):
    season = tmp_path / "bad.toml"
    season.write_text("start = 2027-03-01\nunknown = 1\n", encoding="utf-8")
    output = tmp_path / "out"

    assert main(["build", str(season), "-o", str(output)]) == EXIT_INPUT_ERROR

    assert "ttg: error:" in capsys.readouterr().err
    assert not output.exists()


def test_missing_season_file_is_an_input_error(tmp_path, capsys):
    assert main(["build", str(tmp_path / "missing.toml")]) == EXIT_INPUT_ERROR
    assert "missing.toml" in capsys.readouterr().err


def test_a_command_is_required(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main([])
    assert exit_info.value.code != 0
