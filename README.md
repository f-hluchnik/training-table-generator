# Training table generator

A command-line plan compiler: from a short season file (races, plan start, paces, current load) it produces a printable A4 landscape training table in the style of [`docs/reference/2026-marathon-training.pdf`](docs/reference/2026-marathon-training.pdf).

The table is an outline, not a prescription: print it, colour the cells by hand during the season, and adapt it to life. The tool never refuses a plan; it lays it out and warns about anything questionable.

## Set-up

You need three things on your computer: **Git**, **Python 3.11 or newer** (check with `python3 --version`), and a terminal. Nothing else: the Typst compiler that draws the PDF and its fonts come with the Python package `typst`, so there is no LaTeX, browser or other program to install.

1. **Get the code**

   ```sh
   git clone https://github.com/f-hluchnik/training-table-generator.git
   cd training-table-generator
   ```

2. **Create a virtual environment** (a private folder for this project's Python packages, so nothing is installed system-wide):

   ```sh
   python3 -m venv .venv
   ```

3. **Activate it.** Do this in every new terminal before using the tool:

   ```sh
   . .venv/bin/activate          # macOS and Linux
   .venv\Scripts\activate        # Windows (PowerShell or cmd)
   ```

   The prompt now starts with `(.venv)`.

4. **Install the tool and its test dependencies:**

   ```sh
   pip install -e '.[dev]'
   ```

   On Windows cmd, write the quotes as `"` instead of `'`.

5. **Check that it works:**

   ```sh
   ttg --version
   pytest
   ```

   `pytest` should end with all tests passing (about 300, a few seconds).

Only the macOS/Linux commands have been run by the author; the Windows lines are the standard equivalents.

**Problems.** `python3: command not found` or a version below 3.11: install a current Python from [python.org](https://www.python.org/downloads/) and use its `python3` (on Windows `py -3`) in step 2. `ttg: command not found`: the virtual environment is not active (step 3). To update later, run `git pull` and, if `pip` complains, repeat step 4.

## Making your plan

1. Copy a season file and edit it. [`seasons/test-2027.toml`](seasons/test-2027.toml) is a good start (two tune-up races and a marathon); [`seasons/2026.toml`](seasons/2026.toml) is the reference season. The smallest useful file:

   ```toml
   start = 2027-05-03            # or: weeks = 20  (neither: starts next Monday)

   [[race]]
   name = "Prague Marathon"
   date = 2027-10-10
   distance_km = 42.195          # priority = "A" by default

   [paces]
   race_result = { distance_km = 42.195, time = "3:30:02" }   # a recent race; paces are derived from it

   [load]
   easy_run_km = 12              # one easy run
   long_run_km = 15              # the long run of the first week
   ```

   Every field, with defaults and the error messages, is in [`docs/PLAN.md`](docs/PLAN.md) §4.

2. Build it:

   ```sh
   ttg build my-season.toml                 # writes out/my-season/plan.pdf and plan.json
   ttg build my-season.toml -o my-plan/     # or into a folder of your choice
   ```

3. Open `plan.pdf` and print it on **A4, landscape, at 100 % scale** (not "fit to page"), so the cells keep their size for colouring.

Warnings about the plan (a long run above half the week, a plan too short for its race, …; [`docs/TRAINING_MODEL.md`](docs/TRAINING_MODEL.md) §7) are printed in the terminal and do not stop the build. An invalid season file prints the offending field, writes nothing and exits with code 1. `plan.json` is the same plan as data; you do not need it for printing.

## Development

Work in the activated virtual environment (set-up above). Before committing, run what CI runs on Python 3.11 and 3.12:

```sh
ruff check && ruff format --check && mypy && pytest
```

`ruff format` fixes the formatting. CI also builds both reference seasons and keeps their PDFs. The repository is organised by ticket (one branch per ticket); see the documentation below.

## Documentation

- [`docs/PLAN.md`](docs/PLAN.md): goals, requirements, architecture, data contracts
- [`docs/TRAINING_MODEL.md`](docs/TRAINING_MODEL.md): training rules and their sources
- [`docs/DECISIONS.md`](docs/DECISIONS.md): decisions and open questions
- [`docs/TICKETS.md`](docs/TICKETS.md): work items and status
- [`docs/SESSIONS.md`](docs/SESSIONS.md): how tickets are grouped into working sessions
