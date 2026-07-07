function $(id) { return document.getElementById(id); }

function fmtValue(key, value) {
  if (value === null) return "disabled";
  if (key === "dry_run") return value ? "ON" : "OFF";
  if (key === "warning_minutes_before") return Array.isArray(value) ? value.join(",") : String(value);
  return String(value);
}

function renderPending(pending) {
  const list = $("pending-list");
  list.innerHTML = "";
  $("pending-count").textContent = pending.length;
  $("pending-empty-hint").classList.toggle("hidden", pending.length > 0);

  for (const p of pending) {
    const el = document.createElement("div");
    el.className = "pending-item";
    el.innerHTML = `
      <div class="pending-item-head">
        <span class="pending-field"></span>
        <span class="chip amber" style="margin-left: auto;">weakening</span>
      </div>
      <div class="pending-diff">
        <span class="new tnum"></span>
      </div>
      <div class="pending-meta">
        <span>activates ${escapeHtml(p.effective_at_human)}</span>
        <span>in ${escapeHtml(p.remaining_hm)}</span>
      </div>
      <button class="btn sm danger pending-cancel">Cancel</button>
    `;
    el.querySelector(".pending-field").textContent = p.key;
    el.querySelector(".new").textContent = fmtValue(p.key, p.value);
    el.querySelector(".pending-cancel").addEventListener("click", async () => {
      await window.pywebview.api.cancel_pending(p.key);
      await reload();
    });
    list.appendChild(el);
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function applyFormValues(settings) {
  $("daily_cap_minutes").value = settings.daily_cap_minutes;
  $("hard_cutoff_time").value = settings.hard_cutoff_time || "";
  $("warning_minutes_before").value = (settings.warning_minutes_before || []).join(",");
  $("grace_seconds").value = settings.grace_seconds;
  $("idle_threshold_seconds").value = settings.idle_threshold_seconds;
  $("edit_cooldown_hours").value = settings.edit_cooldown_hours;
  $("late_night_hour").value = settings.late_night_hour;
  const toggle = $("dry_run");
  toggle.classList.toggle("on", !!settings.dry_run);
  $("dry-state").textContent = settings.dry_run ? "ON" : "OFF";
  $("dry-state").classList.toggle("tone-amber", !!settings.dry_run);
  $("dry-state").classList.toggle("tone-green", !settings.dry_run);
}

function readFormValues() {
  const warnings = $("warning_minutes_before").value
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean)
    .map((x) => parseInt(x, 10))
    .filter((n) => Number.isFinite(n) && n >= 0);

  const cutoff = $("hard_cutoff_time").value.trim();

  return {
    daily_cap_minutes: parseInt($("daily_cap_minutes").value, 10),
    hard_cutoff_time: cutoff || null,
    warning_minutes_before: [...new Set(warnings)].sort((a, b) => b - a),
    grace_seconds: parseInt($("grace_seconds").value, 10),
    idle_threshold_seconds: parseInt($("idle_threshold_seconds").value, 10),
    edit_cooldown_hours: parseInt($("edit_cooldown_hours").value, 10),
    late_night_hour: parseInt($("late_night_hour").value, 10),
    dry_run: $("dry_run").classList.contains("on"),
  };
}

async function reload() {
  const settings = await window.pywebview.api.get_settings();
  applyFormValues(settings);
  renderPending(settings.pending);
  const status = await window.pywebview.api.get_status();
  $("today-fill").style.width = `${status.used_pct}%`;
  $("today-usage").textContent = `${status.used_hm} / ${status.cap_hm}`;
  $("armed-label").textContent = status.dry_run ? "Dry-run" : "Lock armed";
  $("armed-dot").style.color = status.dry_run ? "var(--amber)" : "var(--green)";
}

function setStatus(msg, cls) {
  const el = $("apply-status");
  el.textContent = msg;
  el.className = `status-msg ${cls || ""}`;
}

function wire() {
  $("dry_run").addEventListener("click", () => {
    const el = $("dry_run");
    el.classList.toggle("on");
    const on = el.classList.contains("on");
    $("dry-state").textContent = on ? "ON" : "OFF";
    $("dry-state").classList.toggle("tone-amber", on);
    $("dry-state").classList.toggle("tone-green", !on);
  });

  $("reload").addEventListener("click", reload);

  $("apply").addEventListener("click", async () => {
    let form;
    try {
      form = readFormValues();
    } catch (err) {
      setStatus(String(err), "err");
      return;
    }
    if (!Number.isFinite(form.daily_cap_minutes) || form.daily_cap_minutes < 0) {
      setStatus("Daily cap must be a non-negative number.", "err");
      return;
    }
    if (!Number.isFinite(form.late_night_hour) || form.late_night_hour < 0 || form.late_night_hour > 24) {
      setStatus("Late-night hour must be between 0 and 24.", "err");
      return;
    }
    // A cleared number field parses to NaN → JSON null → int(None) crash in
    // apply_settings, dropping the whole batch. Reject before sending.
    for (const [key, label] of [
      ["grace_seconds", "Grace seconds"],
      ["idle_threshold_seconds", "Idle threshold"],
      ["edit_cooldown_hours", "Edit cooldown"],
    ]) {
      if (!Number.isFinite(form[key]) || form[key] < 0) {
        setStatus(`${label} must be a non-negative number.`, "err");
        return;
      }
    }
    setStatus("Applying…");
    try {
      const res = await window.pywebview.api.apply_settings(form);
      const parts = [];
      if (res.applied.length) parts.push(`${res.applied.length} applied`);
      if (res.deferred.length) parts.push(`${res.deferred.length} deferred`);
      setStatus(parts.join(" · ") || "No changes.", res.deferred.length ? "warn" : "ok");
      renderPending(res.pending);
      await reload();
    } catch (err) {
      setStatus(String(err.message || err), "err");
    }
  });
}

window.addEventListener("pywebviewready", () => {
  wire();
  reload();
  setInterval(() => {
    // Keep pending countdowns and today-progress fresh without stomping edits.
    window.pywebview.api.get_settings().then((s) => {
      renderPending(s.pending);
    });
    window.pywebview.api.get_status().then((s) => {
      $("today-fill").style.width = `${s.used_pct}%`;
      $("today-usage").textContent = `${s.used_hm} / ${s.cap_hm}`;
    });
  }, 2000);
});
