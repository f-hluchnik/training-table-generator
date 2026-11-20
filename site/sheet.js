// The landing page's example sheet: the first weeks of the example season, drawn from the plan.json
// built from `seasons/test-2027.toml`, with a month of colouring already done (D-051).

import { renderSheet, sheetText } from "./sheet-render.js";

// A month of a season already lived: four runs a week, intensity dropped when ill in week 3
// (the sheet's own rule), week 4 under way. Day indexes are Monday = 0.
const DIARY = {
  1: { runs: { 1: "easy", 3: "quality", 5: "easy", 6: "long" }, km: 46 },
  2: { runs: { 1: "easy", 3: "quality", 4: "easy", 6: "long" }, km: 49 },
  3: { runs: { 1: "easy", 5: "easy", 6: "long" }, event: 3, km: 38 },
  4: { runs: { 1: "easy" } },
};

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
  const text = sheetText(JSON.parse(document.getElementById("sheet-text").textContent));
  const response = await fetch(figure.dataset.plan);
  if (!response.ok) throw new Error(`${figure.dataset.plan}: ${response.status}`);
  const plan = await response.json();
  const scroll = figure.querySelector(".sheet-scroll");
  scroll.replaceChildren(renderSheet(plan, text, { diary: DIARY }));
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
