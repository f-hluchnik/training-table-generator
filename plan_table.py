"""
Renders a Week-by-week plan as a single HTML file styled to look like a
plain printed spreadsheet: a calendar grid, a segmented "actual mileage"
gauge built from real table columns (color one box per 2 km run, by hand,
after printing), and letter-coded prescriptions with a legend below. Sized
for A4 landscape print.

Column widths are set on <col> elements rather than <td>, because in a
fixed-layout table only the first row's cells (or the <col>s) determine
column widths - relying on later rows silently does nothing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from html import escape

DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Accent colors, only used when render_html(..., use_color=True). Bright
# enough to read as color-coding at a glance, not just a tint.
QUALITY_ACCENT = {"H": "#5FA800", "I": "#E13A1F", "T": "#1F6FE0", "R": "#9C9C98"}

# Row geometry: everything else (day-column width, etc.) is derived from this.
ROW_HEIGHT_MM = 5.0
DAY_COL_RATIO = 1.6   # day column width = ratio * row height

WEEK_COL_MM = 7.0
QUALITY_COL_MM = 26.0
LONG_COL_MM = 17.0
TOTAL_COL_MM = 11.0
MONO_CHAR_MM = 1.7     # rough width of one monospace character at 8pt
EASY_COL_MIN_MM = 10.0


@dataclass
class Week:
    week_num: int
    start_date: date
    easy_runs: list[float]
    quality_type: str                      # 'H' | 'I' | 'T' | 'R'
    quality_detail: str | None = None      # e.g. "6 x 1'"; None for rest weeks
    long_run_km: float | None = None
    long_run_tag: str | None = None        # e.g. "w/ MP" appended to LR cell
    total_km: float | None = None          # drives the fill-in gauge length
    over_target: bool = False              # prescribed total notably exceeds target
    note: str | None = None                # overrides total_km display

    @property
    def end_date(self) -> date:
        return self.start_date + timedelta(days=6)


@dataclass
class LegendItem:
    code: str
    label: str
    pace: str | None = None    # None for entries with no fixed pace (e.g. rest)


@dataclass
class Plan:
    title: str
    subtitle: str
    weeks: list[Week]
    legend: list[LegendItem] = field(default_factory=list)
    segment_km: float = 2.0
    race_dates: list[date] = field(default_factory=list)


def _num(x: float | int | None) -> str:
    if x is None:
        return ""
    if float(x).is_integer():
        return str(int(x))
    return f"{x:.1f}"


def _fmt_easy(runs: list[float]) -> str:
    return " + ".join(_num(r) for r in runs)


def _fmt_long(week: Week) -> str:
    if week.long_run_km is None:
        return '<span class="muted">Rest</span>'
    txt = _num(week.long_run_km) + " km"
    if week.long_run_tag:
        txt += f' <span class="tag">{escape(week.long_run_tag)}</span>'
    return txt


def _fmt_total(week: Week) -> str:
    if week.note:
        return f'<span class="note">{escape(week.note)}</span>'
    if week.total_km is not None:
        marker = '<span class="flag" title="Exceeds computed weekly target by more than the tolerance">*</span>' if week.over_target else ""
        return _num(week.total_km) + marker
    return ""


def _quality_cell(week: Week, use_color: bool) -> str:
    style = f'style="--accent:{QUALITY_ACCENT.get(week.quality_type, "#000")}"' if use_color else ""
    if week.quality_type == "R" or not week.quality_detail:
        return f'<div class="qr" {style}><span class="qr-type muted">{escape(week.quality_type)}</span></div>'
    return (
        f'<div class="qr" {style}>'
        f'<span class="qr-type">{escape(week.quality_type)}</span> '
        f'<span class="qr-detail">{escape(week.quality_detail)}</span>'
        f"</div>"
    )


def render_html(
    plan: Plan,
    use_color: bool = False,
    seg_width_mm: float = 2.0,
    actual_col_budget_mm: float = 130.0,
) -> str:
    max_segments = max(
        (math.ceil((w.total_km or 0) / plan.segment_km) for w in plan.weeks),
        default=0,
    )
    # Shrink the box width if the widest week's gauge wouldn't fit the page.
    if max_segments > 0:
        seg_width_mm = min(seg_width_mm, actual_col_budget_mm / max_segments)

    day_col_mm = ROW_HEIGHT_MM * DAY_COL_RATIO
    race_dates = set(plan.race_dates)

    max_easy_chars = max((len(_fmt_easy(w.easy_runs)) for w in plan.weeks), default=5)
    easy_col_mm = max(EASY_COL_MIN_MM, max_easy_chars * MONO_CHAR_MM + 3.0)

    rows: list[str] = []
    for week in plan.weeks:
        row_class = "week-row"
        if week.quality_type == "R":
            row_class += " deload"

        day_cells = []
        for i in range(7):
            d = week.start_date + timedelta(days=i)
            cls = "day race-day" if d in race_dates else "day"
            day_cells.append(f'<td class="{cls}">{d.day}</td>')

        # Every row gets the same number of boxes (the plan-wide max) so the
        # gauge lines up as real table columns; the Total column already
        # says what that week's target is, so the boxes themselves don't
        # need to be shaded to repeat that information.
        seg_cells = []
        for i in range(max_segments):
            edge = " seg-first" if i == 0 else (" seg-last" if i == max_segments - 1 else "")
            seg_cells.append(
                f'<td class="seg-cell{edge}" onclick="this.classList.toggle(\'filled\')"></td>'
            )

        rows.append(
            f'<tr class="{row_class}">'
            f'<td class="week-num">{week.week_num}</td>'
            f"{''.join(day_cells)}"
            f"{''.join(seg_cells)}"
            f'<td class="easy">{_fmt_easy(week.easy_runs)}</td>'
            f'<td class="quality">{_quality_cell(week, use_color)}</td>'
            f'<td class="long">{_fmt_long(week)}</td>'
            f'<td class="total">{_fmt_total(week)}</td>'
            f"</tr>"
        )

    legend_items = "".join(
        f'<div class="legend-item"><span class="legend-code">{escape(item.code)}</span>'
        + (f'<span class="legend-pace">{escape(item.pace)}</span>' if item.pace else "")
        + f'<span class="legend-label">{escape(item.label)}</span></div>'
        for item in plan.legend
    )

    day_header = "".join(f"<th>{d}</th>" for d in DAY_LABELS)
    seg_cols = "".join(f'<col style="width:{seg_width_mm:.2f}mm">' for _ in range(max_segments))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{escape(plan.title)}</title>
<style>
  @page {{ size: A4 landscape; margin: 10mm; }}

  * {{ box-sizing: border-box; }}
  html, body {{
    margin: 0;
    background: #E9E9E9;
    color: #000;
    font-family: Calibri, "Segoe UI", Arial, sans-serif;
    font-variant-numeric: tabular-nums;
  }}
  .page {{
    width: 277mm;
    margin: 6mm auto;
    padding: 6mm 6mm 4mm;
    background: #FFF;
  }}
  h1 {{ font-size: 14pt; font-weight: 700; margin: 0 0 1mm; }}
  .subtitle {{ color: #333; font-size: 8pt; margin: 0 0 3mm; }}

  table {{
    border-collapse: collapse;
    font-size: 8pt;
    table-layout: fixed;
    border: 2.5pt solid #000;
  }}
  th, td {{
    border: 0.5pt solid #000;
    padding: 0 1mm;
    height: {ROW_HEIGHT_MM}mm;
    line-height: {ROW_HEIGHT_MM}mm;
    text-align: center;
    overflow: hidden;
  }}
  thead th {{
    background: #EDEDED;
    font-weight: 700;
    font-size: 7.5pt;
    line-height: 1.3;
    height: {ROW_HEIGHT_MM + 1}mm;
    text-transform: lowercase;
    border-bottom: 2pt solid #000;
  }}

  .mono {{ font-family: Consolas, "Liberation Mono", Menlo, monospace; }}

  td.week-num, th.wk-head {{ border-right: 2pt solid #000; font-weight: 700; }}
  td.day {{ color: #222; }}
  td.day.race-day {{ font-weight: 700; }}
  td.easy, td.long, .qr-detail {{ font-family: Consolas, "Liberation Mono", Menlo, monospace; }}
  td.quality {{ text-align: left; }}
  td.total {{ color: #333; }}

  td.seg-cell {{
    border: 0.5pt solid #888;
    cursor: pointer;
    padding: 0;
  }}
  td.seg-cell.filled {{ background: #000; }}
  td.seg-cell.seg-first {{ border-left: 2pt solid #000; }}
  td.seg-cell.seg-last {{ border-right: 2pt solid #000; }}

  .qr {{ padding-left: 0.5mm; }}
  .qr[style] {{ border-left: 3pt solid var(--accent); padding-left: 1.5mm; }}
  .qr-type {{ font-weight: 700; }}
  .qr-detail {{ color: #222; }}

  .muted {{ color: #999; }}
  .note {{ font-style: italic; color: #333; }}
  .tag {{ font-size: 6.5pt; color: #666; }}
  .flag {{ color: #333; font-weight: 700; margin-left: 0.5mm; }}

  tr.deload td:not(.seg-cell) {{ background: #F3F3F3; }}

  .legend {{
    margin-top: 2.5mm;
    display: flex;
    flex-wrap: wrap;
    gap: 1mm 6mm;
    font-size: 6.5pt;
  }}
  .legend-item {{ display: flex; gap: 1mm; white-space: nowrap; }}
  .legend-code {{ font-weight: 700; }}
  .legend-pace {{ color: #333; font-family: Consolas, "Liberation Mono", Menlo, monospace; }}
  .legend-label {{ color: #666; }}
  .legend-note {{ font-size: 6.5pt; color: #666; margin-top: 1mm; }}

  .no-print {{ margin: 4mm auto 0; width: 277mm; text-align: right; }}
  .no-print button {{ font: inherit; padding: 1mm 4mm; cursor: pointer; }}

  @media print {{
    html, body {{ background: #FFF; }}
    .page {{ margin: 0; padding: 0; width: auto; }}
    .no-print {{ display: none; }}
  }}
</style>
</head>
<body>
  <div class="no-print"><button onclick="window.print()">Print</button></div>
  <div class="page">
    <h1>{escape(plan.title)}</h1>
    <p class="subtitle">{escape(plan.subtitle)}</p>
    <table>
      <colgroup>
        <col style="width:{WEEK_COL_MM}mm">
        {"".join(f'<col style="width:{day_col_mm}mm">' for _ in range(7))}
        {seg_cols}
        <col style="width:{easy_col_mm:.2f}mm">
        <col style="width:{QUALITY_COL_MM}mm">
        <col style="width:{LONG_COL_MM}mm">
        <col style="width:{TOTAL_COL_MM}mm">
      </colgroup>
      <thead>
        <tr>
          <th class="wk-head">Wk</th>
          {day_header}
          <th colspan="{max_segments}">Actual &mdash; {plan.segment_km:g} km / box</th>
          <th>Easy</th>
          <th>Quality</th>
          <th>Long</th>
          <th>Total</th>
        </tr>
      </thead>
      <tbody>
        {''.join(rows)}
      </tbody>
    </table>
    <div class="legend">
      {legend_items}
    </div>
    <p class="legend-note">* prescribed total exceeds the computed weekly target for that week (by more than the tolerance).</p>
  </div>
</body>
</html>
"""