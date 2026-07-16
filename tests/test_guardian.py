import datetime as dt
import json
import tempfile
import time
import unittest
from pathlib import Path

from hard_lock import guardian


class GuardianTestCase(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self._orig_data_dir = guardian.paths.data_dir
        self._orig_cfg_path = guardian.paths.config_path
        guardian.paths.data_dir = lambda: self.d
        guardian.paths.config_path = lambda: self.d / "config.json"

    def tearDown(self):
        guardian.paths.data_dir = self._orig_data_dir
        guardian.paths.config_path = self._orig_cfg_path

    def test_fresh_heartbeat_is_alive(self):
        guardian.write_heartbeat("main")
        self.assertTrue(guardian.is_alive("main"))
        self.assertLess(guardian.heartbeat_age("main"), 1.0)

    def test_missing_heartbeat_is_not_alive(self):
        self.assertFalse(guardian.is_alive("watchdog"))
        self.assertIsNone(guardian.heartbeat_age("watchdog"))

    def test_stale_heartbeat_is_not_alive(self):
        (self.d / "main.heartbeat").write_text(str(time.time() - 100), encoding="utf-8")
        self.assertFalse(guardian.is_alive("main"))

    def test_clear_heartbeat(self):
        guardian.write_heartbeat("main")
        guardian.clear_heartbeat("main")
        self.assertIsNone(guardian.heartbeat_age("main"))

    def test_disarm_due_reads_shared_config(self):
        cfg = self.d / "config.json"
        past = (dt.datetime.now() - dt.timedelta(minutes=1)).isoformat()
        cfg.write_text(json.dumps({"disarm_at": past}), encoding="utf-8")
        self.assertTrue(guardian.disarm_due())

        future = (dt.datetime.now() + dt.timedelta(hours=5)).isoformat()
        cfg.write_text(json.dumps({"disarm_at": future}), encoding="utf-8")
        self.assertFalse(guardian.disarm_due())

        cfg.write_text(json.dumps({"disarm_at": None}), encoding="utf-8")
        self.assertFalse(guardian.disarm_due())

    def test_disarm_due_false_when_no_config(self):
        self.assertFalse(guardian.disarm_due())


if __name__ == "__main__":
    unittest.main()
