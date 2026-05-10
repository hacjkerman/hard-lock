import tkinter as tk
from tkinter import messagebox, ttk

from .shutdown import initiate_shutdown


def fmt(seconds: float) -> str:
    s = max(0, int(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:d}:{m:02d}:{sec:02d}"


def show_warning(message: str) -> None:
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    messagebox.showwarning("HARD LOCK", message, parent=root)
    root.destroy()


class GraceCountdown:
    def __init__(self, seconds: int, dry_run: bool):
        self.remaining = seconds
        self.dry_run = dry_run
        self.root = tk.Tk()
        self.root.title("HARD LOCK — Shutting Down")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="black")
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)

        bar = tk.Frame(self.root, bg="black", padx=20, pady=10)
        bar.pack()

        self.label = tk.Label(
            bar, text="", fg="red", bg="black",
            font=("Consolas", 48, "bold"),
        )
        self.label.pack(side="left", padx=(0, 20))
        tk.Label(
            bar,
            text="SAVE YOUR WORK — SHUTDOWN CANNOT BE CANCELED",
            fg="white", bg="black", font=("Consolas", 14, "bold"),
        ).pack(side="left")

        self.root.update_idletasks()
        w = self.root.winfo_reqwidth()
        sw = self.root.winfo_screenwidth()
        self.root.geometry(f"+{(sw - w) // 2}+0")
        self._keep_on_top()

    def _keep_on_top(self) -> None:
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(500, self._keep_on_top)

    def run(self) -> None:
        self._tick()
        self.root.mainloop()

    def _tick(self) -> None:
        if self.remaining <= 0:
            self.root.destroy()
            initiate_shutdown(dry_run=self.dry_run)
            return
        self.label.config(text=str(self.remaining))
        self.remaining -= 1
        self.root.after(1000, self._tick)


class StatusWindow:
    def __init__(self, config, state, tracker):
        self.config = config
        self.state = state
        self.tracker = tracker
        self.warnings_fired: set = set()
        self._grace_triggered = False

        self.root = tk.Tk()
        self.root.title("Hard Lock")
        self.root.geometry("380x320")
        self.root.attributes("-topmost", True)

        self.remaining_label = tk.Label(
            self.root, text="--:--:--", font=("Consolas", 32, "bold")
        )
        self.remaining_label.pack(pady=16)

        self.used_label = tk.Label(self.root, text="", font=("Consolas", 11))
        self.used_label.pack()
        self.cutoff_label = tk.Label(self.root, text="", font=("Consolas", 11))
        self.cutoff_label.pack()
        self.cap_label = tk.Label(self.root, text="", font=("Consolas", 11))
        self.cap_label.pack(pady=(10, 0))
        self.pending_label = tk.Label(
            self.root, text="", font=("Consolas", 10), fg="orange"
        )
        self.pending_label.pack(pady=(4, 0))
        self.mode_label = tk.Label(
            self.root, text="", font=("Consolas", 10), fg="gray"
        )
        self.mode_label.pack(pady=(6, 0))

        tk.Button(
            self.root, text="Settings", command=self._open_settings
        ).pack(pady=(10, 0))

    def _open_settings(self) -> None:
        SettingsWindow(self.root, self.config)

    def run(self) -> None:
        self._tick()
        self.root.mainloop()

    def _effective_remaining(self) -> float:
        r = self.config.remaining_seconds(self.state)
        c = self.config.cutoff_remaining_seconds()
        return r if c is None else min(r, c)

    def _tick(self) -> None:
        if self._grace_triggered:
            return

        delta = self.tracker.tick()
        self.state.accumulate(delta)
        self.state.save()

        effective = self._effective_remaining()
        cutoff = self.config.cutoff_remaining_seconds()

        self.remaining_label.config(text=fmt(effective))
        self.used_label.config(text=f"Used today: {fmt(self.state.used_seconds)}")
        self.cutoff_label.config(
            text=(
                f"Hard cutoff in: {fmt(cutoff)}"
                if cutoff is not None
                else "Hard cutoff: disabled"
            )
        )
        self.cap_label.config(text=f"Daily cap: {self.config.daily_cap_minutes} min")
        self.pending_label.config(text=self.config.pending_summary() or "")
        self.mode_label.config(text="DRY RUN MODE" if self.config.dry_run else "ARMED")

        for w in sorted(self.config.warning_minutes_before, reverse=True):
            if w not in self.warnings_fired and effective <= w * 60:
                self.warnings_fired.add(w)
                self.root.after(0, lambda w=w: show_warning(f"{w} minute(s) until shutdown."))

        if effective <= self.config.grace_seconds:
            self._grace_triggered = True
            self.root.destroy()
            GraceCountdown(self.config.grace_seconds, self.config.dry_run).run()
            return

        self.root.after(1000, self._tick)


