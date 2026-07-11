import unittest

from hard_lock import league


class LeagueTestCase(unittest.TestCase):
    def test_running_process_names_nonempty(self):
        names = league.running_process_names()
        self.assertGreater(len(names), 0)
        # names are lowercased
        self.assertTrue(all(n == n.lower() for n in names))

    def test_detects_a_running_process(self):
        # this test process is python
        self.assertTrue(league.is_game_active(["python.exe"]))

    def test_rejects_absent_process(self):
        self.assertFalse(league.is_game_active(["no_such_game_zzz.exe"]))

    def test_empty_list_is_false(self):
        self.assertFalse(league.is_game_active([]))

    def test_case_insensitive(self):
        self.assertTrue(league.is_game_active(["PYTHON.EXE"]))


if __name__ == "__main__":
    unittest.main()
