import unittest
import sys
import os
import json
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

# Mock the parts of PyQt that are used during class definition
# This is to avoid metaclass conflicts with MagicMock
mock_form_class = type('MockForm', (object,), {'setupUi': lambda self, widget: None})
mock_qdialog = type('MockQDialog', (object,), {'accept': lambda self: None})
MOCK_MODULES['qgis.PyQt'].uic.loadUiType.return_value = (mock_form_class, object)
MOCK_MODULES['qgis.PyQt.QtWidgets'].QDialog = mock_qdialog
MOCK_MODULES['qgis.PyQt.QtCore'].QSettings.return_value.value.return_value = 'en'
# --- End of Mocking ---

# Add the parent directory to the Python path to allow sibling imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from reneW.parameter_editor_dialog import ParameterEditorDialog

class TestParameterEditorDialog(unittest.TestCase):
    """Test suite for the ParameterEditorDialog logic."""

    @unittest.mock.patch('reneW.parameter_editor_dialog.ParameterEditorDialog.__init__', lambda *args, **kwargs: None)
    def setUp(self):
        """Set up a mock dialog for each test."""
        self.dialog = ParameterEditorDialog(parent=None)
        # Manually create mock widgets and instance variables
        self.dialog.mPipeTypeCombo = MagicMock()
        self.dialog.mMaterialsTable = MagicMock()
        self.dialog.mBtnAddRow = MagicMock()
        self.dialog.mBtnRemoveRow = MagicMock()
        self.dialog.mButtonBox = MagicMock()
        self.dialog.param_file = 'dummy_path.json'
        self.dialog.data = {}

    def test_load_and_populate(self):
        """Test that data is loaded from JSON and populates the UI."""
        sample_data = {
            "parameter_sets": [
                {"name": "Water", "materials": [{"key": "Iron"}]},
                {"name": "Sewer", "materials": [{"key": "Clay"}]}
            ]
        }
        # Mock the open function to return our sample data
        m = unittest.mock.mock_open(read_data=json.dumps(sample_data))
        with unittest.mock.patch('builtins.open', m):
            self.dialog._load_data()
            self.dialog._populate_combo()
            self.dialog.mPipeTypeCombo.count.return_value = 2

            # Check that the combo box was populated
            self.assertEqual(self.dialog.mPipeTypeCombo.count(), 2)
            self.dialog.mPipeTypeCombo.addItem.assert_any_call("Water")
            self.dialog.mPipeTypeCombo.addItem.assert_any_call("Sewer")

            # Check that the table is populated for the first item
            self.dialog.mPipeTypeCombo.currentText.return_value = "Water"
            self.dialog._populate_table()
            self.dialog.mMaterialsTable.rowCount.return_value = 1
            self.assertEqual(self.dialog.mMaterialsTable.rowCount(), 1)
            self.dialog.mMaterialsTable.setItem.assert_called()

    @unittest.mock.patch('reneW.parameter_editor_dialog.json.dump')
    def test_save_data(self, mock_json_dump):
        """Test that data is correctly read from the UI and saved to JSON."""
        # Setup mock UI state
        self.dialog.mPipeTypeCombo.currentText.return_value = "Water"
        self.dialog.mMaterialsTable.rowCount.return_value = 1

        # Mock the data for a single row in the table
        mock_item = MagicMock()
        mock_item.text.side_effect = ['Iron', 'fe', '1900', '2000', '10', '0.5', '5']
        self.dialog.mMaterialsTable.item.return_value = mock_item

        # Mock the parameter set to be updated
        self.dialog.data = {"parameter_sets": [{"name": "Water", "materials": []}]}

        # Mock the open function
        with unittest.mock.patch('builtins.open', unittest.mock.mock_open()):
            self.dialog.accept()  # This triggers the save

        # Check that json.dump was called once
        mock_json_dump.assert_called_once()

        # Check the data that was passed to json.dump
        written_data = mock_json_dump.call_args[0][0]
        saved_material = written_data['parameter_sets'][0]['materials'][0]

        self.assertEqual(saved_material['key'], 'Iron')
        self.assertEqual(saved_material['keywords'], ['fe'])
        self.assertEqual(saved_material['year_min'], 1900)
        self.assertEqual(saved_material['params']['a'], 10.0)


from reneW.reneW_dialog import ReneWDialog

class TestReneWDialog(unittest.TestCase):
    """Test suite for the ReneWDialog data handling logic."""

    @unittest.mock.patch('reneW.reneW_dialog.ReneWDialog.__init__', lambda *args, **kwargs: None)
    def setUp(self):
        """Set up a mock dialog for each test."""
        self.dialog = ReneWDialog(parent=None)
        # Manually create mock widgets and instance variables
        self.dialog.mCheckBoxEnableDimensionWeighting = MagicMock()
        self.dialog.mSpinBoxDimensionFactor = MagicMock()
        self.dialog.mBtnEditParameters = MagicMock()
        self.dialog.mCheckHotspot = MagicMock()
        self.dialog.mSpinBoxHotspotThreshold = MagicMock()
        self.dialog.mSpinBoxHotspotDistance = MagicMock()
        self.dialog.mButtonBox = MagicMock()
        self.dialog.mStatusLabel = MagicMock()
        self.dialog.tabs = []

    def test_save_and_load_settings(self):
        """Test that settings are saved and loaded with dynamic keys."""
        # Setup mock tabs and widgets
        mock_tab = {
            'name': 'Water',
            'check': MagicMock(),
            'layer_combo': MagicMock(),
            'mat_combo': MagicMock(),
            'year_combo': MagicMock(),
            'dim_combo': MagicMock(),
            'reno_year_combo': MagicMock(),
            'reno_method_combo': MagicMock()
        }
        self.dialog.tabs = [mock_tab]

        # --- Test Save ---
        mock_tab['check'].isChecked.return_value = True
        mock_tab['layer_combo'].currentLayer.return_value.id.return_value = 'layer123'
        mock_tab['mat_combo'].currentField.return_value = 'material_field'

        mock_project = MagicMock()
        with unittest.mock.patch('qgis.core.QgsProject.instance', return_value=mock_project):
            self.dialog.save_settings()

            # Check that settings were written with dynamic keys
            mock_project.writeEntry.assert_any_call('reneW', 'tab_Water_enabled', True)
            mock_project.writeEntry.assert_any_call('reneW', 'tab_Water_layer', 'layer123')
            mock_project.writeEntry.assert_any_call('reneW', 'tab_Water_materialField', 'material_field')

        # --- Test Load ---
        # Mock the return values from project settings
        def read_entry_side_effect(group, key, default):
            if key == 'tab_Water_layer': return 'layer123'
            if key == 'tab_Water_materialField': return 'material_field'
            return default

        mock_project.readBoolEntry.return_value = (True, True)
        mock_project.readEntry.side_effect = read_entry_side_effect

        # Mock the setLayer method
        with unittest.mock.patch('qgis.core.QgsProject.instance', return_value=mock_project):
            self.dialog.load_settings()

            # Check that settings were loaded and widgets updated
            mock_tab['check'].setChecked.assert_called_with(True)
            mock_tab['mat_combo'].setField.assert_called_with('material_field')


if __name__ == '__main__':
    unittest.main()
