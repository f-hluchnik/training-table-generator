# Decisions

Status values: **Agreed** (confirmed by the owner), **Proposed** (architect's recommendation, waiting for the owner's yes/no), **Superseded**.
Record new decisions at the end. Never renumber.

Origin of D-001 to D-024: architecture review session, 13 Nov 2026. The owner reviewed D-011 to D-020 in this file the same day; his comments are recorded in the decisions.

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

The tool tracks nothing; it only prints the empty sheet. *Amended by D-032:* no colour legend on the sheet.

### D-008 "Life happens" rules printed on the sheet
The order in which sessions are dropped is printed in the footer. The text is configurable.
*Amended 13 Nov 2026:* the default follows the standard order. Short on time: an easy run first, then intensity, then the long run. Tired or ill: intensity first. The owner's original order was intensity first in both cases (`TRAINING_MODEL.md` §8).

### D-009 Phases are laid out automatically, backward from the races
The owner gives races and the start; the compiler places race weeks, tapers, race-specific blocks, recovery and general build weeks (`TRAINING_MODEL.md` §5). Phase lengths can be overridden.
*Supersedes* the first proposal of this session (an explicit phase list written by the owner), which conflicts with D-004.

### D-010 Coach defaults decide the training rules
Where the owner has no opinion (deload depth, long-run share, taper shape, ...), the defaults follow established coaching guidance, with sources, documented in `TRAINING_MODEL.md`. The 2026 plan worked for the owner (no injury, marathon 3:30:02 at the planned pace), but it is one runner and one season: it is a reference to reproduce, not a source of defaults.

---

## Agreed (proposed by the architect, confirmed by the owner in this file)

### D-011 Season file in TOML
One `season.toml` per plan. Python reads it with stdlib `tomllib` (Python ≥ 3.11), so there is no parser dependency. Alternative: YAML (needs PyYAML, and has implicit-typing pitfalls).
Python ≥ 3.11 (the owner has 3.11 and 3.12), always in a virtual environment (`.venv`, git-ignored).

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
*Check:* 3:30:02 marathon → VDOT 44.5, threshold ≈ 4:40/km, interval ≈ 4:18/km, MP 4:59/km (T-03: interval changed from the first estimate of 4:17 after fitting it to the book, `TRAINING_MODEL.md` §2). The owner's 2026 values were T 4:30 and I 4:15, so threshold was about 10 s/km fast (see `TRAINING_MODEL.md` §2).

### D-016 Weekly structure: 3–6 runs, always one quality run and one long run
- `runs_per_week` = 3–6, default 4. Every week has exactly one quality run and one long run; the rest are easy runs (1–4).
- Sessions are not assigned to days: the runner fills the calendar by hand (D-007).

*Owner's question:* would 3, 5 or 6 days be an unnecessary complication? *Answer:* no, as long as only the number of easy runs changes. That touches only the easy-run list (D-022) and the width of the ER column. A second quality session or a mid-week medium-long run (Pfitzinger style) would change the training model, so it would need a new decision.

