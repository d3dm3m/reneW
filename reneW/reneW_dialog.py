import os
from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDialog
from qgis.core import QgsMapLayerProxyModel

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

        # --- Vatten Tab ---
        self.mCheckVatten.toggled.connect(self.mGroupVatten.setEnabled)
        self.mMapLayerComboVatten.setFilters(QgsMapLayerProxyModel.VectorLayer)
        self.mMapLayerComboVatten.layerChanged.connect(self.mFieldComboMaterialVatten.setLayer)
        self.mMapLayerComboVatten.layerChanged.connect(self.mFieldComboYearVatten.setLayer)
        self.mMapLayerComboVatten.layerChanged.connect(self.mFieldComboDimensionVatten.setLayer)
        self.mGroupVatten.setEnabled(False)

        # --- Spillvatten Tab ---
        self.mCheckSpillvatten.toggled.connect(self.mGroupSpillvatten.setEnabled)
        self.mMapLayerComboSpillvatten.setFilters(QgsMapLayerProxyModel.VectorLayer)
        self.mMapLayerComboSpillvatten.layerChanged.connect(self.mFieldComboMaterialSpillvatten.setLayer)
        self.mMapLayerComboSpillvatten.layerChanged.connect(self.mFieldComboYearSpillvatten.setLayer)
        self.mMapLayerComboSpillvatten.layerChanged.connect(self.mFieldComboDimensionSpillvatten.setLayer)
        self.mGroupSpillvatten.setEnabled(False)

        # --- Dagvatten Tab ---
        self.mCheckDagvatten.toggled.connect(self.mGroupDagvatten.setEnabled)
        self.mMapLayerComboDagvatten.setFilters(QgsMapLayerProxyModel.VectorLayer)
        self.mMapLayerComboDagvatten.layerChanged.connect(self.mFieldComboMaterialDagvatten.setLayer)
        self.mMapLayerComboDagvatten.layerChanged.connect(self.mFieldComboYearDagvatten.setLayer)
        self.mMapLayerComboDagvatten.layerChanged.connect(self.mFieldComboDimensionDagvatten.setLayer)
        self.mGroupDagvatten.setEnabled(False)

        # --- Hotspot Analysis Settings ---
        # The groupbox itself is not checkable, so we connect the checkbox to the controls inside
        self.mCheckHotspot.toggled.connect(self.mSpinBoxHotspotThreshold.setEnabled)
        self.mCheckHotspot.toggled.connect(self.mSpinBoxHotspotDistance.setEnabled)
        self.mSpinBoxHotspotThreshold.setEnabled(False)
        self.mSpinBoxHotspotDistance.setEnabled(False)


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

        # Vatten
        if self.mCheckVatten.isChecked() and self.mMapLayerComboVatten.currentLayer():
            configs.append({
                'type': 'Vatten',
                'layer': self.mMapLayerComboVatten.currentLayer(),
                'material_field': self.mFieldComboMaterialVatten.currentField(),
                'year_field': self.mFieldComboYearVatten.currentField(),
                'dimension_field': self.mFieldComboDimensionVatten.currentField()
            })

        # Spillvatten
        if self.mCheckSpillvatten.isChecked() and self.mMapLayerComboSpillvatten.currentLayer():
            configs.append({
                'type': 'Spillvatten',
                'layer': self.mMapLayerComboSpillvatten.currentLayer(),
                'material_field': self.mFieldComboMaterialSpillvatten.currentField(),
                'year_field': self.mFieldComboYearSpillvatten.currentField(),
                'dimension_field': self.mFieldComboDimensionSpillvatten.currentField()
            })

        # Dagvatten
        if self.mCheckDagvatten.isChecked() and self.mMapLayerComboDagvatten.currentLayer():
            configs.append({
                'type': 'Dagvatten',
                'layer': self.mMapLayerComboDagvatten.currentLayer(),
                'material_field': self.mFieldComboMaterialDagvatten.currentField(),
                'year_field': self.mFieldComboYearDagvatten.currentField(),
                'dimension_field': self.mFieldComboDimensionDagvatten.currentField()
            })

        return configs

    # --- Getter methods for hotspot settings ---
    def isHotspotAnalysisEnabled(self) -> bool:
        """Returns True if hotspot analysis is enabled."""
        return self.mCheckHotspot.isChecked()

    def getHotspotThreshold(self) -> float:
        """Returns the renewal need threshold for hotspot analysis."""
        return self.mSpinBoxHotspotThreshold.value()

    def getHotspotDistance(self) -> float:
        """Returns the buffer distance for hotspot analysis."""
        return self.mSpinBoxHotspotDistance.value()
