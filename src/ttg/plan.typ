// Training table sheet: lays out plan.json (docs/PLAN.md §4, §5). No training logic here (D-012):
// the template only arranges what the plan contains.
//
// The plan arrives as JSON text in the `plan` input (see ttg.render).

#let plan = json(bytes(sys.inputs.plan))

// ---------------------------------------------------------------- style
// Fonts ship with the `typst` package, so the sheet looks the same on every machine.
#let serif = "Libertinus Serif"
#let mono = "DejaVu Sans Mono"

// Line hierarchy (D-024): exactly three weights. Values to be approved on a printed page.
#let outline = 1.5pt + black
#let group = 0.75pt + black
#let hairline = 0.25pt + luma(55%)

#let header-fill = luma(85%)
#let band-fill = luma(88%)
#let note-ink = luma(60%)

// ---------------------------------------------------------------- geometry
#let page-margin = 8mm
#let page-width = 297mm
#let title-size = 20pt
#let text-size = 8pt
#let table-height = 152mm // budget for all rows on one page; rows shrink for long plans
#let max-row-height = 6.4mm
// Rows never get smaller than this, so the text clears the lines and the cells can still be
// coloured by hand (owner, S5). Longer plans (above about 40 weeks) continue on a second page,
// with the header repeated.
#let min-row-height = 3.7mm
#let max-box-width = 1.2mm // D-019: 1 km per box; shrinks if the gauge would not fit

// Fixed columns. ER holds up to four easy runs (D-016), QR and LR the longest prescriptions.
#let month-width = 6mm
#let week-width = 7mm
#let day-width = 10mm
#let phase-width = 6mm
#let easy-width = 24mm
#let quality-width = 24mm
#let long-width = 27mm
#let note-width = 13mm

#let days-per-week = 7
#let weeks = plan.weeks
#let box-count = plan.gauge.boxes
#let label-every = plan.gauge.label_every_km

#let fixed-width = (
  month-width + week-width + days-per-week * day-width + phase-width
    + easy-width + quality-width + long-width + note-width
)
#let box-width = calc.min(
  max-box-width,
  (page-width - 2 * page-margin - fixed-width) / box-count,
)
#let row-height = calc.max(min-row-height, calc.min(max-row-height, table-height / (weeks.len() + 1)))

// Column indices (x of the first column of each group).
#let col-days = 2
#let col-gauge = col-days + days-per-week
#let col-phase = col-gauge + box-count
#let col-easy = col-phase + 1
#let col-quality = col-easy + 1
#let col-long = col-quality + 1
#let col-note = col-long + 1
#let col-count = col-note + 1
#let header-rows = 1
#let row-count = header-rows + weeks.len()

// ---------------------------------------------------------------- helpers
#let day-names = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

// Runs of consecutive weeks with equal `key`: array of (key, first week index, length).
#let spans(key) = {
  let runs = ()
  for (i, week) in weeks.enumerate() {
    let value = week.at(key)
    if runs.len() > 0 and runs.last().at(0) == value {
      runs.last().at(2) += 1
    } else {
      runs.push((value, i, 1))
    }
  }
  runs
}

#let band(content, rows) = table.cell(
  rowspan: rows,
  fill: band-fill,
  align: center + horizon,
  inset: 0pt,
  rotate(-90deg, reflow: true, text(font: serif, content)),
)

#let prescription(text-content) = text(font: mono, text-content)

// ---------------------------------------------------------------- table
#let header-cells = (
  table.cell(fill: header-fill, colspan: col-days, []),
  ..day-names.map(name => table.cell(fill: header-fill, align: center + horizon, strong(name))),
  ..range(calc.quo(box-count, label-every)).map(block => table.cell(
    colspan: label-every,
    align: right + horizon,
    inset: (right: 0.6mm),
    text(size: 0.9 * text-size, weight: "regular", str((block + 1) * label-every)),
  )),
  table.cell(fill: header-fill, []),
  table.cell(fill: header-fill, align: center + horizon, text(font: mono, weight: "bold", "ER")),
  table.cell(fill: header-fill, align: center + horizon, text(font: mono, weight: "bold", "QR")),
  table.cell(fill: header-fill, align: center + horizon, text(font: mono, weight: "bold", "LR")),
  table.cell(align: center + horizon, text(fill: note-ink, "note")),
)

