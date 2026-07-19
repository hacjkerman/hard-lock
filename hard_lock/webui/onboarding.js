const STEPS = 5;
let current = 0;
let entering = false;  // true once setup is saved: the button just opens the HUD

function $(id) { return document.getElementById(id); }

function fmtCap(hours) {
  const h = Math.floor(hours);
  const m = Math.round((hours - h) * 60);
  return m ? `${h}h ${m}m` : `${h}h`;
}

function capHours() { return parseFloat($("cap").value); }
function isOn(id) { return $(id).classList.contains("on"); }

function renderDots() {
  const dots = $("dots");
  dots.innerHTML = "";
  for (let i = 0; i < STEPS; i++) {
    const d = document.createElement("span");
    if (i <= current) d.classList.add("on");
    dots.appendChild(d);
  }
}

function showStep(i) {
  current = Math.max(0, Math.min(STEPS - 1, i));
  for (const s of document.querySelectorAll(".step")) {
    s.classList.toggle("hidden", Number(s.dataset.step) !== current);
  }
  renderDots();
  $("back").disabled = current === 0;
  $("next").textContent = current === STEPS - 1 ? "Start Hard Lock" : "Continue";
  $("hint").classList.toggle("hidden", current !== STEPS - 1 && current !== 2);
  if (current === STEPS - 1) buildRecap();
}

function buildRecap() {
  const cutoff = $("cutoff").value.trim();
  const rows = [
    ["Daily active cap", fmtCap(capHours())],
    ["Hard cutoff", cutoff || "off"],
    ["Late-night prompt", $("latenight").value === "24" ? "off" : `from ${String($("latenight").value).padStart(2, "0")}:00`],
    ["Mode", isOn("dry_run") ? "Dry-run (simulated)" : "Armed"],
    ["Start at logon", isOn("autostart") ? "yes" : "no"],
  ];
  const el = $("recap");
  el.innerHTML = "";
  for (const [k, v] of rows) {
    const row = document.createElement("div");
    row.className = "recap-row";
    row.innerHTML = `<span class="k"></span><span class="v"></span>`;
    row.querySelector(".k").textContent = k;
    row.querySelector(".v").textContent = v;
    el.appendChild(row);
  }
}

function collect() {
  const cutoff = $("cutoff").value.trim();
  return {
    daily_cap_minutes: Math.round(capHours() * 60),
    hard_cutoff_time: cutoff || null,
    late_night_hour: parseInt($("latenight").value, 10),
    dry_run: isOn("dry_run"),
    autostart: isOn("autostart"),
  };
}

async function finish() {
  $("next").disabled = true;
  $("back").disabled = true;
  try {
    const res = await window.pywebview.api.finish_onboarding(collect());
    if (isOn("commit-enable")) {
      await window.pywebview.api.commit(parseInt($("commit-duration").value, 10));
    }
    if (res.autostart && !res.autostart.ok) {
      const msg = $("autostart-msg");
      msg.textContent = `Autostart: ${res.autostart.message} You can run install-autostart.bat as administrator later.`;
      msg.classList.remove("hidden");
      entering = true;  // next click routes to enter_app only (no re-finish)
      $("next").textContent = "Open Hard Lock";
      $("next").disabled = false;
      return;
    }
    window.pywebview.api.enter_app();
  } catch (err) {
    console.error("finish failed", err);
    $("next").disabled = false;
  }
}

function wire() {
  $("cap").addEventListener("input", () => { $("cap-val").textContent = capHours() % 1 ? capHours().toFixed(1) : String(capHours()); });
  for (const id of ["dry_run", "autostart", "commit-enable"]) {
    $(id).addEventListener("click", () => $(id).classList.toggle("on"));
  }
  $("back").addEventListener("click", () => showStep(current - 1));
  $("next").addEventListener("click", () => {
    if (entering) { window.pywebview.api.enter_app(); return; }
    if (current === STEPS - 1) finish();
    else showStep(current + 1);
  });
}

async function init() {
  try {
    const info = await window.pywebview.api.get_onboarding_info();
    if (Number.isFinite(info.daily_cap_minutes)) {
      const h = info.daily_cap_minutes / 60;
      $("cap").value = h;
      $("cap-val").textContent = h % 1 ? h.toFixed(1) : String(h);
    }
    if (info.hard_cutoff_time) $("cutoff").value = info.hard_cutoff_time;
    if (Number.isFinite(info.late_night_hour)) $("latenight").value = info.late_night_hour;
    $("dry_run").classList.toggle("on", info.dry_run !== false);
  } catch (err) {
    console.error("onboarding info failed", err);
  }
  showStep(0);
}

window.addEventListener("pywebviewready", () => {
  wire();
  init();
});
