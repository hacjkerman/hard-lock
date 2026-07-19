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
  HardLock                        Launch the app (HUD; late-night prompt after the hour).
  HardLock --install              Install the logon + heartbeat tasks.
  HardLock --uninstall            Remove the logon + heartbeat tasks.
  HardLock --status               Show whether autostart is installed.
  HardLock --test-shutdown [s] [real]
                                  Show the grace countdown then shut down per the
                                  current mode. A number sets the grace seconds;
                                  'real' forces an actual power-off even in dry-run.
                                  Changes no config (no boot-loop risk).
  HardLock --help                 Show this help.
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


def _parse_test_args(rest, default_grace: int, config_dry_run: bool):
    """(grace_seconds, dry_run) for `--test-shutdown [seconds] [real]`. A bare
    number overrides the grace length; 'real' forces an actual power-off even in
    dry-run. Never mutates config — so a test can't cause a boot loop."""
    grace = default_grace
    force_real = False
    for a in rest:
        if str(a).lower() == "real":
            force_real = True
        else:
            try:
                grace = max(1, int(a))
            except (ValueError, TypeError):
                pass
    return grace, (config_dry_run and not force_real)


def _run_test_shutdown(rest: "list[str]") -> int:
    """On-demand shutdown test: show the grace countdown, then shut down per the
    current mode (dry-run simulates; armed powers off for real). Sets NO limit
    and writes NO trigger to config, so there's nothing to revert and no risk of
    the machine shutting down again on the next boot. Holds during a game, just
    like the real limit — a test must never power off mid-match either."""
    from .config import Config
    from .history import EventLog
    from .ui import GraceCountdown
    from . import league

    config = Config.load(CONFIG_PATH)
    grace, dry = _parse_test_args(rest, config.grace_seconds, config.dry_run)
    log = EventLog(paths.events_path())
    if config.defer_for_games and league.is_game_active(config.defer_for_games):
        try:
            log.append("shutdown_test", held="game", dry_run=dry)
        except Exception:
            pass
        print("A defer-for game is running — Hard Lock holds the shutdown; test skipped.")
        return 0
    try:
        log.append("shutdown_test", dry_run=dry, grace_seconds=grace)
    except Exception:
        pass
    GraceCountdown(grace, dry).run()  # blocks: countdown → initiate_shutdown(dry)
    return 0


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
    if argv and argv[0] == "--watchdog":
        from . import guardian
        return guardian.run_watchdog()
    if argv and argv[0] == "--ensure":
        # Scheduled-task backstop: relaunch the main app if it isn't running and
        # no disarm is due. Cheap — no UI, returns immediately.
        from . import guardian
        if not guardian.is_alive("main") and not guardian.disarm_due():
            guardian.spawn("main")
        return 0
    if argv and argv[0] == "--test-shutdown":
        return _run_test_shutdown(argv[1:])
    if argv:
        return _run_cli(argv)

    import webview

    from . import build, guardian

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
    # Track HUD visibility so we can auto-hide it during a game and restore it
    # after — but only if we were the ones who hid it.
    hud_visible: list[bool] = [False]
    hud_auto_hidden: list[bool] = [False]
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
                hud_visible[0] = True
                _dismiss_prompt()  # HUD already up (on-demand path) → safe to destroy now
                return
            except Exception:
                hud_window_ref[0] = None
        win = webview.create_window(
            "Hard Lock",
            url=(WEBUI_DIR / "hud.html").as_uri(),
            js_api=api,
            width=300,
            height=420,
            frameless=True,
            on_top=True,
            resizable=False,
            # Drag only by the titlebar (.pywebview-drag-region in hud.html);
            # full-window easy_drag would hijack the scrollbar and body clicks.
            easy_drag=False,
        )
        hud_window_ref[0] = win
        hud_visible[0] = True

        def _on_hud_closing():
            # Hide to the tray instead of exiting — unless we're really shutting
            # down (grace or Quit), in which case allow the close.
            if force_close[0]:
                return True
            try:
                win.hide()
            except Exception:
                pass
            hud_visible[0] = False
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
            url=(WEBUI_DIR / "settings.html").as_uri(),
            js_api=api,
            width=1040,
            height=640,
            min_size=(880, 540),
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
            url=(WEBUI_DIR / "history.html").as_uri(),
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
        hud_visible[0] = False

    def on_game_change(active: bool) -> None:
        # Auto-hide the HUD while a game is running so its always-on-top window
        # can't float over the game; restore it afterward, but only if WE hid it
        # (don't resurrect a HUD the user chose to tuck away).
        try:
            win = hud_window_ref[0]
            if win is None:
                return
            if active:
                if hud_visible[0]:
                    win.hide()
                    hud_visible[0] = False
                    hud_auto_hidden[0] = True
            elif hud_auto_hidden[0]:
                hud_auto_hidden[0] = False
                win.show()
                hud_visible[0] = True
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
            url=(WEBUI_DIR / "session.html").as_uri(),
            js_api=api,
            width=460,
            height=540,
            frameless=True,
            on_top=True,
            resizable=False,
            # Drag only by the titlebar (.pywebview-drag-region in session.html);
            # full-window easy_drag would hijack the slider and the buttons.
            easy_drag=False,
        )
        prompt_window_ref[0] = win
        _attach_prompt_guard(win)

    def re_arm() -> None:
        # Leave the dormant (disarmed) state: relaunch a fresh armed instance,
        # then tear this dormant one down.
        guardian.spawn("main")
        _teardown_windows()

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
        on_game_change=on_game_change,
        re_arm=re_arm,
        event_log=event_log,
        day_history=day_history,
    )

    # If a disarm has matured, run DORMANT: no enforcement, no watchdog — just a
    # HUD offering to re-arm. Otherwise run ARMED, as a single instance, with the
    # watchdog keeping us alive.
    dormant = config.disarm_due()
    tick_stop = threading.Event()

    if not build.DEV_BUILD and not dormant and guardian.acquire_singleton(r"Local\HardLockMain") is None:
        return 0  # another armed instance already owns the lock

    def tick_loop() -> None:
        while not tick_stop.wait(1.0):
            try:
                api.tick()
            except Exception:
                pass

    def guardian_loop() -> None:
        # Heartbeat + resurrect the watchdog; stop everything once a disarm matures.
        while not tick_stop.wait(guardian.HEARTBEAT_INTERVAL):
            guardian.write_heartbeat("main")
            if config.disarm_due():
                try:
                    event_log.append("disarmed")
                except Exception:
                    pass
                _teardown_windows()  # ends the webview loop → this process exits
                return
            if not guardian.is_alive("watchdog"):
                guardian.spawn("watchdog")

    if not dormant:
        threading.Thread(target=tick_loop, name="hardlock-ticker", daemon=True).start()
        # The dev build is closable and guardian-free (see hard_lock/build.py).
        if not build.DEV_BUILD:
            guardian.write_heartbeat("main")
            guardian.spawn("watchdog")
            threading.Thread(target=guardian_loop, name="hardlock-guardian", daemon=True).start()

    # Tray stop action: dev build actually quits; prod requests the cooldown-gated
    # disarm (no one-click quit).
    def _tray_stop_action() -> None:
        try:
            if build.DEV_BUILD:
                tick_stop.set()
                _teardown_windows()
            else:
                api.request_disarm()
        except Exception:
            pass

    tray_ref[0] = tray.start_tray(
        api,
        on_show_hud=open_hud,
        on_settings=open_settings,
        on_history=open_history,
        on_disarm=_tray_stop_action,
    )

    # Dormant → the HUD shows the disarmed / re-arm state. Otherwise: first launch
    # → onboarding; else after the late-night hour → the (bounded) session prompt,
    # but only if there's time to commit (past the cutoff it would be a dead
    # screen, so skip to the HUD); otherwise straight to the HUD.
    if dormant:
        open_hud()
    elif not config.setup_completed:
        win = webview.create_window(
            "Hard Lock — Setup",
            url=(WEBUI_DIR / "onboarding.html").as_uri(),
            js_api=api,
            width=760,
            height=560,
            min_size=(680, 520),
            on_top=True,
        )
        prompt_window_ref[0] = win
        _attach_prompt_guard(win)
    elif config.is_late_night() and api.get_session_prompt_info()["max_minutes"] >= 5:
        open_session_prompt()
    else:
        open_hud()

    webview.start(debug=False)

    # Webview loop returned — stop the ticker/guardian and tray during shutdown.
    tick_stop.set()
    guardian.clear_heartbeat("main")
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
