import sys
import threading

from . import autostart, paths, tray
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

    from . import league
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
    tray_ref: list = [None]
    grace_requested: list[bool] = [False]
    # When True, the HUD's close button really closes (grace/quit); otherwise a
    # close just hides it to the tray so the app keeps running in the background.
    force_close: list[bool] = [False]
    # Set true only for the programmatic hand-off destroy of the late-night
    # prompt, so its hide-to-tray guard lets that one close through.
    prompt_closing: list[bool] = [False]

    def _teardown_windows() -> None:
        force_close[0] = True
        try:
            for w in list(webview.windows):
                w.destroy()
        except Exception:
            pass
        if tray_ref[0] is not None:
            try:
                tray_ref[0].stop()
            except Exception:
                pass

    def request_grace() -> None:
        grace_requested[0] = True
        _teardown_windows()

    def _dismiss_prompt() -> None:
        # Tear down the onboarding / session-timer prompt after the hand-off.
        # Called only once the HUD is guaranteed to exist, so there's never a
        # moment with zero windows (which would end webview.start()).
        pw = prompt_window_ref[0]
        if pw is not None:
            prompt_window_ref[0] = None
            prompt_closing[0] = True  # allow the hand-off destroy past the guard
            try:
                pw.destroy()
            except Exception:
                pass

    def open_hud() -> None:
        # Reuse the HUD if it's just hidden to the tray.
        existing = hud_window_ref[0]
        if existing is not None:
            try:
                existing.show()
                _dismiss_prompt()  # HUD already up (on-demand path) → safe to destroy now
                return
            except Exception:
                hud_window_ref[0] = None
        win = webview.create_window(
            "Hard Lock",
            url=str(WEBUI_DIR / "hud.html"),
            js_api=api,
            width=300,
            height=420,
            frameless=True,
            on_top=True,
            resizable=False,
            easy_drag=True,
        )
        hud_window_ref[0] = win

        def _on_hud_closing():
            # Hide to the tray instead of exiting — unless we're really shutting
            # down (grace or Quit), in which case allow the close.
            if force_close[0]:
                return True
            try:
                win.hide()
            except Exception:
                pass
            return False

        try:
            win.events.closing += _on_hud_closing
        except Exception:
            pass

        # HUD now exists → tear down the prompt (launch hand-off).
        _dismiss_prompt()

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

    def _attach_prompt_guard(win) -> None:
        # The onboarding / late-night prompt is the ONLY window before the HUD
        # exists. Without this, closing it (Alt+F4) would exit the whole app and
        # silently disable the lock. Hide to the tray instead — unless it's the
        # hand-off destroy (prompt_closing) or a real shutdown (force_close).
        def _on_closing():
            if force_close[0] or prompt_closing[0]:
                return True
            try:
                win.hide()
            except Exception:
                pass
            return False

        try:
            win.events.closing += _on_closing
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

    def hide_hud() -> None:
        win = hud_window_ref[0]
        if win is not None:
            try:
                win.hide()
            except Exception:
                pass

    def open_session_prompt() -> None:
        # The "set a work timer" prompt, used both at late-night launch and
        # on demand from the HUD. Reuses the session window if it's still up.
        existing = prompt_window_ref[0]
        if existing is not None:
            try:
                existing.show()
                return
            except Exception:
                prompt_window_ref[0] = None
        prompt_closing[0] = False  # fresh prompt: its close hides, not exits
        win = webview.create_window(
            "Hard Lock — Set timer",
            url=str(WEBUI_DIR / "session.html"),
            js_api=api,
            width=460,
            height=540,
            frameless=True,
            on_top=True,
            resizable=False,
            easy_drag=True,
        )
        prompt_window_ref[0] = win
        _attach_prompt_guard(win)

    api = Api(
        config=config,
        state=state,
        tracker=tracker,
        request_grace=request_grace,
        open_settings=open_settings,
        open_hud=open_hud,
        open_history=open_history,
        hide_hud=hide_hud,
        open_session_prompt=open_session_prompt,
        league_active=league.is_game_active,
        event_log=event_log,
        day_history=day_history,
    )

    # The clock runs on its own thread, independent of any window, so active
    # time keeps accruing even while the HUD is hidden to the tray or the
    # late-night prompt is up. get_status is now a read-only snapshot.
    tick_stop = threading.Event()

    def tick_loop() -> None:
        while not tick_stop.wait(1.0):
            try:
                api.tick()
            except Exception:
                pass

    ticker = threading.Thread(target=tick_loop, name="hardlock-ticker", daemon=True)
    ticker.start()

    # System tray: keeps the app alive in the background when the HUD is closed.
    # Optional — if pystray/Pillow aren't available it simply doesn't appear.
    def quit_app() -> None:
        tick_stop.set()
        _teardown_windows()  # sets force_close, destroys windows, stops tray

    tray_ref[0] = tray.start_tray(
        api,
        on_show_hud=open_hud,
        on_settings=open_settings,
        on_history=open_history,
        on_quit=quit_app,
    )

    # First launch → onboarding wizard. Else after the late-night hour → the
    # session-timer prompt. Otherwise straight to the HUD. Each front window
    # hands off to the HUD (open_hud destroys it) and hides-to-tray on close.
    if not config.setup_completed:
        win = webview.create_window(
            "Hard Lock — Setup",
            url=str(WEBUI_DIR / "onboarding.html"),
            js_api=api,
            width=760,
            height=560,
            min_size=(680, 520),
            on_top=True,
        )
        prompt_window_ref[0] = win
        _attach_prompt_guard(win)
    elif config.is_late_night():
        open_session_prompt()
    else:
        open_hud()

    webview.start(debug=False)

    # Webview loop returned — stop the ticker and tray during shutdown.
    tick_stop.set()
    if tray_ref[0] is not None:
        try:
            tray_ref[0].stop()
        except Exception:
            pass

    # Main event loop returned. If grace was triggered, run the tkinter
    # countdown on the main thread — pywebview cannot coexist with a fresh
    # tkinter mainloop in the same process, but the webview loop has now
    # exited so we own the thread again.
    if grace_requested[0]:
        GraceCountdown(config.grace_seconds, config.dry_run).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
