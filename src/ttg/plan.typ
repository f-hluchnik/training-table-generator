// Training table sheet: lays out plan.json (docs/PLAN.md §4, §5). No training logic here (D-012):
// the template only arranges what the plan contains.
//
// The plan arrives as JSON text in the `plan` input (see ttg.render).

#let plan = json(bytes(sys.inputs.plan))

// ---------------------------------------------------------------- style
// Fonts ship with the `typst` package, so the sheet looks the same on every machine. Data is set
// in the mono (the whole table, and the codes, paces and dates in the footer), words in the serif
// (the title and the footer's text) (D-048).
#let serif = "Libertinus Serif"
#let mono = "DejaVu Sans Mono"

// Line hierarchy (D-024): exactly three weights (D-048: lighter than the first approved values).
#let outline = 1.2pt + black
#let group = 0.6pt + black
#let hairline = 0.25pt + luma(55%)

#let header-fill = luma(90%)
#let band-fill = luma(94%)
#let note-ink = luma(60%)
#let week-number-ink = luma(40%) // the week numbers step back behind the dates (D-048)

// ---------------------------------------------------------------- geometry
#let page-margin = 8mm
#let page-width = 297mm
#let title-size = 14pt
#let text-size = 8pt
// The footer's data in the mono at this share of the text size, so its x-height matches the serif's.
#let footer-data-scale = 0.88
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
#let note-width = 14mm

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
// Long plans have shorter rows, so the table's text shrinks with them, in proportion: the text size
// at full rows, down to this at the smallest rows (a 40-week plan) (owner, S8; D-049).
#let min-table-text-size = 7pt
#let row-share = (row-height - min-row-height) / (max-row-height - min-row-height) // 0 at the smallest rows, 1 at full
#let table-text-size = min-table-text-size + row-share * (text-size - min-table-text-size)
#let note-size = table-text-size * 7 / 8 // the mono `recovery` fits the note column

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

// A band label keeps this clearance from the band's lines on every side.
#let band-label-clearance = 0.6mm
// Below this size a label is hard to read on the printed sheet; a phase band shows its short form
// instead (D-044).
#let min-band-label-size = 5pt

// A label set along `along` and across `across`: the largest size up to the text size at which it
// fits, and the content to place.
#let fitting(label, along, across) = {
  let natural = measure(text(font: mono, size: table-text-size, label))
  let size = table-text-size * calc.min(1, along / natural.width, across / natural.height)
  (size: size, label: label, body: text(font: mono, size: size, label))
}

// The label of a band of `rows` weeks and `width`, set in whichever direction gives it the larger
// size: rotated along the band, or horizontal across a band too short for its word (a one-week
// recovery). It never runs over the band's lines. When the word would fall below the readable size
// either way, the band shows `short` instead (`rec.`); months have no short form (D-044, D-048).
#let band-label(label, short, rows, width) = context {
  let length = rows * row-height - 2 * band-label-clearance
  let breadth = width - 2 * band-label-clearance
  let best(text-content) = {
    let rotated = fitting(text-content, length, breadth)
    let horizontal = fitting(text-content, breadth, length)
    if horizontal.size > rotated.size { (..horizontal, rotated: false) } else { (..rotated, rotated: true) }
  }
  let word = best(label)
  let shown = if short == none or word.size >= min-band-label-size { word } else { best(short) }
  let extent = measure(shown.body)
  // The marker lets tests check the fit (`typst.query(..., "<ttg-band-fit>")`).
  let fit = metadata((
    label: shown.label,
    size-pt: shown.size.pt(),
    rotated: shown.rotated,
    along-mm: extent.width.mm(),
    along-available-mm: (if shown.rotated { length } else { breadth }).mm(),
    across-mm: extent.height.mm(),
    across-available-mm: (if shown.rotated { breadth } else { length }).mm(),
  ))
  [#if shown.rotated { rotate(-90deg, reflow: true, shown.body) } else { shown.body }#fit<ttg-band-fit>]
}

#let band(label, rows, width, short: none) = table.cell(
  rowspan: rows,
  // Cells spanning fixed-height rows are unbreakable by default; a band longer than a page
  // would push the whole table to the next page and overflow it.
  breakable: true,
  fill: band-fill,
  align: center + horizon,
  inset: 0pt,
  // The marker lets tests query the bands (`typst.query(..., "<ttg-band>")`).
  [#band-label(label, short, rows, width)#metadata(label)<ttg-band>],
)

