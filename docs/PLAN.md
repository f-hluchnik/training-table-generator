# Plan

## 1. Goal

Automate building a printable training-table outline like `docs/reference/2026-marathon-training.pdf` from a handful of inputs. The tool is a plan compiler, not a coach (D-001). The runner prints the sheet, colours it by hand during the season (D-007), and adapts it to life with the rules printed on it (D-008).

## 2. Requirements (owner, 13 Nov 2026)

- **R-1** One A4 landscape page per plan, laid out as in the reference (§5). Plans above about 40 weeks continue on a second page, so the cells stay large enough to colour (D-028).
- **R-2** Inputs: any number of races on any dates; plan start as a date or as a number of weeks; paces with defaults and overrides; starting load (D-004, D-005).
- **R-3** The plan is an outline: weekly planned km is an approximation; a week is a success at ≥ 80 % (D-006).
- **R-4** Unrealistic or risky input gives warnings, never a refusal (D-001).
- **R-5** "Just the right amount of simple": few required inputs, everything else defaulted and overridable.
- **R-6** A personal command-line tool; no website (D-002, D-036).

**Non-goals:** recording or analysing actual runs, adapting the plan to past performance, assigning sessions to days, multi-sport training.

## 3. Architecture

```
seasons/2026.toml ──spec──▶ Season ──layout──▶ phases ──expand──▶ Plan ──checks──▶ warnings
                                                                    │
                                                         plan.json ◀┘──render (Typst)──▶ plan.pdf
```

Modules of the package `ttg`. Everything marked *pure* follows D-013.

| Module | Responsibility | Pure |
|---|---|---|
| `model` | immutable dataclasses: `Season`, `Race`, `Paces`, `Phase`, `Week`, `Session`, `Plan` | yes |
| `paces` | `Pace` type; defaults from a race result (D-015); overrides | yes |
| `calendar` | Monday-based weeks, week ↔ date, month of a week (the month containing its Thursday) | yes |
| `layout` | backward phase layout, compression, layout warnings (`TRAINING_MODEL.md` §5) | yes |
| `sessions` | session catalogue, progressions, km estimate (§1, §3, §4) | yes |
| `long_run` | long-run growth, caps, deload, taper and restart (§4, §6) | yes |
| `expand` | phase rules → weeks; applies `[overrides]` (D-030) | yes |
| `checks` | warnings C1–C8 (§7) | yes |
| `export` | `Plan` → JSON-ready dict including display strings (D-012) | yes |
| `spec` | read and validate `season.toml` → `Season` (errors for invalid input) | no |
| `render` | write `plan.json`, call Typst with the template `src/ttg/plan.typ` (D-035) | no |
| `cli` | `ttg build SEASON.toml [-o DIR]` → `plan.json`, `plan.pdf`; warnings on stderr | no |

**Errors vs warnings:** invalid input (unparsable date, start after the last race, negative km) is an error and nothing is built. Questionable input is a warning, and the plan is still built.

**Dependencies:** `typst` from PyPI (pinned; the Typst compiler bundled, no separate install), `pytest` for development. Nothing else. Python ≥ 3.11, in a virtual environment (D-011).

## 4. Data contracts

### season.toml (input, D-011, D-025)

Required: at least one race, a race result as the pace anchor, and the starting load. Everything else is optional. Unknown fields are errors.

Minimal example:

```toml
start = 2027-05-03            # or: weeks = 20  (neither → next Monday)

[[race]]
name = "Prague Marathon"
date = 2027-10-10
distance_km = 42.195          # priority = "A" by default

[paces]
race_result = { distance_km = 42.195, time = "3:30:02" }

[load]
easy_run_km = 12
long_run_km = 15
```

All fields:

| Field | Type | Default | Meaning |
|---|---|---|---|
| `start` | date | — | Week 1 is the Monday-based week containing it. At most one of `start` and `weeks`; neither → the next Monday, today if it is a Monday (D-004, D-029). |
| `weeks` | integer ≥ 1 | — | Plan length: the plan ends with the week of the last race day and has this many weeks. |
| `[sheet] title` | text | `"training plan"` | Title printed on the sheet. |
| `[sheet] rules` | list of texts | TRAINING_MODEL §8 | "Life happens" rules in the footer (D-008). |
| `[[race]] name` | text | required | Unique. |
| `[[race]] date` | date | required | First race day; its week is the race week (D-029). |
| `[[race]] end` | date ≥ `date` | — | Last day of a multi-day race. |
| `[[race]] distance_km` | number > 0 | required | Decides the race type (TRAINING_MODEL §5). |
| `[[race]] priority` | `"A"`, `"B"`, `"C"` | `"A"` | D-017. |
| `[[race]] taper_weeks` | integer ≥ 1 | by distance | Includes the race week (D-009). Not for C races. |
| `[[race]] specific_weeks` | integer ≥ 0 | by distance | Race-specific block. Not for C races. |
| `[[race]] recovery_weeks` | integer ≥ 0 | by distance | Recovery after the race. Not for C races. |
| `[paces] race_result` | `{ distance_km, time }` | required | Anchor for the default paces (D-015); `time` is `"h:mm:ss"` or `"m:ss"`. |
| `[paces] easy`, `mp`, `threshold`, `interval` | `"m:ss"` per km | derived | Overrides (D-005). |
| `[load] easy_run_km` | integer ≥ 1 | required | Length of an easy run (D-022). |
| `[load] long_run_km` | integer ≥ 1 | required | Long run of the first week. |
| `[load] runs_per_week` | integer 3–6 | 4 | D-016. |
| `[overrides] N` | table | — | Changes to week N (D-012); fields below. |
| `… easy` | `"regular"`, `"reduced"` | computed | Easy-run pattern (D-022). |
| `… quality` | table, see below | computed | The quality session. |
| `… long_run_km` | integer ≥ 0 | computed | 0 = no long run. |
| `… note` | text | computed | Replaces the last column (planned km or *taper*, *race*, …). |

