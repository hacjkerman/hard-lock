"""System tray icon + menu (pystray).

Optional affordance: if pystray/Pillow are missing or the icon fails to start,
the app runs without a tray — the lock never depends on it. The tray runs its
own message loop on a daemon thread alongside pywebview's loop.
"""

import threading


def make_image(rgb=(76, 194, 255, 255)):
    """A small padlock glyph for the tray icon."""
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.arc([22, 12, 42, 40], start=180, end=360, fill=rgb, width=5)   # shackle
    d.rounded_rectangle([17, 28, 47, 52], radius=5, fill=rgb)        # body
    d.ellipse([30, 37, 34, 45], fill=(24, 24, 24, 255))             # keyhole
    return img


def build_icon(api, on_show_hud, on_settings, on_history, on_quit):
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

    def wrap(fn):
        # pystray invokes callbacks as (icon, item); our callbacks take no args.
        def handler(_icon, _item):
            try:
                fn()
            except Exception:
                pass
        return handler

    menu = pystray.Menu(
        pystray.MenuItem(status_text, None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Show HUD", wrap(on_show_hud), default=True),
        pystray.MenuItem("Open settings", wrap(on_settings)),
        pystray.MenuItem("View history", wrap(on_history)),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit Hard Lock", wrap(on_quit)),
    )
    return pystray.Icon("hardlock", make_image(), "Hard Lock", menu)


def start_tray(api, on_show_hud, on_settings, on_history, on_quit):
    """Build and run the tray on a daemon thread. Returns the icon, or None if
    the tray couldn't be created."""
    icon = build_icon(api, on_show_hud, on_settings, on_history, on_quit)
    if icon is None:
        return None
    threading.Thread(target=icon.run, name="hardlock-tray", daemon=True).start()
    return icon
