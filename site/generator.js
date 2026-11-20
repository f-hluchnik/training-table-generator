// The generator page (D-052): a form for the season file, the same Python generator the command line
// runs (`ttg.web`, under Pyodide in the browser), and the sheet drawn from its plan.json.
// Nothing the visitor types leaves the browser; it is kept in localStorage only to be there next time.

import { element, renderSheet, sheetText } from "./sheet-render.js";

// The Python runtime, pinned: a new version could change how it loads under us.
const PYODIDE_URL = "https://cdn.jsdelivr.net/pyodide/v314.0.8/full/";
const STORAGE_KEY = "ttg-generator-form-1";

// The fields of the form, by name. A name is the field's path in the season file; the fields of a
// repeated row (a race, a week's change) are named from the row.
const FIELDS = [
  "start",
  "weeks",
  "sheet.title",
  "sheet.rules",
  "paces.race_result.distance_km",
  "paces.race_result.time",
  "paces.easy",
  "paces.mp",
  "paces.threshold",
  "paces.interval",
  "load.beginner",
  "load.easy_run_km",
  "load.long_run_km",
  "load.runs_per_week",
];
// What only a runner who trains regularly must give (D-054). With the level left open the generator
// decides it (`ttg.web`), so these are required only when "I train regularly" is chosen.
const REQUIRED_WHEN_REGULAR = ["paces.race_result.distance_km", "paces.race_result.time", "load.easy_run_km"];
const LEVEL = "load.beginner";
const ROW_FIELDS = {
  race: [
    "name",
    "date",
    "end",
    "distance_km",
    "priority",
    "taper_weeks",
    "specific_weeks",
    "recovery_weeks",
    "hilly",
    "goal",
  ],
  override: ["week", "easy", "quality.type", "quality.reps", "quality.minutes", "quality.km", "long_run_km", "note"],
};
// What a race that is only a tune-up (priority C) has no use for: it has no phases of its own.
const PHASE_FIELDS = ["taper_weeks", "specific_weeks", "recovery_weeks", "hilly"];
// The quality fields of a session without repetitions (strides, none).
const REPETITION_FIELDS = ["quality.reps", "quality.minutes", "quality.km"];

// The printed page, as the PDF's (D-028, D-049): A4 landscape, 8 mm margins; the rows shrink with the
// number of weeks, and the text with them. `chrome` is the title and the footer, with a margin for
// error, measured on a printed sheet; `border` is what a row's line adds to it. The browser's rows
// need a little less than the PDF's to fit 40 weeks on a page.
const PAGE_MM = { width: 281, height: 194, chrome: 38, border: 0.27 };
const ROW_MM = { max: 6.4, min: 3.5 };
const FONT_PT = { max: 8, min: 7 };
const MM_PER_PX = 25.4 / 96;

const form = document.getElementById("generator");
const text = sheetText(JSON.parse(document.getElementById("generator-text").textContent));
const lists = { race: document.getElementById("races"), override: document.getElementById("overrides") };
const templates = { race: document.getElementById("race-template"), override: document.getElementById("override-template") };
const result = document.getElementById("result");
const status = document.getElementById("status");

// --- the form's values --------------------------------------------------------

// { "a.b": 1 } → { a: { b: 1 } }
function nest(entries) {
  const root = {};
  for (const [path, value] of entries) {
    const keys = path.split(".");
    const last = keys.pop();
    keys.reduce((node, key) => (node[key] ??= {}), root)[last] = value;
  }
  return root;
}

function lookup(object, path) {
  return path.split(".").reduce((node, key) => node?.[key], object);
}

const control = (scope, name) => scope.querySelector(`[name="${name}"]`);
// A pair of radio buttons is a yes or no, or null while neither is chosen.
const radios = (input) => input.form.querySelectorAll(`[name="${input.name}"]`);
function read(input) {
  if (input.type === "checkbox") return input.checked;
  if (input.type === "radio") {
    const chosen = [...radios(input)].find((radio) => radio.checked);
    return chosen ? chosen.value === "true" : null;
  }
  return input.value;
}
function write(input, value) {
  if (input.type === "checkbox") input.checked = value === true;
  else if (input.type === "radio") for (const radio of radios(input)) radio.checked = radio.value === String(value);
  else input.value = typeof value === "string" ? value : "";
}

