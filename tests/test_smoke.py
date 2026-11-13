"""Smoke tests: the package installs, the console script runs, Typst compiles."""

import pytest
import typst

import ttg
from ttg.cli import main


def test_version_is_exposed():
    assert ttg.__version__


def test_cli_prints_version(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0
    assert ttg.__version__ in capsys.readouterr().out


def test_bundled_typst_compiles_a_pdf():
    pdf = typst.compile(b"= Smoke test")
    assert pdf.startswith(b"%PDF-")
