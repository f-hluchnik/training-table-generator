"""Command-line entry point: `ttg build SEASON.toml [-o DIR]` (T-09).

The only module besides `spec` and `render` that touches files, the clock or the console
(D-013). Input errors are reported on stderr with exit code 1 and nothing is written; warnings
never stop a build (D-001).
"""

import argparse
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from ttg import __version__
from ttg.expand import expand
from ttg.export import export
from ttg.model import PlanWarning, SeasonError
from ttg.render import write_outputs
from ttg.spec import load_season

EXIT_INPUT_ERROR = 1
# The default output: `out/<season file name>/` next to the season file, so it does not depend on the
# folder `ttg` is run from (D-046). `out/` is git-ignored; each season gets its own folder inside.
OUTPUT_FOLDER_NAME = "out"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ttg",
        description="Compile a season file into a printable training table.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    build = commands.add_parser("build", help="write plan.json and plan.pdf for a season file")
    build.add_argument("season", type=Path, metavar="SEASON.toml", help="the season file")
    build.add_argument(
        "-o",
        "--output",
        type=Path,
        metavar="DIR",
        help=f"output folder (default: {OUTPUT_FOLDER_NAME}/<season file name>/ next to the season file)",
    )
    return parser


def _format_warning(warning: PlanWarning) -> str:
    where = "" if warning.week is None else f" (week {warning.week})"
    return f"warning {warning.code}{where}: {warning.message}"


def _build(season_path: Path, output: Path | None) -> int:
    try:
        plan = expand(load_season(season_path), date.today())
    except (SeasonError, OSError) as error:
        print(f"ttg: error: {error}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    directory = output if output is not None else default_output(season_path)
    written = write_outputs(export(plan), directory)
    for warning in plan.warnings:
        print(_format_warning(warning), file=sys.stderr)
    for path in written:
        print(f"wrote {path}")
    return 0


def default_output(season_path: Path) -> Path:
    """`out/<season file name>/` in the season file's folder (D-046)."""
    return season_path.parent / OUTPUT_FOLDER_NAME / season_path.stem


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return _build(args.season, args.output)
