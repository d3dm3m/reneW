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

        # --- Single Layer Configuration ---
        self.mMapLayerCombo.setFilters(QgsMapLayerProxyModel.VectorLayer)
        self.mMapLayerCombo.layerChanged.connect(self.mFieldComboMaterial.setLayer)
        self.mMapLayerCombo.layerChanged.connect(self.mFieldComboYear.setLayer)
        self.mMapLayerCombo.layerChanged.connect(self.mFieldComboDimension.setLayer)
        self.mMapLayerCombo.layerChanged.connect(self.mFieldComboRenoYear.setLayer)
        self.mMapLayerCombo.layerChanged.connect(self.mFieldComboRenoMethod.setLayer)

        # --- Hotspot Analysis Settings ---
        self.mCheckHotspot.toggled.connect(self.mSpinBoxHotspotThreshold.setEnabled)
        self.mCheckHotspot.toggled.connect(self.mSpinBoxHotspotDistance.setEnabled)
        self.mSpinBoxHotspotThreshold.setEnabled(False)
        self.mSpinBoxHotspotDistance.setEnabled(False)


    # --- Getter methods for global settings ---
    def useDimensionWeighting(self) -> bool:
        return self.mCheckBoxEnableDimensionWeighting.isChecked()

    def dimensionFactor(self) -> float:
        return self.mSpinBoxDimensionFactor.value()

    # --- Getter for selected configuration ---
    def get_analysis_configs(self) -> list:
        """
        Returns a list containing the single configuration for the selected layer.
        The structure matches the previous list-based return for compatibility.
        """
        configs = []

        # Ensure a layer is selected
        current_layer = self.mMapLayerCombo.currentLayer()
        if current_layer:
            configs.append({
                'type': self.mComboSystemType.currentText(), # "Vatten", "Spillvatten", "Dagvatten"
                'layer': current_layer,
                'material_field': self.mFieldComboMaterial.currentField(),
                'year_field': self.mFieldComboYear.currentField(),
                'dimension_field': self.mFieldComboDimension.currentField(),
                'reno_year_field': self.mFieldComboRenoYear.currentField(),
                'reno_method_field': self.mFieldComboRenoMethod.currentField()
            })

        return configs

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

        # System Type
        project.writeEntry('reneW', 'systemType', self.mComboSystemType.currentText())

        # Layer & Fields
        if self.mMapLayerCombo.currentLayer():
            project.writeEntry('reneW', 'selectedLayer', self.mMapLayerCombo.currentLayer().id())
        project.writeEntry('reneW', 'materialField', self.mFieldComboMaterial.currentField())
        project.writeEntry('reneW', 'yearField', self.mFieldComboYear.currentField())
        project.writeEntry('reneW', 'dimensionField', self.mFieldComboDimension.currentField())
        project.writeEntry('reneW', 'renoYearField', self.mFieldComboRenoYear.currentField())
        project.writeEntry('reneW', 'renoMethodField', self.mFieldComboRenoMethod.currentField())

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

        # System Type
        system_type = project.readEntry('reneW', 'systemType', 'Vatten')[0]
        index = self.mComboSystemType.findText(system_type)
        if index >= 0:
            self.mComboSystemType.setCurrentIndex(index)

        # Layer & Fields
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

        # Global settings
        self.mCheckBoxEnableDimensionWeighting.setChecked(project.readBoolEntry('reneW', 'dimensionWeightingEnabled', False)[0])
        self.mSpinBoxDimensionFactor.setValue(project.readDoubleEntry('reneW', 'dimensionFactor', 0.001)[0])

        # Hotspot settings
        self.mCheckHotspot.setChecked(project.readBoolEntry('reneW', 'hotspotEnabled', False)[0])
        self.mSpinBoxHotspotThreshold.setValue(project.readDoubleEntry('reneW', 'hotspotThreshold', 0.5)[0])
        self.mSpinBoxHotspotDistance.setValue(project.readDoubleEntry('reneW', 'hotspotDistance', 5.0)[0])