const rows = (kind) => [...lists[kind].children];

function collect() {
  const fields = nest(FIELDS.map((name) => [name, read(control(form, name))]));
  const rowValues = (kind) => rows(kind).map((row) => nest(ROW_FIELDS[kind].map((name) => [name, read(control(row, name))])));
  return { ...fields, race: rowValues("race"), overrides: rowValues("override") };
}

function restore(values) {
  for (const name of FIELDS) write(control(form, name), lookup(values, name));
  for (const kind of Object.keys(lists)) {
    lists[kind].replaceChildren();
    for (const rowValues of values[kind === "override" ? "overrides" : kind] ?? []) {
      const row = addRow(kind);
      for (const name of ROW_FIELDS[kind]) write(control(row, name), lookup(rowValues, name));
      syncRow(row);
    }
  }
  if (!rows("race").length) addRow("race");
  syncLevel();
  openFilledFolds();
}

// A fold that has something in it is open, so nothing the visitor entered is hidden.
function openFilledFolds() {
  const filled = (input) => (input.type === "checkbox" ? input.checked : input.value !== "");
  for (const fold of form.querySelectorAll("details[data-fold]")) {
    fold.open = [...fold.querySelectorAll("input, select, textarea")].some(filled);
  }
}

// The last form the visitor built, if the browser keeps it. Nothing depends on it.
function save(values) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(values));
  } catch {
    // private mode or no storage: the form simply starts empty next time
  }
}

function saved() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY));
  } catch {
    return null;
  }
}

// --- repeated rows: races and a week's changes ---------------------------------

function addRow(kind) {
  const row = templates[kind].content.firstElementChild.cloneNode(true);
  lists[kind].append(row);
  numberRows(kind);
  return row;
}

function numberRows(kind) {
  rows(kind).forEach((row, index) => {
    row.querySelector(".row-title").textContent = text[kind].replace("{n}", index + 1);
    // A season needs a race: the only one cannot be removed.
    row.querySelector(".remove-row").hidden = kind === "race" && rows(kind).length === 1;
  });
}

// What one field makes of the others in its row.
function syncRow(row) {
  const priority = control(row, "priority");
  if (priority) {
    const tuneUp = priority.value === "C";
    for (const name of PHASE_FIELDS) {
      const input = control(row, name);
      input.disabled = tuneUp;
      if (tuneUp) write(input, "");
    }
  }
  const type = control(row, "quality.type");
  if (type) {
    const repeated = type.selectedOptions[0]?.hasAttribute("data-repeated");
    for (const name of REPETITION_FIELDS) {
      const input = control(row, name);
      input.disabled = !repeated;
      if (!repeated) write(input, "");
    }
  }
}

function syncLevel() {
  const regular = read(control(form, LEVEL)) === false;
  for (const name of REQUIRED_WHEN_REGULAR) control(form, name).required = regular;
}

// A race needs a name for the list under the table; an unnamed one is called as its row is.
function withRaceNames(values) {
  const race = values.race.map((entry, index) => ({ ...entry, name: entry.name.trim() || text.race.replace("{n}", index + 1) }));
  return { ...values, race };
}

form.addEventListener("change", (event) => {
  const row = event.target.closest(".row");
  if (row) syncRow(row);
  syncLevel();
});

form.addEventListener("click", (event) => {
  const add = event.target.closest("[data-add]");
  if (add) {
    const row = addRow(add.dataset.add);
    syncRow(row);
    control(row, ROW_FIELDS[add.dataset.add][0]).focus();
  }
  const remove = event.target.closest(".remove-row");
  if (remove) {
    const row = remove.closest(".row");
    const kind = row.dataset.kind;
    row.remove();
    numberRows(kind);
  }
});

