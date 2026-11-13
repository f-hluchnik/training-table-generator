# Sessions

How the tickets are grouped into working sessions, with the prompt that starts each one. Each session starts by reading `CLAUDE.md`, the docs and the Git state (CLAUDE.md §10).

| Session | Tickets | Prerequisite |
|---|---|---|
| S0 | — architecture review | done 13 Nov 2026 |
| S1 | T-01, T-02 | — (all decisions made) |
| S2 | T-03, T-05 | S1 |
| S3 | T-04 | S1 |
| S4 | T-08 | S1 (can run in parallel with S2/S3) |
| S5 | T-06, T-07 | S2, S3 |
| S6 | T-09, T-10 | S4, S5 |
| S7 | T-14 review, T-15; T-12 evaluated | S6 |
| S8 | T-15 brought to `main`, README | S7 |

## Prompts

**S1**
> Read CLAUDE.md and docs/. Then do T-01 and T-02 on their branches. In T-02, propose the exact season.toml and plan.json schemas before writing code.

**S2**
> Read CLAUDE.md and docs/. Do T-03 (paces) and T-05 (sessions and progressions). Verify the VDOT paces against Daniels' published tables and report any deviation.

**S3**
> Read CLAUDE.md and docs/. Do T-04 (calendar and phase layout). Start by listing the test cases from the ticket and the expected layouts, and get them confirmed before implementing the compression rules.

**S4**
> Read CLAUDE.md and docs/. Do T-08: a Typst template rendering the sample plan.json to match docs/reference/2026-marathon-training.pdf. Show page images side by side with the reference.

**S5**
> Read CLAUDE.md and docs/. Do T-06 and T-07. The golden test on seasons/2026.toml is the acceptance criterion; list every intentional difference from the reference.

**S6**
> Read CLAUDE.md and docs/. Do T-09 and T-10. Build both seasons end to end and attach the PDFs to the PR.
