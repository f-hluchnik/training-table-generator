# Tickets

Status: **todo**, **in progress**, **done**, **blocked (reason)**. One branch per ticket, named `t-NN-short-name`.

All decisions needed for T-01–T-10 are made (D-001–D-029). Q-5 and Q-6 are for the later tickets.

```
T-01 ─▶ T-02 ─┬─▶ T-03 ─┐
              ├─▶ T-04 ─┼─▶ T-06 ─▶ T-07 ─▶ T-09 ─▶ T-10
              ├─▶ T-05 ─┘                  ▲
              └─▶ T-08 (from a hand-written plan.json) ─┘
```

---

### T-01 Project skeleton — done
- `pyproject.toml`: package `ttg`, `requires-python >= 3.11` (D-011), `typst` pinned, `pytest` as a dev dependency, console script `ttg`.
- Development in a virtual environment: `python3 -m venv .venv && . .venv/bin/activate && pip install -e '.[dev]'`, documented in the README.
- `src/ttg/` layout, `tests/`, `seasons/`, `templates/`.
- `.gitignore` covers `__pycache__`, `.venv` and build output (`out/`).
- GitHub Actions workflow running `pytest` on push.
- The prototype stays untouched until T-10.

**Done when:** `pip install -e .[dev] && pytest` passes on a clean checkout (with an empty test suite plus one smoke test) and CI is green.

### T-02 Domain model and season file — done
- `model` dataclasses, `spec` loader and validation with clear error messages.
- Fix the `season.toml` schema (PLAN §4).
- Fix the `plan.json` schema and write a hand-made sample for the first 4 weeks of 2026, which T-08 uses.
- Write `seasons/2026.toml` (from `docs/reference/`) and `seasons/test-2027.toml`.

**Done when:** both seasons load; invalid files (bad date, start after the last race, unknown field) fail with a message naming the field; the schema is documented in PLAN §4.

*Done 13 Nov 2026 (S1):* schemas D-025–D-027. The `Pace` type (parse and format) was salvaged here because the loader validates paces; T-03 adds the derivation. Only the input-side model exists; `Phase`, `Week` and `Plan` come with T-04 and T-06. Sample: `tests/fixtures/sample-plan-2026-weeks-1-4.json`.

### T-03 Paces — done
- `Pace` (parse, format) exists since T-02; add what the derivation needs.
- VDOT from a race result and derived easy / MP / T / I (D-015); overrides.
- Verify against Daniels' published tables for at least three VDOT values.

**Done when:** tests pass, including the 3:30:02 check in `TRAINING_MODEL.md` §2, with deviations from the table documented.

### T-04 Calendar and phase layout — done
- Monday weeks; the month of a week; race weeks, multi-day races; plan length from `start` or `weeks`.
- Error when a race falls before the start implied by `weeks` (the loader only checks an explicit `start`).
- Backward layout and compression with warnings (`TRAINING_MODEL.md` §5).
- Calibrate the default lengths table and record the sources.

**Done when:** tests pass for:
- the 2026 layout (with its overrides) matching the reference phases;
- one race;
- two A races 3 weeks apart;
- a C race inside a build;
- a 6-week plan for a marathon (warning);
- start after the race (error).

*Done 13 Nov 2026 (S3):* `ttg.calendar` and `ttg.layout`; the layout rules, the calibrated lengths and the calendar edge cases are D-029. The test cases and their expected layouts were confirmed by the owner before implementation (`tests/test_layout.py`). The layout returns phases (`build`, `specific`, `taper` ending with the race week, `recovery`); deload and race weeks are week kinds that T-06 sets inside them. C races get no phase; T-06 finds their week with `Calendar.week_of`. Warnings C1 and C2 come from the layout. `SeasonError` moved to `ttg.model`, so the pure core doesn't import the loader.

### T-05 Sessions and progressions — done
- Session catalogue (`TRAINING_MODEL.md` §1); 3–6 runs per week (D-016); regular and reduced easy runs (D-022).
- H/I/T progressions salvaged from the prototype, MP repeats, LR with MP km, strides.
- Quality km estimate; T cap.

**Done when:** tests reproduce the 2026 quality sessions and their km.

*Note (T-05):* the session types and reps are reproduced exactly; the km only within 3 km, because the owner's km are hand estimates (`TRAINING_MODEL.md` §3). Left for T-06: LR progression and caps, `LongRun` printing (`28 km (10 MP)`), which week gets which session. The hill rule keeps doubling the duration every 4th occurrence (5×2′, 5×4′, …); not capped, since 2026-length plans never reach it.

### T-06 Week expansion and overrides — done
- Phase rules → weeks, the 3:1 cycle, phase labels (D-026), LR progression and caps, deload, taper, race and recovery weeks.
- `[overrides]`, with an error for an override past the last week; `export` to `plan.json` (D-027).
- Prune `seasons/2026.toml` overrides that the defaults make unnecessary, and list the remaining differences (D-020).