// --- Python in the browser, in a worker ----------------------------------------

// A plan of the longest length builds in well under a second (D-053); a build that is still going
// after this is stopped, so a page can never hang on one.
const GENERATE_TIMEOUT_MS = 10_000;

class TimedOut extends Error {}

let worker;
let ready;
let nextId = 0;
const pending = new Map();

function settle(id, outcome, value) {
  const request = pending.get(id);
  if (!request) return;
  clearTimeout(request.timer);
  pending.delete(id);
  request[outcome](value);
}

// Ends the worker, and every request waiting for it; the next one starts a new worker.
function stopWorker(reason) {
  worker?.terminate();
  worker = undefined;
  ready = undefined;
  for (const id of [...pending.keys()]) settle(id, "reject", reason);
}

function send(message, timeoutMs) {
  return new Promise((resolve, reject) => {
    const id = nextId++;
    const timer = timeoutMs && setTimeout(() => stopWorker(new TimedOut()), timeoutMs);
    pending.set(id, { resolve, reject, timer });
    worker.postMessage({ id, ...message });
  });
}

// Started once, on first need; the page asks at once, since the generator is what the page is for.
function loadGenerator() {
  if (!worker) {
    worker = new Worker(new URL("./generator-worker.js", import.meta.url), { type: "module" });
    worker.onmessage = ({ data }) =>
      data.error === undefined ? settle(data.id, "resolve", data.result) : settle(data.id, "reject", new Error(data.error));
    worker.onerror = (event) => stopWorker(new Error(event.message || "the generator's worker failed"));
    const load = { kind: "load", pyodideUrl: PYODIDE_URL, wheelUrl: new URL(form.dataset.wheel, location.href).href };
    // A failed load is not kept: the next submit starts a new worker and tries again.
    ready = send(load).catch((error) => {
      stopWorker(error);
      throw error;
    });
  }
  return ready;
}

async function generate(values) {
  await loadGenerator();
  const reply = await send({ kind: "generate", form: JSON.stringify(values), today: today() }, GENERATE_TIMEOUT_MS);
  return JSON.parse(reply);
}

