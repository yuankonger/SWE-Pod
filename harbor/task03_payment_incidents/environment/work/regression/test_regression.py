"""The company's end-to-end regression suite: starts the whole company from its history and checks what must keep working.

    python3 -m unittest -v test_regression          (from this directory, inside the toolchain image)
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import Company  # noqa: E402
from regression_checks import RegressionChecks  # noqa: E402


class Regression(Company, RegressionChecks, unittest.TestCase):
    pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
