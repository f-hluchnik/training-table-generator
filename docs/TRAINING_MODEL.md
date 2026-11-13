# Training model

The training rules the compiler applies, with sources. Each rule is marked:

- **[source]**: established coaching guidance, with a reference (§10).
- **[2026]**: taken from the owner's 2026 plan.
- **[default]**: our own choice, to be checked in the ticket that implements it.

Every number here becomes a named constant in code, with the same tag (CLAUDE.md §3).

## 1. Vocabulary

| Code | Session | Notes |
|---|---|---|
| ER | easy run | easy pace |
| S | easy run with strides | *e*/2 km with e.g. 6 × 20″ fast, relaxed; replaces the quality run in deload weeks |
| H | hill repeats | effort-based, no pace; recovery = jog down (≈ effort duration) [2026] |
| I | intervals (VO₂max) | I pace, 2′ jog recovery [2026] |
| T | threshold intervals | T pace, 2′ jog recovery [2026] |
| MP | marathon-pace repeats | e.g. 3 × 3 km at MP [2026] |
| LR | long run | easy pace; optionally the last *n* km at MP, printed `28 km (10 MP)` (D-018) |
| RACE | the race | replaces the long run of its week |

## 2. Paces (D-005, D-015)

- **Input:** one recent race result. Defaults are derived with Daniels' VDOT model **[source 1, 2]**; any pace can be overridden.
- **MP:** defaults to the race-equivalent marathon pace; a goal pace overrides it.

Implemented in `ttg.paces` (T-03). The fractions of VDOT are named constants:

| Pace | Rule | Basis |
|---|---|---|
| Threshold | pace at 88 % of VDOT | **[source 1, 2]** |
| Interval | pace at 97.5 % of VDOT | **[default]**, fitted to the book (Daniels gives 95–100 %) |
| Easy | pace at 70 % of VDOT | **[default]**; Daniels' range is 59–74 % **[source 2]**, the book's range at VDOT 51 is 63–73 % |
| MP | pace of the race-equivalent marathon time | **[source 1, 2]**, D-015 |

**Verification against Daniels' tables (T-03).** I did not have the book. The values below are transcribed from secondary sources (sources 1 and 12); tests in `tests/test_paces.py`. Table values are whole seconds (per mile in the 2nd edition, per 400 m for I), so the comparison allows for rounding.

| Check | Table | Computed | Deviation |
|---|---|---|---|
| VDOT of the 5 km, 10 km and marathon times for VDOT 50, 55, 58 (2nd ed. table 3.1) | 50 / 55 / 58 | within 0.1 | none beyond the rounding of the times |
| M, VDOT 50 / 55 / 57 (2nd ed. table 3.2) | 4:31 / 4:10 / 4:03 per km | ≤ 1 s/km | none |
| T, VDOT 50 / 55 / 57 (2nd ed.) | 4:15 / 3:56 / 3:49 per km | ≤ 0.3 s/km | none |
| I, VDOT 50 / 55 / 57 (2nd ed., 93 / 87 / 85 s per 400 m) | 3:52.5 / 3:37.5 / 3:32.5 | +2.4 / −0.1 / −1.3 s/km | up to 2.4 s/km, the table's resolution (1 s per 400 m = 2.5 s/km) |
| M / T / I, VDOT 51 (4th ed. table 5.2, per km) | 4:27 / 4:11 / 3:51 | −0.4 / +0.1 / +0.1 s | none |
| E, VDOT 51 | 4:52–5:29 per km | default 5:02 | inside the range |

Not verified: the E pace beyond VDOT 51, the R pace (not used), and VDOT values outside 50–58. The formulas are the published Daniels–Gilbert equations, so the values should hold elsewhere in the usual range, but I have not checked them there.

Result for the owner's marathon, 3:30:02 → VDOT 44.5:

| Pace | Derived | 2026 plan | Comment |
|---|---|---|---|
| Easy | 5:37 (range 5:22–6:26) | 5:30 | inside the range |
| MP | 4:59 | 4:58 | spot on (raced 4:59) |
| Threshold | 4:40 | 4:30 | ≈ 10 s/km fast; it implies VDOT ≈ 46.6 |
| Interval | 4:18 | 4:15 | consistent; the first estimate here (≈ 4:17) used 98 % |

For comparison, Daniels' table for VDOT 51 gives M 4:27, T 4:11, I 3:51 per km **[source 1]**: T ≈ M − 16 s, I ≈ T − 20 s.

