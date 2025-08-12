import os
from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDialog, QDialogButtonBox
from qgis.PyQt.QtCore import QVariant
from qgis.core import QgsMapLayerProxyModel, QgsProject, QgsVectorLayer

# This loads your .ui file
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'reneW_dialog_base.ui'))

class ReneWDialog(QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(ReneWDialog, self).__init__(parent)
        self.setupUi(self)

        # --- Tab Configurations ---
        self.tabs = [
            {
                'name': 'Vatten',
                'check': self.mCheckVatten,
                'group': self.mGroupVatten,
                'layer_combo': self.mMapLayerComboVatten,
                'mat_combo': self.mFieldComboMaterialVatten,
                'year_combo': self.mFieldComboYearVatten,
                'dim_combo': self.mFieldComboDimensionVatten,
            },
            {
                'name': 'Spillvatten',
                'check': self.mCheckSpillvatten,
                'group': self.mGroupSpillvatten,
                'layer_combo': self.mMapLayerComboSpillvatten,
                'mat_combo': self.mFieldComboMaterialSpillvatten,
                'year_combo': self.mFieldComboYearSpillvatten,
                'dim_combo': self.mFieldComboDimensionSpillvatten,
            },
            {
                'name': 'Dagvatten',
                'check': self.mCheckDagvatten,
                'group': self.mGroupDagvatten,
                'layer_combo': self.mMapLayerComboDagvatten,
                'mat_combo': self.mFieldComboMaterialDagvatten,
                'year_combo': self.mFieldComboYearDagvatten,
                'dim_combo': self.mFieldComboDimensionDagvatten,
            }
        ]

        # --- Global Settings ---
        self.mCheckBoxEnableDimensionWeighting.toggled.connect(self.mSpinBoxDimensionFactor.setEnabled)

        # --- Setup each tab ---
        for tab in self.tabs:
            tab['check'].toggled.connect(tab['group'].setEnabled)
            tab['layer_combo'].setFilters(QgsMapLayerProxyModel.VectorLayer)
            tab['layer_combo'].layerChanged.connect(tab['mat_combo'].setLayer)
            tab['layer_combo'].layerChanged.connect(tab['year_combo'].setLayer)
            tab['layer_combo'].layerChanged.connect(tab['dim_combo'].setLayer)
            # Connect validation signals
            tab['check'].toggled.connect(self._validate_inputs)
            tab['layer_combo'].layerChanged.connect(self._validate_inputs)
            tab['mat_combo'].fieldChanged.connect(self._validate_inputs)
            tab['year_combo'].fieldChanged.connect(self._validate_inputs)
            tab['dim_combo'].fieldChanged.connect(self._validate_inputs)
            # Set initial state
            tab['group'].setEnabled(False)

        # --- Hotspot Analysis Settings ---
        self.mCheckHotspot.toggled.connect(self.mSpinBoxHotspotThreshold.setEnabled)
        self.mCheckHotspot.toggled.connect(self.mSpinBoxHotspotDistance.setEnabled)
        self.mSpinBoxHotspotThreshold.setEnabled(False)
        self.mSpinBoxHotspotDistance.setEnabled(False)

        # --- Set initial validation state ---
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

        if self.mCheckVatten.isChecked() and self.mMapLayerComboVatten.currentLayer():
            configs.append({
                'type': 'Vatten',
                'layer': self.mMapLayerComboVatten.currentLayer(),
                'material_field': self.mFieldComboMaterialVatten.currentField(),
                'year_field': self.mFieldComboYearVatten.currentField(),
                'dimension_field': self.mFieldComboDimensionVatten.currentField(),
                'reno_year_field': self.mFieldComboRenoYearVatten.currentField(),
                'reno_method_field': self.mFieldComboRenoMethodVatten.currentField()
            })

        if self.mCheckSpillvatten.isChecked() and self.mMapLayerComboSpillvatten.currentLayer():
            configs.append({
                'type': 'Spillvatten',
                'layer': self.mMapLayerComboSpillvatten.currentLayer(),
                'material_field': self.mFieldComboMaterialSpillvatten.currentField(),
                'year_field': self.mFieldComboYearSpillvatten.currentField(),
                'dimension_field': self.mFieldComboDimensionSpillvatten.currentField(),
                'reno_year_field': self.mFieldComboRenoYearSpillvatten.currentField(),
                'reno_method_field': self.mFieldComboRenoMethodSpillvatten.currentField()
            })

        if self.mCheckDagvatten.isChecked() and self.mMapLayerComboDagvatten.currentLayer():
            configs.append({
                'type': 'Dagvatten',
                'layer': self.mMapLayerComboDagvatten.currentLayer(),
                'material_field': self.mFieldComboMaterialDagvatten.currentField(),
                'year_field': self.mFieldComboYearDagvatten.currentField(),
                'dimension_field': self.mFieldComboDimensionDagvatten.currentField(),
                'reno_year_field': self.mFieldComboRenoYearDagvatten.currentField(),
                'reno_method_field': self.mFieldComboRenoMethodDagvatten.currentField()
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
                error_messages.append(f"{tab['name']}: Inget lager valt.")
                continue

            # Check that required fields are selected
            if not tab['mat_combo'].currentField():
                error_messages.append(f"{tab['name']}: Materialfält saknas.")
            if not tab['year_combo'].currentField():
                error_messages.append(f"{tab['name']}: Anläggningsår-fält saknas.")
            else:
                # Check that year field is numeric
                year_field_name = tab['year_combo'].currentField()
                if not layer.fields().field(year_field_name).isNumeric():
                    error_messages.append(f"{tab['name']}: Anläggningsår måste vara ett numeriskt fält.")

            if not tab['dim_combo'].currentField():
                error_messages.append(f"{tab['name']}: Dimensionsfält saknas.")
            else:
                # Check that dimension field is numeric
                dim_field_name = tab['dim_combo'].currentField()
                if not layer.fields().field(dim_field_name).isNumeric():
                    error_messages.append(f"{tab['name']}: Dimension måste vara ett numeriskt fält.")

        if not is_at_least_one_tab_active:
            error_messages.append("Välj minst en ledningstyp att analysera.")

        if error_messages:
            ok_button.setEnabled(False)
            self.mStatusLabel.setText("Fel: " + " | ".join(error_messages))
            self.mStatusLabel.setStyleSheet("color: red;")
        else:
            ok_button.setEnabled(True)
            self.mStatusLabel.setText("Status: Redo att köra analys.")
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

        # Vatten
        project.writeEntry('reneW', 'vattenEnabled', self.mCheckVatten.isChecked())
        if self.mMapLayerComboVatten.currentLayer():
            project.writeEntry('reneW', 'vattenLayer', self.mMapLayerComboVatten.currentLayer().id())
        project.writeEntry('reneW', 'vattenMaterialField', self.mFieldComboMaterialVatten.currentField())
        project.writeEntry('reneW', 'vattenYearField', self.mFieldComboYearVatten.currentField())
        project.writeEntry('reneW', 'vattenDimensionField', self.mFieldComboDimensionVatten.currentField())
        project.writeEntry('reneW', 'vattenRenoYearField', self.mFieldComboRenoYearVatten.currentField())
        project.writeEntry('reneW', 'vattenRenoMethodField', self.mFieldComboRenoMethodVatten.currentField())

        # Spillvatten
        project.writeEntry('reneW', 'spillvattenEnabled', self.mCheckSpillvatten.isChecked())
        if self.mMapLayerComboSpillvatten.currentLayer():
            project.writeEntry('reneW', 'spillvattenLayer', self.mMapLayerComboSpillvatten.currentLayer().id())
        project.writeEntry('reneW', 'spillvattenMaterialField', self.mFieldComboMaterialSpillvatten.currentField())
        project.writeEntry('reneW', 'spillvattenYearField', self.mFieldComboYearSpillvatten.currentField())
        project.writeEntry('reneW', 'spillvattenDimensionField', self.mFieldComboDimensionSpillvatten.currentField())
        project.writeEntry('reneW', 'spillvattenRenoYearField', self.mFieldComboRenoYearSpillvatten.currentField())
        project.writeEntry('reneW', 'spillvattenRenoMethodField', self.mFieldComboRenoMethodSpillvatten.currentField())

        # Dagvatten
        project.writeEntry('reneW', 'dagvattenEnabled', self.mCheckDagvatten.isChecked())
        if self.mMapLayerComboDagvatten.currentLayer():
            project.writeEntry('reneW', 'dagvattenLayer', self.mMapLayerComboDagvatten.currentLayer().id())
        project.writeEntry('reneW', 'dagvattenMaterialField', self.mFieldComboMaterialDagvatten.currentField())
        project.writeEntry('reneW', 'dagvattenYearField', self.mFieldComboYearDagvatten.currentField())
        project.writeEntry('reneW', 'dagvattenDimensionField', self.mFieldComboDimensionDagvatten.currentField())
        project.writeEntry('reneW', 'dagvattenRenoYearField', self.mFieldComboRenoYearDagvatten.currentField())
        project.writeEntry('reneW', 'dagvattenRenoMethodField', self.mFieldComboRenoMethodDagvatten.currentField())

        # Global settings
        project.writeEntry('reneW', 'dimensionWeightingEnabled', self.useDimensionWeighting())
        project.writeEntry('reneW', 'dimensionFactor', self.dimensionFactor())

        # Hotspot settings
        project.writeEntry('reneW', 'hotspotEnabled', self.isHotspotAnalysisEnabled())
        project.writeEntry('reneW', 'hotspotThreshold', self.getHotspotThreshold())
        project.writeEntry('reneW', 'hotspotDistance', self.getHotspotDistance())

    def load_settings(self):
        """Loads the dialog's settings from the current QGIS project."""
        project = QgsProject.instance()

        def set_layer_if_exists(combo, layer_id):
            if layer_id:
                layer = QgsProject.instance().mapLayer(layer_id)
                if layer:
                    combo.setLayer(layer)

        # Vatten
        self.mCheckVatten.setChecked(project.readBoolEntry('reneW', 'vattenEnabled', False))
        set_layer_if_exists(self.mMapLayerComboVatten, project.readEntry('reneW', 'vattenLayer', ''))
        self.mFieldComboMaterialVatten.setField(project.readEntry('reneW', 'vattenMaterialField', ''))
        self.mFieldComboYearVatten.setField(project.readEntry('reneW', 'vattenYearField', ''))
        self.mFieldComboDimensionVatten.setField(project.readEntry('reneW', 'vattenDimensionField', ''))
        self.mFieldComboRenoYearVatten.setField(project.readEntry('reneW', 'vattenRenoYearField', ''))
        self.mFieldComboRenoMethodVatten.setField(project.readEntry('reneW', 'vattenRenoMethodField', ''))

        # Spillvatten
        self.mCheckSpillvatten.setChecked(project.readBoolEntry('reneW', 'spillvattenEnabled', False))
        set_layer_if_exists(self.mMapLayerComboSpillvatten, project.readEntry('reneW', 'spillvattenLayer', ''))
        self.mFieldComboMaterialSpillvatten.setField(project.readEntry('reneW', 'spillvattenMaterialField', ''))
        self.mFieldComboYearSpillvatten.setField(project.readEntry('reneW', 'spillvattenYearField', ''))
        self.mFieldComboDimensionSpillvatten.setField(project.readEntry('reneW', 'spillvattenDimensionField', ''))
        self.mFieldComboRenoYearSpillvatten.setField(project.readEntry('reneW', 'spillvattenRenoYearField', ''))
        self.mFieldComboRenoMethodSpillvatten.setField(project.readEntry('reneW', 'spillvattenRenoMethodField', ''))

        # Dagvatten
        self.mCheckDagvatten.setChecked(project.readBoolEntry('reneW', 'dagvattenEnabled', False))
        set_layer_if_exists(self.mMapLayerComboDagvatten, project.readEntry('reneW', 'dagvattenLayer', ''))
        self.mFieldComboMaterialDagvatten.setField(project.readEntry('reneW', 'dagvattenMaterialField', ''))
        self.mFieldComboYearDagvatten.setField(project.readEntry('reneW', 'dagvattenYearField', ''))
        self.mFieldComboDimensionDagvatten.setField(project.readEntry('reneW', 'dagvattenDimensionField', ''))
        self.mFieldComboRenoYearDagvatten.setField(project.readEntry('reneW', 'dagvattenRenoYearField', ''))
        self.mFieldComboRenoMethodDagvatten.setField(project.readEntry('reneW', 'dagvattenRenoMethodField', ''))

        # Global settings
        self.mCheckBoxEnableDimensionWeighting.setChecked(project.readBoolEntry('reneW', 'dimensionWeightingEnabled', False))
        self.mSpinBoxDimensionFactor.setValue(project.readDoubleEntry('reneW', 'dimensionFactor', 0.001))

        # Hotspot settings
        self.mCheckHotspot.setChecked(project.readBoolEntry('reneW', 'hotspotEnabled', False))
        self.mSpinBoxHotspotThreshold.setValue(project.readDoubleEntry('reneW', 'hotspotThreshold', 0.5))
        self.mSpinBoxHotspotDistance.setValue(project.readDoubleEntry('reneW', 'hotspotDistance', 5.0))
