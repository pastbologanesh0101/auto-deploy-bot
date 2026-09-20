import os
import subprocess
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestStatusCli(unittest.TestCase):
    def test_version_flag_prints_version_and_exits_zero(self):
        result = subprocess.run(
            [sys.executable, "status.py", "--version"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("auto-deploy-bot", result.stdout)


if __name__ == "__main__":
    unittest.main()