McMillan names the same intensities Endurance, Stamina and Speed, and also starts from a race result **[source 3, 4]**. His exact formula is not published, hence Daniels (D-015).

## 3. Week structure (D-016)

3–6 runs, default 4: one quality run, one LR, the rest easy runs (D-016). Easy runs are *e* each; in reduced weeks the last one is *e*/2. They never grow and are not a lever for anything else (D-022). The weekly planned km is the sum of all runs (D-006). Quality-run km are estimated as follows **[2026, prototype]**: 10′ warm-up + reps × work + (reps − 1) × recovery + 10′ cool-down, everything at easy pace except the work itself (hill efforts also counted at easy pace). Reps given in km (MP repeats, T 6 × 1 km) count the km themselves, with 2′ easy recoveries. A strides run (S) counts as half an easy run, rounded up. A C race in place of the quality run counts its distance; an A or B race in place of the long run is not counted (D-030). All km are rounded to whole km, halves up. Implemented in `ttg.sessions` (T-05) and `ttg.expand` (T-06).

**Against the 2026 reference.** The sessions (type, reps, minutes) are reproduced exactly for weeks 1–3, 5–7, 9–11 and 14–15; week 13 is the override (rule: 9 × 1′, owner: 10 × 1′). The owner's quality km (second page of the reference) are hand estimates and deviate from the estimate:

| Session | Owner | Estimate |
|---|---|---|
| H 6–9 × 1′ | 8, 8, 9, 9 | 5.6, 6.0, 6.4, 6.7 (2.0–2.6 less) |
| I 5×3′, 6×3′, 5×4′, 6×4′ | 8, 9, 9, 10 | 8.6, 9.7, 9.8, 11.1 (−0.6 to +1.1) |
| T 3×8′, 3×10′, 4×8′, 4×10′ | 10, 11, 11, 11 | 9.7, 11.0, 11.8, 13.6 (−0.3 to +2.6) |

The test allows 3 km and pins the estimate itself. The hill km are low because the estimate counts the effort at easy pace and cannot know the route to the hill; no rule is added to reproduce the owner's numbers (D-020).

## 4. Phase kinds

### build (general preparation)
- **3:1 cycle:** three loading weeks (build or specific), then one deload week **[2026, source 6]**. Any taper, race or recovery week restarts the count, so the cycle runs on from the build into the specific block and starts afresh after a race (D-030).
- **Quality rotation:** H → I → T **[2026]**. Each type progresses each time it occurs **[2026]**:
  - H: 6×1′ → +1 rep each time; at 10 reps, halve the reps and double the duration. In 2026 the owner wrote 10×1′ for the 4th occurrence, where this rule gives 9×1′; that week is an override in the reference season.
  - I: 5×3′ → 6×3′ → 5×4′ → 6×4′ → 5×5′ …
  - T: 3×8′ → 3×10′ → 4×8′ → 4×10′ → 5×8′, held there by the cap of **40′ total at T** (tempo work is 15–40 min) **[source 5]**.
- **LR:** +2 km per loading week **[2026: +2–3 km]**, up to the build cap (§6); the cap stops growth but never cuts a longer starting long run. Coaches usually add 1–2 miles a week to the long run **[source 22]**; the "10 % rule" is about weekly volume and has weak evidence **[source 21]**, so it is only a warning (C3). After a race the LR restarts at 75 % of the previous peak, at most the next race's build cap **[default, owner S5]**. A reduced LR (deload, taper, restart) is never shorter than an easy run **[default]**.
- **Easy runs:** regular (D-022).
- **Label:** *build*, for deloads too (D-026).

### deload (every 4th build week)
- Defined by its purpose: **no intensity** (the quality run becomes S) and a **shorter long run, 75 % of the last build LR** **[default]**. The easy runs are reduced (D-022).
- The weekly total is a consequence, not a target. With 2026's numbers it lands at about 70–80 % of the previous week, depending on the easy runs, which is inside the usual 10–30 % cut **[source 6, 7]**. No check polices it.
- The week still feels like rest: no intensity and a clearly shorter long run.
- 2026 cut to about 50–55 % (61 → 33 km). That is deeper than standard, which is acceptable but not the default; the golden test lists it as a difference (D-030).

### specific (race-specific preparation; content depends on race distance)

| Race | Quality run | Long run |
|---|---|---|
| ≤ 10 km | I and T alternating | capped lower (§6) |
| half marathon | T | — |
| marathon | MP repeats: 3×3 km, +1 rep a week **[2026]** | the last MP km grow 6 → 8 → 10 … **[default]** |