**Done when:** golden test: `seasons/2026.toml` produces the reference table week for week (intentional differences listed in the test). `test-2027` is reviewed by the owner and frozen as a snapshot.

*S5 (13 Nov 2026):* `ttg.expand` (phases → weeks, overrides), `ttg.long_run` (growth, caps, deload, taper, restart), `ttg.export` (plan.json); the rules are D-030. Golden test `tests/test_golden_2026.py`: no overrides were added to copy the reference (owner); every difference is listed with its reason. Snapshots of both seasons in `tests/fixtures/plan-*.json` (`tests/test_snapshots.py`); the generated 2026 plan replaced the hand-transcribed `sample-plan-2026-full.json`. `build_session` gave way to per-type progressions (`progression_session`), so a rotation can continue across phases and past a C race. After the owner's first review (S5): longer C races replace the long run, the I progression is capped, races print their distance and are listed in the footer, a C race in a recovery block warns. Coach review of test-2027 (D-033): MP long runs alternate with plain ones, no MP in a tune-up race's week, strides in race week. The owner approved test-2027 with these rules; `plan-test-2027.json` is frozen.

### T-07 Checks — done
Warnings C3–C8 (`TRAINING_MODEL.md` §7), each a small function with a named threshold constant. C1 and C2 come from the layout since T-04 (D-029); T-07 only merges them.

**Done when:** each check has a firing and a non-firing test; 2026 produces the expected warnings (C4, C8, shortened specific block).

*Done 13 Nov 2026 (S5):* `ttg.checks` (`check(plan)` returns every warning, ordered by week); D-031. 2026 warns C8, C4 (weeks 13, 14), C3 (week 14, the 40 km override) and C1. The snapshots now carry the warnings. Since the I progression is capped (D-030), C6 and C7 fire only for overrides; test-2027 has none.

### T-08 Typst renderer — done
- `plan.typ` (first `templates/plan.typ`, since T-09 `src/ttg/plan.typ`) reproducing the reference sheet from `plan.json` (PLAN §5), starting from `tests/fixtures/sample-plan-2026-weeks-1-4.json`; gauge per D-019 (1 km per box, 80 % marker); line hierarchy per D-024; an ER column wide enough for 4 easy runs.
- Fonts: choose ones bundled or commonly available, and document the choice (D-028).
- Added: `ttg.render` (`render_pdf`, `render_file`; the plan reaches Typst as the `plan` input), and `tests/fixtures/sample-plan-2026-full.json`, the whole 2026 table transcribed for layout tests (MP km in long runs are placeholders). T-06 replaced it with the generated snapshots `plan-2026.json` and `plan-test-2027.json`.
- Packaging: `render.TEMPLATE` points into the repository, so it works from a checkout or an editable install. Shipping the template inside a wheel was left to T-09 (done, D-035).

**Done when:** the hand-made sample renders, and later the full 2026 plan. Compare a page image side by side with the reference PDF; the owner approves the look on a printed page (D-024).

*Done 13 Nov 2026 (S5):* the owner approved the printed look and D-028. Added: a minimum row height of 3.7 mm; plans above about 40 weeks continue on a second page with the header repeated (D-028).

### T-09 Command line — done
- `ttg build SEASON.toml [-o DIR]` writes `plan.json` and `plan.pdf` and prints warnings.
- Exit code 0 when built (with or without warnings), non-zero on input errors.

**Done when:** an end-to-end test builds both seasons.

*Done 13 Nov 2026 (S6):* `ttg.cli` (`build`), `render.write_outputs`; `tests/test_cli.py` builds both seasons and compares `plan.json` with the snapshots. Warnings go to stderr as `warning C4 (week 13): …`, the written paths to stdout; an input error (invalid season, unreadable file) prints `ttg: error: …` to stderr, exits 1 and writes nothing. Without `-o` the output goes to `out/<season file name>/`, so two seasons never overwrite each other. The Typst template moved into the package (`src/ttg/plan.typ`) and is declared as package data, so an installed wheel renders too (D-035). CI builds both seasons and keeps the PDFs as a build artefact.

### T-10 Remove the prototype — todo
Delete the prototype files and Flask (D-014); update the README.

**Done when:** the repository contains only the new package; tests and both builds pass.

### Later (not scheduled)
- **T-11** Website feasibility spike (Q-6): Pyodide + Typst WebAssembly on a static page.
- **T-12** Elevation for mountain ultras (Q-5).
- **T-13** Coloured print, optional (D-032): the colour scheme shown in the table itself, e.g. the ER, QR and LR columns tinted green, yellow and blue, instead of a separate legend.
