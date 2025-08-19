import os
from datetime import datetime

from qgis.core import QgsProject, Qgis, QgsMapLayerProxyModel, QgsVectorLayer, QgsWkbTypes
from qgis.PyQt.QtWidgets import (QDialog, QDialogButtonBox, QWidget, QVBoxLayout,
                                 QCheckBox, QGroupBox, QGridLayout, QLabel,
                                 QFormLayout, QDoubleSpinBox, QSpinBox,
                                 QComboBox, QLineEdit, QHBoxLayout)
from qgis.PyQt.QtCore import QSettings
from qgis.PyQt import uic
from qgis.gui import QgsFieldComboBox, QgsMapLayerComboBox
from .parameter_editor_dialog import ParameterEditorDialog
from . import utils


FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'reneW_dialog_base.ui'))


class ReneWDialog(QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(ReneWDialog, self).__init__(parent)
        self.setupUi(self)

        hotspot_groupbox = QGroupBox(self.tr("Hotspot Analysis"))
        hotspot_layout = QFormLayout(hotspot_groupbox)
        self.mCheckBoxEnableHotspot = QCheckBox(
            self.tr("Enable Hotspot Analysis")
        )
        self.mSpinBoxHotspotThreshold = QDoubleSpinBox()
        self.mSpinBoxHotspotRadius = QSpinBox()
        self.mSpinBoxHotspotThreshold.setDecimals(2)
        self.mSpinBoxHotspotThreshold.setSingleStep(0.01)
        self.mSpinBoxHotspotThreshold.setRange(0.0, 1.0)
        self.mSpinBoxHotspotThreshold.setValue(0.75)
        self.mSpinBoxHotspotRadius.setRange(1, 1000)
        self.mSpinBoxHotspotRadius.setValue(50)
        self.mSpinBoxHotspotRadius.setSuffix(" m")
        hotspot_layout.addRow(self.mCheckBoxEnableHotspot)
        hotspot_layout.addRow(self.tr("Renewal need threshold:"),
                              self.mSpinBoxHotspotThreshold)
        hotspot_layout.addRow(self.tr("Search radius:"),
                              self.mSpinBoxHotspotRadius)
        self.groupBox.layout().insertWidget(2, hotspot_groupbox)
        self.mCheckBoxEnableHotspot.toggled[bool].connect(
            self.mSpinBoxHotspotThreshold.setEnabled
        )
        self.mCheckBoxEnableHotspot.toggled[bool].connect(
            self.mSpinBoxHotspotRadius.setEnabled
        )
        self.mSpinBoxHotspotThreshold.setEnabled(False)
        self.mSpinBoxHotspotRadius.setEnabled(False)

        optimism_group = QGroupBox("Optimism Factors")
        optimism_layout = QGridLayout()

        self.water_factor_spinbox = QDoubleSpinBox()
        self.water_factor_spinbox.setRange(0.5, 1.5)
        self.water_factor_spinbox.setSingleStep(0.1)
        self.water_factor_spinbox.setValue(1.0)
        optimism_layout.addWidget(QLabel("Water:"), 0, 0)
        optimism_layout.addWidget(self.water_factor_spinbox, 0, 1)

        self.wastewater_factor_spinbox = QDoubleSpinBox()
        self.wastewater_factor_spinbox.setRange(0.5, 1.5)
        self.wastewater_factor_spinbox.setSingleStep(0.1)
        self.wastewater_factor_spinbox.setValue(1.0)
        optimism_layout.addWidget(QLabel("Wastewater:"), 1, 0)
        optimism_layout.addWidget(self.wastewater_factor_spinbox, 1, 1)

        self.stormwater_factor_spinbox = QDoubleSpinBox()
        self.stormwater_factor_spinbox.setRange(0.5, 1.5)
        self.stormwater_factor_spinbox.setSingleStep(0.1)
        self.stormwater_factor_spinbox.setValue(1.0)
        optimism_layout.addWidget(QLabel("Stormwater:"), 2, 0)
        optimism_layout.addWidget(self.stormwater_factor_spinbox, 2, 1)

        optimism_group.setLayout(optimism_layout)
        self.groupBox.layout().addWidget(optimism_group)

        self.prop_group = QGroupBox(self.tr("Property-based Year Imputation"))
        prop_layout = QVBoxLayout()

        layer_layout = QHBoxLayout()
        layer_layout.addWidget(QLabel(self.tr("Property Layer:")))
        self.propertyLayerCombo = QComboBox()
        layer_layout.addWidget(self.propertyLayerCombo)
        prop_layout.addLayout(layer_layout)

        field_layout = QHBoxLayout()
        field_layout.addWidget(QLabel(self.tr("Year Field:")))
        self.propertyYearFieldCombo = QComboBox()
        field_layout.addWidget(self.propertyYearFieldCombo)
        prop_layout.addLayout(field_layout)

        kneigh_layout = QHBoxLayout()
        kneigh_layout.addWidget(QLabel(self.tr("K Neighbors:")))
        self.kNeighborsSpin = QSpinBox()
        self.kNeighborsSpin.setRange(1, 200)
        self.kNeighborsSpin.setValue(15)
        kneigh_layout.addWidget(self.kNeighborsSpin)
        prop_layout.addLayout(kneigh_layout)

        frac_layout = QHBoxLayout()
        frac_layout.addWidget(QLabel(self.tr("Sample Fractions (0–1, comma separated):")))
        self.sampleFractionsEdit = QLineEdit("0,0.25,0.5,0.75,1")
        frac_layout.addWidget(self.sampleFractionsEdit)
        prop_layout.addLayout(frac_layout)

        self.prop_group.setLayout(prop_layout)
        self.layout().addWidget(self.prop_group)

        self.mTemporalGroupBox = QGroupBox(self.tr("Temporal Analysis"))
        self.mTemporalGroupBox.setCheckable(True)
        self.mTemporalGroupBox.setChecked(False)
        temporal_layout = QGridLayout(self.mTemporalGroupBox)
        self.mTemporalStartYearSpinBox = QSpinBox()
        self.mTemporalEndYearSpinBox = QSpinBox()
        self.mTemporalStepSpinBox = QSpinBox()
        self.mNumClassesSpinBox = QSpinBox()
        current_year = datetime.now().year
        self.mTemporalStartYearSpinBox.setRange(current_year - 10,
                                                current_year + 100)
        self.mTemporalStartYearSpinBox.setValue(current_year)
        self.mTemporalEndYearSpinBox.setRange(current_year, current_year + 200)
        self.mTemporalEndYearSpinBox.setValue(current_year + 40)
        self.mTemporalStepSpinBox.setRange(1, 20)
        self.mTemporalStepSpinBox.setValue(5)
        self.mNumClassesSpinBox.setRange(3, 9)
        self.mNumClassesSpinBox.setValue(5)
        temporal_layout.addWidget(QLabel(self.tr("Start Year:")), 0, 0)
        temporal_layout.addWidget(self.mTemporalStartYearSpinBox, 0, 1)
        temporal_layout.addWidget(QLabel(self.tr("End Year:")), 0, 2)
        temporal_layout.addWidget(self.mTemporalEndYearSpinBox, 0, 3)
        temporal_layout.addWidget(QLabel(self.tr("Step (Years):")), 1, 0)
        temporal_layout.addWidget(self.mTemporalStepSpinBox, 1, 1)
        temporal_layout.addWidget(QLabel(self.tr("Number of Color Classes:")),
                                  1, 2)
        temporal_layout.addWidget(self.mNumClassesSpinBox, 1, 3)
        self.verticalLayout_2.insertWidget(self.verticalLayout_2.count() - 3,
                                           self.mTemporalGroupBox)

        self.tabs = []
        self._create_dynamic_tabs()
        self.mCheckBoxEnableDimensionWeighting.toggled[bool].connect(
            self.mSpinBoxDimensionFactor.setEnabled
        )
        self.mBtnEditParameters.clicked.connect(self._open_parameter_editor)
        self.mTemporalGroupBox.toggled[bool].connect(self._validate_inputs)
        self.mTemporalStartYearSpinBox.valueChanged.connect(
            self._validate_inputs
        )
        self.mTemporalEndYearSpinBox.valueChanged.connect(self._validate_inputs)
        try:
            self.btnAutoDetect.clicked.connect(self._auto_detect_layers_fields)
        except Exception:
            pass

        self.propertyLayerCombo.clear()
        for lyr in QgsProject.instance().mapLayers().values():
            if (isinstance(lyr, QgsVectorLayer) and
                    lyr.geometryType() == QgsWkbTypes.PointGeometry):
                self.propertyLayerCombo.addItem(lyr.name(), lyr.id())

        self.propertyLayerCombo.currentIndexChanged.connect(
            self._updatePropertyFields
        )
        self._updatePropertyFields()

        self._validate_inputs()

    def _update_municipality_filter(self):
        self.mMunicipalityFilterCombo.clear()
        self.mMunicipalityFilterCombo.addItem(self.tr("All"), userData=None)

        source_layer = None
        muni_field = None

        for tab in self.tabs:
            if tab['check'].isChecked():
                layer = tab['layer_combo'].currentLayer()
                field = tab['muni_combo'].currentField()
                if layer and field:
                    source_layer = layer
                    muni_field = field
                    break

        if not source_layer or not muni_field:
            self.mMunicipalityFilterCombo.setEnabled(False)
            return

        self.mMunicipalityFilterCombo.setEnabled(True)
        idx = source_layer.fields().lookupField(muni_field)
        if idx != -1:
            unique_values = source_layer.uniqueValues(idx)
            for value in sorted(list(unique_values)):
                self.mMunicipalityFilterCombo.addItem(str(value),
                                                      userData=value)

    def _create_dynamic_tabs(self):
        while self.mTabWidget.count() > 0:
            self.mTabWidget.removeTab(0)
        self.tabs = []
        tab_names = ["water", "sewer", "stormwater"]
        for set_name in tab_names:
            tab_widget = QWidget()
            tab_layout = QVBoxLayout(tab_widget)
            check = QCheckBox(self.tr("Analyze {0} pipes").format(set_name))
            group = QGroupBox()
            grid_layout = QGridLayout(group)
            fields_to_create = [
                {'label': self.tr("Layer:"), 'name': 'layer_combo',
                 'widget': QgsMapLayerComboBox},
                {'label': self.tr("Municipality field (optional):"),
                 'name': 'muni_combo', 'widget': QgsFieldComboBox},
                {'label': self.tr("Material field:"), 'name': 'mat_combo',
                 'widget': QgsFieldComboBox},
                {'label': self.tr("Construction year field:"),
                 'name': 'year_combo', 'widget': QgsFieldComboBox},
                {'label': self.tr("Dimension field:"), 'name': 'dim_combo',
                 'widget': QgsFieldComboBox},
                {'label': self.tr("Renovation year (optional):"),
                 'name': 'reno_year_combo', 'widget': QgsFieldComboBox},
                {'label': self.tr("Renovation method (optional):"),
                 'name': 'reno_method_combo', 'widget': QgsFieldComboBox}
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
            check.toggled[bool].connect(group.setEnabled)
            tab_data['layer_combo'].setFilters(
                QgsMapLayerProxyModel.VectorLayer
            )
            for combo_name in ['muni_combo', 'mat_combo', 'year_combo',
                               'dim_combo', 'reno_year_combo',
                               'reno_method_combo']:
                tab_data['layer_combo'].layerChanged.connect(
                    tab_data[combo_name].setLayer
                )

            check.toggled[bool].connect(self._validate_inputs)
            check.toggled[bool].connect(self._update_municipality_filter)
            tab_data['layer_combo'].layerChanged.connect(self._validate_inputs)
            tab_data['layer_combo'].layerChanged.connect(
                self._update_municipality_filter
            )
            tab_data['muni_combo'].fieldChanged.connect(
                self._update_municipality_filter
            )
            tab_data['mat_combo'].fieldChanged.connect(self._validate_inputs)
            tab_data['year_combo'].fieldChanged.connect(self._validate_inputs)
            tab_data['dim_combo'].fieldChanged.connect(self._validate_inputs)
            group.setEnabled(False)

        self._update_municipality_filter()

    def _open_parameter_editor(self):
        editor_dialog = ParameterEditorDialog(self)
        editor_dialog.exec()
        self._create_dynamic_tabs()
        self._update_municipality_filter()
        self._validate_inputs()

    def _apply_detected_to_ui(self, pipe_type: str, layer, picks: dict):
        tab_name_map = {
            "water": "water",
            "wastewater": "sewer",
            "stormwater": "stormwater"
        }
        target_tab_name = tab_name_map.get(pipe_type)
        if not target_tab_name:
            return

        for tab in self.tabs:
            if tab['name'] == target_tab_name:
                tab['check'].setChecked(True)
                if layer:
                    tab['layer_combo'].setLayer(layer)

                field_map = {
                    "material_field": "mat_combo",
                    "year_field": "year_combo",
                    "dimension_field": "dim_combo",
                    "municipality_field": "muni_combo",
                    "reno_year_field": "reno_year_combo",
                    "reno_method_field": "reno_method_combo"
                }

                for role, field_name in picks.items():
                    combo_name = field_map.get(role)
                    if combo_name and combo_name in tab and field_name:
                        tab[combo_name].setField(field_name)
                break

    def _auto_detect_layers_fields(self):
        plan = {
            "water": ["material_field", "year_field", "dimension_field",
                      "municipality_field"],
            "wastewater": ["material_field", "year_field",
                           "dimension_field", "reno_year_field",
                           "reno_method_field", "municipality_field"],
            "stormwater": ["material_field", "year_field",
                           "dimension_field", "municipality_field"],
        }

        for pipe_type in ["water", "wastewater", "stormwater"]:
            layer, lscore = utils.pick_best_layer(pipe_type)
            if not layer or lscore == 0:
                utils.log_info(f"[AutoDetect] No good layer for {pipe_type}.")
                continue

            picks = {}
            for role in plan[pipe_type]:
                fname, fscore = utils.pick_best_field(layer, role, pipe_type)
                if fname:
                    picks[role] = fname

            self._apply_detected_to_ui(pipe_type, layer, picks)
            roles_str = ", ".join([f"{k}:{v}" for k, v in picks.items()])
            utils.log_info(
                f"[AutoDetect] {pipe_type}: layer='{layer.name()}' "
                f"(score={lscore}); fields: {roles_str}"
            )

        try:
            iface = getattr(self, 'iface', None)
            if iface:
                iface.messageBar().pushMessage(
                    "reneW", "Auto-detection complete.", level=Qgis.Info,
                    duration=4
                )
        except Exception as e:
            utils.log_warning(f"Could not push message to bar: {e}")

    def _updatePropertyFields(self):
        self.propertyYearFieldCombo.clear()
        idx = self.propertyLayerCombo.currentIndex()
        if idx < 0:
            return
        layer_id = self.propertyLayerCombo.itemData(idx)
        layer = QgsProject.instance().mapLayer(layer_id)
        if not layer:
            return
        for field in layer.fields():
            self.propertyYearFieldCombo.addItem(field.name())

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

    def useTemporalAnalysis(self) -> bool:
        return self.mTemporalGroupBox.isChecked()

    def temporalStartYear(self) -> int:
        return self.mTemporalStartYearSpinBox.value()

    def temporalEndYear(self) -> int:
        return self.mTemporalEndYearSpinBox.value()

    def temporalStep(self) -> int:
        return self.mTemporalStepSpinBox.value()

    def numColorClasses(self) -> int:
        return self.mNumClassesSpinBox.value()

    def waterOptimismFactor(self) -> float:
        return self.water_factor_spinbox.value()

    def wastewaterOptimismFactor(self) -> float:
        return self.wastewater_factor_spinbox.value()

    def stormwaterOptimismFactor(self) -> float:
        return self.stormwater_factor_spinbox.value()

    def get_selected_municipality_code(self):
        return self.mMunicipalityFilterCombo.currentData()

    def get_analysis_configs(self) -> list:
        configs = []
        for tab in self.tabs:
            if tab['check'].isChecked() and tab['layer_combo'].currentLayer():
                type_name = tab['name']
                if type_name == "stormwater":
                    type_name = "sewer/storm"
                elif type_name == "sewer":
                    type_name = "sewer/spill"

                configs.append({
                    'type': type_name,
                    'layer': tab['layer_combo'].currentLayer(),
                    'municipality_field': tab['muni_combo'].currentField(),
                    'material_field': tab['mat_combo'].currentField(),
                    'year_field': tab['year_combo'].currentField(),
                    'dimension_field': tab['dim_combo'].currentField(),
                    'reno_year_field': tab['reno_year_combo'].currentField(),
                    'reno_method_field': tab['reno_method_combo'].currentField()
                })
        return configs

    def propertyLayer(self):
        idx = self.propertyLayerCombo.currentIndex()
        if idx < 0:
            return None
        layer_id = self.propertyLayerCombo.itemData(idx)
        return QgsProject.instance().mapLayer(layer_id)

    def propertyYearField(self):
        return self.propertyYearFieldCombo.currentText()

    def propertyKNeighbors(self):
        return self.kNeighborsSpin.value()

    def propertySampleFractions(self):
        text = self.sampleFractionsEdit.text().strip()
        if not text:
            return [0.0, 0.5, 1.0]
        try:
            return [float(x) for x in text.split(",") if x.strip() != ""]
        except Exception:
            return [0.0, 0.5, 1.0]

    def _validate_inputs(self):
        try:
            ok_button = self.mButtonBox.button(
                QDialogButtonBox.StandardButton.Ok
            )
        except AttributeError:
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
                error_messages.append(
                    self.tr("{0}: No layer selected.").format(tab['name'])
                )
                continue
            if not tab['mat_combo'].currentField():
                error_messages.append(
                    self.tr("{0}: Material field is missing.").format(tab['name'])
                )
            if not tab['year_combo'].currentField():
                error_messages.append(
                    self.tr("{0}: Year field is missing.").format(tab['name'])
                )
            else:
                year_field_name = tab['year_combo'].currentField()
                if not layer.fields().field(year_field_name).isNumeric():
                    error_messages.append(
                        self.tr("{0}: Year field must be numeric.").format(tab['name'])
                    )
            if not tab['dim_combo'].currentField():
                error_messages.append(
                    self.tr("{0}: Dimension field is missing.").format(tab['name'])
                )
        if not is_at_least_one_tab_active:
            error_messages.append(
                self.tr("Select at least one pipe type to analyze.")
            )
        if self.useTemporalAnalysis():
            if self.temporalStartYear() >= self.temporalEndYear():
                error_messages.append(
                    self.tr("Temporal Analysis: End year must be after start year.")
                )
        if error_messages:
            ok_button.setEnabled(False)
            self.mStatusLabel.setText(self.tr("Error: ") + " | ".join(error_messages))
            self.mStatusLabel.setStyleSheet("color: red;")
        else:
            ok_button.setEnabled(True)
            self.mStatusLabel.setText(self.tr("Status: Ready to run analysis."))
            self.mStatusLabel.setStyleSheet("color: green;")

    def save_settings(self):
        project = QgsProject.instance()
        project.writeEntry(
            'reneW', 'municipalityFilter',
            self.mMunicipalityFilterCombo.currentText()
        )
        for tab in self.tabs:
            prefix = f"tab_{tab['name']}"
            project.writeEntryBool('reneW', f'{prefix}_enabled',
                                   tab['check'].isChecked())
            if tab['layer_combo'].currentLayer():
                project.writeEntry('reneW', f'{prefix}_layer',
                                   tab['layer_combo'].currentLayer().id())
            project.writeEntry('reneW', f'{prefix}_municipalityField',
                               tab['muni_combo'].currentField())
            project.writeEntry('reneW', f'{prefix}_materialField',
                               tab['mat_combo'].currentField())
            project.writeEntry('reneW', f'{prefix}_yearField',
                               tab['year_combo'].currentField())
            project.writeEntry('reneW', f'{prefix}_dimensionField',
                               tab['dim_combo'].currentField())
            project.writeEntry('reneW', f'{prefix}_renoYearField',
                               tab['reno_year_combo'].currentField())
            project.writeEntry('reneW', f'{prefix}_renoMethodField',
                               tab['reno_method_combo'].currentField())
        project.writeEntryBool('reneW', 'dimensionWeightingEnabled',
                               self.useDimensionWeighting())
        project.writeEntryDouble('reneW', 'dimensionFactor',
                                 self.dimensionFactor())
        project.writeEntryBool('reneW', 'hotspotAnalysisEnabled',
                               self.useHotspotAnalysis())
        project.writeEntryDouble('reneW', 'hotspotThreshold',
                                 self.hotspotThreshold())
        project.writeEntry('reneW', 'hotspotRadius', self.hotspotRadius())
        project.writeEntryBool('reneW', 'temporalAnalysisEnabled',
                               self.useTemporalAnalysis())
        project.writeEntry('reneW', 'temporalStartYear',
                           self.temporalStartYear())
        project.writeEntry('reneW', 'temporalEndYear', self.temporalEndYear())
        project.writeEntry('reneW', 'temporalStep', self.temporalStep())
        project.writeEntry('reneW', 'numColorClasses', self.numColorClasses())

        settings = QSettings()
        settings.setValue("reneW/water_factor",
                          self.water_factor_spinbox.value())
        settings.setValue("reneW/wastewater_factor",
                          self.wastewater_factor_spinbox.value())
        settings.setValue("reneW/stormwater_factor",
                          self.stormwater_factor_spinbox.value())
        settings.setValue("prop_layer_idx",
                          self.propertyLayerCombo.currentIndex())
        settings.setValue("prop_year_field",
                          self.propertyYearFieldCombo.currentText())
        settings.setValue("prop_k_neighbors", self.kNeighborsSpin.value())
        settings.setValue("prop_fractions", self.sampleFractionsEdit.text())

    def load_settings(self):
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
            tab['check'].setChecked(
                project.readBoolEntry('reneW', f'{prefix}_enabled', False)[0]
            )
            set_layer_if_exists(
                tab['layer_combo'], project.readEntry('reneW', f'{prefix}_layer', '')[0]
            )
            tab['muni_combo'].setField(
                project.readEntry('reneW', f'{prefix}_municipalityField', '')[0]
            )
            tab['mat_combo'].setField(
                project.readEntry('reneW', f'{prefix}_materialField', '')[0]
            )
            tab['year_combo'].setField(
                project.readEntry('reneW', f'{prefix}_yearField', '')[0]
            )
            tab['dim_combo'].setField(
                project.readEntry('reneW', f'{prefix}_dimensionField', '')[0]
            )
            tab['reno_year_combo'].setField(
                project.readEntry('reneW', f'{prefix}_renoYearField', '')[0]
            )
            tab['reno_method_combo'].setField(
                project.readEntry('reneW', f'{prefix}_renoMethodField', '')[0]
            )
        self.mCheckBoxEnableDimensionWeighting.setChecked(
            project.readBoolEntry('reneW', 'dimensionWeightingEnabled', False)[0]
        )
        self.mSpinBoxDimensionFactor.setValue(
            project.readDoubleEntry('reneW', 'dimensionFactor', 0.001)[0]
        )
        self.mCheckBoxEnableHotspot.setChecked(
            project.readBoolEntry('reneW', 'hotspotAnalysisEnabled', False)[0]
        )
        self.mSpinBoxHotspotThreshold.setValue(
            project.readDoubleEntry('reneW', 'hotspotThreshold', 0.75)[0]
        )
        self.mSpinBoxHotspotRadius.setValue(
            int(project.readEntry('reneW', 'hotspotRadius', '50')[0])
        )
        self.mTemporalGroupBox.setChecked(
            project.readBoolEntry('reneW', 'temporalAnalysisEnabled', False)[0]
        )
        self.mTemporalStartYearSpinBox.setValue(
            project.readNumEntry('reneW', 'temporalStartYear', datetime.now().year)[0]
        )
        self.mTemporalEndYearSpinBox.setValue(
            project.readNumEntry('reneW', 'temporalEndYear', datetime.now().year + 40)[0]
        )
        self.mTemporalStepSpinBox.setValue(
            project.readNumEntry('reneW', 'temporalStep', 5)[0]
        )
        self.mNumClassesSpinBox.setValue(
            project.readNumEntry('reneW', 'numColorClasses', 5)[0]
        )

        settings = QSettings()
        self.water_factor_spinbox.setValue(
            settings.value("reneW/water_factor", 1.0, type=float)
        )
        self.wastewater_factor_spinbox.setValue(
            settings.value("reneW/wastewater_factor", 1.0, type=float)
        )
        self.stormwater_factor_spinbox.setValue(
            settings.value("reneW/stormwater_factor", 1.0, type=float)
        )

        idx = int(settings.value("prop_layer_idx", -1))
        if idx >= 0 and idx < self.propertyLayerCombo.count():
            self.propertyLayerCombo.setCurrentIndex(idx)

        self._updatePropertyFields()

        field = settings.value("prop_year_field", "")
        if field and self.propertyYearFieldCombo.findText(field) != -1:
            self.propertyYearFieldCombo.setCurrentText(field)
        self.kNeighborsSpin.setValue(
            int(settings.value("prop_k_neighbors", 15))
        )
        self.sampleFractionsEdit.setText(
            settings.value("prop_fractions", "0,0.25,0.5,0.75,1")
        )
