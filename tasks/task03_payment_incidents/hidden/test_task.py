"""The verifier's checks for task03_payment_incidents: the regression suite (task 1's) and the incident checks.

`rubric.toml` beside this file and the regression suite's are the list of criteria. `kernel/rubric.py` runs them
and puts the directories that hold the checks on the import path.
"""
import unittest

from common import Company
from incident_checks import IncidentChecks
from regression_checks import RegressionChecks


class Task03(IncidentChecks, Company, RegressionChecks, unittest.TestCase):
    pass
