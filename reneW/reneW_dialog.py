import os
from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDialog
from qgis.core import QgsMapLayerProxyModel, QgsProject

# This loads your .ui file
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'reneW_dialog_base.ui'))

class ReneWDialog(QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(ReneWDialog, self).__init__(parent)
        self.setupUi(self)

        # --- Global Settings ---
        self.mCheckBoxEnableDimensionWeighting.toggled.connect(self.mSpinBoxDimensionFactor.setEnabled)

        # --- Tab 1: Risk Calculation (Single Layer) ---
        self.mMapLayerCombo.setFilters(QgsMapLayerProxyModel.VectorLayer)
        self.mMapLayerCombo.layerChanged.connect(self.mFieldComboMaterial.setLayer)
        self.mMapLayerCombo.layerChanged.connect(self.mFieldComboYear.setLayer)
        self.mMapLayerCombo.layerChanged.connect(self.mFieldComboDimension.setLayer)
        self.mMapLayerCombo.layerChanged.connect(self.mFieldComboRenoYear.setLayer)
        self.mMapLayerCombo.layerChanged.connect(self.mFieldComboRenoMethod.setLayer)

        # --- Tab 2: Samordning & Hotspots ---
        # Filters
        self.mMapLayerComboVattenHotspot.setFilters(QgsMapLayerProxyModel.VectorLayer)
        self.mMapLayerComboSpillHotspot.setFilters(QgsMapLayerProxyModel.VectorLayer)
        self.mMapLayerComboDagHotspot.setFilters(QgsMapLayerProxyModel.VectorLayer)

        # Hotspot Checkbox logic
        if hasattr(self, 'mCheckHotspot'):
             self.mCheckHotspot.toggled.connect(self.mSpinBoxHotspotThreshold.setEnabled)
             self.mCheckHotspot.toggled.connect(self.mSpinBoxHotspotDistance.setEnabled)
             self.mSpinBoxHotspotThreshold.setEnabled(False)
             self.mSpinBoxHotspotDistance.setEnabled(False)

        # --- Tab 3: Cost Parameters ---
        self.mCheckTrenchBox.toggled.connect(self._toggle_trench_box)

    def _toggle_trench_box(self, checked):
        # If trench box is used, slope implies vertical walls (0 slope or undefined, but typically width is constant)
        # Here we can disable slope or set it to 0.
        self.mSpinBoxSlope.setEnabled(not checked)
        if checked:
             self.mSpinBoxSlope.setValue(0.0)

    # --- Getter methods for global settings ---
    def useDimensionWeighting(self) -> bool:
        return self.mCheckBoxEnableDimensionWeighting.isChecked()

    def dimensionFactor(self) -> float:
        return self.mSpinBoxDimensionFactor.value()

    # --- Cost Parameter Getters ---
    def getStandardDepth(self) -> float:
        return self.mSpinBoxStandardDepth.value()

    def getSlope(self) -> float:
        return self.mSpinBoxSlope.value()

    def useTrenchBox(self) -> bool:
        return self.mCheckTrenchBox.isChecked()

    def includeAsphalt(self) -> bool:
        return self.mCheckAsphalt.isChecked()

    def getExcavationPrice(self) -> float:
        return self.mSpinBoxExcavationPrice.value()

    # --- Getter for Risk Calculation (Tab 1) ---
    def get_analysis_configs(self) -> list:
        """
        Returns a list containing the single configuration for the selected layer,
        PLUS the cost parameters merged into the config dictionary.
        """
        configs = []

        current_layer = self.mMapLayerCombo.currentLayer()
        if current_layer:
            configs.append({
                'type': self.mComboSystemType.currentText(),
                'layer': current_layer,
                'material_field': self.mFieldComboMaterial.currentField(),
                'year_field': self.mFieldComboYear.currentField(),
                'dimension_field': self.mFieldComboDimension.currentField(),
                'reno_year_field': self.mFieldComboRenoYear.currentField(),
                'reno_method_field': self.mFieldComboRenoMethod.currentField(),

                # Cost Parameters
                'cost_depth': self.getStandardDepth(),
                'cost_slope': self.getSlope(),
                'cost_trench_box': self.useTrenchBox(),
                'cost_include_asphalt': self.includeAsphalt(),
                'cost_excavation_price': self.getExcavationPrice()
            })

        return configs

    # --- Getter for Hotspot Layers (Tab 2) ---
    def get_hotspot_layers(self) -> dict:
        """
        Returns a dictionary of selected layers for coordination analysis.
        """
        return {
            'Vatten': self.mMapLayerComboVattenHotspot.currentLayer(),
            'Spillvatten': self.mMapLayerComboSpillHotspot.currentLayer(),
            'Dagvatten': self.mMapLayerComboDagHotspot.currentLayer()
        }

    # --- Getter methods for hotspot settings ---
    def isHotspotAnalysisEnabled(self) -> bool:
        # If checkbox exists, use it. Else assume enabled if user clicks the button.
        if hasattr(self, 'mCheckHotspot'):
            return self.mCheckHotspot.isChecked()
        return True

    def getHotspotThreshold(self) -> float:
        return self.mSpinBoxHotspotThreshold.value()

    def getHotspotDistance(self) -> float:
        return self.mSpinBoxHotspotDistance.value()

    def save_settings(self):
        """Saves the dialog's settings to the current QGIS project."""
        project = QgsProject.instance()

        # Tab 1
        project.writeEntry('reneW', 'systemType', self.mComboSystemType.currentText())
        if self.mMapLayerCombo.currentLayer():
            project.writeEntry('reneW', 'selectedLayer', self.mMapLayerCombo.currentLayer().id())
        project.writeEntry('reneW', 'materialField', self.mFieldComboMaterial.currentField())
        project.writeEntry('reneW', 'yearField', self.mFieldComboYear.currentField())
        project.writeEntry('reneW', 'dimensionField', self.mFieldComboDimension.currentField())
        project.writeEntry('reneW', 'renoYearField', self.mFieldComboRenoYear.currentField())
        project.writeEntry('reneW', 'renoMethodField', self.mFieldComboRenoMethod.currentField())

        project.writeEntry('reneW', 'dimensionWeightingEnabled', self.useDimensionWeighting())
        project.writeEntryDouble('reneW', 'dimensionFactor', self.dimensionFactor())

        # Tab 3 Cost
        project.writeEntryDouble('reneW', 'costStandardDepth', self.getStandardDepth())
        project.writeEntryDouble('reneW', 'costSlope', self.getSlope())
        project.writeEntry('reneW', 'costTrenchBox', self.useTrenchBox())
        project.writeEntry('reneW', 'costIncludeAsphalt', self.includeAsphalt())
        project.writeEntryDouble('reneW', 'costExcavationPrice', self.getExcavationPrice())

        # Tab 2
        if self.mMapLayerComboVattenHotspot.currentLayer():
            project.writeEntry('reneW', 'hotspotLayerVatten', self.mMapLayerComboVattenHotspot.currentLayer().id())
        if self.mMapLayerComboSpillHotspot.currentLayer():
            project.writeEntry('reneW', 'hotspotLayerSpill', self.mMapLayerComboSpillHotspot.currentLayer().id())
        if self.mMapLayerComboDagHotspot.currentLayer():
            project.writeEntry('reneW', 'hotspotLayerDag', self.mMapLayerComboDagHotspot.currentLayer().id())

        if hasattr(self, 'mCheckHotspot'):
            project.writeEntry('reneW', 'hotspotEnabled', self.isHotspotAnalysisEnabled())

        project.writeEntryDouble('reneW', 'hotspotThreshold', self.getHotspotThreshold())
        project.writeEntryDouble('reneW', 'hotspotDistance', self.getHotspotDistance())

    def load_settings(self):
        """Loads the dialog's settings from the current QGIS project."""
        project = QgsProject.instance()

        # Tab 1
        system_type = project.readEntry('reneW', 'systemType', 'Vatten')[0]
        index = self.mComboSystemType.findText(system_type)
        if index >= 0:
            self.mComboSystemType.setCurrentIndex(index)

        layer_id = project.readEntry('reneW', 'selectedLayer', '')[0]
        if layer_id:
            layer = QgsProject.instance().mapLayer(layer_id)
            if layer:
                self.mMapLayerCombo.setLayer(layer)

        self.mFieldComboMaterial.setField(project.readEntry('reneW', 'materialField', '')[0])
        self.mFieldComboYear.setField(project.readEntry('reneW', 'yearField', '')[0])
        self.mFieldComboDimension.setField(project.readEntry('reneW', 'dimensionField', '')[0])
        self.mFieldComboRenoYear.setField(project.readEntry('reneW', 'renoYearField', '')[0])
        self.mFieldComboRenoMethod.setField(project.readEntry('reneW', 'renoMethodField', '')[0])

        self.mCheckBoxEnableDimensionWeighting.setChecked(project.readBoolEntry('reneW', 'dimensionWeightingEnabled', False)[0])
        self.mSpinBoxDimensionFactor.setValue(project.readDoubleEntry('reneW', 'dimensionFactor', 0.001)[0])

        # Tab 3 Cost
        self.mSpinBoxStandardDepth.setValue(project.readDoubleEntry('reneW', 'costStandardDepth', 2.5)[0])
        self.mSpinBoxSlope.setValue(project.readDoubleEntry('reneW', 'costSlope', 1.0)[0])
        self.mCheckTrenchBox.setChecked(project.readBoolEntry('reneW', 'costTrenchBox', False)[0])
        self.mCheckAsphalt.setChecked(project.readBoolEntry('reneW', 'costIncludeAsphalt', True)[0])
        self.mSpinBoxExcavationPrice.setValue(project.readDoubleEntry('reneW', 'costExcavationPrice', 350.0)[0])

        # Tab 2
        def set_layer(combo, key):
            lid = project.readEntry('reneW', key, '')[0]
            if lid:
                l = QgsProject.instance().mapLayer(lid)
                if l: combo.setLayer(l)

        set_layer(self.mMapLayerComboVattenHotspot, 'hotspotLayerVatten')
        set_layer(self.mMapLayerComboSpillHotspot, 'hotspotLayerSpill')
        set_layer(self.mMapLayerComboDagHotspot, 'hotspotLayerDag')

        if hasattr(self, 'mCheckHotspot'):
            self.mCheckHotspot.setChecked(project.readBoolEntry('reneW', 'hotspotEnabled', False)[0])

        self.mSpinBoxHotspotThreshold.setValue(project.readDoubleEntry('reneW', 'hotspotThreshold', 0.5)[0])
        self.mSpinBoxHotspotDistance.setValue(project.readDoubleEntry('reneW', 'hotspotDistance', 5.0)[0])
