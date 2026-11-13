# Decisions

Status values: **Agreed** (confirmed by the owner), **Proposed** (architect's recommendation, waiting for the owner's yes/no), **Superseded**.
Record new decisions at the end. Never renumber.

Origin of D-001 to D-020: architecture review session, 13 Nov 2026.

---

## Agreed

### D-001 A plan compiler, not a training coach
The tool turns a few inputs into a plan *outline* and automates the tedious, error-prone parts: dates, session progressions, km arithmetic, totals, checks, layout. It does not try to find the optimal plan for a goal, and it never refuses a plan: unrealistic or risky plans get **warnings**.
*Why:* training algorithms prescribe plans that stop fitting life. The owner adapts the outline during the season with his own rules (D-008).

### D-002 Personal tool first, command line first
The owner is the only known user. A website is nice-to-have, later (D-013 keeps the option open). No web framework now.

### D-003 Renderer: Typst
The PDF is rendered by a Typst template from `plan.json`.
*Verified 13 Nov 2026:* `typst` 0.15.2 from PyPI compiled a table from a TOML file with rows spanning several weeks, rotated month/phase labels, 35 gauge columns and bold race days.
*Rejected:* LaTeX (string templating and escaping from Python, TeX installation, slow); HTML + print CSS (the prototype; output depends on the browser, no direct PDF).

### D-004 Any races, any dates; plan length from start date or week count
Any number of races on any dates. The plan ends on the last race day. Its start is given either as a start date or as a number of weeks; with neither, it starts next Monday. Races too close together, or a plan too short for its race, give a warning, not an error.

### D-005 Paces: defaults plus overrides
Every pace has a computed default (D-015) and can be overridden in the season file.

### D-006 Weekly km is derived, not an input
The planned km of a week is the sum of its planned sessions (quality sessions estimated from warm-up, reps, recoveries, cool-down). It is printed in grey as an approximation. Success rule printed on the sheet: a week counts as done at **≥ 80 %** of the planned km.

### D-007 The sheet is coloured by hand
- **Calendar cells:** one per day, coloured after each run: green easy, yellow quality, blue long, red triangle in a corner for an unexpected event (illness, trip, ...).
- **Gauge:** narrow boxes of 2 km, coloured at the end of the week by the km actually run.

The tool tracks nothing; it only prints the empty sheet and the colour legend.

### D-008 "Life happens" rules printed on the sheet
The order in which sessions are dropped is printed in the footer (default: 1. intensity, 2. an easy run, 3. the long run). The text is configurable. For the coach's comment on the order, see `TRAINING_MODEL.md` §8.

### D-009 Phases are laid out automatically, backward from the races
The owner gives races and the start; the compiler places race weeks, tapers, race-specific blocks, recovery and general build weeks (`TRAINING_MODEL.md` §5). Phase lengths can be overridden.
*Supersedes* the first proposal of this session (an explicit phase list written by the owner), which conflicts with D-004.

### D-010 Coach defaults decide the training rules
Where the owner has no opinion (deload depth, long-run share, taper shape, ...), the defaults follow established coaching guidance, with sources, documented in `TRAINING_MODEL.md`. The 2026 plan worked for the owner (no injury, marathon 3:30:02 at the planned pace), but it is one runner and one season: it is a reference to reproduce, not a source of defaults.

---

## Proposed

