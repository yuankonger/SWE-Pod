"""The verifier's checks for task01_order_confirmation: the regression suite and the OPS-7 checks, on one running company.

`rubric.toml` beside this file is the list of criteria. `kernel/rubric.py` runs it and puts the directories that
hold the checks on the import path (this one and ../regression).
"""
import unittest

from common import Company
from ops7_checks import Ops7Checks
from regression_checks import RegressionChecks


class Task01(Company, RegressionChecks, Ops7Checks, unittest.TestCase):
    pass