The long run grows to the full cap (§6) only here. Marathon-pace work is capped at 90 minutes per session, for the repeats and for the MP km of a long run: Daniels' limit is the lesser of 90 min and 16 miles **[source 20]**. With 2026's MP (4:58) that is 6 × 3 km and 18 km. Deloads inside the block are as in build.
| ultra | build rotation H → I → T (D-023) | toward the ultra cap |

Elevation (vertical metres) is out of scope in v1 (Q-5).

### taper (ends with the race week)
- **Marathon (2 weeks including race week):** about 70–75 % of peak volume, then 40–50 % in race week **[source 8]**. Intensity is kept short (e.g. T 6×1 km **[2026]**), and the last LR is about 60 % of the peak LR. 2026 did 69 % and 35 %: close to the guidance.
- **Rule for every distance (D-030):** each taper week before the race week has T 6 × 1 km **[2026]** and a LR of 75 % of the peak since the last race **[default]**, 60 % in the week just before the race week **[source 8]**, without MP km. The race week has no quality run.
- Lengths: see §5.

Taper, race and recovery weeks all use the reduced easy pair (D-022).

### race week
The race replaces the LR. The race day prints bold in the calendar, and the week's row ends on race day.

### recovery (after a race)
- **Week 1:** easy runs only, no LR.
- **Week 2 and later:** easy runs plus a LR of one easy run's length ("flush" in 2026, 12 km) **[2026]**.
- After that, the next phase starts.
- Pfitzinger uses a 5-week return-to-running schedule after a marathon **[source 9]**. Our recovery block is shorter because the next phase starts gently anyway; a warning fires if quality returns sooner than the defaults below.

## 5. Phase layout (D-009, D-029)

The compiler works **backward from each race** (A and B; C races only replace one quality run, D-017).

Default lengths in weeks, calibrated in T-04. A "2-week taper" in the sources is about 14 days before race day; here it is the race week plus the week before.

| Race type | Distance | Taper incl. race week | Specific | Recovery after |
|---|---|---|---|---|
| 10 km | ≤ 10 km | 1 **[source 14]** | 3 **[default]** | 1 **[source 15]** |
| half | ≤ half marathon | 2 **[source 14]** | 4 **[default]** | 2 **[source 15]** |
| marathon | ≤ marathon | 2 **[source 13, 8; 2026]** | 6 **[source 16]** | 2 **[2026; source 9 is longer, see §4 recovery]** |
| ultra | longer | 3 **[source 17, 18; 2026]** | 6 **[source 18]** | 3 **[source 19]** |

- **Race type** from the distance, with 0.1 km slack so that 21.1 or 42.2 count as a half or a full marathon **[default]**.
- **Taper:** the meta-analysis of Bosquet et al. found a two-week taper optimal **[source 13]**; coaching guides give 7–10 days for 10 km and 10–14 days for a half **[source 14]**. For ultras, coach-written 100 km plans use two taper weeks plus the race week **[source 17]**; Koop places the biggest training block 6–9 weeks before the race **[source 18]**, which leaves 3 weeks.
- **Specific:** Daniels' phases are 6 weeks each, at least 3 when time is short **[source 16]**. For 10 km and the half no source gives a separate length: our default.
- **Recovery:** Pfitzinger plans one recovery week after a key race and notes that 15 km or longer may need another week **[source 15]**. After a 100-mile race, at least 3–4 weeks **[source 19]**. After a marathon Pfitzinger uses 5 weeks **[source 9]**; ours is 2 because the following build starts gently (§4 recovery).
- **B races:** the default taper is one week shorter, never below the race week (D-017). An explicit `taper_weeks` is taken as is.

Placing the phases:

1. Each A or B race has a race week: the week of its first day. It is the last week of the taper.
2. Before the taper comes the race's specific block; after the race week, its recovery.
3. Between two races: recovery → build (if room) → specific → taper. Before the first race: build → specific → taper.
4. After the last A or B race (only when C races or a multi-day race extend the plan): recovery, then build.
5. Two A or B races in the same week share one race week: the later race's taper and specific block apply, the earlier race gets no recovery, and C1 warns.

**When the weeks are too few**, blocks give way in this order (owner, S3). Each block is shortened only as far as needed, and each shortened block gives one warning: C1 when the cause is the previous race, C2 when the plan starts too late.

Between two races:
1. Build weeks (filler; no warning).
2. The later race's specific block, down to 0.
3. The earlier race's recovery, down to 1 week.
4. The later race's taper, down to the race week.
5. The earlier race's recovery, down to 0: the races are too close.