### D-011 Season file in TOML
One `season.toml` per plan. Python reads it with stdlib `tomllib` (Python ≥ 3.11), so there is no parser dependency. Alternative: YAML (needs PyYAML, and has implicit-typing pitfalls).
*Depends on:* Q-1 (Python version on the owner's Mac).

### D-012 Three-stage pipeline with `plan.json` as a build artefact
`season.toml` → **expand** → `plan.json` → **render** → `plan.pdf`.
- `plan.json` contains everything the sheet shows: numbers and the pre-formatted display strings. Typst only lays it out; there is no logic in the template.
- Manual changes go into `[overrides]` in `season.toml`, keyed by week number, never into `plan.json`, so regenerating is always safe.

*Why:* there is one place for logic (Python, testable). The JSON is a stable contract a future web renderer could reuse.

### D-013 Pure core
Everything except loading (`spec`), the command line (`cli`) and rendering (`render`) is pure functions on immutable dataclasses: no I/O, no clock.
*Why:* trivial tests, and the website routes (Q-6) stay open, because Python can run in the browser (Pyodide).

### D-014 Replace the prototype
- New package `ttg`.
- Salvage, with tests: the `Pace` type, the H/I/T progressions, and the quality-session km estimate. They reproduce the 2026 numbers.
- Delete `config.py`, `generator.py`, `build.py`, `my_plan.py`, `plan_table.py`, `app.py`, `templates/` and Flask once the new pipeline reproduces the reference season.

*Why:* the prototype's interlocking clamps (about 30 tunables), its forward 4-week cycle that ignores races, and its unsolved multi-race handling are structural. They are not bugs to fix one by one.

### D-015 Default paces from one race result (Daniels VDOT formula)
- **Input:** one recent race result (distance, time).
- **Defaults:** easy, threshold and interval paces derived with Jack Daniels' VDOT equations (Daniels–Gilbert oxygen-cost model). Marathon pace defaults to the race-equivalent pace; a goal pace overrides it.
- **Hills:** effort-based, no pace.

*Why Daniels and not McMillan:* the owner prefers McMillan or Galloway. McMillan's calculator, however, is not published as a formula as far as we know, so it cannot be reproduced exactly; Daniels' equations are published. Zone names on the sheet stay neutral (easy, threshold, interval, MP).
*Check:* 3:30:02 marathon → VDOT 44.5, threshold ≈ 4:40/km, interval ≈ 4:17/km, MP 4:59/km. The owner's 2026 values were T 4:30 and I 4:15, so threshold was about 10 s/km fast (see `TRAINING_MODEL.md` §2).

### D-016 Fixed weekly structure
Default four runs a week: two easy runs, one quality run, one long run. The number of easy runs can be configured (1–3). Sessions are not assigned to days: the runner fills the calendar by hand (D-007).

### D-017 Race priority A / B / C
- **A:** full taper and recovery.
- **B:** taper shortened by one week.
- **C:** tune-up race. No taper or recovery block; it replaces that week's quality session.

Default: A.
*Why:* without C, any tune-up 10 km in a marathon build would get a full taper and recovery.

### D-018 Unambiguous notation
- `–` means no session.
- `RACE` means the race.
- `R` is no longer used (in 2026 it meant both "rest" and "race").
- A long run with marathon-pace km prints as `28 km (10 MP)`.
- Strides print as `S`.

### D-019 Gauge geometry
- 2 km per box.
- The width covers the plan's highest planned week, rounded up to the next 10 km, with labels every 10 km.
- Box width shrinks if the gauge would not fit the page.

*Owner decides (Q-4):* an extra 80 % tick per row.

### D-020 Reference seasons as acceptance tests
- `seasons/2026.toml` must reproduce the reference table, using overrides where 2026 differs from the new defaults. This tests expressiveness.
- `seasons/test-2027.toml` is an arbitrary season (the owner has no 2027 races yet) whose output the owner reviews once and which is then frozen. This tests the defaults. Proposal: half marathon (C) in April, 10 km (C) in early September, marathon (A) in October.

---

## Open questions (need the owner)

- **Q-1** What Python version is on your Mac (`python3 --version`)? ≥ 3.11 is needed for D-011 as proposed.
- **Q-2** Are *base / strength / volume* more than names? In 2026 they used the same rotation; the only change was the second easy run going 6 → 12 km in week 5. Proposal: one *build* kind, with display names taken from its position (base, strength, volume, ...).
- **Q-3** Should easy runs grow by default? Proposal: the easy runs from the input stay fixed, except the shorter one grows by 2 km per 4-week cycle up to the longer one. The rest of the volume growth comes from the long run and the quality session.
- **Q-4** Do you want an 80 % tick in each gauge row (a thick line where 80 % of that week's planned km ends), making the success rule visible on paper?
- **Q-5** Mountain ultras: should v1 handle elevation (vertical metres per week, hill-heavy long runs) or only km? Proposal: km only in v1. An ultra uses the marathon rules with a higher long-run cap and hills as the quality session; elevation is a later ticket.
- **Q-6** Website route, later: (a) the Python core in the browser via Pyodide plus a Typst WebAssembly build, which works as a static site on GitHub Pages; (b) port the core to TypeScript; (c) a small server, which cannot run on GitHub Pages. No decision needed now; D-013 keeps (a) and (b) open. Typst-in-browser is not yet verified.
