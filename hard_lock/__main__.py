import sys

from . import autostart, paths
from .config import Config
from .state import State

CONFIG_PATH = paths.config_path()
STATE_PATH = paths.state_path()
WEBUI_DIR = paths.webui_dir()


USAGE = """Hard Lock - a self-imposed Windows shutdown lock.

Usage:
  HardLock                  Launch the app (HUD; late-night prompt after the hour).
  HardLock --install        Install the logon task so it starts automatically.
  HardLock --uninstall      Remove the logon task.
  HardLock --status         Show whether autostart is installed.
  HardLock --help           Show this help.
"""


def _emit(msg: str) -> None:
    """Show a CLI result. A windowed (frozen) build has no console attached to
    the invoking terminal, so also surface it as a dialog there."""
    print(msg)
    if paths.is_frozen():
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, msg, "Hard Lock", 0x40)
        except Exception:
            pass


def _run_cli(argv: "list[str]") -> int:
    arg = argv[0]
    if arg in ("--install", "--install-autostart"):
        ok, msg = autostart.install()
        _emit(msg)
        return 0 if ok else 1
    if arg in ("--uninstall", "--uninstall-autostart"):
        ok, msg = autostart.uninstall()
        _emit(msg)
        return 0 if ok else 1
    if arg in ("--status", "--autostart-status"):
        _emit(autostart.status())
        return 0
    if arg in ("--help", "-h", "/?"):
        _emit(USAGE)
        return 0
    _emit(f"Unknown option: {arg}\n\n{USAGE}")
    return 2


def main(argv: "list[str] | None" = None) -> int:
    if sys.platform != "win32":
        print("Hard Lock v1 is Windows-only.", file=sys.stderr)
        return 1

    argv = sys.argv[1:] if argv is None else argv
    if argv:
        return _run_cli(argv)

    import webview

    from .api import Api
    from .history import DayHistory, EventLog
    from .tracker import ActiveTimeTracker
    from .ui import GraceCountdown

    config = Config.load(CONFIG_PATH)
    state = State.load(STATE_PATH)
    tracker = ActiveTimeTracker(config.idle_threshold_seconds)
    event_log = EventLog(paths.events_path())
    day_history = DayHistory(paths.history_path())

    settings_window_ref: list = [None]
    history_window_ref: list = [None]
    hud_window_ref: list = [None]
    prompt_window_ref: list = [None]
    grace_requested: list[bool] = [False]

    def request_grace() -> None:
        grace_requested[0] = True
        try:
            for w in list(webview.windows):
                w.destroy()
        except Exception:
            pass

    def open_hud() -> None:
        # Create the HUD first so there's always ≥1 window open, then dismiss
        # the late-night prompt if it launched us.
        win = webview.create_window(
            "Hard Lock",
            url=str(WEBUI_DIR / "hud.html"),
            js_api=api,
            width=300,
            height=280,
            frameless=True,
            on_top=True,
            resizable=False,
            easy_drag=True,
        )
        hud_window_ref[0] = win
        pw = prompt_window_ref[0]
        if pw is not None:
            prompt_window_ref[0] = None
            try:
                pw.destroy()
            except Exception:
                pass

    def _track_window(ref: list, win) -> None:
        # Clear the ref when the user closes the window. pywebview's show() on a
        # destroyed window silently no-ops (doesn't raise), so without this the
        # ref stays stale and the button that reopens it goes dead until restart.
        ref[0] = win

        def _on_closed(*_):
            ref[0] = None

        try:
            win.events.closed += _on_closed
        except Exception:
            pass

    def open_settings() -> None:
        existing = settings_window_ref[0]
        if existing is not None:
            try:
                existing.show()
                return
            except Exception:
                settings_window_ref[0] = None
        win = webview.create_window(
            "Hard Lock — Settings",
            url=str(WEBUI_DIR / "settings.html"),
            js_api=api,
            width=900,
            height=620,
            min_size=(760, 520),
        )
        _track_window(settings_window_ref, win)

    def open_history() -> None:
        existing = history_window_ref[0]
        if existing is not None:
            try:
                existing.show()
                return
            except Exception:
                history_window_ref[0] = None
        win = webview.create_window(
            "Hard Lock — History",
            url=str(WEBUI_DIR / "history.html"),
            js_api=api,
            width=900,
            height=640,
            min_size=(760, 520),
        )
        _track_window(history_window_ref, win)

    api = Api(
        config=config,
        state=state,
        tracker=tracker,
        request_grace=request_grace,
        open_settings=open_settings,
        open_hud=open_hud,
        open_history=open_history,
        event_log=event_log,
        day_history=day_history,
    )

    # After the configured late-night hour, open the session-timer prompt first
    # and let it hand off to the HUD once the user commits (or skips). Otherwise
    # go straight to the HUD.
    if config.is_late_night():
        prompt_window_ref[0] = webview.create_window(
            "Hard Lock — Late night",
            url=str(WEBUI_DIR / "session.html"),
            js_api=api,
            width=460,
            height=496,
            frameless=True,
            on_top=True,
            resizable=False,
            easy_drag=True,
        )
    else:
        open_hud()

    webview.start(debug=False)

    # Main event loop returned. If grace was triggered, run the tkinter
    # countdown on the main thread — pywebview cannot coexist with a fresh
    # tkinter mainloop in the same process, but the webview loop has now
    # exited so we own the thread again.
    if grace_requested[0]:
        GraceCountdown(config.grace_seconds, config.dry_run).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
