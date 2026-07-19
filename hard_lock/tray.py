"""System tray icon + menu (pystray).

Optional affordance: if pystray/Pillow are missing or the icon fails to start,
the app runs without a tray — the lock never depends on it. The tray runs its
own message loop on a daemon thread alongside pywebview's loop.
"""

import threading


def make_image(size=64):
    """The Hard Lock mark: a red badge with a white padlock whose keyhole is a
    power symbol (lock + shutdown). Drawn at high resolution and downscaled so
    it's smooth at any size. Shared by the tray and the .ico generator."""
    from PIL import Image, ImageDraw

    S = 512  # supersample, then downscale to `size`
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def u(v):  # design coordinates are in a 256-unit space
        return v * S / 256.0

    RED = (207, 48, 32, 255)
    WHITE = (255, 255, 255, 255)

    d.rounded_rectangle([u(16), u(16), u(240), u(240)], radius=u(56), fill=RED)

    sw = max(2, int(u(16)))  # shackle stroke
    d.arc([u(100), u(68), u(156), u(124)], start=180, end=360, fill=WHITE, width=sw)
    d.line([u(100), u(96), u(100), u(122)], fill=WHITE, width=sw)
    d.line([u(156), u(96), u(156), u(122)], fill=WHITE, width=sw)

    d.rounded_rectangle([u(76), u(116), u(180), u(206)], radius=u(16), fill=WHITE)

    pw = max(2, int(u(7)))  # power-symbol keyhole
    d.arc([u(111), u(147), u(145), u(181)], start=305, end=595, fill=RED, width=pw)
    d.line([u(128), u(143), u(128), u(163)], fill=RED, width=pw)

    if size != S:
        img = img.resize((size, size), Image.LANCZOS)
    return img


def build_icon(api, on_show_hud, on_settings, on_history, on_disarm):
    """Construct the pystray Icon (does not start it). Returns None if pystray
    is unavailable."""
    try:
        import pystray
    except Exception:
        return None

    def status_text(_item):
        try:
            s = api.get_status()
            mode = "dry-run" if s.get("dry_run") else "armed"
            return f"{s.get('remaining_hm', '--')} left · {mode}"
        except Exception:
            return "Hard Lock"

    def disarm_label(_item):
        # Reflect a pending disarm so it's clear it's counting down, not instant.
        try:
            s = api.get_status()
            if s.get("disarm_pending"):
                return f"Disarming in {s.get('disarm_remaining_hm', '')}…"
        except Exception:
            pass
        return "Disarm (waits out cooldown)"

    def wrap(fn):
        # pystray invokes callbacks as (icon, item); our callbacks take no args.
        def handler(_icon, _item):
            try:
                fn()
            except Exception:
                pass
        return handler

    # Prod has no one-click quit — the only stop is a cooldown-gated disarm, so
    # tired-you can't just close it. The dev build restores a real Quit.
    from . import build
    last_item = (
        pystray.MenuItem("Quit Hard Lock", wrap(on_disarm))
        if build.DEV_BUILD
        else pystray.MenuItem(disarm_label, wrap(on_disarm))
    )
    menu = pystray.Menu(
        pystray.MenuItem(status_text, None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Show HUD", wrap(on_show_hud), default=True),
        pystray.MenuItem("Open settings", wrap(on_settings)),
        pystray.MenuItem("View history", wrap(on_history)),
        pystray.Menu.SEPARATOR,
        last_item,
    )
    return pystray.Icon("hardlock", make_image(), "Hard Lock", menu)


def start_tray(api, on_show_hud, on_settings, on_history, on_disarm):
    """Build and run the tray on a daemon thread. Returns the icon, or None if
    the tray couldn't be created."""
    icon = build_icon(api, on_show_hud, on_settings, on_history, on_disarm)
    if icon is None:
        return None
    threading.Thread(target=icon.run, name="hardlock-tray", daemon=True).start()
    return icon