Before the first race: build weeks, then the specific block down to 0, then the taper down to the race week.

The taper stays ahead of the specific block: a week or two of race-specific work between two races builds little (Daniels wants at least 3 weeks per phase, **[source 16]**), while a taper week clearly pays **[source 13]**. When time is short, Daniels likewise keeps the final, race-specific phase ahead of the middle ones **[source 16]**.

2026 check: ultra (week 17) → marathon (week 23) leaves 5 weeks in between.
- **Defaults:** ultra B taper 2, recovery 3; the marathon's specific block becomes 1 week (step 2), with a warning.
- **2026 plan:** recovery 2 + specific 2, and a 3-week ultra taper although the ultra was the B race. The reference season overrides these two lengths; the specific block then shrinks to 2 weeks with a warning. The phase blocks match the reference sheet (base 1–4, strength 5–8, volume 9–14, ultra 15–17, pivot 18–21, race 22–23): build 1–8, ultra specific 9–14, taper 15–17, recovery 18–19, marathon specific 20–21, taper 22–23. Only the labels differ (D-026).

## 6. Long-run caps [default]

| Race | Cap | Basis |
|---|---|---|
| ≤ 10 km | 16 km | default |
| half | 21 km | default |
| marathon | 32 km | Daniels' long-run cap **[source 10]** |
| ultra | 40 km | **[2026]** |

The cap is reached in the race-specific block. Build weeks stop at 75 % of it (marathon: 24 km), so long plans peak near the race instead of holding the full cap for months **[default, owner S5]**. The cap of a week is that of the next A or B race (after the last one: the last one).

Overrides above the cap are allowed and produce a warning.

## 7. Checks (warnings only, D-001)

| # | Check | Threshold | Basis |
|---|---|---|---|
| C1 | races too close | a block shortened because of the previous race, or two races in one week (§5); emitted by the layout | default |
| C2 | plan too short | a block of the first A or B race shortened because the plan starts too late (§5); emitted by the layout | default |
| C3 | weekly ramp | planned km +10 % over the previous build week (not after deload or recovery) | common heuristic, weak evidence |
| C4 | long-run share | LR > 50 % of the planned week (40–50 % is normal with 4 runs a week; 2026 peaked at 54 %) | default |
| C5 | LR above cap | §6 | §6 |
| C6 | threshold volume | > 40′ at T in one session | **[source 5]** |
| C7 | interval volume | > 10 km or > 8 % of the week at I in one session | **[source 11]** |
| C8 | pace consistency | overridden T more than 10 s/km off the derived T | default |

Warnings go to the command line, not on the sheet.

## 8. "Life happens" rules (D-008)

The owner's 2026 order was intensity first, then an easy run, then the long run. That order is right when the cause is fatigue or illness. When the cause is lack of time, the standard is to drop an easy run first and keep the quality run and the long run. The long run goes last either way. The owner agreed to the standard (D-008).

Default footer (configurable):
> Short on time: drop an easy run → intensity → long run. Tired or ill: drop intensity first. A week counts at ≥ 80 % of the planned km.

## 9. Coach review of the 2026 plan

| Topic | 2026 | Verdict | Default from now on |
|---|---|---|---|
| MP | 4:58 | correct (raced 4:59) | derived or goal |
| Threshold pace | 4:30 | about 10 s/km fast | derived ≈ 4:40 |
| Threshold volume | up to 4×10′ | within McMillan's 15–40′ | cap 40′ |
| Interval volume | up to 6×4′ | within guidance | C7 |
| Deload depth | 50–55 % | deeper than standard | no intensity, LR 75 % (≈ 70–80 % of the week) |
| Long-run share | up to 54 % | high, a result of 4 runs a week | warning > 50 % |
| Long run peak | 40 km (ultra) | fine for an ultra | cap per race (§6) |
| Marathon block | 2 weeks of MP work | thin, forced by the race dates | compression + warning |
| Marathon taper | 69 % / 35 % | close to 70–75 / 40–50 % | §4 taper |

The owner finished the season uninjured and ran the planned marathon pace. That is evidence the plan suited him, but one runner and one season, so it doesn't override the guidance (D-010).

## 10. Sources

