// Draws the first weeks of the example season from its plan.json, the same data the PDF is
// typeset from, so the page never shows a sheet the generator would not print (D-051).
// The visitor colours days and logs km the way a runner does on the printed sheet.

// A press cycles a day through these marks, then back to blank. "event" is the red corner for
// something unexpected (illness, a trip), as on the author's sheets.
const MARKS = ["easy", "quality", "long", "event"];
const WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];

// A month of a season already lived: four runs a week, intensity dropped when ill in week 3
// (the sheet's own rule), week 4 under way. Day indexes are Monday = 0.
const DIARY = {
  1: { runs: { 1: "easy", 3: "quality", 5: "easy", 6: "long" }, km: 46 },
  2: { runs: { 1: "easy", 3: "quality", 4: "easy", 6: "long" }, km: 49 },
  3: { runs: { 1: "easy", 5: "easy", 6: "long" }, event: 3, km: 38 },
  4: { runs: { 1: "easy" } },
};

// The km are coloured by how much of the plan they reach: green from 80 %, the share at which a
// week counts as done (D-006); yellow from 50 %; red below (the author's own colouring).
const LEVELS = [
  { share: 0.8, level: "full" },
  { share: 0.5, level: "part" },
  { share: 0, level: "low" },
];

function level(km, planned) {
  if (km === 0 || planned === 0) return "";
  return LEVELS.find(({ share }) => km >= share * planned).level;
}

function element(tag, attributes = {}, ...children) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attributes)) {
    if (name === "class") node.className = value;
    else if (name === "style") node.style.cssText = value;
    else node.setAttribute(name, value);
  }
  node.append(...children);
  return node;
}

// A marker stroke is never quite straight; the same cell always leans the same way.
function tilt(seed) {
  return (((seed * 7919) % 17) / 8 - 1).toFixed(2) + "deg";
}

// Consecutive weeks with the same value share one band, as on the sheet.
function bands(weeks, key) {
  const result = [];
  for (const week of weeks) {
    const last = result[result.length - 1];
    if (last && last.label === week[key]) last.span += 1;
    else result.push({ label: week[key], span: 1, first: week.number });
  }
  return result;
}

function dayButton(day, weekday, week, text) {
  const button = element("button", { type: "button", style: `--tilt: ${tilt(week.number * 7 + weekday)}` });
  button.append(element("span", {}, day.text));
  if (day.race) button.classList.add("race");
  const diary = DIARY[week.number] || {};
  const run = diary.runs && diary.runs[weekday];
  if (run) button.dataset.run = run;
  if (diary.event === weekday) button.dataset.event = "";

  const describe = () => {
    const state = button.dataset.run ? text.runs[button.dataset.run] : text.blank;
    const event = "event" in button.dataset ? `, ${text.event}` : "";
    button.setAttribute("aria-label", `${text.weekdays[weekday]} ${day.text}: ${state}${event}`);
  };
  const mark = () => ("event" in button.dataset ? "event" : button.dataset.run);
  button.addEventListener("click", () => {
    const next = MARKS[MARKS.indexOf(mark()) + 1];
    delete button.dataset.run;
    delete button.dataset.event;
    if (next === "event") button.dataset.event = "";
    else if (next) button.dataset.run = next;
    describe();
  });
  describe();
  return button;
}

// The gauge is a slider: press a box, or use the arrow keys, to log the week's km.
function gauge(week, boxes, text) {
  const track = element("div", {
    class: "gauge-track",
    role: "slider",
    tabindex: "0",
    "aria-valuemin": "0",
    "aria-valuemax": String(boxes),
    style: `--boxes: ${boxes}`,
  });
  const cells = Array.from({ length: boxes }, () => element("span"));
  track.append(...cells);

  const set = (km) => {
    const value = Math.max(0, Math.min(boxes, km));
    track.dataset.km = value;
    track.dataset.level = level(value, week.planned_km);
    cells.forEach((cell, index) => cell.classList.toggle("done", index < value));
    track.setAttribute("aria-valuenow", String(value));
    track.setAttribute("aria-valuetext", text.km(value, week.planned_km));
    track.setAttribute("aria-label", text.gauge(week.number));
  };
  track.addEventListener("click", (event) => {
    const box = cells.indexOf(event.target) + 1;
    if (box > 0) set(box === Number(track.dataset.km) ? 0 : box);
  });
  const steps = { ArrowRight: 1, ArrowUp: 1, ArrowLeft: -1, ArrowDown: -1, PageUp: 10, PageDown: -10 };
  track.addEventListener("keydown", (event) => {
    const km = Number(track.dataset.km);
    if (event.key in steps) set(km + steps[event.key]);
    else if (event.key === "Home") set(0);
    else if (event.key === "End") set(boxes);
    else return;
    event.preventDefault();
  });
  set((DIARY[week.number] || {}).km || 0);
  return track;
}

function header(plan, text) {
  const labels = plan.gauge.boxes / plan.gauge.label_every_km;
  const gaugeHead = element(
    "div",
    { class: "gauge-head", style: `--labels: ${labels}` },
    ...Array.from({ length: labels }, (_, index) =>
      element("span", {}, String((index + 1) * plan.gauge.label_every_km))
    )
  );
  return element(
    "thead",
    {},
    element(
      "tr",
      {},
      element("th", { class: "month" }),
      element("th", { class: "week" }),
      ...WEEKDAYS.map((day, index) =>
        element("th", { class: index === 0 ? "group" : "", abbr: text.weekdays[index] }, day)
      ),
      element("th", { class: "gauge group" }, gaugeHead),
      element("th", { class: "phase group" }),
      element("th", {}, "ER"),
      element("th", {}, "QR"),
      element("th", { class: "end" }, "LR"),
      element("th", { class: "note" }, "note")
    )
  );
}

