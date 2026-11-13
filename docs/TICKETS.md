# Tickets

Status: **todo**, **in progress**, **done**, **blocked (reason)**. One branch per ticket, named `t-NN-short-name`.

All decisions needed for T-01–T-10 are made (D-001–D-029). Q-5 is for the later ticket (T-12). The website (T-11) and coloured print (T-13) were dropped in S6 (D-036).

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

*Note (T-05):* the session types and reps are reproduced exactly; the km only within 3 km, because the owner's km are hand estimates (`TRAINING_MODEL.md` §3). Left for T-06: LR progression and caps, `LongRun` printing (`28 km (10 MP)`), which week gets which session. The hill rule keeps doubling the duration every 4th occurrence (5×2′, 5×4′, …); not capped, since 2026-length plans never reach it. *Limited since S8: reps of at most 2′, 20′ in all, held at 9 × 2′ (D-043).*

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

### T-10 Remove the prototype — done
Delete the prototype files and Flask (D-014); update the README.

**Done when:** the repository contains only the new package; tests and both builds pass.

*Done 13 Nov 2026 (S6):* deleted `config.py`, `generator.py`, `build.py`, `my_plan.py`, `plan_table.py`, `app.py` and `templates/index.html` (the Flask page; `plan.typ` had moved into the package in T-09). Flask was not declared in `pyproject.toml`, so no dependency needed removing. Nothing in `src/` or `tests/` referenced the prototype. The salvaged parts (`Pace`, the H/I/T progressions, the quality-km estimate) live on in `ttg.paces` and `ttg.sessions`. Both seasons build unchanged (the snapshots are identical).

### T-14 Review and refactoring — done
A whole-project review by an architect and an engineer (S7, 13 Nov 2026), and the owner's answers to its questions (Q-7–Q-10).

*Bugs fixed:*
- **Long plans lost weeks.** A month or phase band longer than a page could not break (Typst cells spanning only fixed-height rows are unbreakable by default), so a real 60-week plan put the title alone on page 1, the table on page 2 and cut off weeks 55–60. The bands are now breakable, and a band continued on the next page is labelled again there (D-037). The old test repeated 2026's short bands and missed it; the new ones render a generated 60-week plan.
- **Crashes instead of input errors:** `nan`/`inf` distances, a season file that is not UTF-8, an override key like `²`, and a deload after three long C races (an `assert`). The first three are `SeasonError`s naming the field; the deload reduces the plan's first long run.
- **Two adjacent phases with one label** (back-to-back tapers) merged into one band: `plan.json` 2 numbers the phases (D-037).

*Behaviour changed (owner):* an override can no longer replace a race (D-038); C4 and C5 skip a race in the long run's place (D-039).

*Code:* `Plan.warnings` holds every warning (`expand` runs the checks; `export(plan)` takes no separate list, so it cannot drop C3–C8 by mistake). `ruff` and `mypy --strict` in CI (D-040), with the typing they asked for: required `spec` fields read through a `REQUIRED` default, `Session` repetitions narrowed. `Race.date` no longer shadows `datetime.date`. `gauge.km_per_box` dropped, `render_file` removed (unused), `MARATHON_KM` defined once, the template computes its bands once. Shared test helpers in `tests/support.py`.

*Verified:* both reference seasons produce the same `plan.json` as before except for the contract change (`schema_version` 2, `weeks[].phase`, no `km_per_box`); their sheets are unchanged by eye; the 60-week plan has two pages with every week and every band labelled.

### T-15 Hilly races — done (merged in #21; #20 had gone into the T-14 branch)
Q-8 (b), owner S7: a `hilly` marker on a race leans its race-specific block into hill repeats, as an experienced coach would adjust it; the race type, phase lengths and caps stay by distance.

*S7:* `[[race]] hilly = true` (D-041, proposed by the coach, for the owner in the PR). The specific block alternates hill repeats with the race's own intensity, threshold instead of marathon pace; no MP km in the long runs; the footer marks the race `(A, hilly)`. Everything outside the specific block is unchanged (tested). Both reference seasons are unchanged (no hilly race).

*S8 (13 Nov 2026):* PR #20 was stacked on #19 and merged 14 seconds after #19, so it went into `t-14-review-refactor` instead of `main`. The same commit is brought to `main` in a new pull request, unchanged; checked again there: lint, types, 331 tests, both reference seasons' `plan.json` identical to `main`. Checked on long hilly plans: with hills every other week, the uncapped hill progression peaks at 8 × 2′ in a hilly test-2027, 6 × 4′ in a 43-week and 9 × 4′ (36′ of hard climbing) in a 52-week hilly plan, the order of the 40′ threshold cap. *Owner, S8:* cap it, and label no race-specific block with a distance its race is not. Then (owner): never more than 2′ of uphill running in one rep, and a warning for overrides. Done in the same PR: hill reps of at most 2′ and at most 20′ of effort, the progression held at 9 × 2′, warning C9 for overrides (D-043); a 30 km race's block is labelled *specific* (D-042). Both reference seasons unchanged; a 30 km hilly sheet inspected. The README was rewritten to explain the whole tool without the other documents.

