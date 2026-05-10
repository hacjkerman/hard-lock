import ctypes
import time


class ActiveTimeTracker:
    def __init__(self, idle_threshold_seconds: float):
        import ctypes.wintypes

        self.idle_threshold = idle_threshold_seconds
        self._user32 = ctypes.windll.user32
        self._kernel32 = ctypes.windll.kernel32

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.wintypes.UINT),
                ("dwTime", ctypes.wintypes.DWORD),
            ]

        self._LASTINPUTINFO = LASTINPUTINFO
        self._last_poll = time.monotonic()

    def _idle_seconds(self) -> float:
        lii = self._LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(lii)
        self._user32.GetLastInputInfo(ctypes.byref(lii))
        return (self._kernel32.GetTickCount() - lii.dwTime) / 1000.0

    def tick(self) -> float:
        now = time.monotonic()
        elapsed = now - self._last_poll
        self._last_poll = now
        if self._idle_seconds() > self.idle_threshold:
            return 0.0
        return elapsed
