import subprocess
import unittest
from unittest import mock

from hard_lock import autostart


def _cp(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


class LaunchCommandTestCase(unittest.TestCase):
    def test_frozen_uses_executable(self):
        with mock.patch("hard_lock.paths.is_frozen", return_value=True), \
             mock.patch("hard_lock.autostart.sys") as sysmod:
            sysmod.executable = r"C:\Apps\HardLock\HardLock.exe"
            cmd = autostart.launch_command()
        self.assertEqual(cmd, r'"C:\Apps\HardLock\HardLock.exe"')

    def test_source_uses_interpreter_and_launcher(self):
        with mock.patch("hard_lock.paths.is_frozen", return_value=False):
            cmd = autostart.launch_command()
        self.assertIn("launch.py", cmd)
        # both the interpreter and the script path are quoted
        self.assertEqual(cmd.count('"'), 4)


class SchtasksTestCase(unittest.TestCase):
    def test_install_builds_onlogon_task(self):
        with mock.patch.object(autostart, "_schtasks", return_value=_cp(0)) as st, \
             mock.patch.object(autostart, "launch_command", return_value='"X"'):
            ok, msg = autostart.install()
        self.assertTrue(ok)
        logon_args = st.call_args_list[0][0]  # first call = the logon task
        self.assertIn("/create", logon_args)
        self.assertIn("/sc", logon_args)
        self.assertIn("ONLOGON", logon_args)
        self.assertIn("/f", logon_args)
        self.assertIn(autostart.TASK_NAME, logon_args)
        # second call = the every-minute heartbeat backstop
        hb_args = st.call_args_list[1][0]
        self.assertIn("MINUTE", hb_args)
        self.assertIn(autostart.HEARTBEAT_TASK, hb_args)

    def test_install_access_denied_hints_elevation(self):
        with mock.patch.object(autostart, "_schtasks", return_value=_cp(1, stderr="ERROR: Access is denied.")):
            ok, msg = autostart.install()
        self.assertFalse(ok)
        self.assertIn("elevated", msg.lower())

    def test_uninstall_missing_task_is_success(self):
        with mock.patch.object(autostart, "_schtasks",
                               return_value=_cp(1, stderr="ERROR: The system cannot find the task specified.")):
            ok, msg = autostart.uninstall()
        self.assertTrue(ok)

    def test_is_installed_reflects_query_returncode(self):
        with mock.patch.object(autostart, "_schtasks", return_value=_cp(0)):
            self.assertTrue(autostart.is_installed())
        with mock.patch.object(autostart, "_schtasks", return_value=_cp(1)):
            self.assertFalse(autostart.is_installed())


class ElevatedTestCase(unittest.TestCase):
    def test_install_elevated_runs_install(self):
        with mock.patch.object(autostart, "_run_cli_elevated", return_value=True) as r:
            self.assertTrue(autostart.install_elevated())
        r.assert_called_once_with("--install")

    def test_uninstall_elevated_runs_uninstall(self):
        with mock.patch.object(autostart, "_run_cli_elevated", return_value=True) as r:
            autostart.uninstall_elevated()
        r.assert_called_once_with("--uninstall")

    def test_cli_target_frozen(self):
        with mock.patch("hard_lock.paths.is_frozen", return_value=True), \
             mock.patch.object(autostart, "sys") as sysmod:
            sysmod.executable = r"C:\Apps\HardLock.exe"
            exe, prefix = autostart._cli_target()
        self.assertEqual(exe, r"C:\Apps\HardLock.exe")
        self.assertEqual(prefix, "")

    def test_run_cli_elevated_shellexecute_success_and_failure(self):
        fake = mock.MagicMock()
        with mock.patch.object(autostart, "_cli_target", return_value=("X.exe", "")):
            fake.shell32.ShellExecuteW.return_value = 42  # > 32 = success
            with mock.patch("ctypes.windll", fake):
                self.assertTrue(autostart._run_cli_elevated("--install"))
            fake.shell32.ShellExecuteW.return_value = 5  # <= 32 = failure
            with mock.patch("ctypes.windll", fake):
                self.assertFalse(autostart._run_cli_elevated("--install"))


class CliTestCase(unittest.TestCase):
    def test_status_cli(self):
        from hard_lock.__main__ import _run_cli
        with mock.patch("hard_lock.autostart.status", return_value="Autostart: not installed."):
            self.assertEqual(_run_cli(["--status"]), 0)

    def test_unknown_option(self):
        from hard_lock.__main__ import _run_cli
        self.assertEqual(_run_cli(["--nope"]), 2)

    def test_help(self):
        from hard_lock.__main__ import _run_cli
        self.assertEqual(_run_cli(["--help"]), 0)

    def test_install_cli_delegates(self):
        from hard_lock.__main__ import _run_cli
        with mock.patch("hard_lock.autostart.install", return_value=(True, "ok")):
            self.assertEqual(_run_cli(["--install"]), 0)
        with mock.patch("hard_lock.autostart.install", return_value=(False, "bad")):
            self.assertEqual(_run_cli(["--install"]), 1)


class TestShutdownArgsTestCase(unittest.TestCase):
    def test_defaults_to_config_mode_and_grace(self):
        from hard_lock.__main__ import _parse_test_args
        # dry-run config → simulated; grace falls back to the default
        self.assertEqual(_parse_test_args([], 60, True), (60, True))
        self.assertEqual(_parse_test_args([], 60, False), (60, False))

    def test_seconds_override(self):
        from hard_lock.__main__ import _parse_test_args
        self.assertEqual(_parse_test_args(["10"], 60, False), (10, False))
        # junk is ignored, keeps the default
        self.assertEqual(_parse_test_args(["abc"], 60, False), (60, False))
        # never below 1
        self.assertEqual(_parse_test_args(["0"], 60, False), (1, False))

    def test_real_forces_actual_shutdown_even_in_dry_run(self):
        from hard_lock.__main__ import _parse_test_args
        grace, dry = _parse_test_args(["real"], 60, True)
        self.assertFalse(dry)  # forced real despite dry-run config
        grace, dry = _parse_test_args(["5", "real"], 60, True)
        self.assertEqual((grace, dry), (5, False))

    def test_main_routes_test_shutdown(self):
        from hard_lock import __main__ as m
        with mock.patch.object(m, "_run_test_shutdown", return_value=0) as run:
            self.assertEqual(m.main(["--test-shutdown", "5", "real"]), 0)
        run.assert_called_once_with(["5", "real"])

    def test_test_shutdown_holds_during_a_game(self):
        # Even a deliberate test must not power off mid-match — it holds and
        # never reaches the grace countdown.
        from hard_lock import __main__ as m
        cfg = mock.Mock(grace_seconds=60, dry_run=False, defer_for_games=["League of Legends.exe"])
        with mock.patch("hard_lock.config.Config.load", return_value=cfg), \
             mock.patch("hard_lock.league.is_game_active", return_value=True), \
             mock.patch("hard_lock.history.EventLog"), \
             mock.patch("hard_lock.ui.GraceCountdown") as grace:
            rc = m._run_test_shutdown([])
        self.assertEqual(rc, 0)
        grace.assert_not_called()  # never counted down → never shut down

    def test_test_shutdown_proceeds_without_a_game(self):
        from hard_lock import __main__ as m
        cfg = mock.Mock(grace_seconds=1, dry_run=True, defer_for_games=["League of Legends.exe"])
        with mock.patch("hard_lock.config.Config.load", return_value=cfg), \
             mock.patch("hard_lock.league.is_game_active", return_value=False), \
             mock.patch("hard_lock.history.EventLog"), \
             mock.patch("hard_lock.ui.GraceCountdown") as grace:
            rc = m._run_test_shutdown([])
        self.assertEqual(rc, 0)
        grace.assert_called_once()  # ran the countdown (dry-run → simulated)


if __name__ == "__main__":
    unittest.main()