*Coach:* extra days as easy runs is the standard, safe way to add frequency. Most of a runner's volume should be easy, and spreading it over more runs lowers the long run's share of the week (with 6 runs, 2026's peak week would be 4 × 12 + 10 + 40 = 98 km, so the 40 km long run is 41 % of the week instead of 54 %). Fewer runs (3) keep the quality run and the long run and drop easy runs, consistent with D-008.

### D-017 Race priority A / B / C
- **A:** full taper and recovery.
- **B:** taper shortened by one week.
- **C:** tune-up race. No taper or recovery block; it replaces that week's quality session.

Default: A.
*Why:* without C, any tune-up 10 km in a marathon build would get a full taper and recovery.

*Owner:* agreed.

### D-018 Unambiguous notation
- `–` means no session.
- `RACE` means the race.
- `R` is no longer used (in 2026 it meant both "rest" and "race").
- A long run with marathon-pace km prints as `28 km (10 MP)`.
- Strides print as `S`.

### D-019 Gauge geometry
- **1 km per box** (owner, 13 Nov 2026: more boxes to colour, but the coloured area is the same). Not configurable.
- The width covers the plan's highest planned week, rounded up to the next 10 km, with labels every 10 km.
- Box width shrinks if the gauge would not fit the page.
- The 80 % rule is shown minimally (Q-4): in each row, the border after the box where 80 % of that week's planned km is reached is one step heavier in the line hierarchy (D-024). No other marks.

*History:* a 1 km and a 2 km mock-up were compared on 13 Nov 2026 (140 mm gauge, 80 boxes of 1.75 mm). The owner chose 1 km. In the mock-up the 80 % line was too heavy, which led to D-024.

### D-020 Reference seasons as acceptance tests
- `seasons/2026.toml` must reproduce the reference table, using overrides where 2026 differs from the new defaults. This tests expressiveness.
- `seasons/test-2027.toml` is an arbitrary season (the owner has no 2027 races yet) whose output the owner reviews once and which is then frozen. This tests the defaults. Proposal: half marathon (C) in April, 10 km (C) in early September, marathon (A) in October.

*Amended 13 Nov 2026 (owner):* the 2026 plan has known flaws and is not a perfect example. No input field or rule is added only to reproduce it. `seasons/2026.toml` uses the general features; every remaining difference is listed in the golden test as intentional. Known so far: the grey weekly km in the reference are not the sums of the sessions (its second page subtracts a correction, e.g. 38 printed for a 41 km week), whereas D-006 prints the sum; and the phase labels follow D-026.

---

## Open questions (need the owner)

- **Q-1** *Answered:* Python 3.11 and 3.12 available; work in a virtual environment → D-011.
- **Q-2** *Answered:* only labels → D-021, later replaced by D-026.
- **Q-3** *Answered:* easy runs don't grow → D-022.
- **Q-4** *Answered:* a thicker line, minimal → D-019.
- **Q-5** *Answered:* km only in v1; elevation is a later ticket. The ultra quality sessions are not limited to hills → D-023.
- **Q-6** Website route, later: (a) the Python core in the browser via Pyodide plus a Typst WebAssembly build, which works as a static site on GitHub Pages; (b) port the core to TypeScript; (c) a small server, which cannot run on GitHub Pages. No decision needed now; D-013 keeps (a) and (b) open. Typst-in-browser is not yet verified.

---

## Agreed later in the session

### D-021 Phase names are display labels only
*Superseded by D-026 (13 Nov 2026): the position-based labels were arbitrary.*

All general-preparation weeks are one phase kind, *build*, with the same rules. The rotated phase label on the sheet is a mental map for the runner. Build blocks are labelled by position, one label per 4-week cycle: *base*, *strength*, *volume*, then *volume* again. The labels are configurable in `[sheet]`. Specific, taper, race and recovery phases have their own default labels.

### D-022 Easy runs: predictable background, no growth
The input gives one easy-run length *e* (2026: 12 km).
- **Regular weeks:** all easy runs are *e* (2026: 12+12).
- **Reduced weeks** (deload, taper, race and recovery): the last easy run is *e*/2, rounded to whole km (2026: 12+6).

Easy runs never grow; volume growth comes from the long run and the quality session. Any week can be overridden (2026 weeks 1–3 used the reduced pair).

*Owner:* 12+6 is not a hard rule. Easy runs should be predictable, but they aren't the main thing. So **no other rule is calibrated against them**. The deload rule is defined by its purpose (no intensity, a shorter long run), and the weekly total falls wherever it falls (`TRAINING_MODEL.md` §4).

### D-023 Ultra quality sessions keep the full rotation
The ultra's race-specific block keeps the build rotation H → I → T; it is not limited to hills. What changes for an ultra is the long-run cap (`TRAINING_MODEL.md` §6). Elevation stays out of v1 (Q-5).

### D-024 Line hierarchy: the sheet must look good
The sheet is printed and kept on the wall for months, so it must look aesthetically pleasing, not just correct. All rules come from a small set of named line weights, used consistently across the whole table:

1. **Outline:** the table border, the header separator, and the boundaries between column groups (week | calendar | gauge | phase | prescriptions).
2. **Group:** month boundaries, the 10 km marks in the gauge, and the 80 % marker (D-019).
3. **Hairline:** everything else (day cells, 1 km boxes, rows).

No other weights. The exact values (e.g. 1.5 / 0.75 / 0.25 pt) and greys are chosen in T-08 and approved by the owner on a printed page.

---

## Agreed in session S1 (13 Nov 2026)

### D-025 season.toml schema
The fields and their validation are documented in PLAN §4. Choices beyond PLAN's first draft:
- **Phase lengths live on the race:** optional `taper_weeks`, `specific_weeks`, `recovery_weeks` on `[[race]]`, instead of a separate `[phases]` section keyed by race name. A length belongs to one race, and a mistyped race name cannot silently miss. Not allowed on C races (D-017).
- **A quality override is a table,** `{ type = "H", reps = 10, minutes = 1 }`, not a notation string like `"H 10x1'"`. *Owner:* prefer the explicit form, so the file is clear when coming back to it after months.
- **Display-only settings are in `[sheet]`:** `title` and `rules` (D-008). No phase labels (D-026).
- **`race_result` is always required,** even when every pace is overridden: check C8 compares an overridden threshold pace with the derived one.
- **Overrides per week:** `easy`, `quality`, `long_run_km`, `note`. *Owner:* notes for special weeks are wanted (e.g. *holiday*). There is no label override (D-026).
- Km in the load and in overrides are whole numbers, as printed on the sheet.

### D-026 Phase labels are derived, never typed
*Owner:* labels should not be arbitrary; rather none than random ones. The phase column shows only labels the compiler derives from the phase:
- general build weeks, deloads included → *build*;
- the race-specific block → the race type: *10 km*, *half*, *marathon*, *ultra*;
- the taper including the race week → *taper*;
- recovery after a race → *recovery*.

Not configurable. *Supersedes* D-021 (base / strength / volume by position).

### D-027 plan.json contract
The fields are documented in PLAN §4. Every value the sheet prints is computed in Python, including each day's printed date and whether it is a race day (D-012); the template does no date arithmetic. Days are always 7 per week, `null` after the plan ends. `schema_version` marks the contract for a future web renderer (Q-6). Warnings are structured (`code`, `week`, `message`) and not printed on the sheet.

---

## Proposed in session S4, agreed in S5 (13 Nov 2026)

### D-028 Sheet fonts and drawing values (T-08) — Agreed
- **Fonts:** *Libertinus Serif* for the calendar, titles and footer; *DejaVu Sans Mono* for the prescriptions (ER, QR, LR). Both ship inside the `typst` package, so the sheet looks the same on every machine and in a future browser build (Q-6). The reference was made in Excel with a Garamond-like serif; its font is not redistributable and not present on every machine.
- **Line weights (D-024):** outline 1.5 pt black; group 0.75 pt black; hairline 0.25 pt, 55 % grey. They are named constants at the top of `src/ttg/plan.typ` (moved there in T-09, D-035). The 10 km marks, the month boundaries and the 80 % marker share the group weight; the phase boundaries use the group weight in the phase column only.
- **Geometry:** the gauge box is at most 1.2 mm wide (96 mm for 80 boxes; owner's request, 13 Nov 2026: smaller gauge, wider calendar) and shrinks further until the table fits the page width (A4 landscape, 8 mm margins). Day cells are 10 mm wide. Rows are 6.4 mm and shrink so that long plans stay on one page.

*Owner, S5:* agrees with the printed look, the greys and the weights, and with this decision as written. Phase boundaries keep the group weight (an addition to D-024's list).
- **Long plans (owner, S5):** rows never shrink below 3.7 mm, so the text clears the lines and the cells can still be coloured by hand. Up to about 40 weeks the sheet stays on one page; longer plans continue on a second page with the header repeated (amends R-1 for those plans). At 52 weeks the rows would otherwise be 2.9 mm.

---

## Agreed in session S3 (13 Nov 2026)

### D-029 Phase layout: what gives way, calibrated lengths, calendar edge cases
Proposed by the architect, agreed by the owner. Details and sources in `TRAINING_MODEL.md` §5.
- **Compression order between two races:** build weeks → the later race's specific block, down to 0 → the earlier race's recovery, down to 1 week → the later race's taper, down to the race week → the earlier race's recovery, down to 0. Each block is shortened only as far as needed. *Changed from the first draft*, which stopped the specific block at 1 week and cut the taper first: a single week of race-specific work between two races builds little, a taper week clearly pays.
- **Short plan before the first race:** the same priority. The taper is kept first, then the specific block; build weeks get what is left.
- **Warnings:** one per shortened block, emitted by the layout: C1 when the previous race is the cause, C2 when the plan starts too late. T-07 does not recompute them.
- **Default lengths calibrated:** unchanged except the recovery after a half marathon, 1 → 2 weeks.
- **Calendar:** a week belongs to the month of its Thursday (ISO 8601). A race's week is the week of its first day; the plan ends on the last race's last day, so a multi-day race running from Sunday into Monday adds a short last week. Without `start` or `weeks`, the plan starts next Monday, or today if today is a Monday. Two A or B races in the same week share one race week, the earlier race gets no recovery, and C1 warns.
- `weeks = N` gives a plan of exactly N weeks, ending with the week of the last race day.

---

## Session S5 (13 Nov 2026)

### D-030 Week expansion rules (T-06)
How `ttg.expand` turns phases into weeks. The numbers are named constants in `ttg.expand`, `ttg.long_run` and `ttg.sessions`; sources in `TRAINING_MODEL.md` §4 and §6.

*Agreed with the owner in S5:*
- **No overrides only to copy the reference.** `seasons/2026.toml` keeps the overrides of S1; every other difference from the reference sheet is listed in `tests/test_golden_2026.py` with its reason (amends the plan in D-020 and `TRAINING_MODEL.md` §4 to override the 2026 deload depth).
- **Build cap:** build weeks grow the long run only up to 75 % of the race's cap; the race-specific block grows it to the full cap. Without it, a 32-week marathon plan would hold 32 km for 17 weeks.
- **Restart after a race:** the first loading week after a race starts the long run at 75 % of the previous peak, but never above the next race's build cap. That is how a big race is accounted for: after the 40 km ultra peak the marathon block restarts at 24 km, not 30. *Owner:* asked whether this could be configurable; a week override already covers a one-off, so no new field.
- **Races in planned km:** a C race counts its distance (it is training load); an A or B race does not (as in the reference; a 101 km ultra would also swamp the gauge). In plan.json a C race up to 10 km is a quality run of type `race`; an A or B race, or a longer C race, is the long run (`km` 0 for A or B).
- **A C race from the half marathon up replaces the long run**, and that week has no quality run: the race is the week's long, hard effort. A C race up to 10 km replaces the quality run (D-017). Neither advances the progression it replaces. *Coach, S5:* a half marathon plus a 21 km long run in one week (test-2027 week 5) is two long efforts; tune-up races of that length take the long run's place.
- **The I progression holds within Daniels' limit**: at most the lesser of 10 km and 8 % of the week at I pace (source 11), in whole km, like T at 40′. Without it, test-2027 reached 6 × 5′ (7 km in a 60 km week).
- **Which race:** a race cell prints its distance, `RACE 21 km` (amends D-018's bare `RACE`); the footer lists the races: `races: Half marathon 4 apr (C); …`. The note column is too narrow for names.
- **A C race inside a recovery block warns** (C1): racing returns sooner than the recovery allows. Overrides that bring back quality are taken as is.
- **The long run may plateau at the build cap** in long plans (test-2027: 24 km in weeks 9–24). *Coach, S5:* that is a maintenance long run in a long base period; the deloads give the variation, and the growth resumes in the race-specific block. No change. *Checked against sources afterwards (owner's question):* holding a load for weeks before raising it is Daniels' own advice (about four weeks per step, source 25); 24 km at 5:37 is 2 h 15, inside his 150-minute long-run limit (source 25). As a share of the week (41–44 % of 55–59 km) it is above Daniels' 25–30 %, which is a property of 4 runs a week (D-016) and is policed by C4 at 50 %, not of the plateau.
- **Overrides change only their own week.** Later weeks, the deload and the taper are computed from the rules, not from the overridden values (2026: the taper reduces from the computed 35 km peak, not from week 14's 40 km override). *Owner:* "if I want it to affect the other weeks, I should override them too."
- **Long-run growth stays +2 km per loading week.** *Owner:* "the growth should be around 10 %?" The 10 % rule is about weekly volume, and its only randomised trial found no fewer injuries (Buist et al. 2008, source 21); long-run guidance is usually an absolute 1–2 miles a week (source 22). A percentage would put the biggest steps near the peak. The weekly 10 % stays a warning (C3). *Open:* the owner may still prefer 10 %; it is one function (`long_run.grow`).

*Proposed in the T-06 pull request; agreed by the owner when merging (S5):*
- **3:1 cycle:** a deload after every three consecutive loading weeks (build or specific); any taper, race or recovery week restarts the count. This places 2026's deloads in weeks 4, 8 and 12, and none in the two marathon weeks after the recovery. "Counted from the plan start" (`TRAINING_MODEL.md` §4) would have put one in week 20.
- **Quality rotation:** each type keeps its own progression for the whole plan; a rotation (build H → I → T, which the ultra block continues; I/T for 10 km) continues where it stopped. A C race takes the quality run's place without advancing the rotation.
- **Taper:** in the weeks before the race week, the quality run is T 6 × 1 km and the long run is 60 % of the peak since the last race in the week just before the race week, 75 % earlier. No MP km in the taper's long run. Race week: strides (D-033); the race replaces the long run.
- **Recovery:** easy runs only in the first week; later recovery weeks add a long run of one easy-run length (2026's 12 km "flush").
- **MP cap:** at most 90 minutes at marathon pace in one session (Daniels), for both the MP repeats and the MP km of a long run. A 6-week marathon block would otherwise reach 8 × 3 km.
- **A long run is never shorter than an easy run** when it is reduced (deload, taper, restart).
- **Last column:** the planned km in build, deload and specific weeks; the words *taper*, *race*, *recovery* otherwise, as on the reference sheet. A `note` override replaces either.
- **Notation:** `MP: 3x3 km` with a colon, like every other session (the reference printed `MP 3x3 km`).

### D-031 Checks C3 and C7 (T-07)
- **C3 compares easy runs + long run**, not the total planned km. *Owner, S5:* agreed. On the total, 2026 warned in weeks 2, 6 and 10 only because the rotation moves from hills (estimated 6 km) to intervals (10 km); now it warns only for week 14, the 40 km long-run override.
- **C7 is compared in whole km**, the sheet's precision (D-025). *Agreed (owner, merging #14).* 2026 week 2 (I 5 × 3′ = 3.53 km against 8 % of 44 km = 3.52 km) no longer warns over 0.01 km. The I progression holds within the same limit (D-030), so C7 fires only for overrides; test-2027 has no warnings.
- 2026 warns C8, C4 (weeks 13, 14), C3 (week 14) and C1 (week 23). The ticket expected C4, C8 and the shortened specific block; C3 for week 14 is the override's jump and is kept.
### D-032 No colour legend on the sheet
*Owner, S5:* the sheet is otherwise black and white, so a legend of coloured swatches is out of place. The colour scheme of D-007 stays the runner's own; the sheet and plan.json no longer carry it (`footer.colours` removed from the contract).
*Later, if wanted:* an option for coloured print, where the table is its own legend (e.g. the ER, QR and LR columns tinted in the colours of their runs), ticket T-13.

### D-033 Coach review of test-2027 (T-06)
*Owner, S5:* agrees with test-2027 on condition that an experienced coach would approve it. The coach approves the structure (periodisation, 3:1 deloads, capped T, I and MP work, a 10 km tune-up five weeks out, two-week taper) and changes three rules, agreed by the owner:
- **MP long runs alternate with plain long runs** in the marathon-specific block: MP km (6 → 8 → 10 …) in every other long run; deloads don't count in the alternation. The MP long run is one of the hardest sessions of a marathon plan, and the block also has a weekly midweek MP session; without the alternation test-2027 weeks 29–30 held 27–32 km at MP in 76–79 km weeks (35–40 %). Pfitzinger's schedules alternate MP long runs with plain ones (source 23), and coaches advise alternating them to limit injury and overtraining risk (source 24). The MP stimulus stays weekly through the midweek session.
- **No MP km in a tune-up race's week:** the C race is that week's hard effort. The alternation goes on after it.
- **Race week keeps strides (S)** instead of no quality run: the legs stay sharp, and the race week holds 24 km instead of 18 (about 30 % of the peak; guidance 40–50 %, source 8). Pfitzinger's final weeks keep short runs with strides (source 23).
- Not changed: in a long plan the weekly volume stays flat during the build (test-2027: 55–60 km for about 20 weeks). That is a maintenance base, a consequence of the plan's length and of fixed easy runs (D-022), not of the rules.

test-2027 is frozen as the snapshot `tests/fixtures/plan-test-2027.json` with these rules.

### D-034 Pace legend lists S and H
*Owner, S5:* the legend missed the strides run. The legend now lists every session code printed in the table: `ER`, `S` (e/2 km easy with 6 × 20″ fast, relaxed strides, TRAINING_MODEL §1), `H` (hard uphill effort, jog down; effort-based, no pace, D-015), `I`, `T`, `MP`, `LR`.

---

## Session S6 (13 Nov 2026)

### D-035 Command line output and template location (T-09) — Proposed
- **Output folder:** `ttg build SEASON.toml` writes `plan.json` and `plan.pdf` into `out/<season file name>/` (git-ignored); `-o DIR` writes them straight into `DIR`. *Why:* a fixed `out/` would let a second season silently overwrite the first.
- **Exit codes:** 0 when built, with or without warnings; 1 for an input error (invalid season file or an unreadable one), with nothing written; 2 for a command-line usage error (argparse). Warnings and errors go to stderr, the written paths to stdout.
- **The Typst template lives in the package:** `templates/plan.typ` became `src/ttg/plan.typ`, declared as package data, so a wheel or a non-editable install renders as well. The `templates/` folder held only the prototype's page afterwards (removed in T-10).
