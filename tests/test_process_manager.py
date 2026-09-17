import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from process_manager import ProcessManager  # noqa: E402


class TestProcessManager(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.pid_file = os.path.join(self.tmpdir.name, "test.pid")
        self.pm = ProcessManager(self.pid_file)

    def tearDown(self):
        if self.pm.is_running():
            self.pm.stop()
        self.tmpdir.cleanup()

    def test_is_running_false_initially(self):
        self.assertFalse(self.pm.is_running())

    def test_start_creates_pid_file_and_marks_running(self):
        self.pm.start("sleep 30")
        self.assertTrue(os.path.exists(self.pid_file))
        self.assertTrue(self.pm.is_running())

    def test_start_is_idempotent_when_already_running(self):
        pid1 = self.pm.start("sleep 30")
        pid2 = self.pm.start("sleep 30")
        self.assertEqual(pid1, pid2)

    def test_stop_terminates_process_and_clears_pid_file(self):
        self.pm.start("sleep 30")
        self.assertTrue(self.pm.is_running())

        result = self.pm.stop()

        self.assertTrue(result)
        self.assertFalse(self.pm.is_running())
        self.assertFalse(os.path.exists(self.pid_file))

    def test_stop_when_not_running_returns_false(self):
        result = self.pm.stop()
        self.assertFalse(result)

    def test_is_running_false_after_process_exits_on_its_own(self):
        self.pm.start("true")
        import time

        time.sleep(0.3)
        self.assertFalse(self.pm.is_running())


if __name__ == "__main__":
    unittest.main()
