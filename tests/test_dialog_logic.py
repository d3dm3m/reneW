import unittest
import sys
import os
from unittest.mock import MagicMock, patch

from tests.mock_utils import setup_qgis_mocks

setup_qgis_mocks()

# Add the parent directory to the Python path to allow sibling imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from reneW.parameter_editor_dialog import ParameterEditorDialog
from reneW.reneW_dialog import ReneWDialog


class TestParameterEditorDialog(unittest.TestCase):
    """Test suite for the refactored ParameterEditorDialog logic."""

    @patch(
        "reneW.parameter_editor_dialog.open",
        new_callable=unittest.mock.mock_open,
        read_data="{}",
    )
    @patch(
        "reneW.parameter_editor_dialog.ParameterEditorDialog.__init__",
        lambda *args, **kwargs: None,
    )
    def setUp(self, mock_open):
        """Set up a mock dialog for each test."""
        self.dialog = ParameterEditorDialog()
        self.dialog.mPipeTypeCombo = MagicMock()
        self.dialog.mMaterialsTable = MagicMock()
        self.dialog.mBtnAddRow = MagicMock()
        self.dialog.mBtnRemoveRow = MagicMock()
        self.dialog.mButtonBox = MagicMock()
        self.dialog.param_file = "dummy_path.json"
        self.dialog.data = {
            "material_defaults": {
                "pvc": {"mu": 60, "sigma": 5},
                "segjarn": {"mu": 90, "sigma": 5},
            },
            "water": {"segjarn": {"mu": 100, "sigma": 8}},
            "sewer": {"spill": {}, "storm": {}},
        }

    @patch("reneW.parameter_editor_dialog.QTableWidgetItem")
    @patch("reneW.parameter_editor_dialog.QFont")
    def test_populate_table_merged_view(self, mock_qfont, mock_qtablewidgetitem):
        """Test that the table shows a merged view of defaults and overrides."""

        # Configure the mock for QTableWidgetItem to behave like the real thing
        def mock_qtablewidgetitem_factory(text=""):
            mock_item = MagicMock()
            mock_item.text.return_value = str(text)
            return mock_item

        mock_qtablewidgetitem.side_effect = mock_qtablewidgetitem_factory

        italic_font_instance = mock_qfont.return_value
        self.dialog.mPipeTypeCombo.currentText.return_value = "water"

        # The test data includes 'pvc' (default) and 'segjarn' (override for water)
        self.dialog._populate_table()

        # Assert that QFont() was called to create the italic font
        mock_qfont.assert_called()
        italic_font_instance.setItalic.assert_called_with(True)

        # There should be 2 rows: pvc (from default) and segjarn (from water override)
        self.assertEqual(self.dialog.mMaterialsTable.setRowCount.call_args[0][0], 2)

        # Get the item mocks that were passed to setItem
        calls = self.dialog.mMaterialsTable.setItem.call_args_list
        # Create a dictionary of {text: item_mock} for the key items (column 0)
        items = {
            call.args[2].text(): call.args[2] for call in calls if call.args[1] == 0
        }

        # 'pvc' is a default, so its key item should get the italic font
        self.assertIn("pvc", items)
        items["pvc"].setFont.assert_called_with(italic_font_instance)

        # 'segjarn' is an override, so its key item should NOT get the italic font
        self.assertIn("segjarn", items)
        items["segjarn"].setFont.assert_not_called()

    @patch("reneW.parameter_editor_dialog.json.dump")
    def test_save_data_with_overrides(self, mock_json_dump):
        """Test that only overrides and new materials are saved."""
        self.dialog.mPipeTypeCombo.currentText.return_value = "water"
        self.dialog.mMaterialsTable.rowCount.return_value = 3

        def item_side_effect(row, col):
            mock_cell = MagicMock()
            if row == 0:
                mock_cell.text.return_value = ["pvc", "60", "5"][col].strip()
            elif row == 1:
                mock_cell.text.return_value = ["segjarn", "110.5", "9.5"][col].strip()
            elif row == 2:
                mock_cell.text.return_value = ["new_mat", "99", "9"][col].strip()
            return mock_cell

        self.dialog.mMaterialsTable.item.side_effect = item_side_effect
        with patch("builtins.open", unittest.mock.mock_open()):
            self.dialog.accept()
        written_data = mock_json_dump.call_args[0][0]
        saved_water_bucket = written_data["water"]
        self.assertNotIn("pvc", saved_water_bucket)
        self.assertIn("segjarn", saved_water_bucket)
        self.assertEqual(saved_water_bucket["segjarn"]["mu"], 110.5)
        self.assertIn("new_mat", saved_water_bucket)
        self.assertEqual(saved_water_bucket["new_mat"]["mu"], 99)


class TestReneWDialog(unittest.TestCase):
    """Test suite for the ReneWDialog data handling logic."""

    @patch("reneW.reneW_dialog.ReneWDialog.__init__", lambda *args, **kwargs: None)
    def setUp(self):
        """Set up a mock dialog for each test."""
        self.dialog = ReneWDialog()
        self.dialog.tr = lambda x: x
        self.dialog.mCheckBoxEnableDimensionWeighting = MagicMock()
        self.dialog.mSpinBoxDimensionFactor = MagicMock()
        self.dialog.mBtnEditParameters = MagicMock()
        self.dialog.mButtonBox = MagicMock()
        self.dialog.mStatusLabel = MagicMock()
        self.dialog.mMunicipalityFilterCombo = MagicMock()
        self.dialog.mCheckBoxEnableHotspot = MagicMock()
        self.dialog.mSpinBoxHotspotThreshold = MagicMock()
        self.dialog.mSpinBoxHotspotRadius = MagicMock()
        self.dialog.mTemporalGroupBox = MagicMock()
        self.dialog.mTemporalGroupBox.isChecked.return_value = (
            False  # Default to disabled
        )
        self.dialog.mTemporalStartYearSpinBox = MagicMock()
        self.dialog.mTemporalStartYearSpinBox.value.return_value = 2025
        self.dialog.mTemporalEndYearSpinBox = MagicMock()
        self.dialog.mTemporalEndYearSpinBox.value.return_value = 2065
        self.dialog.mTemporalStepSpinBox = MagicMock()
        self.dialog.mTemporalStepSpinBox.value.return_value = 5
        self.dialog.tabs = []

    def test_validation_logic_invalid_temporal_range(self):
        """Test validation logic: Invalid temporal year range."""
        mock_ok_button = MagicMock()
        self.dialog.mButtonBox.button.return_value = mock_ok_button
        mock_layer = MagicMock()
        mock_layer.fields.return_value.field.return_value.isNumeric.return_value = True
        self.dialog.tabs = [
            {
                "name": "Water",
                "check": MagicMock(isChecked=lambda: True),
                "layer_combo": MagicMock(currentLayer=lambda: mock_layer),
                "mat_combo": MagicMock(currentField=lambda: "mat"),
                "year_combo": MagicMock(currentField=lambda: "year"),
                "dim_combo": MagicMock(currentField=lambda: "dim"),
            }
        ]
        self.dialog.mTemporalGroupBox.isChecked.return_value = True
        self.dialog.mTemporalStartYearSpinBox.value.return_value = 2050
        self.dialog.mTemporalEndYearSpinBox.value.return_value = 2040
        self.dialog._validate_inputs()
        mock_ok_button.setEnabled.assert_called_with(False)

        # Retrieve the actual text passed to the mock
        actual_error_text = self.dialog.mStatusLabel.setText.call_args[0][0]
        expected_error = "Temporal Analysis: End year must be after start year."
        self.assertIn(expected_error, actual_error_text)
