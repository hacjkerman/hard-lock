function $(id) { return document.getElementById(id); }

let dayKeys = [];  // ["mon", … "sun"], from get_settings
const armedActivate = new Set();  // pending keys one click into "Activate now"
const DAY_LABEL = { mon: "Mon", tue: "Tue", wed: "Wed", thu: "Thu", fri: "Fri", sat: "Sat", sun: "Sun" };

function fieldLabel(key) {
  let m = key.match(/^cap_(\w+)$/);
  if (m) return `${DAY_LABEL[m[1]] || m[1]} cap`;
  m = key.match(/^cutoff_(\w+)$/);
  if (m) return `${DAY_LABEL[m[1]] || m[1]} cutoff`;
  return key;
}

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
      <div class="pending-actions">
        <button class="btn sm pending-activate">Activate now</button>
        <button class="btn sm danger pending-cancel">Cancel</button>
      </div>
    `;
    el.querySelector(".pending-field").textContent = fieldLabel(p.key);
    el.querySelector(".new").textContent = fmtValue(p.key, p.value);
    el.querySelector(".pending-cancel").addEventListener("click", async () => {
      await window.pywebview.api.cancel_pending(p.key);
      await reload();
    });

    // Manual override: first click arms, second click applies now (skips the
    // cooldown). Armed state lives in armedActivate so the 2s poll re-render
    // doesn't reset it mid-confirm.
    const actBtn = el.querySelector(".pending-activate");
    if (armedActivate.has(p.key)) {
      actBtn.textContent = "Skip cooldown?";
      actBtn.classList.add("danger");
    }
    actBtn.addEventListener("click", async () => {
      if (!armedActivate.has(p.key)) {
        armedActivate.add(p.key);
        actBtn.textContent = "Skip cooldown?";
        actBtn.classList.add("danger");
        setTimeout(() => armedActivate.delete(p.key), 3000);
        return;
      }
      armedActivate.delete(p.key);
      await window.pywebview.api.activate_pending(p.key);
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

function buildPerDay(settings) {
  dayKeys = settings.day_keys || [];
  // A queued (deferred) edit isn't in force yet, but show it in the grid — with
  // an amber "queued" mark — so the change stays visible and re-applying is a
  // no-op instead of silently reverting to the current value.
  const pend = {};
  for (const p of settings.pending || []) pend[p.key] = p.value;
  const body = $("perday-body");
  body.innerHTML = "";
  dayKeys.forEach((k, i) => {
    const tr = document.createElement("tr");
    if (i === settings.today_index) tr.className = "today";
    tr.innerHTML = `
      <td class="perday-day"></td>
      <td><input id="cap_${k}" class="field perday-cap" type="number" min="0" step="5" /></td>
      <td><input id="cutoff_${k}" class="field perday-cutoff" type="time" /></td>
    `;
    tr.querySelector(".perday-day").textContent = settings.day_labels[i];
    body.appendChild(tr);
    const capK = `cap_${k}`, cutK = `cutoff_${k}`;
    const capQ = capK in pend, cutQ = cutK in pend;
    $(capK).value = capQ ? pend[capK] : settings.cap_by_day[i];
    $(cutK).value = (cutQ ? pend[cutK] : settings.cutoff_by_day[i]) || "";
    if (capQ) markQueued($(capK));
    if (cutQ) markQueued($(cutK));
  });
}

function markQueued(input) {
  input.classList.add("queued");
  input.title = "Queued — activates after your cooldown (see Pending changes).";
}

function applyFormValues(settings) {
  buildPerDay(settings);
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

let autostartBusy = false;

function setAutostartToggle(on) {
  $("autostart").classList.toggle("on", on);
  $("autostart-state").textContent = on ? "ON" : "OFF";
  $("autostart-state").classList.toggle("tone-green", on);
  $("autostart-state").classList.toggle("tone-amber", !on);
}

async function onAutostartToggle() {
  if (autostartBusy) return;
  autostartBusy = true;
  const wantOn = !$("autostart").classList.contains("on");
  $("autostart-hint").textContent = "Approve the Windows prompt…";
  try {
    await window.pywebview.api.set_autostart(wantOn);
    // Installing/removing runs elevated (UAC) and is async — poll the real state.
    let installed = !wantOn;
    for (let i = 0; i < 6; i++) {
      await new Promise((r) => setTimeout(r, 700));
      installed = (await window.pywebview.api.get_autostart_status()).installed;
      if (installed === wantOn) break;
    }
    setAutostartToggle(installed);
    $("autostart-hint").textContent =
      installed === wantOn
        ? (wantOn ? "Enabled — Hard Lock will start at logon." : "Disabled.")
        : "Not changed (prompt declined). You can run install-autostart.bat as admin.";
  } catch (err) {
    $("autostart-hint").textContent = "Failed: " + (err.message || err);
  } finally {
    autostartBusy = false;
  }
}

function readFormValues() {
  const warnings = $("warning_minutes_before").value
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean)
    .map((x) => parseInt(x, 10))
    .filter((n) => Number.isFinite(n) && n >= 0);

  const form = {
    warning_minutes_before: [...new Set(warnings)].sort((a, b) => b - a),
    grace_seconds: parseInt($("grace_seconds").value, 10),
    idle_threshold_seconds: parseInt($("idle_threshold_seconds").value, 10),
    edit_cooldown_hours: parseInt($("edit_cooldown_hours").value, 10),
    late_night_hour: parseInt($("late_night_hour").value, 10),
    dry_run: $("dry_run").classList.contains("on"),
  };
  for (const k of dayKeys) {
    form[`cap_${k}`] = parseInt($(`cap_${k}`).value, 10);
    const c = $(`cutoff_${k}`).value.trim();
    form[`cutoff_${k}`] = c || null;
  }
  return form;
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
  // Autostart state is queried separately (schtasks), so it's not part of the
  // frequent get_settings poll.
  if (!autostartBusy) {
    window.pywebview.api
      .get_autostart_status()
      .then((s) => setAutostartToggle(!!s.installed))
      .catch(() => {});
  }
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

  $("autostart").addEventListener("click", onAutostartToggle);

  $("reload").addEventListener("click", reload);

  $("apply").addEventListener("click", async () => {
    let form;
    try {
      form = readFormValues();
    } catch (err) {
      setStatus(String(err), "err");
      return;
    }
    for (const k of dayKeys) {
      if (!Number.isFinite(form[`cap_${k}`]) || form[`cap_${k}`] < 0) {
        setStatus("Each day's cap must be a non-negative number.", "err");
        return;
      }
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
      if (res.applied.length) parts.push(`${res.applied.length} applied now`);
      if (res.deferred.length) parts.push(`${res.deferred.length} queued (activates after cooldown — see Pending changes)`);
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
