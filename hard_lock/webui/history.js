const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const TONE = { red: "var(--red)", amber: "var(--amber)", green: "var(--green)", neutral: "var(--text-tertiary)" };

function $(id) { return document.getElementById(id); }

function fmtDate(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return `${MONTHS[m - 1]} ${d}`;
}

function statCard({ label, value, note, tone }) {
  const el = document.createElement("div");
  el.className = "bigstat";
  const color = tone ? `style="color: ${tone}"` : "";
  el.innerHTML = `
    <div class="label">${label}</div>
    <div class="value" ${color}></div>
    <div class="note"></div>`;
  el.querySelector(".value").textContent = value;
  el.querySelector(".note").textContent = note || "";
  return el;
}

function renderStats(stats) {
  const grid = $("stats-grid");
  grid.innerHTML = "";
  const capH = stats.cap_hours;
  [
    { label: "Current streak", value: `${stats.current_streak} days`, note: "under cap", tone: TONE.green },
    { label: "Best streak", value: `${stats.best_streak} days`, note: "in this window" },
    { label: "Avg active", value: stats.avg_active_hm, note: "per active day" },
    { label: "Shutdowns", value: String(stats.shutdowns), note: "in last 42 days", tone: stats.shutdowns ? TONE.red : null },
  ].forEach((s) => grid.appendChild(statCard(s)));
  return capH;
}

function renderChart(days, capHours) {
  const chart = $("chart");
  chart.innerHTML = "";
  const maxActive = days.reduce((m, d) => Math.max(m, d.active_hours), 0);
  const scaleTop = Math.max(capHours * 1.5, maxActive * 1.05, 1);

  const capLine = document.createElement("div");
  capLine.className = "cap-line";
  capLine.style.bottom = `${(capHours / scaleTop) * 100}%`;
  capLine.innerHTML = `<span class="cap-label">CAP ${capHours % 1 ? capHours.toFixed(1) : capHours}h</span>`;
  chart.appendChild(capLine);

  for (const d of days) {
    const col = document.createElement("div");
    col.className = "bar-col";
    col.title = `${d.date} · ${d.active_hm}${d.hit_cap ? " · hit cap" : ""}${d.shutdown ? " · shutdown" : ""}`;
    const h = Math.max(0, Math.min(100, (d.active_hours / scaleTop) * 100));
    const bar = document.createElement("div");
    bar.className = "bar" + (d.hit_cap ? " hit" : "") + (d.has_data ? "" : " empty");
    bar.style.height = `${h}%`;
    col.appendChild(bar);
    if (d.shutdown) {
      const marker = document.createElement("div");
      marker.className = "marker";
      col.appendChild(marker);
    }
    chart.appendChild(col);
  }

  const axis = $("chart-axis");
  axis.innerHTML = "";
  const idxs = [0, Math.floor((days.length - 1) / 3), Math.floor((2 * (days.length - 1)) / 3), days.length - 1];
  for (const i of idxs) {
    const s = document.createElement("span");
    s.textContent = fmtDate(days[i].date);
    axis.appendChild(s);
  }
}

function renderEvents(events) {
  const list = $("events-list");
  list.innerHTML = "";
  $("events-empty").classList.toggle("hidden", events.length > 0);
  for (const e of events) {
    const row = document.createElement("div");
    row.className = "event-row";
    row.innerHTML = `
      <div class="when"></div>
      <span class="dot" style="background: ${TONE[e.tone] || TONE.neutral}"></span>
      <div class="label"></div>`;
    row.querySelector(".when").textContent = e.when;
    row.querySelector(".label").textContent = e.label;
    list.appendChild(row);
  }
}

async function refresh() {
  try {
    const h = await window.pywebview.api.get_history();
    const capH = renderStats(h.stats);
    renderChart(h.days, capH);
    renderEvents(h.events);
  } catch (err) {
    console.error("history refresh failed", err);
  }
}

window.addEventListener("pywebviewready", () => {
  refresh();
  setInterval(refresh, 5000);
});
