import unittest

from hard_lock import tray


class FakeApi:
    def get_status(self):
        return {"remaining_hm": "1h 00m", "dry_run": True}


class TrayTestCase(unittest.TestCase):
    def test_make_image_size(self):
        img = tray.make_image()
        self.assertEqual(img.size, (64, 64))

    def test_build_icon_constructs_menu(self):
        icon = tray.build_icon(
            FakeApi(), lambda: None, lambda: None, lambda: None, lambda: None
        )
        self.assertIsNotNone(icon)
        # status line + 3 actions + quit (plus separators)
        items = list(icon.menu)
        labels = [str(i.text) for i in items if getattr(i, "text", None)]
        self.assertTrue(any("Show HUD" in x for x in labels))
        self.assertTrue(any("Quit" in x for x in labels))

    def test_menu_actions_wired(self):
        calls = []
        icon = tray.build_icon(
            FakeApi(),
            lambda: calls.append("hud"),
            lambda: calls.append("settings"),
            lambda: calls.append("history"),
            lambda: calls.append("quit"),
        )
        by_text = {}
        for item in icon.menu:
            text = getattr(item, "text", None)
            if text:
                by_text[str(text)] = item
        # invoking a menu item runs its action (pystray's MenuItem.__call__(icon))
        by_text["Show HUD"](icon)
        by_text["Quit Hard Lock"](icon)
        self.assertEqual(calls, ["hud", "quit"])


if __name__ == "__main__":
    unittest.main()
