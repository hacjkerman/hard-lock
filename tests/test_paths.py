import os
import unittest
from pathlib import Path
from unittest import mock

from hard_lock import paths


class DataDirTestCase(unittest.TestCase):
    def test_frozen_prod_uses_hardlock(self):
        with mock.patch.object(paths, "is_frozen", return_value=True), \
             mock.patch("hard_lock.build.DEV_BUILD", False), \
             mock.patch.dict(os.environ, {"APPDATA": str(Path.cwd())}):
            self.assertEqual(paths.data_dir().name, "HardLock")

    def test_frozen_dev_uses_hardlockdev(self):
        with mock.patch.object(paths, "is_frozen", return_value=True), \
             mock.patch("hard_lock.build.DEV_BUILD", True), \
             mock.patch.dict(os.environ, {"APPDATA": str(Path.cwd())}):
            self.assertEqual(paths.data_dir().name, "HardLockDev")


if __name__ == "__main__":
    unittest.main()
