import unittest
import sys
import os
from unittest.mock import MagicMock, patch

# Ensure the mock setup is run before other imports
from tests.mock_utils import setup_qgis_mocks
setup_qgis_mocks()

# Add the parent directory to the Python path to allow sibling imports from reneW
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the functions and classes to be tested from the dialog
from reneW.reneW_dialog import (
    _strip_accents,
    _norm,
    _score_layer_for_pipe_type,
    _pick_best_layer,
    _sample_field_values_numeric,
    _score_field_for_role,
    _pick_best_field,
    ReneWDialog
)
from qgis.core import QgsVectorLayer

class TestAutoDetectLogic(unittest.TestCase):
    """Test suite for the auto-detection logic in reneW_dialog.py."""

    def setUp(self):
        """Set up mock objects for each test."""
        # A mock for the dialog itself, to test methods like _apply_detected_to_ui
        self.dialog = MagicMock()
        # You can add more complex mocks here as needed, e.g., mock layers and fields
        pass

    def test_strip_accents(self):
        """Test that accents are correctly removed from strings."""
        self.assertEqual(_strip_accents("vattenåäö"), "vattenaao")
        self.assertEqual(_strip_accents("DRICKSVATTEN"), "DRICKSVATTEN")
        self.assertEqual(_strip_accents("Renovação"), "Renovacao")
        self.assertEqual(_strip_accents(""), "")

    def test_norm(self):
        """Test the full normalization function (_norm)."""
        self.assertEqual(_norm("Vatten-Ledning_ÅÄÖ"), "vattenledningaao")
        self.assertEqual(_norm("  Spill Vatten  "), "spillvatten")
        self.assertEqual(_norm(None), "")
        self.assertEqual(_norm(123), "123")

    def test_score_layer_for_pipe_type(self):
        """Test the layer scoring logic."""
        mock_layer = MagicMock()
        mock_layer.name.return_value = "Dricksvattenledningar_2023"

        # Mock fields
        mock_field_mat = MagicMock()
        mock_field_mat.name.return_value = "material"
        mock_field_dim = MagicMock()
        mock_field_dim.name.return_value = "diameter"
        mock_field_year = MagicMock()
        mock_field_year.name.return_value = "byggnadsar"
        mock_layer.fields.return_value = [mock_field_mat, mock_field_dim, mock_field_year]

        # Should get a high score for water
        water_score = _score_layer_for_pipe_type(mock_layer, "water")
        self.assertGreater(water_score, 10)

        # Should get a low score for wastewater
        wastewater_score = _score_layer_for_pipe_type(mock_layer, "wastewater")
        self.assertLess(wastewater_score, 10)

    def test_score_field_for_role(self):
        """Test the field scoring logic."""
        mock_layer = MagicMock()

        # Mock a good year field
        good_year_field = MagicMock()
        good_year_field.name.return_value = "install_year"
        good_year_field.type.return_value = 2 # QVariant.Int
        with patch('reneW.reneW_dialog._sample_field_values_numeric', return_value=(2005, 2020, 10)):
            score = _score_field_for_role(mock_layer, good_year_field, "year_field", "water")
            self.assertGreaterEqual(score, 12) # 6 for prefix, 3 for type, 3 for range

        # Mock a bad year field (wrong type)
        bad_year_field = MagicMock()
        bad_year_field.name.return_value = "year_as_string"
        bad_year_field.type.return_value = 10 # QVariant.String
        with patch('reneW.reneW_dialog._sample_field_values_numeric', return_value=(None, None, 0)):
            score = _score_field_for_role(mock_layer, bad_year_field, "year_field", "water")
            self.assertLess(score, 10)

        # Mock a good material field
        good_mat_field = MagicMock()
        good_mat_field.name.return_value = "Rormaterial"
        good_mat_field.type.return_value = 10 # QVariant.String
        score = _score_field_for_role(mock_layer, good_mat_field, "material_field", "water")
        self.assertGreaterEqual(score, 7) # 4 for substring, 3 for type

    @patch('reneW.reneW_dialog.QgsProject')
    @patch('reneW.reneW_dialog.isinstance', return_value=True)
    def test_pick_best_layer(self, mock_isinstance, mock_qgs_project):
        """Test the logic for picking the best layer."""
        # Create mock layers
        mock_field = MagicMock()
        mock_field.name.return_value = "material"

        water_layer = MagicMock()
        water_layer.name.return_value = "VA_Vattenledningar"
        water_layer.fields.return_value = [mock_field]

        sewer_layer = MagicMock()
        sewer_layer.name.return_value = "Avlopp-Spill"
        sewer_layer.fields.return_value = [mock_field]

        # Mock the project instance to return our layers
        mock_qgs_project.instance.return_value.mapLayers.return_value.values.return_value = [water_layer, sewer_layer]

        # Test picking for water
        best_water_layer, best_water_score = _pick_best_layer("water")
        self.assertEqual(best_water_layer.name(), "VA_Vattenledningar")
        self.assertGreater(best_water_score, 0)

        # Test picking for wastewater
        best_sewer_layer, best_sewer_score = _pick_best_layer("wastewater")
        self.assertEqual(best_sewer_layer.name(), "Avlopp-Spill")
        self.assertGreater(best_sewer_score, 0)

    def test_pick_best_field(self):
        """Test the logic for picking the best field for a given role."""
        mock_layer = MagicMock()

        # Create mock fields
        field1 = MagicMock()
        field1.name.return_value = "material"
        field1.type.return_value = 10 # String

        field2 = MagicMock()
        field2.name.return_value = "construction_year"
        field2.type.return_value = 2 # Int

        field3 = MagicMock()
        field3.name.return_value = "diameter"
        field3.type.return_value = 4 # Double

        mock_layer.fields.return_value = [field1, field2, field3]

        # Test picking material field
        with patch('reneW.reneW_dialog._sample_field_values_numeric', return_value=(None, None, 0)):
             best_field, best_score = _pick_best_field(mock_layer, "material_field", "water")
             self.assertEqual(best_field, "material")
             self.assertGreater(best_score, 5)

        # Test picking year field
        with patch('reneW.reneW_dialog._sample_field_values_numeric', return_value=(1990, 2010, 50)):
            best_field, best_score = _pick_best_field(mock_layer, "year_field", "water")
            self.assertEqual(best_field, "construction_year")
            self.assertGreater(best_score, 5)

    @patch('reneW.reneW_dialog._pick_best_layer')
    @patch('reneW.reneW_dialog._pick_best_field')
    def test_auto_detect_layers_fields(self, mock_pick_field, mock_pick_layer):
        """Test the main auto-detect handler."""
        # --- Setup Mocks ---
        # Mock a dialog instance
        with patch('reneW.reneW_dialog.ReneWDialog.__init__', lambda x, y=None: None):
            dialog = ReneWDialog()
            dialog.tr = lambda x: x
            dialog.iface = MagicMock()
            dialog._apply_detected_to_ui = MagicMock()

            # Mock the return values of the picker functions
            mock_layer = MagicMock()
            mock_layer.name.return_value = "test_layer"
            mock_pick_layer.return_value = (mock_layer, 10)
            mock_pick_field.return_value = ("test_field", 10)

            # --- Action ---
            dialog._auto_detect_layers_fields()

            # --- Assertions ---
            # Check that the picker functions were called for each pipe type
            self.assertEqual(mock_pick_layer.call_count, 3)

            # Check that _apply_detected_to_ui was called for each pipe type
            self.assertEqual(dialog._apply_detected_to_ui.call_count, 3)

            # Check the arguments of the first call to _apply_detected_to_ui
            first_call_args = dialog._apply_detected_to_ui.call_args_list[0][0]
            self.assertEqual(first_call_args[0], "water") # pipe_type
            self.assertEqual(first_call_args[1], mock_layer) # layer

    def test_apply_detected_to_ui(self):
        """Test the UI application logic."""
        # --- Setup Mocks ---
        with patch('reneW.reneW_dialog.ReneWDialog.__init__', lambda x, y=None: None):
            dialog = ReneWDialog()

            # Create a mock tab structure
            mock_tab = {
                'name': 'water',
                'check': MagicMock(),
                'layer_combo': MagicMock(),
                'mat_combo': MagicMock(),
                'year_combo': MagicMock(),
                'dim_combo': MagicMock(),
                'muni_combo': MagicMock()
            }
            dialog.tabs = [mock_tab]

            mock_layer = MagicMock()
            picks = {
                "material_field": "mat_field",
                "year_field": "year_field",
            }

            # --- Action ---
            dialog._apply_detected_to_ui("water", mock_layer, picks)

            # --- Assertions ---
            mock_tab['check'].setChecked.assert_called_with(True)
            mock_tab['layer_combo'].setLayer.assert_called_with(mock_layer)
            mock_tab['mat_combo'].setField.assert_called_with("mat_field")
            mock_tab['year_combo'].setField.assert_called_with("year_field")


if __name__ == '__main__':
    unittest.main()