1. J. Daniels, *Daniels' Running Formula*, Human Kinetics. VDOT tables (VDOT 51 example as summarised at <https://test.knowt.com/note/a382dd53-8a7c-4d42-9c7a-b0ccb6e6aa80/part-2-Jack-Daniels-Running-Formula--->). T-03 verifies against the book's tables.
2. Daniels–Gilbert oxygen-cost equation and zone percentages: <https://fitmetriclab-com.pages.dev/en/tools/running/training-paces-vdot/>
3. McMillan training zones: <https://www.mcmillanrunning.com/zones-workouts-a-runners-guide-to-training-smarter/>
4. McMillan calculator uses a race result: <https://www.mcmillanrunning.com/wp-content/uploads/2016/08/UsingMcMillanCalculatorResults.pdf>
5. McMillan, tempo runs 15–40 min: <https://www.mcmillanrunning.com/?p=445900>
6. Down weeks (reduce volume, ease off the hardest sessions): <https://runnersconnect.net/why-planned-down-weeks-are-important/>
7. Deload 10–30 %: <https://runtothefinish.com/recovery-week-running/>
8. Marathon taper 70–75 % then 40–50 % of peak: <https://runnersconnect.net/running-training-articles/how-to-taper-for-a-marathon/>
9. Pfitzinger 5-week post-marathon recovery: <https://runningwithrock.com/pfitzinger-marathon-plan/>
10. Daniels long-run cap 32 km: <https://ctyeh.com/running/vdot?lang=en>
11. Interval session ≤ 10 km or 8 % of weekly mileage: <https://ctyeh.com/running/interval?lang=en>
12. Daniels, *Daniels' Running Formula*, 2nd ed., tables 3.1 and 3.2 (VDOT 50, 55–58), transcribed at <https://www.runningahead.com/groups/the_league/forum/0a085839fcc9423887c0bae90092e299>
13. Bosquet, Montpetit, Arvisais, Mujika (2007), *Effects of tapering on performance: a meta-analysis*, Med Sci Sports Exerc 39(8): 1358–1365; summary: <https://coachsci.sdsu.edu/csa/vol131/bosquet.htm>
14. Taper length by distance (10 km 7–10 days, half 10–14 days): <https://www.runnersblueprint.com/the-tapering-manual-2-weeks-3-weeks-or-none-at-all-how-to-taper-like-a-pro-from-5k-to-100k/>
15. Pfitzinger & Latter, *Faster Road Racing*, "After the race" (one recovery week; 15 km or longer may need another): <https://canada.humankinetics.com/blogs/excerpt/after-the-race-hellip>
16. Daniels, *Daniels' Running Formula*, ch. 10: four 6-week phases; with less time at least 3 weeks per phase, Phase IV (final quality) prioritised over II and III. Summaries: <https://voicetest.knowt.com/note/facf31df-2dca-4c4a-b8fc-4b7bfcd54266/part-3-Jack-Daniels-Running-Formula--->, <https://cdbaca.github.io/ssg/reading-daniels-running-formula-chapter-10.html>
17. Coach-written 100 km plan: race-specific weeks 13–17, taper weeks 18–19, race week 20: <https://www.trainingpeaks.com/training-plans/running/trail/tp-680386/20-week-100k-ultramarathon-training-plan-intermediate-4-days-per-week>
18. J. Koop, highest-volume block 6–9 weeks before an ultra: <https://trainright.com/how-much-time-do-you-really-need-to-train-for-an-ultramarathon/>
19. At least 3–4 weeks of recovery after a 100-mile race: <https://vert.run/100-miles-training-guide/>
20. Daniels, *Daniels' Running Formula*, table of training intensities: M-pace running up to the lesser of 90 min and 16 miles per session; quoted at <https://www.runningahead.com/forums/post/8acf6a4b0f634d4ebfb25f87b1304a6e> and <https://www.runningahead.com/forums/post/e989f57406784efdabd375505274c770>.
21. Buist et al. (2008), *No effect of a graded training program on the number of running-related injuries in novice runners: a randomized controlled trial*, Am J Sports Med 36(1): 33–39 (10 % rule vs a faster programme: 20.8 % vs 20.3 % injured): <https://research.rug.nl/en/publications/no-effect-of-a-graded-training-program-on-the-number-of-running-r/>
22. Long run extended by 1–2 miles a week in marathon preparation: <https://www.ajc.com/news/health-news/marathon-training-increase-the-miles-and-find-your-pace/ZRGCER7QV5HK3F4SSATF5MMKQ4/>

Sources 1, 10, 11, 12, 16 and 20 are secondary summaries of Daniels; prefer the book when implementing. Source 22 is a newspaper interview, weak; the +2 km step itself is from 2026.
