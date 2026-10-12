import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from funnylex.__main__ import main


class HW1(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.chdir(ROOT)
        cls.out = tempfile.mkdtemp()
        assert main(["--out", cls.out, "build"]) == 0

    def test_cases(self):
        self.assertEqual(main(["--out", self.out, "test", "tests/cases.json"]), 0)


if __name__ == "__main__":
    unittest.main()
