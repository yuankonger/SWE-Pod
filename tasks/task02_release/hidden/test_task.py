"""The verifier's checks for task02_release: the regression suite, OPS-7's checks (task 1's) and the six other tickets.

`rubric.toml` beside this file and task 1's are the list of criteria. `kernel/rubric.py` runs them and puts the
directories that hold the checks on the import path.
"""
import unittest

from common import Company
from ops7_checks import Ops7Checks
from regression_checks import RegressionChecks
from release_checks import ReleaseChecks


class Task02(Company, RegressionChecks, Ops7Checks, ReleaseChecks, unittest.TestCase):
    pass
