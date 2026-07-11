const STATE_LABEL = { green: "healthy", amber: "warning", red: "critical" };
const shownWarnings = new Set();

function $(id) { return document.getElementById(id); }

function render(status) {
  const s = status.state;

  const time = $("remaining");
  time.textContent = status.remaining_clock;  // H:MM:SS — ticks every second
  time.classList.remove("green", "amber", "red");
  time.classList.add(s);

  const chip = $("state-chip");
  chip.classList.remove("green", "amber", "red");
  chip.classList.add(s);
  $("state-label").textContent = STATE_LABEL[s] || "";

  $("sub-usage").textContent = status.limit_label;

  const fill = $("progress-fill");
  // Depletes with the countdown: full = lots of time, empty = shutdown near.
  fill.style.width = `${status.remaining_pct}%`;
  const bar = $("progress");
  bar.classList.remove("green", "amber", "red");
  bar.classList.add(s);

  const cutoffText = status.cutoff_remaining_hm
    ? `${status.hard_cutoff_time} · in ${status.cutoff_remaining_hm}`
    : "disabled";
  $("cutoff-text").textContent = cutoffText;

  $("session-card").classList.toggle("hidden", !status.session_active);
  if (status.session_active) {
    $("session-text").textContent = `${status.session_remaining_hm} left`;
  }
  $("timer-btn-label").textContent = status.session_active ? "Change work timer" : "Set a work timer";

  $("held-note").classList.toggle("hidden", !status.shutdown_held);
  $("dry-run-note").classList.toggle("hidden", !status.dry_run);

  for (const m of status.recent_warnings) {
    if (!shownWarnings.has(m)) {
      shownWarnings.add(m);
      announceWarning(m);
    }
  }
}

function announceWarning(m) {
  // Phase 1 — minimum warning affordance. Phase 2 replaces with
  // proper pywebview toast windows.
  const note = document.createElement("div");
  note.className = "warning-banner";
  note.textContent = `${m} minute${m === 1 ? "" : "s"} until shutdown. Save your work.`;
  document.body.appendChild(note);
  setTimeout(() => note.remove(), 8000);
}

async function poll() {
  try {
    const status = await window.pywebview.api.get_status();
    render(status);
  } catch (err) {
    console.error("poll failed", err);
  }
}

function wire() {
  $("open-settings").addEventListener("click", () => {
    window.pywebview.api.open_settings();
  });
  $("open-history").addEventListener("click", () => {
    window.pywebview.api.open_history();
  });
  $("hud-hide").addEventListener("click", () => {
    window.pywebview.api.hide_hud();
  });
  $("open-timer").addEventListener("click", () => {
    window.pywebview.api.open_session_prompt();
  });
  $("toggle-dry-run").addEventListener("click", async () => {
    const settings = await window.pywebview.api.get_settings();
    await window.pywebview.api.apply_settings({ dry_run: !settings.dry_run });
    poll();
  });
}

window.addEventListener("pywebviewready", () => {
  wire();
  poll();
  setInterval(poll, 1000);
});