// ---------------------------------------------------------------- table
#let header-cells = (
  table.cell(fill: header-fill, colspan: col-days, []),
  ..day-names.map(name => table.cell(fill: header-fill, align: center + horizon, name)),
  ..range(calc.quo(box-count, label-every)).map(block => table.cell(
    colspan: label-every,
    align: right + horizon,
    inset: (right: 0.6mm),
    text(size: 0.9 * table-text-size, weight: "regular", str((block + 1) * label-every)),
  )),
  table.cell(fill: header-fill, []),
  ..("ER", "QR", "LR").map(code => table.cell(fill: header-fill, align: center + horizon, code)),
  table.cell(align: center + horizon, text(size: note-size, fill: note-ink, "note")),
)

// The cells of one week row. `month-bands` and `phase-bands` are runs, cut at page breaks.
#let week-cells(index, week, month-bands, phase-bands) = {
  let cells = ()
  let month-band = month-bands.find(run => run.at(0) == index)
  if month-band != none { cells.push(band(week.month, month-band.at(1), month-width)) }
  // The marker tells the next layout pass which page this week's row is on.
  cells.push(table.cell(align: center + horizon, [#text(fill: week-number-ink, str(week.number))#metadata(index)<ttg-week>]))
  for day in week.days {
    let label = if day == none { [] } else if day.race { strong(day.text) } else { day.text }
    cells.push(table.cell(align: center + horizon, label))
  }
  cells += range(box-count).map(_ => [])
  let phase-band = phase-bands.find(run => run.at(0) == index)
  if phase-band != none { cells.push(band(week.phase_label, phase-band.at(1), phase-width, short: week.phase_short)) }
  cells.push(week.easy.text)
  cells.push(week.quality.text)
  cells.push(week.long.text)
  cells.push(table.cell(align: center + horizon, text(size: note-size, fill: note-ink, week.note)))
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

  // Group weight also between the column groups (D-048).
  for x in (col-days, col-gauge, col-phase, col-easy) {
    all.push(table.vline(x: x, end: row-count, stroke: group))
  }

  // Outline: the frame and the header separator.
  all.push(table.hline(y: 0, end: framed, stroke: outline))
  all.push(table.hline(y: 1, end: framed, stroke: outline))
  all.push(table.hline(y: row-count, end: framed, stroke: outline))
  for x in (0, framed) {
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
// Quiet typography (D-047): hierarchy by the type alone, no grey and no `=`, brackets or
// semicolons. Each entry is a bold key and a colon, its value roman, its description italic; a thin
// black rule, a different kind of mark from the text, separates the entries of every footer line.
#let separator-rule-weight = 0.4pt
#let list-separator = [#h(2mm)#box(height: 0.75em, stroke: (left: separator-rule-weight + black))#h(2mm)]

#let data(body) = text(font: mono, size: footer-data-scale * text-size, body)

#let pace-entry(entry) = {
  [#data(strong(entry.code)):]
  if entry.pace != "" [ #data(entry.pace)]
  if entry.label != "" [ #emph(entry.label)]
}
#let pace-legend = plan.paces.map(pace-entry).join(list-separator)

// The races of the season, so a "RACE" cell can be told apart (owner, S5): the dates set apart
// like the session codes above them.
#let race-entry(race) = [#data(strong(race.dates)): #race.name #emph[(#race.details)]]
#let race-list = plan.footer.races.map(race-entry).join(list-separator)

#let footer-rules = (..plan.footer.rules, plan.footer.success).join(list-separator)

// ---------------------------------------------------------------- page
#set page(paper: "a4", flipped: true, margin: page-margin)
#set text(font: serif, size: text-size, lang: "en")

// The title starts at the table's left edge (D-048).
#align(center, block(width: fixed-width + box-count * box-width, align(left)[
  #text(size: title-size, weight: "bold")[#plan.title]
  #v(1mm)
]))

#align(center, text(font: mono, size: table-text-size, sheet))

#v(2mm)
#align(center)[
  #pace-legend
  #v(0.5mm)
  #race-list
  #v(0.5mm)
  #footer-rules
]
