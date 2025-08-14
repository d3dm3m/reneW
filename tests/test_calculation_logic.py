# test_calculation_logic.py
import math
import unittest
import sys
import os
from unittest.mock import MagicMock

# --- Mock QGIS modules for testing without a QGIS environment ---
MOCK_MODULES = {
    'qgis': MagicMock(),
    'qgis.core': MagicMock(),
    'qgis.gui': MagicMock(),
    'qgis.PyQt': MagicMock(),
    'qgis.PyQt.QtCore': MagicMock(),
    'qgis.PyQt.QtWidgets': MagicMock(),
    'qgis.PyQt.QtGui': MagicMock(),
}
sys.modules.update(MOCK_MODULES)
# --- End of Mocking ---

# Add the parent directory to the Python path to allow sibling imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from reneW.calculation_logic import (
    Cohort,
    MaterialParams,
    renewal_for_cohort_period,
    renewal_totals,
    decades_from,
    cumulative_by_period,
    derive_sigma_from_t50_t10,
)


class TestCalculationLogic(unittest.TestCase):
    def test_young_cohort_zero(self):
        mp = MaterialParams(mu=100.0, sigma=30.0)
        c = Cohort(length_km=5.0, install_year=2035, material_key="m")
        # Forecast period before installation → zero
        r = renewal_for_cohort_period(c, 2020, 2030, mp)
        self.assertAlmostEqual(r, 0.0, places=9)

    def test_pe_small_renewal_early(self):
        # Water PE defaults
        pe = MaterialParams(mu=125.6, sigma=27.7)
        c = Cohort(length_km=10.0, install_year=2000, material_key="pe")
        # Early horizon: 2020-2030 should be extremely small
        r = renewal_for_cohort_period(c, 2020, 2030, pe)
        self.assertLess(r, 0.05)  # should be near zero

    def test_cumulative_approaches_length(self):
        mp = MaterialParams(mu=100.0, sigma=25.0)
        c = Cohort(length_km=12.5, install_year=2000, material_key="m")
        periods = decades_from(2000, 40)  # 400 years
        totals = renewal_totals([c], periods, {"m": mp})
        self.assertAlmostEqual(sum(totals), 12.5, places=3)

    def test_clamping_bounds(self):
        mp = MaterialParams(mu=50.0, sigma=5.0)
        c = Cohort(length_km=1.0, install_year=1900, material_key="m")
        # Very long future window should not exceed the cohort length
        r = renewal_for_cohort_period(c, 1900, 2500, mp)
        self.assertLessEqual(r, 1.0)
        self.assertGreaterEqual(r, 0.0)

    def test_sigma_from_t50_t10(self):
        # Dagvatten utbyggnad: t50=125, t10=200 → sigma ≈ 58.5
        sigma = derive_sigma_from_t50_t10(125.0, 200.0)
        self.assertAlmostEqual(sigma, 58.5, places=1)


if __name__ == '__main__':
    unittest.main()