function today() {
  const now = new Date();
  const pad = (number) => String(number).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

// --- showing the outcome ------------------------------------------------------

function setStatus(message) {
  status.textContent = message;
}

function clearOutcome() {
  for (const input of form.querySelectorAll("[aria-invalid]")) input.removeAttribute("aria-invalid");
  for (const input of form.elements) input.setCustomValidity("");
  result.querySelector(".problem").hidden = true;
  result.querySelector(".slow").hidden = true;
}

// A message is about what was typed when it came; a changed form is a new question.
form.addEventListener("input", clearOutcome);

// The input a message is about: its path, as `race[2].date` or `overrides.13.quality.reps`.
function inputFor(path) {
  const race = path.match(/^race\[(\d+)\]\.(\w+)/);
  if (race) return rows("race")[race[1] - 1] && control(rows("race")[race[1] - 1], race[2]);
  const indexed = path.match(/^overrides\[(\d+)\]\.(\w+)/);
  if (indexed) return rows("override")[indexed[1] - 1] && control(rows("override")[indexed[1] - 1], indexed[2]);
  const week = path.match(/^overrides\.(\d+)(\.quality)?(?:\.(\w+))?/);
  if (week) {
    const row = rows("override").find((candidate) => Number(control(candidate, "week").value) === Number(week[1]));
    return row && control(row, week[3] ? `${week[2] ? "quality." : ""}${week[3]}` : week[2] ? "quality.minutes" : "week");
  }
  return control(form, path);
}

function showProblem(message) {
  const problem = result.querySelector(".problem");
  // The messages come from the generator, in English, and name the field as the season file does.
  problem.querySelector(".message").textContent = message;
  problem.hidden = false;
  const path = message.match(/^([\w.[\]]+): /)?.[1];
  const input = path && inputFor(path);
  if (input) {
    input.setAttribute("aria-invalid", "true");
    input.closest("details")?.setAttribute("open", "");
    // The browser's own bubble at the field, so the message is seen where the mistake is.
    input.setCustomValidity(message);
    input.reportValidity();
  } else {
    problem.scrollIntoView({ block: "nearest" });
  }
}

function showWarnings(warnings) {
  const box = result.querySelector(".warnings");
  box.hidden = warnings.length === 0;
  box.querySelector("ul").replaceChildren(
    ...warnings.map((warning) =>
      element(
        "li",
        {},
        element("a", { href: `${form.dataset.reference}#${warning.code.toLowerCase()}` }, warning.code),
        warning.week === null ? " " : ` ${text.week.replace("{week}", warning.week)}: `,
        element("span", { lang: "en" }, warning.message)
      )
    )
  );
}

// The sheet on paper: the rows sized in mm like the PDF's, and the widths (all in rem) shrunk to the
// page's width if the sheet is wider. A root font size, not `zoom`: a zoomed table breaks inside a row.
function fitToPage(paper, weeks) {
  // The header row is a row too.
  const fitting = (PAGE_MM.height - PAGE_MM.chrome) / (weeks + 1) - PAGE_MM.border;
  const rowMm = Math.min(ROW_MM.max, Math.max(ROW_MM.min, fitting));
  const share = (ROW_MM.max - rowMm) / (ROW_MM.max - ROW_MM.min);
  const scale = Math.min(1, PAGE_MM.width / (paper.offsetWidth * MM_PER_PX));
  const root = document.documentElement.style;
  root.setProperty("--print-scale", scale.toFixed(3));
  root.setProperty("--print-row", `${rowMm.toFixed(3)}mm`);
  root.setProperty("--print-font", `${(FONT_PT.max - share * (FONT_PT.max - FONT_PT.min)).toFixed(2)}pt`);
}

function showResult({ plan, season_toml: seasonToml }) {
  const paper = renderSheet(plan, text, { title: true });
  result.querySelector(".sheet-scroll").replaceChildren(paper);
  fitToPage(paper, plan.weeks.length);
  showWarnings(plan.warnings);
  result.querySelector(".season-file pre").textContent = seasonToml;
  result.querySelector(".download").onclick = () => {
    const url = URL.createObjectURL(new Blob([seasonToml], { type: "text/plain;charset=utf-8" }));
    element("a", { href: url, download: "season.toml" }).click();
    URL.revokeObjectURL(url);
  };
  for (const part of result.querySelectorAll("[data-after-build]")) part.hidden = false;
  result.focus({ preventScroll: true });
  result.scrollIntoView({ block: "start" });
}

result.querySelector(".print").addEventListener("click", () => window.print());

// --- the form is sent ---------------------------------------------------------

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearOutcome();
  setStatus(text.building);
  const submit = form.querySelector('button[type="submit"]');
  submit.disabled = true;
  try {
    const reply = await generate(withRaceNames(collect()));
    if (reply.error) showProblem(reply.error);
    else {
      // The level the plan was made for, also when the generator chose it.
      write(control(form, LEVEL), reply.beginner);
      syncLevel();
      save(collect());
      showResult(reply);
    }
  } catch (error) {
    console.error(error);
    result.querySelector(error instanceof TimedOut ? ".slow" : ".failure").hidden = false;
  } finally {
    submit.disabled = false;
    setStatus("");
  }
});

// --- the page starts ----------------------------------------------------------

const earlier = saved();
if (earlier) {
  try {
    restore(earlier);
  } catch (error) {
    // a form saved by another version of the page: start empty
    console.warn(error);
    restore({});
  }
} else {
  restore({});
}
for (const row of document.querySelectorAll(".row")) syncRow(row);

setStatus(text.loading);
loadGenerator()
  .then(() => {
    if (status.textContent === text.loading) setStatus("");
  })
  .catch((error) => {
    console.error(error);
    setStatus("");
    result.querySelector(".failure").hidden = false;
  });