A quality session is `{ type, reps, minutes | km }`. `type` is `"H"`, `"I"`, `"T"` or `"MP"` with `reps` and exactly one of `minutes` or `km` per repetition; `"S"` (strides) and `"none"` take no other field. Examples:

```toml
[overrides]
1  = { easy = "reduced" }
13 = { quality = { type = "H", reps = 10, minutes = 1 } }
20 = { quality = { type = "MP", reps = 3, km = 3 }, note = "check" }
```

**Errors** (nothing is built; the message names the field, e.g. `race[2].date: …`): unknown field, wrong type, value out of range, missing required field, `start` together with `weeks`, a race ending before `start`, duplicate race names, `end` before `date`, a phase length on a C race, a race before week 1 when the start comes from `weeks` or defaults to next Monday (checked when the calendar is built, `ttg.calendar`), an override for a week past the end of the plan (`overrides.N`, checked by `ttg.expand`).

An override changes only its own week; the progressions of the following weeks ignore it (D-030).

The 2026 reference and the test season are in `seasons/`.

### plan.json (contract between expand and render, D-012, D-027)

Everything the sheet shows, computed in Python, including the display strings. The template only lays it out. A hand-made sample of 2026 weeks 1–4 is `tests/fixtures/sample-plan-2026-weeks-1-4.json`.

```json
{
  "schema_version": 1,
  "title": "marathon training plan",
  "paces": [{"code": "I", "pace": "4:15+2'", "label": "hard"}, ...],
  "gauge": {"km_per_box": 1, "boxes": 80, "label_every_km": 10},
  "weeks": [{
    "number": 23,
    "days": [{"date": "2026-10-05", "text": "5", "race": false}, ..., {"date": "2026-10-10", "text": "10", "race": true}, null],
    "month": "oct",
    "kind": "race",
    "phase_label": "taper",
    "easy": {"km": [12, 6], "text": "12+6"},
    "quality": {"type": "none", "km": 0, "text": "–"},
    "long": {"km": 0, "mp_km": 0, "text": "RACE 42 km"},
    "planned_km": 18, "box_80pct": 15, "note": "race"
  }, ...],
  "footer": {
    "races": ["Beskydská sedmička 28–29 aug (B)", "Běhej Lesy Lednice 10 oct (A)"],
    "rules": ["Short on time: …", "Tired or ill: …"],
    "success": "A week counts at ≥ 80 % of the planned km."
  },
  "warnings": [{"code": "C4", "week": 14, "message": "…"}]
}
```

| Field | Meaning |
|---|---|
| `paces` | The pace legend, in print order; `pace` and `label` may be empty. |
| `gauge.boxes` | The highest planned week rounded up to the next `label_every_km` (D-019). |
| `weeks[].days` | Always 7 entries, Monday to Sunday; `text` is the printed day of the month; `race` marks a race day (printed bold); `null` for days after the plan ends on the last race day. |
| `weeks[].month` | The month containing the week's Thursday. |
| `weeks[].kind` | `build`, `deload`, `specific`, `taper`, `race`, `recovery`. |
| `weeks[].phase_label` | The phase column text (D-026). |
| `weeks[].quality.type` | As in the season file: `H`, `I`, `T`, `MP`, `S`, `none`; or `race` for a C race up to 10 km, which replaces the quality run (D-017, D-030). |
| `weeks[].quality.km` | The estimate of `TRAINING_MODEL.md` §3; a C race counts its distance (D-030). |
| `weeks[].long.km` | The long run. A race replaces it in its race week, or a C race from the half marathon up; an A or B race counts 0, a C race its distance (D-030). |
| `footer.races` | Every race, in date order, as printed under the pace legend: name, date(s), priority (D-030). |
| `weeks[].box_80pct` | The gauge box after which the 80 % border is drawn (D-019). |
| `weeks[].note` | The text of the last column: the planned km in build, deload and specific weeks; *taper*, *race* or *recovery* otherwise; or the override's `note` (D-030). |
| `warnings` | Not printed on the sheet; `week` may be `null`. |

All km are whole numbers. Month and phase cells span the consecutive weeks with equal values; this grouping is layout, not logic.

## 5. The sheet (R-1)

Column order as in the reference:

1. Month (rotated, spanning its weeks)
2. Week number
3. Mon–Sun day numbers: the colouring cells; race days bold; the race week ends on race day
4. Gauge (D-019)
5. Phase (rotated, spanning its weeks)
6. ER
7. QR
8. LR
9. Planned km (grey) or a note (e.g. *taper*, *race*)

Below the table:
- the pace legend, one entry per session code in the table (e.g. `ER=5:30 [easy]; S=6 km + 6×20″ [easy, with fast relaxed strides]; H [hard uphill effort, jog down]; I=4:15+2′ [hard]; …`, D-034)
- the life-happens rules and the 80 % rule (D-008, D-006)

No colour legend: the sheet is black and white, and the colours the runner uses are his own (D-032).

Typography follows the reference: a serif face for the calendar, monospace for the prescriptions. Line weights follow D-024.

## 6. Acceptance (D-020)

- `seasons/2026.toml` reproduces the reference table week for week (with its overrides). Differences that are intentional (D-018 notation) are listed in the test.
- `seasons/test-2027.toml` is reviewed by the owner once and then frozen as a snapshot.
- Unit tests for paces, calendar, layout (including close races and short plans), progressions and checks.
- The PDF for both seasons builds, and a page image is inspected after renderer changes.

## 7. Later

- Elevation for mountain ultras (Q-5).
- Localisation of the sheet labels (Czech), if wanted.
