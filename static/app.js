// Mission Control — report intake. All user/server text is rendered with textContent.
"use strict";

const FIELDS = ["name", "station", "wind_knots", "temp_c", "fuel_pct", "note"];
const NUMERIC = new Set(["wind_knots", "temp_c", "fuel_pct"]);

const form = document.getElementById("report-form");
const submitBtn = document.getElementById("submit");
const statusEl = document.getElementById("status");
const listEl = document.getElementById("reports");
const emptyEl = document.getElementById("empty");

function errorEl(field) {
  return form.querySelector(`[data-error-for="${field}"]`);
}

function clearErrors() {
  form.querySelectorAll(".error").forEach((el) => { el.textContent = ""; });
  form.querySelectorAll("[aria-invalid]").forEach((el) => el.removeAttribute("aria-invalid"));
}

function showErrors(errors) {
  for (const { field, message } of errors) {
    const target = errorEl(field) || errorEl("body");
    target.textContent = message;
    const input = form.elements.namedItem(field);
    if (input) input.setAttribute("aria-invalid", "true");
  }
}

function readForm() {
  const data = {};
  for (const field of FIELDS) {
    const raw = form.elements.namedItem(field).value;
    if (NUMERIC.has(field)) {
      // Send what the user typed; the server decides whether it is a valid number.
      const trimmed = raw.trim();
      if (trimmed === "") continue; // omitted -> server reports "required"
      const num = Number(trimmed);
      data[field] = Number.isNaN(num) ? trimmed : num;
    } else {
      data[field] = raw;
    }
  }
  return data;
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function renderReport(r) {
  const li = el("li", "report");

  const head = el("div", "report-head");
  head.append(el("strong", null, r.name), el("span", "muted", ` · ${r.station}`));
  const when = el("time", "muted", new Date(r.created_at).toLocaleString());
  when.dateTime = r.created_at;
  head.append(when);

  const metrics = el("div", "metrics");
  metrics.append(
    el("span", "metric", `Wind ${r.wind_knots} kn`),
    el("span", "metric", `Temp ${r.temp_c} °C`),
    el("span", "metric", `Fuel ${r.fuel_pct}%`),
  );

  li.append(head, metrics, el("p", "note", r.note));
  return li;
}

function renderList(reports) {
  listEl.replaceChildren(...reports.map(renderReport));
  emptyEl.hidden = reports.length > 0;
}

async function loadReports() {
  try {
    const res = await fetch("/api/reports");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    renderList(await res.json());
  } catch (err) {
    emptyEl.hidden = false;
    emptyEl.textContent = "Could not load reports.";
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearErrors();
  statusEl.textContent = "Sending…";
  submitBtn.disabled = true;

  try {
    const res = await fetch("/api/reports", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(readForm()),
    });
    if (res.status === 422) {
      const body = await res.json();
      showErrors(body.errors || []);
      statusEl.textContent = "Please fix the highlighted fields.";
      return;
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    form.reset();
    statusEl.textContent = "Report filed.";
    await loadReports();
  } catch (err) {
    errorEl("body").textContent = "Could not reach the server. Try again.";
    statusEl.textContent = "";
  } finally {
    submitBtn.disabled = false;
  }
});

loadReports();
