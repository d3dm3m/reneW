import os
import json
from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import (QDialog, QDialogButtonBox, QWidget, QVBoxLayout,
                                 QCheckBox, QGroupBox, QGridLayout, QLabel,
                                 QFormLayout, QDoubleSpinBox, QSpinBox)
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

        # --- Programmatically add Hotspot Analysis controls ---
        hotspot_groupbox = QGroupBox(self.tr("Hotspot Analysis"))
        hotspot_layout = QFormLayout(hotspot_groupbox)

        self.mCheckBoxEnableHotspot = QCheckBox(self.tr("Enable Hotspot Analysis"))
        self.mSpinBoxHotspotThreshold = QDoubleSpinBox()
        self.mSpinBoxHotspotRadius = QSpinBox()

        self.mSpinBoxHotspotThreshold.setDecimals(2)
        self.mSpinBoxHotspotThreshold.setSingleStep(0.1)
        self.mSpinBoxHotspotThreshold.setRange(0.0, 1.0)
        self.mSpinBoxHotspotThreshold.setValue(0.75)

        self.mSpinBoxHotspotRadius.setRange(1, 1000)
        self.mSpinBoxHotspotRadius.setValue(50)
        self.mSpinBoxHotspotRadius.setSuffix(" m")

        hotspot_layout.addRow(self.mCheckBoxEnableHotspot)
        hotspot_layout.addRow(self.tr("Renewal need threshold:"), self.mSpinBoxHotspotThreshold)
        hotspot_layout.addRow(self.tr("Search radius:"), self.mSpinBoxHotspotRadius)

        # Add the new groupbox to the existing layout of global settings
        self.groupBox.layout().insertWidget(2, hotspot_groupbox)

        # --- Connect signals ---
        self.mCheckBoxEnableHotspot.toggled.connect(self.mSpinBoxHotspotThreshold.setEnabled)
        self.mCheckBoxEnableHotspot.toggled.connect(self.mSpinBoxHotspotRadius.setEnabled)
        # Set initial state
        self.mSpinBoxHotspotThreshold.setEnabled(False)
        self.mSpinBoxHotspotRadius.setEnabled(False)
        # --- End of Hotspot Analysis controls ---

        self.tabs = []
        self._create_dynamic_tabs()
        self._populate_municipality_filter()

        # --- Global Settings ---
        self.mCheckBoxEnableDimensionWeighting.toggled.connect(
            self.mSpinBoxDimensionFactor.setEnabled)
        self.mBtnEditParameters.clicked.connect(self._open_parameter_editor)

        # --- Set initial validation state ---
        self._validate_inputs()

    def _populate_municipality_filter(self):
        """Populates the municipality filter combo box from parameters."""
        self.mMunicipalityFilterCombo.clear()
        self.mMunicipalityFilterCombo.addItem(self.tr("All"), userData=None)

        param_file = os.path.join(os.path.dirname(__file__), 'parameters.json')
        try:
            with open(param_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            municipalities = config.get('municipalities', [])
            for muni in municipalities:
                self.mMunicipalityFilterCombo.addItem(muni.get('name'), userData=muni.get('code'))
        except (IOError, json.JSONDecodeError):
            pass # Fail silently if config is missing or corrupt

    def _create_dynamic_tabs(self):
        """Creates UI tabs dynamically based on the parameters.json file."""
        # Clear existing tabs and internal list
        while self.mTabWidget.count() > 0:
            self.mTabWidget.removeTab(0)
        self.tabs = []

        # Define the tabs to be created. These correspond to the top-level keys
        # in the parameters.json that define a set of materials.
        tab_names = ["water", "sewer/spill", "sewer/storm"]

        for set_name in tab_names:
            tab_widget = QWidget()
            tab_layout = QVBoxLayout(tab_widget)
            check = QCheckBox(self.tr("Analyze {0} pipes").format(set_name))
            group = QGroupBox()
            grid_layout = QGridLayout(group)

            fields_to_create = [
                {'label': self.tr("Layer:"), 'name': 'layer_combo', 'widget': QgsMapLayerComboBox},
                {'label': self.tr("Municipality field (optional):"), 'name': 'muni_combo', 'widget': QgsFieldComboBox},
                {'label': self.tr("Material field:"), 'name': 'mat_combo', 'widget': QgsFieldComboBox},
                {'label': self.tr("Construction year field:"), 'name': 'year_combo', 'widget': QgsFieldComboBox},
                {'label': self.tr("Dimension field:"), 'name': 'dim_combo', 'widget': QgsFieldComboBox},
                {'label': self.tr("Renovation year (optional):"), 'name': 'reno_year_combo', 'widget': QgsFieldComboBox},
                {'label': self.tr("Renovation method (optional):"), 'name': 'reno_method_combo', 'widget': QgsFieldComboBox}
            ]

            tab_data = {'name': set_name, 'check': check, 'group': group}
            for i, field_info in enumerate(fields_to_create):
                label = QLabel(field_info['label'])
                combo = field_info['widget']()
                if 'optional' in field_info['label']:
                    combo.setAllowEmptyFieldName(True)

                grid_layout.addWidget(label, i, 0)
                grid_layout.addWidget(combo, i, 1)
                tab_data[field_info['name']] = combo

            tab_layout.addWidget(check)
            tab_layout.addWidget(group)
            self.mTabWidget.addTab(tab_widget, set_name)
            self.tabs.append(tab_data)

            check.toggled.connect(group.setEnabled)
            tab_data['layer_combo'].setFilters(QgsMapLayerProxyModel.VectorLayer)
            for combo_name in ['muni_combo', 'mat_combo', 'year_combo', 'dim_combo', 'reno_year_combo', 'reno_method_combo']:
                tab_data['layer_combo'].layerChanged.connect(tab_data[combo_name].setLayer)

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
        if result:
            self._create_dynamic_tabs()
            self._populate_municipality_filter()
            self._validate_inputs()

    def useDimensionWeighting(self) -> bool:
        return self.mCheckBoxEnableDimensionWeighting.isChecked()

    def dimensionFactor(self) -> float:
        return self.mSpinBoxDimensionFactor.value()

    def useHotspotAnalysis(self) -> bool:
        return self.mCheckBoxEnableHotspot.isChecked()

    def hotspotThreshold(self) -> float:
        return self.mSpinBoxHotspotThreshold.value()

    def hotspotRadius(self) -> int:
        return self.mSpinBoxHotspotRadius.value()

    def get_selected_municipality_code(self):
        """Returns the user data (code) of the selected item in the municipality filter."""
        return self.mMunicipalityFilterCombo.currentData()

    def get_analysis_configs(self) -> list:
        """Returns a list of configurations for all layers selected for analysis."""
        configs = []
        for tab in self.tabs:
            if tab['check'].isChecked() and tab['layer_combo'].currentLayer():
                configs.append({
                    'type': tab['name'],
                    'layer': tab['layer_combo'].currentLayer(),
                    'municipality_field': tab['muni_combo'].currentField(),
                    'material_field': tab['mat_combo'].currentField(),
                    'year_field': tab['year_combo'].currentField(),
                    'dimension_field': tab['dim_combo'].currentField(),
                    'reno_year_field': tab['reno_year_combo'].currentField(),
                    'reno_method_field': tab['reno_method_combo'].currentField()
                })
        return configs

    def _validate_inputs(self):
        """Checks the state of the dialog's inputs and enables/disables the OK button."""
        ok_button = self.mButtonBox.button(QDialogButtonBox.Ok)
        if not ok_button: return

        error_messages = []
        is_at_least_one_tab_active = False

        for tab in self.tabs:
            if not tab['check'].isChecked():
                continue
            is_at_least_one_tab_active = True
            layer = tab['layer_combo'].currentLayer()
            if not isinstance(layer, QgsVectorLayer):
                error_messages.append(self.tr("{0}: No layer selected.").format(tab['name']))
                continue
            if not tab['mat_combo'].currentField():
                error_messages.append(self.tr("{0}: Material field is missing.").format(tab['name']))
            if not tab['year_combo'].currentField():
                error_messages.append(self.tr("{0}: Year field is missing.").format(tab['name']))
            else:
                year_field_name = tab['year_combo'].currentField()
                if not layer.fields().field(year_field_name).isNumeric():
                    error_messages.append(self.tr("{0}: Year field must be numeric.").format(tab['name']))
            if not tab['dim_combo'].currentField():
                error_messages.append(self.tr("{0}: Dimension field is missing.").format(tab['name']))

        if not is_at_least_one_tab_active:
            error_messages.append(self.tr("Select at least one pipe type to analyze."))

        if error_messages:
            ok_button.setEnabled(False)
            self.mStatusLabel.setText(self.tr("Error: ") + " | ".join(error_messages))
            self.mStatusLabel.setStyleSheet("color: red;")
        else:
            ok_button.setEnabled(True)
            self.mStatusLabel.setText(self.tr("Status: Ready to run analysis."))
            self.mStatusLabel.setStyleSheet("color: green;")

    def save_settings(self):
        """Saves the dialog's settings to the current QGIS project."""
        project = QgsProject.instance()
        project.writeEntry('reneW', 'municipalityFilter', self.mMunicipalityFilterCombo.currentText())

        for tab in self.tabs:
            prefix = f"tab_{tab['name']}"
            project.writeEntryBool('reneW', f'{prefix}_enabled', tab['check'].isChecked())
            if tab['layer_combo'].currentLayer():
                project.writeEntry('reneW', f'{prefix}_layer', tab['layer_combo'].currentLayer().id())
            project.writeEntry('reneW', f'{prefix}_municipalityField', tab['muni_combo'].currentField())
            project.writeEntry('reneW', f'{prefix}_materialField', tab['mat_combo'].currentField())
            project.writeEntry('reneW', f'{prefix}_yearField', tab['year_combo'].currentField())
            project.writeEntry('reneW', f'{prefix}_dimensionField', tab['dim_combo'].currentField())
            project.writeEntry('reneW', f'{prefix}_renoYearField', tab['reno_year_combo'].currentField())
            project.writeEntry('reneW', f'{prefix}_renoMethodField', tab['reno_method_combo'].currentField())

        project.writeEntryBool('reneW', 'dimensionWeightingEnabled', self.useDimensionWeighting())
        project.writeEntryDouble('reneW', 'dimensionFactor', self.dimensionFactor())
        project.writeEntryBool('reneW', 'hotspotAnalysisEnabled', self.useHotspotAnalysis())
        project.writeEntryDouble('reneW', 'hotspotThreshold', self.hotspotThreshold())
        project.writeEntry('reneW', 'hotspotRadius', self.hotspotRadius())

    def load_settings(self):
        """Loads the dialog's settings from the current QGIS project."""
        project = QgsProject.instance()

        saved_municipality = project.readEntry('reneW', 'municipalityFilter', '')[0]
        if saved_municipality:
            index = self.mMunicipalityFilterCombo.findText(saved_municipality)
            if index != -1:
                self.mMunicipalityFilterCombo.setCurrentIndex(index)

        def set_layer_if_exists(combo, layer_id):
            if layer_id:
                layer = QgsProject.instance().mapLayer(layer_id)
                if layer:
                    combo.setLayer(layer)

        for tab in self.tabs:
            prefix = f"tab_{tab['name']}"
            tab['check'].setChecked(project.readBoolEntry('reneW', f'{prefix}_enabled', False)[0])
            set_layer_if_exists(tab['layer_combo'], project.readEntry('reneW', f'{prefix}_layer', '')[0])
            tab['muni_combo'].setField(project.readEntry('reneW', f'{prefix}_municipalityField', '')[0])
            tab['mat_combo'].setField(project.readEntry('reneW', f'{prefix}_materialField', '')[0])
            tab['year_combo'].setField(project.readEntry('reneW', f'{prefix}_yearField', '')[0])
            tab['dim_combo'].setField(project.readEntry('reneW', f'{prefix}_dimensionField', '')[0])
            tab['reno_year_combo'].setField(project.readEntry('reneW', f'{prefix}_renoYearField', '')[0])
            tab['reno_method_combo'].setField(project.readEntry('reneW', f'{prefix}_renoMethodField', '')[0])

        self.mCheckBoxEnableDimensionWeighting.setChecked(project.readBoolEntry('reneW', 'dimensionWeightingEnabled', False)[0])
        self.mSpinBoxDimensionFactor.setValue(project.readDoubleEntry('reneW', 'dimensionFactor', 0.001)[0])

        self.mCheckBoxEnableHotspot.setChecked(project.readBoolEntry('reneW', 'hotspotAnalysisEnabled', False)[0])
        self.mSpinBoxHotspotThreshold.setValue(project.readDoubleEntry('reneW', 'hotspotThreshold', 0.75)[0])
        self.mSpinBoxHotspotRadius.setValue(int(project.readEntry('reneW', 'hotspotRadius', '50')[0]))
