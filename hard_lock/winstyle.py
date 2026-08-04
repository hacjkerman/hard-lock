"""Keep the frameless HUD out of the Windows taskbar.

The HUD is a small always-on-top widget, not a document window, so it has no
business owning a taskbar button — and a taskbar button is what Windows flashes
for attention when the window is shown while another app has focus. Marking it
WS_EX_TOOLWINDOW (and clearing WS_EX_APPWINDOW) removes the button entirely, so
it can't ping. Purely cosmetic: never affects enforcement, and every failure
path is a silent no-op.
"""

import ctypes
from ctypes import wintypes

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
SW_HIDE = 0
SW_SHOWNA = 8  # show without stealing focus


def _long_accessors(user32):
    """(get, set) for window longs — the *Ptr variants on 64-bit, else the plain
    ones (32-bit Python has no GetWindowLongPtrW)."""
    get = getattr(user32, "GetWindowLongPtrW", None) or user32.GetWindowLongW
    put = getattr(user32, "SetWindowLongPtrW", None) or user32.SetWindowLongW
    get.restype = ctypes.c_ssize_t
    get.argtypes = [wintypes.HWND, ctypes.c_int]
    put.restype = ctypes.c_ssize_t
    put.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
    return get, put


def find_hwnd(title: str):
    """Top-level window handle for an exact title, or None."""
    try:
        user32 = ctypes.windll.user32
        user32.FindWindowW.restype = wintypes.HWND
        user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        return user32.FindWindowW(None, title) or None
    except Exception:
        return None


def hide_from_taskbar(title: str) -> bool:
    """Remove the named window's taskbar button. Returns True if applied.

    Windows only re-reads the taskbar-relevant styles when a window is re-shown,
    so this hides and re-shows it (without activating, so focus doesn't move).
    """
    try:
        hwnd = find_hwnd(title)
        if not hwnd:
            return False
        user32 = ctypes.windll.user32
        get, put = _long_accessors(user32)
        style = get(hwnd, GWL_EXSTYLE)
        new = (style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
        if new == style:
            return True  # already a tool window
        user32.ShowWindow(hwnd, SW_HIDE)
        put(hwnd, GWL_EXSTYLE, new)
        user32.ShowWindow(hwnd, SW_SHOWNA)
        return True
    except Exception:
        return False
