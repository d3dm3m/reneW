import unittest
import sys
import os
from unittest.mock import MagicMock, patch

# Ensure the mock setup is run before other imports
from tests.mock_utils import setup_qgis_mocks

setup_qgis_mocks()

# Add the parent directory to the Python path to allow sibling imports from reneW
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from reneW.material_lookup import _strip_accents, _norm
from reneW.reneW_dialog import ReneWDialog


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
        self.assertEqual(_norm("Vatten-Ledning_ÅÄÖ"), "vatten-ledning_aao")
        self.assertEqual(_norm("  Spill Vatten  "), "spill vatten")
        self.assertEqual(_norm(None), "")
        self.assertEqual(_norm(123), "123")



    def test_apply_detected_to_ui(self):
        """Test the UI application logic."""
        # --- Setup Mocks ---
        with patch("reneW.reneW_dialog.ReneWDialog.__init__", lambda x, y=None: None):
            dialog = ReneWDialog()

            # Create a mock tab structure
            mock_tab = {
                "name": "water",
                "check": MagicMock(),
                "layer_combo": MagicMock(),
                "mat_combo": MagicMock(),
                "year_combo": MagicMock(),
                "dim_combo": MagicMock(),
                "muni_combo": MagicMock(),
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
            mock_tab["check"].setChecked.assert_called_with(True)
            mock_tab["layer_combo"].setLayer.assert_called_with(mock_layer)
            mock_tab["mat_combo"].setField.assert_called_with("mat_field")
            mock_tab["year_combo"].setField.assert_called_with("year_field")


if __name__ == "__main__":
    unittest.main()
