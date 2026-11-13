# Training table generator

`ttg` is a command-line plan compiler for runners. You describe a season in a short text file: your races, when the plan starts, a recent race result and what you run now. From that it builds a printable A4 landscape training table (PDF), one row per week, in the style of [`docs/reference/2026-marathon-training.pdf`](docs/reference/2026-marathon-training.pdf).

The table is an **outline, not a prescription**. You print it, put it on the wall, colour a cell after each run and adapt the plan to life as you go. The tool automates the tedious, error-prone parts: dates, phases, session progressions, km arithmetic and layout. It never refuses a plan. If something looks risky (races too close together, a plan too short, a long run too big), it still builds the plan and prints a warning.

## Contents

- [The sheet](#the-sheet)
- [Set-up](#set-up)
- [Making your plan](#making-your-plan)
- [The season file](#the-season-file)
- [How the plan is built](#how-the-plan-is-built)
- [Warnings](#warnings)
- [How it works inside](#how-it-works-inside)
- [Development](#development)

## The sheet

One row per week (plans longer than about 40 weeks continue on a second page), with these columns:

| Column | Shows |
|---|---|
| Month | The month a week belongs to (the month of its Thursday), spanning its weeks. |
| Week | The week number, from 1. |
| Mon–Sun | The day of the month: **one cell per day to colour after each run.** Race days are bold; the last week ends on the last race day. |
| Gauge | One narrow box per km, labelled every 10 km. At the end of the week, colour as many boxes as km you ran. A heavier border marks 80 % of the week's planned km: **a week counts as done at ≥ 80 %.** |
| Phase | Where you are in the season: *build*, the race-specific block (*10 km*, *half*, *marathon*, *ultra*), *taper*, *recovery*. |
| ER | The easy runs, km each: `12+12`, or `12+6` in a lighter week. |
| QR | The quality run (codes below). |
| LR | The long run: `24 km`, or `28 km (10 MP)` with the last 10 km at marathon pace. |
| (last) | In grey: the week's planned km, or *taper*, *race*, *recovery*, or your own note. |

Session codes:

| Code | Meaning |
|---|---|
| `H: 6x1'` | Hill repeats: 6 × 1 minute hard uphill effort, jog down. By effort, no pace. |
| `I: 5x3'` | Intervals: 5 × 3 minutes at interval pace, 2′ jog between. |
| `T: 3x8'`, `T: 6x1 km` | Threshold: repeats at threshold pace, 2′ jog between. |
| `MP: 3x3 km` | Marathon-pace repeats, 2′ jog between. |
| `S` | An easy run of half the easy-run length with 6 × 20″ fast, relaxed strides. |
| `RACE 21 km` | A race in place of the session. |
| `–` | No session. |

The planned km assume a 10′ warm-up and a 10′ cool-down around every quality run. Below the table, the sheet prints the pace legend (e.g. `ER=5:37 [easy]; … I=4:18+2′ [hard]`, where `+2′` is the recovery jog), the races with their dates and priorities, and the "life happens" rules: *Short on time: drop an easy run → intensity → long run. Tired or ill: drop intensity first.*

The sheet is black and white, and the colours are yours. The reference season used green for easy, yellow for quality and blue for long runs, with a red triangle in a corner for an unexpected event (illness, a trip).

## Set-up

You need **Git**, **Python 3.11 or newer** (check with `python3 --version`) and a terminal. Nothing else: the Typst compiler that draws the PDF, and its fonts, come with the Python package `typst`.

1. **Get the code:**

   ```sh
   git clone https://github.com/f-hluchnik/training-table-generator.git
   cd training-table-generator
   ```

2. **Create a virtual environment** (a private folder for this project's packages, so nothing is installed system-wide):

   ```sh
   python3 -m venv .venv
   ```

3. **Activate it.** Do this in every new terminal before using the tool. Afterwards the prompt starts with `(.venv)`.

   ```sh
   . .venv/bin/activate          # macOS and Linux
   .venv\Scripts\activate        # Windows (PowerShell or cmd)
   ```

4. **Install the tool** (with the test tools):

   ```sh
   pip install -e '.[dev]'       # on Windows cmd, use " instead of '
   ```

5. **Check that it works:** `ttg --version` prints the version, and `pytest` should pass every test (about 330, a few seconds).

Only the macOS/Linux commands have been run by the author; the Windows lines are the standard equivalents.

**Problems.** If you get `python3: command not found` or a version below 3.11, install a current Python from [python.org](https://www.python.org/downloads/) and use its `python3` (on Windows, `py -3`) in step 2. If you get `ttg: command not found`, the virtual environment is not active (step 3). To update later, run `git pull`, and if `pip` complains, repeat step 4.

## Making your plan

1. **Write a season file.** The smallest useful one:

   ```toml
   start = 2027-05-03            # or: weeks = 20   (neither: the plan starts next Monday)

   [[race]]
   name = "Prague Marathon"
   date = 2027-10-10
   distance_km = 42.195

   [paces]
   race_result = { distance_km = 42.195, time = "3:30:02" }   # a recent race; all paces derive from it

   [load]
   easy_run_km = 12              # the length of one easy run
   long_run_km = 15              # the long run of the first week
   ```

   Two complete examples are in [`seasons/`](seasons/). [`test-2027.toml`](seasons/test-2027.toml) has two tune-up races and a marathon, with everything else defaulted. [`2026.toml`](seasons/2026.toml) is the reference season, with overrides.

2. **Build it:**

   ```sh
   ttg build my-season.toml                 # writes out/my-season/plan.pdf and plan.json
   ttg build my-season.toml -o my-plan/     # or into a folder of your choice
   ```

3. **Print `plan.pdf` on A4, landscape, at 100 % scale** (not "fit to page"), so the cells keep their size for colouring.

**Warnings** about the plan are printed in the terminal as, e.g., `warning C4 (week 13): …` (see [Warnings](#warnings)). They don't stop the build. **An invalid season file** prints the field at fault, e.g. `ttg: error: my-season.toml: race[1].date: expected a date like 2026-05-04 (without quotes), got "2027-10-10"`. In that case nothing is written and the exit code is 1. `plan.json` holds the same plan as data; you don't need it for printing.

To change the plan, edit the season file and build again. Never edit the output: rebuilding always starts from the season file.

## The season file

The season file is a [TOML](https://toml.io) file. Required: at least one race, a race result and the load. Everything else is optional. A misspelled or unknown field is an error, so a typo can't be silently ignored.

| Field | Value | Default | Meaning |
|---|---|---|---|
| `start` | date | – | Week 1 is the Monday–Sunday week containing this date. |
| `weeks` | whole number ≥ 1 | – | Alternatively, the plan's length; it ends with the week of the last race. Give `start` or `weeks`, not both; with neither, the plan starts next Monday. |
| `[sheet] title` | text | `"training plan"` | The title on the sheet. |
| `[sheet] rules` | list of texts | see [The sheet](#the-sheet) | The "life happens" rules in the footer. |
| `[[race]]` | | | One section per race, any number, any dates. |
| `name` | text | required | Unique; printed in the footer. |
| `date` | date | required | The (first) race day. |
| `end` | date | – | The last day of a multi-day race. |
| `distance_km` | number > 0 | required | Decides the race type: up to 10 km, half marathon, marathon, longer = ultra (0.1 km slack, so 21.1 and 42.2 count). |
| `priority` | `"A"`, `"B"`, `"C"` | `"A"` | A: full taper and recovery. B: taper one week shorter. C: a tune-up race inside the training, with no phases of its own. |
| `taper_weeks` | whole number ≥ 1 | by race type | The taper, including the race week. |
| `specific_weeks` | whole number ≥ 0 | by race type | The race-specific block. |
| `recovery_weeks` | whole number ≥ 0 | by race type | Recovery after the race. |
| `hilly` | `true`, `false` | `false` | The race-specific block leans into hill repeats. |
| `[paces] race_result` | `{ distance_km, time }` | required | A recent race; `time` is `"h:mm:ss"` or `"m:ss"`. All paces derive from it. |
| `[paces] easy`, `mp`, `threshold`, `interval` | `"m:ss"` per km | derived | Override a derived pace; `mp` is the place for a goal pace. |
| `[load] easy_run_km` | whole number ≥ 1 | required | The length of an easy run. |
| `[load] long_run_km` | whole number ≥ 1 | required | The long run of the first week. |
| `[load] runs_per_week` | 3–6 | 4 | Always one quality run and one long run; the rest are easy runs. |

The phase lengths and `hilly = true` are not allowed on a C race, because a C race has no phases of its own.

**Overrides** change single weeks, keyed by week number. An override changes only its own week; the following weeks are still computed from the rules.

```toml
[overrides]
1  = { easy = "reduced" }                                  # "regular" or "reduced" (the last easy run halved)
13 = { quality = { type = "H", reps = 10, minutes = 1 } }  # any quality session
14 = { long_run_km = 40 }                                  # 0 = no long run
20 = { quality = { type = "MP", reps = 3, km = 3 }, note = "check" }   # note replaces the last column
```

A quality session is `{ type, reps, minutes }` or `{ type, reps, km }` with `type` one of `"H"`, `"I"`, `"T"`, `"MP"`, or just `{ type = "S" }` (strides) or `{ type = "none" }`. Overriding a cell that holds a race, or a week past the end of the plan, is an error.

**Other errors:** a missing required field, a value of the wrong type or out of range, `end` before `date`, two races with the same name, a race before the plan starts.

## How the plan is built

The rules follow established coaching guidance (Daniels, Pfitzinger, McMillan, Koop and others); each number in the code cites its source or says it is our own default. Details and sources: [`docs/TRAINING_MODEL.md`](docs/TRAINING_MODEL.md).

**Paces.** Derived from your race result with Jack Daniels' VDOT formula: threshold at 88 % of VDOT, interval at 97.5 %, easy at 70 %, marathon pace at the race-equivalent marathon time. Hills go by effort. For example, a 3:30:02 marathon gives easy 5:37, MP 4:59, threshold 4:40 and interval 4:18 per km.

**A week** has one quality run, one long run and the rest easy runs. Easy runs are all `easy_run_km` and never grow. In lighter weeks (deload, taper, race and recovery) the last one is halved. The week's planned km is the sum of all runs. A quality run's km are estimated from warm-up, work, recoveries and cool-down. The tool doesn't assign runs to days: you fill in the calendar.

**Phases** are laid out backward from each A and B race: *build* (general preparation), then a *race-specific* block, then a *taper* ending with the race week, then *recovery*. The default lengths in weeks:

| Race type | Taper (incl. race week) | Specific | Recovery | Long-run cap |
|---|---|---|---|---|
| up to 10 km | 1 | 3 | 1 | 16 km |
| half marathon | 2 | 4 | 2 | 21 km |
| marathon | 2 | 6 | 2 | 32 km |
| ultra | 3 | 6 | 3 | 40 km |

When there isn't enough time, blocks give way in this order, each one only as far as needed: build weeks, then the race-specific block, then the previous race's recovery (down to one week), then the taper (down to the race week), and last the rest of that recovery. Every shortened block gives a warning. Two A or B races in the same week share one race week.

**Build weeks.** Three loading weeks, then a deload week, repeating. The count restarts after a race and runs on into the race-specific block. The quality run rotates hills → intervals → threshold, and each type progresses each time it comes round:

- **Hills:** 6×1′, one rep more each time; at 10 reps, half the reps at double the length (5×2′, …).
- **Intervals:** 5×3′ → 6×3′ → 5×4′ → 6×4′ → …, held at no more than 10 km or 8 % of the week at interval pace.
- **Threshold:** 3×8′ → 3×10′ → 4×8′ → 4×10′ → 5×8′, at most 40′ in total.

The long run grows by 2 km per loading week up to 75 % of the race's cap.

**Deload week:** strides instead of the quality run, the long run at 75 % of the last one, lighter easy runs.

**Race-specific block.** The long run grows to the full cap. The quality run depends on the race:

| Race | Quality run | `hilly = true` |
|---|---|---|
| up to 10 km | intervals and threshold alternating | H → I → H → T |
| half marathon | threshold | H → T |
| marathon | MP repeats, 3×3 km, one rep more each week; every other long run ends with MP km (6, 8, 10 …); at most 90′ at MP per session | H → MP |
| ultra | the build rotation, H → I → T | H → I → H → T |

A hilly race keeps its type, lengths and caps. Hill repeats alone don't prepare you for a hilly course, so the race's own sessions stay in between. Running the long runs on hilly routes is up to you.

**Taper.** In the weeks before the race week: threshold 6 × 1 km and a long run of 75 % of the peak since the last race, 60 % in the week just before the race week. **Race week:** strides; the race takes the long run's place and its km aren't counted. **Recovery:** easy runs only in the first week, then a long run of one easy-run length. After that the long run restarts at 75 % of the previous peak. A shortened long run is never shorter than an easy run.

**C races** are tune-ups inside the training. A C race up to 10 km takes the quality run's place. A longer C race takes the long run's place, and that week has no quality run. Either way its km count, and the progressions continue the next week as if nothing happened.

## Warnings

Warnings never stop the build; they go to the terminal, not on the sheet.

| Code | Warns when |
|---|---|
| C1 | Races are too close: a block was shortened because of the previous race, two races fall in one week, or a C race falls in a recovery block. |
| C2 | The plan is too short: a block before the first A or B race was shortened. |
| C3 | Easy runs + long run grow by more than 10 % from one loading week to the next. |
| C4 | The long run is more than half of the week's planned km. |
| C5 | The long run is above the race's cap: an override, or a starting `long_run_km` above it. |
| C6 | More than 40′ at threshold pace in one session. |
| C7 | More than 10 km, or 8 % of the week, at interval pace in one session. |
| C8 | An overridden threshold pace is more than 10 s/km off the one derived from the race result. |

## How it works inside

```
season.toml ──spec──▶ Season ──layout──▶ phases ──expand + checks──▶ Plan ──export──▶ plan.json ──render (Typst)──▶ plan.pdf
```

All logic is in Python. The Typst template only lays out `plan.json`, which already contains every printed string. Everything except reading the file, the command line and rendering is pure functions on immutable data: no file access, no clock ("today" is passed in). That makes every rule easy to test.

| Module (`src/ttg/`) | Responsibility |
|---|---|
| `spec` | Read and validate the season file; errors name the field. |
| `model` | Immutable data classes: season, races, phases, weeks, plan. |
| `paces` | The `Pace` type and the VDOT derivation. |
| `calendar` | Monday-based weeks, dates and months. |
| `layout` | Phases placed backward from the races, shortened when needed (C1, C2). |
| `sessions` | Session catalogue, progressions and km estimates. |
| `long_run` | Long-run growth, caps, deload, taper and restart. |
| `expand` | Phases → weeks, then the overrides; collects all warnings. |
| `checks` | Warnings C3–C8. |
| `export` | Plan → `plan.json`, including the display strings. |
| `render`, `plan.typ` | Write `plan.json`, compile the template to `plan.pdf`. |
| `cli` | `ttg build`. |

`plan.json` (`schema_version` 2) is the contract between the Python side and the template. Its fields are documented in [`docs/PLAN.md`](docs/PLAN.md) §4.

## Development

Work in the activated virtual environment. Before committing, run what CI (GitHub Actions, Python 3.11 and 3.12) runs:

```sh
ruff check && ruff format --check && mypy && pytest
```

`ruff format` fixes the formatting. CI also builds both reference seasons and keeps their PDFs as a build artefact.

The tests include two acceptance tests on the reference seasons:

- **Golden test** (`tests/test_golden_2026.py`): `seasons/2026.toml` reproduces the reference sheet week by week. Every intentional difference is listed with its reason.
- **Snapshots** (`tests/fixtures/plan-*.json`): the complete `plan.json` of both seasons. After an intended rule change, regenerate them with `TTG_UPDATE_SNAPSHOTS=1 pytest tests/test_snapshots.py` and review the diff.

After a change to the template or to the plan's content, look at a rendered page, not only at the tests.

**Ways of working.** Work is organised in tickets, one branch per ticket (`t-NN-short-name`) and one pull request each. Every training-rule number is a named constant citing its source. A new season-file field needs a recorded decision. The documents in `docs/` are updated in the same change as the code:

- [`docs/PLAN.md`](docs/PLAN.md): goals, requirements, architecture, the `season.toml` and `plan.json` contracts
- [`docs/TRAINING_MODEL.md`](docs/TRAINING_MODEL.md): every training rule with its source, and the coach's review of the 2026 plan
- [`docs/DECISIONS.md`](docs/DECISIONS.md): decisions (D-nnn) with their reasons, and open questions
- [`docs/TICKETS.md`](docs/TICKETS.md): work items and their status
- [`docs/SESSIONS.md`](docs/SESSIONS.md): how tickets were grouped into working sessions
- [`CLAUDE.md`](CLAUDE.md): engineering principles and instructions for the AI assistant that works on the code
