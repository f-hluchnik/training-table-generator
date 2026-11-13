# Plan

## 1. Goal

Automate building a printable training-table outline like `docs/reference/2026-marathon-training.pdf` from a handful of inputs. The tool is a plan compiler, not a coach (D-001). The runner prints the sheet, colours it by hand during the season (D-007), and adapts it to life with the rules printed on it (D-008).

## 2. Requirements (owner, 13 Nov 2026)

- **R-1** One A4 landscape page per plan, laid out as in the reference (§5).
- **R-2** Inputs: any number of races on any dates; plan start as a date or as a number of weeks; paces with defaults and overrides; starting load (D-004, D-005).
- **R-3** The plan is an outline: weekly planned km is an approximation; a week is a success at ≥ 80 % (D-006).
- **R-4** Unrealistic or risky input gives warnings, never a refusal (D-001).
- **R-5** "Just the right amount of simple": few required inputs, everything else defaulted and overridable.
- **R-6** Personal tool first; publishing a website later is nice-to-have (D-002).

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
| `expand` | phase rules → weeks; applies `[overrides]` | yes |
| `checks` | warnings C1–C8 (§7) | yes |
| `export` | `Plan` → JSON-ready dict including display strings (D-012) | yes |
| `spec` | read and validate `season.toml` → `Season` (errors for invalid input) | no |
| `render` | write `plan.json`, call Typst with `templates/plan.typ` | no |
| `cli` | `ttg build SEASON.toml [-o DIR]` → `plan.json`, `plan.pdf`; warnings on stderr | no |

**Errors vs warnings:** invalid input (unparsable date, start after the last race, negative km) is an error and nothing is built. Questionable input is a warning, and the plan is still built.

**Dependencies:** `typst` from PyPI (pinned; the Typst compiler bundled, no separate install), `pytest` for development. Nothing else. Python ≥ 3.11 if D-011 holds.

## 4. Data contracts

### season.toml (input, D-011)

Minimal example. Required: the races, a pace anchor and the starting load (what you run now).

```toml
title = "Marathon 2027"
start = 2027-05-03            # or: weeks = 20  (neither → next Monday)

[[race]]
name = "Prague Marathon"
date = 2027-10-10
distance_km = 42.195          # priority = "A" by default

[paces]
race_result = { distance_km = 42.195, time = "3:30:02" }   # anchor for defaults

[load]                        # required: the current easy runs and long run
easy_runs_km = [12, 6]
long_run_km = 15
```

The 2026 reference uses more:

```toml
[[race]]
name = "Beskydská sedmička"
date = 2026-08-28
end = 2026-08-29               # multi-day race: both days bold
distance_km = 101
priority = "B"

[paces]
mp = "4:58"                    # goal pace overrides the derived one
threshold = "4:30"

[phases]                       # length overrides (weeks)
recovery_after = { "Beskydská sedmička" = 2 }

[overrides.5]                  # week 5
easy_runs_km = [12, 12]
[overrides.13]
quality = "H 10x1'"
[overrides.14]
long_run_km = 40

[sheet]
rules = ["drop intensity", "drop an easy run", "drop the long run"]
```

The exact schema is fixed in T-02. Every field beyond the minimal example needs a decision (CLAUDE.md §3).

### plan.json (contract between expand and render, D-012)

```json
{
  "title": "marathon training plan",
  "paces": [{"code": "ER", "pace": "5:30", "label": "easy"}, ...],
  "gauge": {"km_per_box": 2, "boxes": 35, "label_every_km": 10},
  "weeks": [{
    "number": 1, "start": "2026-05-04", "days": [4,5,6,7,8,9,10],
    "bold_days": [], "last_day_index": 6,
    "month": "may", "phase": "base", "kind": "build",
    "easy": {"km": [12, 6], "text": "12+6"},
    "quality": {"code": "H", "km": 8, "text": "H: 6x1'"},
    "long": {"km": 15, "mp_km": 0, "text": "15 km"},
    "planned_km": 41, "note": ""
  }],
  "footer": {"legend": "...", "rules": ["..."], "success": "≥ 80 % of planned km"},
  "warnings": ["..."]
}
```

The renderer reads only this. Month and phase row spans are computed by the template by grouping equal consecutive values; this is layout, not logic.

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
- the pace legend (e.g. `ER=5:30 [easy]; I=4:15+2′ [hard]; …`)
- the colour legend (D-007)
- the life-happens rules and the 80 % rule (D-008, D-006)

Typography follows the reference: a serif face for the calendar, monospace for the prescriptions.

## 6. Acceptance (D-020)

- `seasons/2026.toml` reproduces the reference table week for week (with its overrides). Differences that are intentional (D-018 notation) are listed in the test.
- `seasons/test-2027.toml` is reviewed by the owner once and then frozen as a snapshot.
- Unit tests for paces, calendar, layout (including close races and short plans), progressions and checks.
- The PDF for both seasons builds, and a page image is inspected after renderer changes.

## 7. Later

- Website (Q-6). D-013 keeps the browser route open.
- Elevation for mountain ultras (Q-5).
- Localisation of the sheet labels (Czech), if wanted.