function body(plan, weeks, text) {
  const months = new Map(bands(weeks, "month").map((band) => [band.first, band]));
  const phases = new Map(bands(weeks, "phase_label").map((band) => [band.first, band]));
  const rows = weeks.map((week) => {
    const row = element("tr");
    const month = months.get(week.number);
    if (month) {
      const end = month.first + month.span - 1 === weeks.length ? " reaches-end" : "";
      row.append(
        element("th", { class: `month${end}`, rowspan: String(month.span), scope: "rowgroup" }, element("span", {}, month.label))
      );
    }
    row.append(element("td", { class: "week" }, String(week.number)));
    week.days.forEach((day, index) => {
      const cell = element("td", { class: index === 0 ? "day group" : "day" });
      if (day) cell.append(dayButton(day, index, week, text));
      row.append(cell);
    });
    row.append(element("td", { class: "gauge group" }, gauge(week, plan.gauge.boxes, text)));
    const phase = phases.get(week.number);
    if (phase) {
      const end = phase.first + phase.span - 1 === weeks.length ? " reaches-end" : "";
      row.append(element("td", { class: `phase group${end}`, rowspan: String(phase.span) }, element("span", {}, phase.label)));
    }
    row.append(
      element("td", {}, week.easy.text),
      element("td", {}, week.quality.text),
      element("td", { class: "end" }, week.long.text),
      element("td", { class: "note" }, week.note)
    );
    return row;
  });
  return element("tbody", {}, ...rows);
}

// The lines under the table, as the sheet prints them: paces, races, rules.
function footer(plan) {
  const line = (entries) => element("p", {}, ...entries.flatMap((entry, index) => (index ? [element("span", { class: "separator", "aria-hidden": "true" }), entry] : [entry])));
  const paces = plan.paces.map((pace) =>
    element("span", { class: "entry" }, element("b", { class: "data" }, pace.code), ": ", element("span", { class: "data" }, pace.pace), " ", element("i", {}, pace.label))
  );
  const races = plan.footer.races.map((race) =>
    element("span", { class: "entry" }, element("b", { class: "data" }, race.dates), `: ${race.name} `, element("i", {}, `(${race.details})`))
  );
  const rules = [...plan.footer.rules, plan.footer.success].map((rule) => element("span", { class: "entry" }, rule));
  return element("div", { class: "sheet-footer" }, line(paces), line(races), line(rules));
}

// The whole season is drawn; until asked, only its first weeks show.
function collapsible(figure, scroll, plan, text) {
  const shown = Number(figure.dataset.weeks);
  const toggle = figure.querySelector(".sheet-toggle");
  const rows = scroll.querySelectorAll("tbody tr");
  if (rows.length <= shown) return;
  // Measured once, with every row laid out: the top of the first hidden week.
  const height = rows[shown].getBoundingClientRect().top - scroll.getBoundingClientRect().top;
  scroll.style.setProperty("--collapsed-height", `${height}px`);
  const set = (collapsed) => {
    scroll.classList.toggle("collapsed", collapsed);
    toggle.setAttribute("aria-expanded", String(!collapsed));
    toggle.textContent = collapsed ? text.showAll.replace("{weeks}", plan.weeks.length) : text.showFirst;
  };
  toggle.hidden = false;
  toggle.addEventListener("click", () => set(!scroll.classList.contains("collapsed")));
  set(true);
}

async function drawSheet(figure) {
  const text = JSON.parse(document.getElementById("sheet-text").textContent);
  text.km = (km, planned) => text.kmText.replace("{km}", km).replace("{planned}", planned);
  text.gauge = (number) => text.gaugeText.replace("{week}", number);
  const response = await fetch(figure.dataset.plan);
  if (!response.ok) throw new Error(`${figure.dataset.plan}: ${response.status}`);
  const plan = await response.json();
  const table = element("table", { class: "sheet" }, element("caption", { class: "visually-hidden" }, text.caption));
  table.append(header(plan, text), body(plan, plan.weeks, text));
  const scroll = figure.querySelector(".sheet-scroll");
  // Table and footer share one width, as on the printed page.
  scroll.replaceChildren(element("div", { class: "sheet-paper" }, table, footer(plan)));
  collapsible(figure, scroll, plan, text);
}

const figure = document.querySelector(".sheet-figure");
if (figure) {
  drawSheet(figure).catch(() => {
    figure.querySelector(".sheet-scroll").replaceChildren();
    figure.querySelector(".sheet-fallback").hidden = false;
  });
}

// A link to a part of the reference opens it: the reference is folded away by default.
function openTarget() {
  const target = location.hash && document.getElementById(location.hash.slice(1));
  const details = target && target.closest("details");
  if (details) details.open = true;
}
window.addEventListener("hashchange", openTarget);
document.addEventListener("click", (event) => {
  const link = event.target.closest('a[href^="#"]');
  const target = link && document.getElementById(link.hash.slice(1));
  const details = target && target.closest("details");
  if (details) details.open = true;
});
openTarget();
