import unittest
import os
import sys

# Add the parent directory to the Python path to allow sibling imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from reneW import calculation_logic
from importlib import reload

class TestCalculationLogic(unittest.TestCase):
    """Test suite for the calculation logic of the reneW plugin."""

    @classmethod
    def setUpClass(cls):
        """Load the original parameters file content once for all tests."""
        cls.original_params_path = os.path.join(
            os.path.dirname(__file__), '..', 'reneW', 'parameters.json'
        )
        # Ensure the file exists before trying to read it
        if os.path.exists(cls.original_params_path):
            with open(cls.original_params_path, 'r') as f:
                cls.original_params_content = f.read()
        else:
            cls.original_params_content = None

    def tearDown(self):
        """Ensure the original parameters file is restored after each test."""
        if self.original_params_content is not None:
            with open(self.original_params_path, 'w') as f:
                f.write(self.original_params_content)
        # Reload the module to ensure it's in a clean state for the next test
        reload(calculation_logic)

    def test_config_loaded_successfully(self):
        """Test that the parameters.json file is loaded correctly."""
        # The module is loaded at startup, so we just check the state.
        reload(calculation_logic) # Ensure fresh load
        self.assertIsNotNone(calculation_logic.CONFIG_DATA, "CONFIG_DATA should be loaded.")
        self.assertIsNone(calculation_logic.get_config_error(), "CONFIG_ERROR should be None on successful load.")
        self.assertIn('parameter_sets', calculation_logic.CONFIG_DATA)

    def test_find_material_params(self):
        """Test the parameter lookup logic."""
        # Test case 1: Simple match for Vatten (Water)
        params = calculation_logic.find_material_params('PE-rör', 2010, 'Vatten')
        self.assertIsNotNone(params)
        self.assertAlmostEqual(params['a'], 106.9383234418553)

        # Test case 2: Match with year constraint
        params = calculation_logic.find_material_params('PVC', 1965, 'Vatten')
        self.assertIsNotNone(params)
        self.assertAlmostEqual(params['a'], 5.9999999999999982) # Should match PVC < 1970

        params = calculation_logic.find_material_params('pvc-ledning', 1975, 'Vatten')
        self.assertIsNotNone(params)
        self.assertAlmostEqual(params['a'], 55.490601649355284) # Should match PVC >= 1970

        # Test case 3: Match for Spillvatten (Foul Water)
        params = calculation_logic.find_material_params('Betong', 1960, 'Spillvatten')
        self.assertIsNotNone(params)
        self.assertAlmostEqual(params['a'], 2.2095582333960015) # Should match Betong 1950-1969

        # Test case 4: Fallback to default
        params = calculation_logic.find_material_params('Okänt material', 2000, 'Dagvatten')
        self.assertIsNotNone(params)
        # Check against the default 'a' value for Dagvatten
        self.assertAlmostEqual(params['a'], 1.9366525983057512)

    def test_calculate_renewal_need(self):
        """Test the renewal need calculation formula."""
        # Test case 1: Basic calculation
        # Using Vatten, PE, age=60, year=1963, dimension=100, no weighting
        # Params: a=106.938, b=0.062543, c=50
        # S(t) = 1 / (1 + ((60 - 50) / 106.938)^0.062543) = 1 / (1 + (0.09351)^0.062543) = 1 / (1 + 0.8620) = 0.5370
        # Need = 1 - S(t) = 0.4630
        renewal_need = calculation_logic.calculate_renewal_need(
            pipeline_type='Vatten', material='PE', age=60, year=1963,
            dimension=100, use_dimension_weighting=False, dimension_factor=0.0
        )
        self.assertAlmostEqual(renewal_need, 0.4630, places=4)

        # Test case 2: Age less than or equal to c
        # age (50) <= c (50), so need should be 0.0
        renewal_need = calculation_logic.calculate_renewal_need(
            pipeline_type='Vatten', material='PE', age=50, year=1973,
            dimension=100, use_dimension_weighting=False, dimension_factor=0.0
        )
        self.assertEqual(renewal_need, 0.0)

        # Test case 3: With dimension weighting
        renewal_need_weighted = calculation_logic.calculate_renewal_need(
            pipeline_type='Vatten', material='PE', age=60, year=1963,
            dimension=100, use_dimension_weighting=True, dimension_factor=0.001
        )
        # weight = 1 + (100 * 0.001) = 1.1
        # expected = 0.4630 * 1.1 = 0.5093
        self.assertAlmostEqual(renewal_need_weighted, 0.5093, places=4)

    def test_missing_parameters_file(self):
        """Test behavior when parameters.json is missing."""
        # Rename the file to simulate it being missing
        os.rename(self.original_params_path, self.original_params_path + ".bak")
        try:
            reload(calculation_logic)
            self.assertIsNone(calculation_logic.CONFIG_DATA)
            self.assertIsNotNone(calculation_logic.get_config_error())
            self.assertIn("not found", calculation_logic.get_config_error())
        finally:
            # Rename it back
            os.rename(self.original_params_path + ".bak", self.original_params_path)

    def test_corrupt_parameters_file(self):
        """Test behavior with a corrupt parameters.json file."""
        # Write invalid JSON to the file
        with open(self.original_params_path, 'w') as f:
            f.write('{"key": "value",}') # Corrupt JSON with trailing comma

        reload(calculation_logic)
        self.assertIsNone(calculation_logic.CONFIG_DATA)
        self.assertIsNotNone(calculation_logic.get_config_error())
        self.assertIn("Failed to load or parse", calculation_logic.get_config_error())


if __name__ == '__main__':
    unittest.main()
