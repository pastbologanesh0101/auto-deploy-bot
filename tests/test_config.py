import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config  # noqa: E402


class TestConfig(unittest.TestCase):
    def test_from_file_loads_valid_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "config.json")
            with open(path, "w") as f:
                json.dump({"target_branch": "release", "poll_interval_seconds": 30}, f)
            config = Config.from_file(path)
            self.assertEqual(config.target_branch, "release")
            self.assertEqual(config.poll_interval_seconds, 30)

    def test_from_file_rejects_unknown_key_with_clear_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "config.json")
            with open(path, "w") as f:
                json.dump({"target_branchh": "main"}, f)
            with self.assertRaises(ValueError) as ctx:
                Config.from_file(path)
            self.assertIn("target_branchh", str(ctx.exception))
            self.assertIn("target_branch", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