### T-16 Band labels fit their bands — in review
*Owner, S8:* *recovery* overlapped its band on a generated sheet. Every month and phase label now shrinks to fit its band; a phase band too short for its word at 5 pt shows a short form from `plan.json` (`phase_short`, schema 3), e.g. *rec.* for a one-week recovery (D-044). Tested: on a 38-week plan with one-week taper and recovery bands every label fits, the short forms print at ≥ 5 pt; the 2026 sheet keeps every label at 8 pt, test-2027 all but its one-week *oct* (7.7 pt); the reference seasons' `plan.json` differ only by `phase_short` and the version. Sheet inspected.

*Also reported (S8):* an 18 km race's block printed *half*. On `main` (D-042, merged in #21) it prints *specific*, checked with an 18 km season; the sheet was most likely built from a checkout before #21 (`git pull`).

### T-17 No 80 % marker — in review
*Owner, S8:* remove the 80 % marks from the gauge and reword the success rule (D-045). The marker and `weeks[].box_80pct` are gone (`plan.json` 4); the footer reads "A week counts as fully done at 80 % of its planned km." Branched from T-16 (#22), which also changes the `plan.json` version. Snapshots regenerated: only `box_80pct`, the footer text and the version change. 2026 sheet inspected.

### T-18 Output next to the season file — in review
*Owner, S8:* the output folder depended on the folder `ttg` was run from. The default is now `out/<season file name>/` next to the season file (D-046); `-o` is unchanged. Tested: a build from another folder writes next to the season file and creates no `out/` in the working folder; checked by hand from two folders.

### T-19 A quiet footer — in review
*Owner, S8:* the legend should look minimalistic. The footer's typography is quieter (D-047): code bold, pace plain, description grey, no punctuation clutter; races and rules separated by grey dots. Two legend texts tidied in `plan.json` (`4:15 + 2′ jog`, *fast, relaxed strides*). Snapshots regenerated, diff reviewed; 2026 and a hilly test-2027 sheet inspected. *Owner's review:* a colon after each code; the race dates set apart (bold, first; `footer.races` structured, `plan.json` 5); then, after trying a grey `|` and a map-like key, hierarchy by type alone: descriptions italic instead of grey, a thin black rule between entries. Sheet inspected again (full page).

### Later (not scheduled)
- **T-12** Elevation for mountain ultras (Q-5). *Evaluated in S7; parked by the owner (Q-7).* The race-type gap it found is covered by T-15 (`hilly`).

#### T-12 evaluation (S7)
The ticket is a title only: no requirement and no done-criterion. *Owner, S7:* keep it parked (Q-7); Q-8 became T-15.

- **The real gap is not elevation on the sheet but the race type.** The type comes from the distance alone (`RaceType.of`), so a 30 km mountain race with 2,000 m+ is a *marathon*: MP repeats, MP long runs, a 32 km cap. That is the wrong training for it. The 2026 ultra (101 km, about 5,300 m+) worked only because any distance above a marathon is an *ultra*.
- **Coach:** for mountain races the specific stimulus is the elevation change per km of the race, not the weekly total; Koop matches the race's gain and loss per mile across the weekly training and finds no dose-response in total vertical (CTS, trainright.com). Hill repeats are already in the ultra rotation (D-023).
- **Smallest useful design** (if it is ever scheduled):
  1. One optional input, `[[race]] elevation_gain_m` (default 0; a new field needs a decision, CLAUDE.md §3).
  2. The race type uses ITRA's km-effort, km + gain / 100 (itra.run), or only replaces MP work (Q-8).
  3. Long runs of the race-specific block print a climbing target at the race's density, `30 km (1600 m+)`, like `28 km (10 MP)` (D-018). No new column and no weekly elevation gauge: the sheet has no room, and the runner plans the route.
  4. `plan.json`: an additive `long.climb_m`, the next `schema_version`.
- **Out of scope:** descent, time-on-feet long runs, per-session elevation, weekly totals.
- **Cost:** about one session (spec, model, expand, export, tests). Check that the LR column (27 mm) fits `32 km (1700 m+)`. `seasons/2026.toml` can stay without elevation so the golden test is untouched.
- **Recommendation:** park it until a season has a mountain race; then do points 1–3.