class SettingsWindow:
    def __init__(self, parent: tk.Tk, config):
        self.config = config
        self.top = tk.Toplevel(parent)
        self.top.title("Hard Lock — Settings")
        self.top.attributes("-topmost", True)
        self.top.transient(parent)
        self.top.grab_set()

        frm = ttk.Frame(self.top, padding=12)
        frm.pack(fill="both", expand=True)

        self.vars: dict[str, tk.Variable] = {}
        row = 0

        def add_entry(label: str, key: str, value: str, width: int = 14) -> None:
            nonlocal row
            ttk.Label(frm, text=label).grid(row=row, column=0, sticky="w", pady=3)
            var = tk.StringVar(value=value)
            ttk.Entry(frm, textvariable=var, width=width).grid(
                row=row, column=1, sticky="w", pady=3, padx=(8, 0)
            )
            self.vars[key] = var
            row += 1

        add_entry(
            "Daily cap (minutes):",
            "daily_cap_minutes",
            str(self.config.daily_cap_minutes),
        )
        add_entry(
            "Hard cutoff (HH:MM, blank=off):",
            "hard_cutoff_time",
            self.config.hard_cutoff_time or "",
        )
        add_entry(
            "Warnings before (min, csv):",
            "warning_minutes_before",
            ",".join(str(x) for x in self.config.warning_minutes_before),
            width=20,
        )
        add_entry(
            "Grace seconds:",
            "grace_seconds",
            str(self.config.grace_seconds),
        )
        add_entry(
            "Idle threshold (sec):",
            "idle_threshold_seconds",
            str(self.config.idle_threshold_seconds),
        )
        add_entry(
            "Edit cooldown (hours):",
            "edit_cooldown_hours",
            str(self.config.edit_cooldown_hours),
        )

        dry_var = tk.BooleanVar(value=self.config.dry_run)
        ttk.Checkbutton(
            frm, text="Dry run (no real shutdown)", variable=dry_var
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(8, 3))
        self.vars["dry_run"] = dry_var
        row += 1

        ttk.Label(
            frm,
            text=(
                "Weakening changes (raise cap, push cutoff later,\n"
                "enable dry run, relax idle/grace/warnings) are\n"
                "delayed by the edit cooldown. Tightening is immediate."
            ),
            foreground="gray",
            justify="left",
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(10, 4))
        row += 1

        pending = self.config.pending_summary()
        if pending:
            ttk.Label(
                frm, text=pending, foreground="orange"
            ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 4))
            row += 1

        btns = ttk.Frame(frm)
        btns.grid(row=row, column=0, columnspan=2, pady=(10, 0), sticky="e")
        ttk.Button(btns, text="Cancel", command=self.top.destroy).pack(
            side="right", padx=(6, 0)
        )
        ttk.Button(btns, text="Apply", command=self._apply).pack(side="right")

    def _apply(self) -> None:
        try:
            new = {
                "daily_cap_minutes": int(self.vars["daily_cap_minutes"].get()),
                "hard_cutoff_time": self.vars["hard_cutoff_time"].get().strip() or None,
                "warning_minutes_before": sorted(
                    {
                        int(x.strip())
                        for x in self.vars["warning_minutes_before"].get().split(",")
                        if x.strip()
                    },
                    reverse=True,
                ),
                "grace_seconds": int(self.vars["grace_seconds"].get()),
                "idle_threshold_seconds": int(self.vars["idle_threshold_seconds"].get()),
                "edit_cooldown_hours": int(self.vars["edit_cooldown_hours"].get()),
                "dry_run": bool(self.vars["dry_run"].get()),
            }
            if new["hard_cutoff_time"] is not None:
                h, m = map(int, new["hard_cutoff_time"].split(":"))
                if not (0 <= h < 24 and 0 <= m < 60):
                    raise ValueError("hard_cutoff_time out of range")
            for k in ("daily_cap_minutes", "grace_seconds", "idle_threshold_seconds",
                     "edit_cooldown_hours"):
                if new[k] < 0:
                    raise ValueError(f"{k} must be non-negative")
            for w in new["warning_minutes_before"]:
                if w < 0:
                    raise ValueError("warning minutes must be non-negative")
        except Exception as exc:
            messagebox.showerror("Invalid settings", str(exc), parent=self.top)
            return

        applied, deferred = self.config.apply_settings(new)
        msg_parts = []
        if applied:
            msg_parts.append("Applied now:\n  " + "\n  ".join(applied))
        if deferred:
            msg_parts.append("Deferred until cooldown:\n  " + "\n  ".join(deferred))
        if not msg_parts:
            msg_parts.append("No changes.")
        messagebox.showinfo(
            "Settings", "\n\n".join(msg_parts), parent=self.top
        )
        self.top.destroy()
