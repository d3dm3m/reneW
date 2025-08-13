import os
import json
from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import (QDialog, QDialogButtonBox, QWidget, QVBoxLayout,
                                 QCheckBox, QGroupBox, QGridLayout, QLabel)
from qgis.core import QgsMapLayerProxyModel, QgsProject, QgsVectorLayer
from qgis.gui import QgsFieldComboBox, QgsMapLayerComboBox
from .parameter_editor_dialog import ParameterEditorDialog

# This loads your .ui file
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'reneW_dialog_base.ui'))


class ReneWDialog(QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(ReneWDialog, self).__init__(parent)
        self.setupUi(self)

        self.tabs = []
        self._create_dynamic_tabs()

        # --- Global Settings ---
        self.mCheckBoxEnableDimensionWeighting.toggled.connect(
            self.mSpinBoxDimensionFactor.setEnabled)
        self.mBtnEditParameters.clicked.connect(self._open_parameter_editor)

        # --- Hotspot Analysis Settings ---
        self.mCheckHotspot.toggled.connect(
            self.mSpinBoxHotspotThreshold.setEnabled)
        self.mCheckHotspot.toggled.connect(
            self.mSpinBoxHotspotDistance.setEnabled)
        self.mSpinBoxHotspotThreshold.setEnabled(False)
        self.mSpinBoxHotspotDistance.setEnabled(False)

        # --- Set initial validation state ---
        self._validate_inputs()

    def _create_dynamic_tabs(self):
        """Creates UI tabs dynamically based on the parameters.json file."""
        # Clear existing tabs from the UI designer
        while self.mTabWidget.count() > 0:
            self.mTabWidget.removeTab(0)

        # Load parameter sets from JSON
        param_file = os.path.join(os.path.dirname(__file__), 'parameters.json')
        try:
            with open(param_file, 'r') as f:
                config = json.load(f)
            parameter_sets = config.get('parameter_sets', [])
        except (IOError, json.JSONDecodeError):
            parameter_sets = []

        # Create a tab for each parameter set
        for param_set in parameter_sets:
            set_name = param_set.get('name')
            if not set_name:
                continue

            # Create widgets for the tab
            tab_widget = QWidget()
            tab_layout = QVBoxLayout(tab_widget)

            check = QCheckBox(self.tr("Analyze {0} pipes").format(set_name))
            group = QGroupBox()
            grid_layout = QGridLayout(group)

            # Define the fields to be created
            fields_to_create = [
                {'label': self.tr("Layer:"), 'name': 'layer_combo',
                 'widget': QgsMapLayerComboBox},
                {'label': self.tr("Material field:"),
                 'name': 'mat_combo', 'widget': QgsFieldComboBox},
                {'label': self.tr("Construction year field:"),
                 'name': 'year_combo', 'widget': QgsFieldComboBox},
                {'label': self.tr("Dimension field:"),
                 'name': 'dim_combo', 'widget': QgsFieldComboBox},
                {'label': self.tr("Renovation year (optional):"),
                 'name': 'reno_year_combo', 'widget': QgsFieldComboBox},
                {'label': self.tr("Renovation method (optional):"),
                 'name': 'reno_method_combo', 'widget': QgsFieldComboBox}
            ]

            tab_data = {'name': set_name, 'check': check, 'group': group}

            for i, field_info in enumerate(fields_to_create):
                label = QLabel(field_info['label'])
                combo = field_info['widget']()
                # Allow empty for optional fields
                if 'reno' in field_info['name']:
                    combo.setAllowEmptyFieldName(True)

                grid_layout.addWidget(label, i, 0)
                grid_layout.addWidget(combo, i, 1)
                tab_data[field_info['name']] = combo

            # Add widgets to tab layout
            tab_layout.addWidget(check)
            tab_layout.addWidget(group)
            self.mTabWidget.addTab(tab_widget, set_name)
            self.tabs.append(tab_data)

            # Connect signals
            check.toggled.connect(group.setEnabled)
            tab_data['layer_combo'].setFilters(
                QgsMapLayerProxyModel.VectorLayer)
            tab_data['layer_combo'].layerChanged.connect(
                tab_data['mat_combo'].setLayer)
            tab_data['layer_combo'].layerChanged.connect(
                tab_data['year_combo'].setLayer)
            tab_data['layer_combo'].layerChanged.connect(
                tab_data['dim_combo'].setLayer)
            tab_data['layer_combo'].layerChanged.connect(
                tab_data['reno_year_combo'].setLayer)
            tab_data['layer_combo'].layerChanged.connect(
                tab_data['reno_method_combo'].setLayer)

            check.toggled.connect(self._validate_inputs)
            tab_data['layer_combo'].layerChanged.connect(self._validate_inputs)
            tab_data['mat_combo'].fieldChanged.connect(self._validate_inputs)
            tab_data['year_combo'].fieldChanged.connect(self._validate_inputs)
            tab_data['dim_combo'].fieldChanged.connect(self._validate_inputs)

            group.setEnabled(False)

    def _open_parameter_editor(self):
        """Opens the parameter editor dialog."""
        editor_dialog = ParameterEditorDialog(self)
        result = editor_dialog.exec_()

        # If the user saved changes, reload the dynamic tabs
        if result:
            self._create_dynamic_tabs()
            self._validate_inputs()

    # --- Getter methods for global settings ---

    def useDimensionWeighting(self) -> bool:
        return self.mCheckBoxEnableDimensionWeighting.isChecked()

    def dimensionFactor(self) -> float:
        return self.mSpinBoxDimensionFactor.value()

    # --- Getter for all selected configurations ---
    def get_analysis_configs(self) -> list:
        """
        Returns a list of configurations for all layers selected for analysis.
        Each configuration is a dictionary.
        """
        configs = []
        for tab in self.tabs:
            if tab['check'].isChecked() and tab['layer_combo'].currentLayer():
                configs.append({
                    'type': tab['name'],
                    'layer': tab['layer_combo'].currentLayer(),
                    'material_field': tab['mat_combo'].currentField(),
                    'year_field': tab['year_combo'].currentField(),
                    'dimension_field': tab['dim_combo'].currentField(),
                    'reno_year_field': tab['reno_year_combo'].currentField(),
                    'reno_method_field': tab['reno_method_combo'].currentField()
                })
        return configs

    # --- Validation Logic ---
    def _validate_inputs(self):
        """
        Checks the state of the dialog's inputs and enables/disables the OK button.
        Updates the status label with guidance for the user.
        """
        ok_button = self.mButtonBox.button(QDialogButtonBox.Ok)
        if not ok_button:
            return

        error_messages = []
        is_at_least_one_tab_active = False

        for tab in self.tabs:
            if not tab['check'].isChecked():
                continue

            is_at_least_one_tab_active = True
            layer = tab['layer_combo'].currentLayer()

            if not isinstance(layer, QgsVectorLayer):
                error_messages.append(self.tr("{0}: No layer selected.").format(
                    tab['name']))
                continue

            # Check that required fields are selected
            if not tab['mat_combo'].currentField():
                error_messages.append(self.tr("{0}: Material field is missing.").format(
                    tab['name']))
            if not tab['year_combo'].currentField():
                error_messages.append(
                    self.tr("{0}: Year field is missing.").format(tab['name']))
            else:
                # Check that year field is numeric
                year_field_name = tab['year_combo'].currentField()
                if not layer.fields().field(year_field_name).isNumeric():
                    error_messages.append(self.tr(
                        "{0}: Year field must be numeric.").format(tab['name']))

            if not tab['dim_combo'].currentField():
                error_messages.append(
                    self.tr("{0}: Dimension field is missing.").format(tab['name']))
            else:
                # Check that dimension field is numeric
                dim_field_name = tab['dim_combo'].currentField()
                if not layer.fields().field(dim_field_name).isNumeric():
                    error_messages.append(self.tr(
                        "{0}: Dimension field must be numeric.").format(tab['name']))

        if not is_at_least_one_tab_active:
            error_messages.append(
                self.tr("Select at least one pipe type to analyze."))

        if error_messages:
            ok_button.setEnabled(False)
            self.mStatusLabel.setText(
                self.tr("Error: ") + " | ".join(error_messages))
            self.mStatusLabel.setStyleSheet("color: red;")
        else:
            ok_button.setEnabled(True)
            self.mStatusLabel.setText(
                self.tr("Status: Ready to run analysis."))
            self.mStatusLabel.setStyleSheet("color: green;")

    # --- Getter methods for hotspot settings ---

    def isHotspotAnalysisEnabled(self) -> bool:
        return self.mCheckHotspot.isChecked()

    def getHotspotThreshold(self) -> float:
        return self.mSpinBoxHotspotThreshold.value()

    def getHotspotDistance(self) -> float:
        return self.mSpinBoxHotspotDistance.value()

    def save_settings(self):
        """Saves the dialog's settings to the current QGIS project."""
        project = QgsProject.instance()

        for tab in self.tabs:
            prefix = f"tab_{tab['name']}"
            project.writeEntry(
                'reneW', f'{prefix}_enabled', tab['check'].isChecked())
            if tab['layer_combo'].currentLayer():
                project.writeEntry(
                    'reneW', f'{prefix}_layer', tab['layer_combo'].currentLayer().id())
            project.writeEntry(
                'reneW', f'{prefix}_materialField', tab['mat_combo'].currentField())
            project.writeEntry(
                'reneW', f'{prefix}_yearField', tab['year_combo'].currentField())
            project.writeEntry(
                'reneW', f'{prefix}_dimensionField', tab['dim_combo'].currentField())
            project.writeEntry(
                'reneW', f'{prefix}_renoYearField', tab['reno_year_combo'].currentField())
            project.writeEntry(
                'reneW', f'{prefix}_renoMethodField', tab['reno_method_combo'].currentField())

        # Global settings
        project.writeEntry('reneW', 'dimensionWeightingEnabled',
                           self.useDimensionWeighting())
        project.writeEntry('reneW', 'dimensionFactor', self.dimensionFactor())

        # Hotspot settings
        project.writeEntry('reneW', 'hotspotEnabled',
                           self.isHotspotAnalysisEnabled())
        project.writeEntry('reneW', 'hotspotThreshold',
                           self.getHotspotThreshold())
        project.writeEntry('reneW', 'hotspotDistance',
                           self.getHotspotDistance())

    def load_settings(self):
        """Loads the dialog's settings from the current QGIS project."""
        project = QgsProject.instance()

        def set_layer_if_exists(combo, layer_id):
            if layer_id:
                layer = QgsProject.instance().mapLayer(layer_id)
                if layer:
                    combo.setLayer(layer)

        for tab in self.tabs:
            prefix = f"tab_{tab['name']}"
            tab['check'].setChecked(project.readBoolEntry(
                'reneW', f'{prefix}_enabled', False)[0])
            set_layer_if_exists(tab['layer_combo'], project.readEntry(
                'reneW', f'{prefix}_layer', ''))
            tab['mat_combo'].setField(project.readEntry(
                'reneW', f'{prefix}_materialField', ''))
            tab['year_combo'].setField(project.readEntry(
                'reneW', f'{prefix}_yearField', ''))
            tab['dim_combo'].setField(project.readEntry(
                'reneW', f'{prefix}_dimensionField', ''))
            tab['reno_year_combo'].setField(project.readEntry(
                'reneW', f'{prefix}_renoYearField', ''))
            tab['reno_method_combo'].setField(project.readEntry(
                'reneW', f'{prefix}_renoMethodField', ''))

        # Global settings
        self.mCheckBoxEnableDimensionWeighting.setChecked(
            project.readBoolEntry('reneW', 'dimensionWeightingEnabled', False)[0])
        self.mSpinBoxDimensionFactor.setValue(
            project.readDoubleEntry('reneW', 'dimensionFactor', 0.001))

        # Hotspot settings
        self.mCheckHotspot.setChecked(
            project.readBoolEntry('reneW', 'hotspotEnabled', False)[0])
        self.mSpinBoxHotspotThreshold.setValue(
            project.readDoubleEntry('reneW', 'hotspotThreshold', 0.5))
        self.mSpinBoxHotspotDistance.setValue(
            project.readDoubleEntry('reneW', 'hotspotDistance', 5.0))
