import unittest
from unittest import mock

from hard_lock import shutdown


class ShutdownTestCase(unittest.TestCase):
    def test_dry_run_never_calls_subprocess(self):
        with mock.patch.object(shutdown.subprocess, "run") as run:
            shutdown.initiate_shutdown(dry_run=True)
            run.assert_not_called()

    def test_armed_calls_shutdown_exe(self):
        with mock.patch.object(shutdown.subprocess, "run") as run:
            shutdown.initiate_shutdown(dry_run=False)
            run.assert_called_once()
            args = run.call_args[0][0]
            self.assertEqual(args[0], "shutdown.exe")
            self.assertIn("/s", args)
            self.assertIn("/f", args)

    def test_armed_suppresses_the_console_window(self):
        # A windowed build has no console, so spawning shutdown.exe without this
        # flashes a console on screen right before the machine goes down.
        with mock.patch.object(shutdown.subprocess, "run") as run:
            shutdown.initiate_shutdown(dry_run=False)
            flags = run.call_args.kwargs.get("creationflags")
            self.assertEqual(flags, shutdown.CREATE_NO_WINDOW)
            self.assertTrue(flags & 0x08000000)


if __name__ == "__main__":
    unittest.main()