#let week-cells(index, week) = {
  let months = spans("month")
  let phases = spans("phase_label")
  let cells = ()
  let month-run = months.find(run => run.at(1) == index)
  if month-run != none { cells.push(band(month-run.at(0), month-run.at(2))) }
  cells.push(table.cell(align: center + horizon, strong(str(week.number))))
  for day in week.days {
    let label = if day == none { [] } else if day.race { strong(day.text) } else { day.text }
    cells.push(table.cell(align: center + horizon, label))
  }
  cells += range(box-count).map(_ => [])
  let phase-run = phases.find(run => run.at(1) == index)
  if phase-run != none { cells.push(band(phase-run.at(0), phase-run.at(2))) }
  cells.push(prescription(week.easy.text))
  cells.push(prescription(week.quality.text))
  cells.push(prescription(week.long.text))
  cells.push(table.cell(align: center + horizon, text(fill: note-ink, week.note)))
  cells
}

// Row `y` is a week row (the header is row 0).
#let week-row(index) = header-rows + index

#let lines = {
  let all = ()
  let framed = col-count - 1 // the note column sits outside the frame (as in the reference)

  // Hairlines: every row, every box of the gauge, the cells between day and prescription columns.
  for y in range(1, row-count) { all.push(table.hline(y: y, end: framed, stroke: hairline)) }
  for x in (1, ..range(col-days + 1, col-gauge + 1), ..range(col-gauge + 1, col-phase), col-quality, col-long) {
    all.push(table.vline(x: x, end: row-count, stroke: hairline))
  }

  // Group weight: month boundaries, phase boundaries, the 10 km marks.
  for (_, first, _) in spans("month").slice(1) {
    all.push(table.hline(y: week-row(first), end: framed, stroke: group))
  }
  for (_, first, _) in spans("phase_label").slice(1) {
    all.push(table.hline(y: week-row(first), start: col-phase, end: col-phase + 1, stroke: group))
  }
  for x in range(col-gauge + label-every, col-phase, step: label-every) {
    all.push(table.vline(x: x, end: row-count, stroke: group))
  }
  // The 80 % marker (D-019): the border after the box where 80 % of the week's km is reached.
  for (index, week) in weeks.enumerate() {
    all.push(table.vline(
      x: col-gauge + week.box_80pct,
      start: week-row(index),
      end: week-row(index) + 1,
      stroke: group,
    ))
  }

  // Outline: the frame, the header separator, the boundaries between column groups.
  all.push(table.hline(y: 0, end: framed, stroke: outline))
  all.push(table.hline(y: 1, end: framed, stroke: outline))
  all.push(table.hline(y: row-count, end: framed, stroke: outline))
  for x in (0, col-days, col-gauge, col-phase, col-easy, framed) {
    all.push(table.vline(x: x, end: row-count, stroke: outline))
  }
  all
}

#let sheet = table(
  columns: (
    month-width,
    week-width,
    ..range(days-per-week).map(_ => day-width),
    ..range(box-count).map(_ => box-width),
    phase-width,
    easy-width,
    quality-width,
    long-width,
    note-width,
  ),
  rows: row-height,
  inset: (x: 1mm, y: 0pt),
  align: left + horizon,
  stroke: none,
  table.header(..header-cells),
  ..weeks.enumerate().map(((index, week)) => week-cells(index, week)).flatten(),
  ..lines,
)

// ---------------------------------------------------------------- footer
#let pace-legend = (
  plan.paces
    .map(entry => {
      let pace = if entry.pace != "" { "=" + entry.pace } else { "" }
      let label = if entry.label != "" { " [" + entry.label + "]" } else { "" }
      [#strong(entry.code)#pace#label]
    })
    .join("; ")
)

// The races of the season, so a "RACE" cell can be told apart (owner, S5).
#let race-list = [#strong[races]: #plan.footer.races.join("; ")]

// ---------------------------------------------------------------- page
#set page(paper: "a4", flipped: true, margin: page-margin)
#set text(font: serif, size: text-size, lang: "en")

#align(center)[
  #text(size: title-size, weight: "bold")[#plan.title]
  #v(2mm)
]

#align(center, sheet)

#v(2mm)
#align(center)[
  #pace-legend \
  #race-list \
  #v(0.5mm)
  #plan.footer.rules.join(" ") #plan.footer.success
]
