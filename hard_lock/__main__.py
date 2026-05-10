import sys
from pathlib import Path

from .config import Config
from .state import State

PROJECT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_DIR / "config.json"
STATE_PATH = PROJECT_DIR / "state.json"
WEBUI_DIR = Path(__file__).resolve().parent / "webui"


def main() -> int:
    if sys.platform != "win32":
        print("Hard Lock v1 is Windows-only.", file=sys.stderr)
        return 1

    import webview

    from .api import Api
    from .tracker import ActiveTimeTracker
    from .ui import GraceCountdown

    config = Config.load(CONFIG_PATH)
    state = State.load(STATE_PATH)
    tracker = ActiveTimeTracker(config.idle_threshold_seconds)

    settings_window_ref: list = [None]
    grace_requested: list[bool] = [False]

    def request_grace() -> None:
        grace_requested[0] = True
        try:
            for w in list(webview.windows):
                w.destroy()
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
        settings_window_ref[0] = win

    api = Api(
        config=config,
        state=state,
        tracker=tracker,
        request_grace=request_grace,
        open_settings=open_settings,
    )

    webview.create_window(
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
