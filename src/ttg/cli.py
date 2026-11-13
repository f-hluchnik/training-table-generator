"""Command-line entry point.

Only `--version` exists so far; `ttg build` arrives in T-09.
"""

import argparse
from collections.abc import Sequence

from ttg import __version__


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ttg",
        description="Compile a season file into a printable training table.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    _parser().parse_args(argv)
    return 0
