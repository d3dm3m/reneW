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
mock_qgsvectorlayer = type('MockQgsVectorLayer', (object,), {})
MOCK_MODULES['qgis.core'].QgsVectorLayer = mock_qgsvectorlayer
MOCK_MODULES['qgis.PyQt.QtCore'].QSettings.return_value.value.return_value = 'en'
# --- End of Mocking ---

# Add the parent directory to the Python path to allow sibling imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from reneW.parameter_editor_dialog import ParameterEditorDialog

class TestParameterEditorDialog(unittest.TestCase):
    """Test suite for the refactored ParameterEditorDialog logic."""

    @unittest.mock.patch('reneW.parameter_editor_dialog.ParameterEditorDialog.__init__', lambda *args, **kwargs: None)
    def setUp(self):
        """Set up a mock dialog for each test."""
        self.dialog = ParameterEditorDialog(parent=None)
        # Manually create mock widgets and instance variables
        self.dialog.mPipeTypeCombo = MagicMock()
        self.dialog.mMaterialsTable = MagicMock()
        self.dialog.mBtnAddMaterialRow = MagicMock()
        self.dialog.mBtnRemoveMaterialRow = MagicMock()
        self.dialog.mButtonBox = MagicMock()
        self.dialog.param_file = 'dummy_path.json'

        # Configure the QTableWidgetItem mock to return a new mock instance each time
        # This is crucial for testing UI elements that are created in a loop.
        MOCK_MODULES['qgis.PyQt.QtWidgets'].QTableWidgetItem.side_effect = lambda text='': MagicMock()

        # Sample data with the new normalized structure
        self.dialog.data = {
            "material_defaults": {
                "pvc": {"mu": 60, "sigma": 5},
                "segjarn": {"mu": 90, "sigma": 5}
            },
            "water": {
                "segjarn": {"mu": 100, "sigma": 8} # Override for water
            },
            "sewer": { "spill": {}, "storm": {} }
        }

    def test_populate_table_merged_view(self):
        """Test that the table shows a merged view of defaults and overrides."""
        qfont_mock_class = MOCK_MODULES['qgis.PyQt.QtGui'].QFont
        italic_font_instance = qfont_mock_class.return_value
        qtablewidgetitem_mock = MOCK_MODULES['qgis.PyQt.QtWidgets'].QTableWidgetItem

        # Simulate user selecting "water"
        self.dialog.mPipeTypeCombo.currentText.return_value = "water"
        self.dialog._populate_table()

        # Check that an italic font was created for styling defaults
        qfont_mock_class.assert_called()
        italic_font_instance.setItalic.assert_called_with(True)

        # There are 2 unique keys: 'pvc' (default) and 'segjarn' (override)
        self.assertEqual(self.dialog.mMaterialsTable.setRowCount.call_args[0][0], 2)

        # Check that QTableWidgetItem was constructed with the correct text values
        # Note: sorted order is 'pvc', then 'segjarn'
        self.assertEqual(qtablewidgetitem_mock.call_args_list[0][0][0], 'pvc')
        self.assertEqual(qtablewidgetitem_mock.call_args_list[1][0][0], '60') # default mu
        self.assertEqual(qtablewidgetitem_mock.call_args_list[3][0][0], 'segjarn')
        self.assertEqual(qtablewidgetitem_mock.call_args_list[4][0][0], '100') # override mu

        # Get the item mocks from the setItem calls
        calls = self.dialog.mMaterialsTable.setItem.call_args_list
        pvc_key_item = calls[0][0][2]
        segjarn_key_item = calls[3][0][2]

        # Check that setFont was called for the default item ('pvc')
        pvc_key_item.setFont.assert_called_with(italic_font_instance)

        # Check that setFont was NOT called for the override item ('segjarn')
        segjarn_key_item.setFont.assert_not_called()

    @unittest.mock.patch('reneW.parameter_editor_dialog.json.dump')
    def test_save_data_with_overrides(self, mock_json_dump):
        """Test that only overrides and new materials are saved."""
        # --- Setup ---
        self.dialog.mPipeTypeCombo.currentText.return_value = "water"
        self.dialog.mMaterialsTable.rowCount.return_value = 3

        # Mock the table items. Rows:
        # 1. 'pvc': Same as default, should NOT be saved.
        # 2. 'segjarn': Different from default, SHOULD be saved as override.
        # 3. 'new_mat': New material, SHOULD be saved as override.
        def item_side_effect(row, col):
            mock_cell = MagicMock()
            if row == 0: # pvc
                mock_cell.text.return_value = ['pvc', '60', '5'][col].strip()
            elif row == 1: # segjarn
                mock_cell.text.return_value = ['segjarn', '110.5', '9.5'][col].strip()
            elif row == 2: # new_mat
                mock_cell.text.return_value = ['new_mat', '99', '9'][col].strip()
            return mock_cell
        self.dialog.mMaterialsTable.item.side_effect = item_side_effect

        # --- Action ---
        with unittest.mock.patch('builtins.open', unittest.mock.mock_open()):
            self.dialog.accept()  # This triggers the save

        # --- Assertions ---
        mock_json_dump.assert_called_once()
        written_data = mock_json_dump.call_args[0][0]

        saved_water_bucket = written_data['water']

        # 'pvc' should NOT be in the water bucket, as it matches the default
        self.assertNotIn('pvc', saved_water_bucket)

        # 'segjarn' SHOULD be in the water bucket with the new override values
        self.assertIn('segjarn', saved_water_bucket)
        self.assertEqual(saved_water_bucket['segjarn']['mu'], 110.5)

        # 'new_mat' SHOULD be in the water bucket
        self.assertIn('new_mat', saved_water_bucket)
        self.assertEqual(saved_water_bucket['new_mat']['mu'], 99)


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
        self.dialog.mButtonBox = MagicMock()
        self.dialog.mStatusLabel = MagicMock()
        self.dialog.mMunicipalityFilterCombo = MagicMock()
        self.dialog.mCheckBoxEnableHotspot = MagicMock()
        self.dialog.mSpinBoxHotspotThreshold = MagicMock()
        self.dialog.mSpinBoxHotspotRadius = MagicMock()
        self.dialog.tabs = []
        self.dialog.tr = lambda x: x  # Mock the translation function

    def test_populate_municipality_filter(self):
        """Test that the municipality filter is populated correctly."""
        sample_data = {
            "municipalities": [
                {"code": 1, "name": "Stockholm"},
                {"code": 2, "name": "Uppsala"}
            ]
        }
        # Mock the open function to return our sample data
        m = unittest.mock.mock_open(read_data=json.dumps(sample_data))
        with unittest.mock.patch('builtins.open', m):
            self.dialog._populate_municipality_filter()

            # Check that the combo box was populated correctly
            self.dialog.mMunicipalityFilterCombo.addItem.assert_any_call("All", userData=None)
            self.dialog.mMunicipalityFilterCombo.addItem.assert_any_call("Stockholm", userData=1)
            self.dialog.mMunicipalityFilterCombo.addItem.assert_any_call("Uppsala", userData=2)

    def test_save_and_load_settings(self):
        """Test that settings are saved and loaded with dynamic keys."""
        # Setup mock tabs and widgets
        mock_tab = {
            'name': 'Water',
            'check': MagicMock(),
            'layer_combo': MagicMock(),
            'muni_combo': MagicMock(),
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
        mock_tab['muni_combo'].currentField.return_value = 'municipality_field'

        mock_project = MagicMock()
        with unittest.mock.patch.object(self.dialog, 'useDimensionWeighting', return_value=True), \
             unittest.mock.patch.object(self.dialog, 'dimensionFactor', return_value=0.005), \
             unittest.mock.patch('qgis.core.QgsProject.instance', return_value=mock_project):
            self.dialog.save_settings()

            # Check that the correct type-specific methods were called
            mock_project.writeEntryBool.assert_any_call('reneW', 'tab_Water_enabled', True)
            mock_project.writeEntry.assert_any_call('reneW', 'tab_Water_layer', 'layer123')
            mock_project.writeEntry.assert_any_call('reneW', 'tab_Water_materialField', 'material_field')
            mock_project.writeEntry.assert_any_call('reneW', 'tab_Water_municipalityField', 'municipality_field')
            mock_project.writeEntryBool.assert_any_call('reneW', 'dimensionWeightingEnabled', True)
            mock_project.writeEntryDouble.assert_any_call('reneW', 'dimensionFactor', 0.005)

        # --- Test Load ---
        # Mock the return values from project settings
        def read_entry_side_effect(group, key, default):
            if key == 'tab_Water_layer':
                return ('layer123', True)
            if key == 'tab_Water_materialField':
                return ('material_field', True)
            if key == 'tab_Water_municipalityField':
                return ('municipality_field', True)
            return (default, True)

        mock_project.readBoolEntry.return_value = (True, True)
        mock_project.readEntry.side_effect = read_entry_side_effect
        mock_project.readDoubleEntry.return_value = (0.5, True)

        # Mock the setLayer method
        with unittest.mock.patch('qgis.core.QgsProject.instance', return_value=mock_project):
            self.dialog.load_settings()

            # Check that settings were loaded and widgets updated
            mock_tab['check'].setChecked.assert_called_with(True)
            mock_tab['mat_combo'].setField.assert_called_with('material_field')
            mock_tab['muni_combo'].setField.assert_called_with('municipality_field')

    def test_validation_logic_valid_case(self):
        """Test validation logic: Valid inputs with a text dimension field."""
        # --- Setup Mocks ---
        mock_ok_button = MagicMock()
        self.dialog.mButtonBox.button.return_value = mock_ok_button

        mock_numeric_field = MagicMock()
        mock_numeric_field.isNumeric.return_value = True
        mock_text_field = MagicMock()
        mock_text_field.isNumeric.return_value = False

        mock_layer = MOCK_MODULES['qgis.core'].QgsVectorLayer()
        mock_layer.fields = MagicMock()
        def field_side_effect(name):
            if name == 'year_field': return mock_numeric_field
            if name == 'dim_field_text': return mock_text_field
            return MagicMock()
        mock_layer.fields.return_value.field.side_effect = field_side_effect

        mock_tab = {
            'name': 'Water',
            'check': MagicMock(isChecked=lambda: True),
            'layer_combo': MagicMock(currentLayer=lambda: mock_layer),
            'mat_combo': MagicMock(currentField=lambda: 'mat_field'),
            'year_combo': MagicMock(currentField=lambda: 'year_field'),
            'dim_combo': MagicMock(currentField=lambda: 'dim_field_text'),
        }
        self.dialog.tabs = [mock_tab]

        # --- Run Validation ---
        self.dialog._validate_inputs()

        # --- Assert ---
        mock_ok_button.setEnabled.assert_called_with(True)
        self.dialog.mStatusLabel.setText.assert_called_with(
            "Status: Ready to run analysis.")

    def test_validation_logic_missing_field(self):
        """Test validation logic: Missing a required field."""
        # --- Setup Mocks ---
        mock_ok_button = MagicMock()
        self.dialog.mButtonBox.button.return_value = mock_ok_button
        mock_layer = MOCK_MODULES['qgis.core'].QgsVectorLayer()
        mock_tab = {
            'name': 'Water',
            'check': MagicMock(isChecked=lambda: True),
            'layer_combo': MagicMock(currentLayer=lambda: mock_layer),
            'mat_combo': MagicMock(currentField=lambda: 'mat_field'),
            'year_combo': MagicMock(currentField=lambda: ''), # Missing year
            'dim_combo': MagicMock(currentField=lambda: 'dim_field'),
        }
        self.dialog.tabs = [mock_tab]

        # --- Run Validation ---
        self.dialog._validate_inputs()

        # --- Assert ---
        mock_ok_button.setEnabled.assert_called_with(False)
        self.dialog.mStatusLabel.setText.assert_called_with(
            "Error: " + "{0}: Year field is missing.".format('Water'))

    def test_validation_logic_non_numeric_year(self):
        """Test validation logic: Non-numeric year field."""
        # --- Setup Mocks ---
        mock_ok_button = MagicMock()
        self.dialog.mButtonBox.button.return_value = mock_ok_button

        mock_non_numeric_field = MagicMock()
        mock_non_numeric_field.isNumeric.return_value = False

        mock_layer = MOCK_MODULES['qgis.core'].QgsVectorLayer()
        mock_layer.fields = MagicMock()
        mock_layer.fields.return_value.field.return_value = mock_non_numeric_field

        mock_tab = {
            'name': 'Water',
            'check': MagicMock(isChecked=lambda: True),
            'layer_combo': MagicMock(currentLayer=lambda: mock_layer),
            'mat_combo': MagicMock(currentField=lambda: 'mat_field'),
            'year_combo': MagicMock(currentField=lambda: 'year_field'),
            'dim_combo': MagicMock(currentField=lambda: 'dim_field'),
        }
        self.dialog.tabs = [mock_tab]

        # --- Run Validation ---
        self.dialog._validate_inputs()

        # --- Assert ---
        mock_ok_button.setEnabled.assert_called_with(False)
        self.dialog.mStatusLabel.setText.assert_called_with(
            "Error: " + "{0}: Year field must be numeric.".format('Water'))
