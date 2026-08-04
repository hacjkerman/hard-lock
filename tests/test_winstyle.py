import unittest
from unittest import mock

from hard_lock import winstyle


class WinStyleTestCase(unittest.TestCase):
    def test_missing_window_is_a_noop(self):
        with mock.patch.object(winstyle, "find_hwnd", return_value=None):
            self.assertFalse(winstyle.hide_from_taskbar("No Such Window"))

    def test_failure_never_raises(self):
        with mock.patch.object(winstyle, "find_hwnd", side_effect=OSError("boom")):
            self.assertFalse(winstyle.hide_from_taskbar("Hard Lock"))

    def test_applies_toolwindow_and_clears_appwindow(self):
        applied = {}

        def fake_get(hwnd, idx):
            return winstyle.WS_EX_APPWINDOW  # starts as a normal taskbar window

        def fake_put(hwnd, idx, value):
            applied["style"] = value
            return 0

        user32 = mock.Mock()
        with mock.patch.object(winstyle, "find_hwnd", return_value=1234), \
             mock.patch("ctypes.windll") as windll, \
             mock.patch.object(winstyle, "_long_accessors", return_value=(fake_get, fake_put)):
            windll.user32 = user32
            self.assertTrue(winstyle.hide_from_taskbar("Hard Lock"))

        self.assertTrue(applied["style"] & winstyle.WS_EX_TOOLWINDOW)   # no taskbar button
        self.assertFalse(applied["style"] & winstyle.WS_EX_APPWINDOW)   # and not forced back on
        # must hide then re-show, or Windows keeps the old taskbar state
        self.assertEqual([c.args[1] for c in user32.ShowWindow.call_args_list],
                         [winstyle.SW_HIDE, winstyle.SW_SHOWNA])

    def test_already_toolwindow_is_left_alone(self):
        user32 = mock.Mock()
        with mock.patch.object(winstyle, "find_hwnd", return_value=1234), \
             mock.patch("ctypes.windll") as windll, \
             mock.patch.object(winstyle, "_long_accessors",
                               return_value=(lambda h, i: winstyle.WS_EX_TOOLWINDOW,
                                             lambda h, i, v: 0)):
            windll.user32 = user32
            self.assertTrue(winstyle.hide_from_taskbar("Hard Lock"))
        user32.ShowWindow.assert_not_called()  # no needless hide/show flicker


if __name__ == "__main__":
    unittest.main()
