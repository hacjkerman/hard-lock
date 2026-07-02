const PRESETS = [15, 30, 45, 60];

let maxMinutes = 120;
let minMinutes = 5;
let minutes = 30;

function $(id) { return document.getElementById(id); }

function clamp(n) {
  if (!Number.isFinite(n)) return minMinutes;
  return Math.max(minMinutes, Math.min(maxMinutes, Math.round(n)));
}

function fmtLabel(m) {
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  const rem = m % 60;
  return rem ? `${h}h${String(rem).padStart(2, "0")}` : `${h}h`;
}

function paintSlider() {
  const span = maxMinutes - minMinutes || 1;
  const pct = ((minutes - minMinutes) / span) * 100;
  const slider = $("minutes-slider");
  slider.value = minutes;
  slider.style.background =
    `linear-gradient(to right, var(--accent) 0 ${pct}%, var(--surface-sunken) ${pct}% 100%)`;
}

function setMinutes(n) {
  minutes = clamp(n);
  $("minutes-value").textContent = minutes;
  paintSlider();
  for (const btn of document.querySelectorAll(".preset")) {
    btn.classList.toggle("active", Number(btn.dataset.min) === minutes);
  }
}

function renderPresets() {
  const wrap = $("presets");
  wrap.innerHTML = "";
  for (const p of PRESETS) {
    const btn = document.createElement("button");
    btn.className = "preset";
    btn.dataset.min = p;
    btn.textContent = `${p}m`;
    btn.disabled = p > maxMinutes;
    btn.addEventListener("click", () => setMinutes(p));
    wrap.appendChild(btn);
  }
}

async function init() {
  try {
    const info = await window.pywebview.api.get_session_prompt_info();
    maxMinutes = Math.max(1, info.max_minutes);
    minMinutes = Math.min(5, maxMinutes);

    if (info.late_night_hour != null) {
      const hh = String(info.late_night_hour).padStart(2, "0");
      $("eyebrow").textContent = `It's after ${hh}:00`;
    }
    if (Number.isFinite(info.grace_seconds)) {
      $("grace-note").textContent = `${info.grace_seconds}-second`;
    }
    if (info.hard_cutoff_time && info.cutoff_remaining_hm) {
      $("floor-text").textContent =
        `Shuts down by ${info.hard_cutoff_time} at the latest · ${info.cutoff_remaining_hm} left before then.`;
    } else {
      $("floor-text").textContent = `At most ${fmtLabel(maxMinutes)} before your daily cap.`;
    }
  } catch (err) {
    console.error("prompt info failed", err);
  }

  const slider = $("minutes-slider");
  slider.min = String(minMinutes);
  slider.max = String(maxMinutes);
  $("slider-min").textContent = fmtLabel(minMinutes);
  $("slider-max").textContent = fmtLabel(maxMinutes);

  renderPresets();
  setMinutes(Math.min(30, maxMinutes));
}

function wire() {
  $("minutes-slider").addEventListener("input", (e) => setMinutes(Number(e.target.value)));

  $("start").addEventListener("click", async () => {
    disable();
    await window.pywebview.api.start_session_timer(minutes);
  });
  $("skip").addEventListener("click", async () => {
    disable();
    await window.pywebview.api.skip_session_timer();
  });
}

function disable() {
  for (const el of document.querySelectorAll("button, input")) el.disabled = true;
}

window.addEventListener("pywebviewready", () => {
  wire();
  init();
});
