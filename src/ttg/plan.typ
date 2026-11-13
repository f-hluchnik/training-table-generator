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

// Runs of consecutive weeks (by index) with equal `key-of(index)`: array of (first index, length).
#let runs(key-of) = {
  let result = ()
  for i in range(weeks.len()) {
    if result.len() > 0 and key-of(result.last().at(0)) == key-of(i) {
      result.last().at(1) += 1
    } else {
      result.push((i, 1))
    }
  }
  result
}
#let month-of(i) = weeks.at(i).month
#let phase-of(i) = weeks.at(i).phase // the phase's number: two adjacent tapers stay apart
#let month-runs = runs(month-of)
#let phase-runs = runs(phase-of)

// A rotated band label keeps this clearance from the lines at both ends of its band.
#let band-label-clearance = 0.6mm
// Below this size a label is hard to read on the printed sheet; a phase band shows its short form
// instead (D-044).
#let min-band-label-size = 5pt

// The size at which `label` fits `available`: the text size, or smaller for a short band.
#let fitting-size(label, available) = {
  let natural = measure(text(font: serif, size: text-size, label)).width
  if natural > available { text-size * (available / natural) } else { text-size }
}

// A band's label, shrunk to fit its band so it never runs over the band's lines (a two-week
// recovery in a long plan). When the word would fall below the readable size, the band shows
// `short` instead (a one-week recovery: `rec.`); months have no short form (D-044).
#let band-label(label, short, rows) = context {
  let available = rows * row-height - 2 * band-label-clearance
  let size = fitting-size(label, available)
  let (shown, shown-size) = if short == none or size >= min-band-label-size {
    (label, size)
  } else {
    (short, fitting-size(short, available))
  }
  let width = measure(text(font: serif, size: shown-size, shown)).width
  // The marker lets tests check the fit (`typst.query(..., "<ttg-band-fit>")`).
  [#text(font: serif, size: shown-size, shown)#metadata((
    label: shown,
    size-pt: shown-size.pt(),
    width-mm: width.mm(),
    available-mm: available.mm(),
  ))<ttg-band-fit>]
}

#let band(label, rows, short: none) = table.cell(
  rowspan: rows,
  // Cells spanning fixed-height rows are unbreakable by default; a band longer than a page
  // would push the whole table to the next page and overflow it.
  breakable: true,
  fill: band-fill,
  align: center + horizon,
  inset: 0pt,
  // The marker lets tests query the bands (`typst.query(..., "<ttg-band>")`).
  [#rotate(-90deg, reflow: true, band-label(label, short, rows))#metadata(label)<ttg-band>],
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

// The cells of one week row. `month-bands` and `phase-bands` are runs, cut at page breaks.
#let week-cells(index, week, month-bands, phase-bands) = {
  let cells = ()
  let month-band = month-bands.find(run => run.at(0) == index)
  if month-band != none { cells.push(band(week.month, month-band.at(1))) }
  // The marker tells the next layout pass which page this week's row is on.
  cells.push(table.cell(align: center + horizon, [#strong(str(week.number))#metadata(index)<ttg-week>]))
  for day in week.days {
    let label = if day == none { [] } else if day.race { strong(day.text) } else { day.text }
    cells.push(table.cell(align: center + horizon, label))
  }
  cells += range(box-count).map(_ => [])
  let phase-band = phase-bands.find(run => run.at(0) == index)
  if phase-band != none { cells.push(band(week.phase_label, phase-band.at(1), short: week.phase_short)) }
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
  for (first, _) in month-runs.slice(1) {
    all.push(table.hline(y: week-row(first), end: framed, stroke: group))
  }
  for (first, _) in phase-runs.slice(1) {
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

// A band that continues on the next page is cut at the break, so both pages show its label.
// The pages come from the previous layout pass (none in the first; cutting moves no row).
#let sheet = context {
  let pages = query(<ttg-week>).map(marker => marker.location().page())
  let page-of(i) = pages.at(i, default: 1)
  let month-bands = runs(i => (month-of(i), page-of(i)))
  let phase-bands = runs(i => (phase-of(i), page-of(i)))
  table(
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
    ..weeks.enumerate().map(((index, week)) => week-cells(index, week, month-bands, phase-bands)).flatten(),
    ..lines,
  )
}

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
