# Training table generator

A command-line plan compiler: from a short season file (races, plan start, paces, current load) it produces a printable A4 landscape training table in the style of [`docs/reference/2026-marathon-training.pdf`](docs/reference/2026-marathon-training.pdf).

Status: under construction. The new package `ttg` is being built ticket by ticket (`docs/TICKETS.md`); the older prototype files in the repository root stay until it replaces them (T-10).

## Development setup

Requires Python 3.11 or newer. Always work in a virtual environment:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
pytest
```

The Typst compiler comes with the `typst` Python package; nothing else needs installing.

## Documentation

- [`docs/PLAN.md`](docs/PLAN.md): goals, requirements, architecture, data contracts
- [`docs/TRAINING_MODEL.md`](docs/TRAINING_MODEL.md): training rules and their sources
- [`docs/DECISIONS.md`](docs/DECISIONS.md): decisions and open questions
- [`docs/TICKETS.md`](docs/TICKETS.md): work items and status
- [`docs/SESSIONS.md`](docs/SESSIONS.md): how tickets are grouped into working sessions
