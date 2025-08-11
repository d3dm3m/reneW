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

        # --- Vatten Tab ---
        self.mCheckVatten.toggled.connect(self.mGroupVatten.setEnabled)
        self.mMapLayerComboVatten.setFilters(QgsMapLayerProxyModel.VectorLayer)
        self.mMapLayerComboVatten.layerChanged.connect(self.mFieldComboMaterialVatten.setLayer)
        self.mMapLayerComboVatten.layerChanged.connect(self.mFieldComboYearVatten.setLayer)
        self.mMapLayerComboVatten.layerChanged.connect(self.mFieldComboDimensionVatten.setLayer)
        self.mMapLayerComboVatten.layerChanged.connect(self.mFieldComboRenoYearVatten.setLayer)
        self.mMapLayerComboVatten.layerChanged.connect(self.mFieldComboRenoMethodVatten.setLayer)
        self.mGroupVatten.setEnabled(False)

        # --- Spillvatten Tab ---
        self.mCheckSpillvatten.toggled.connect(self.mGroupSpillvatten.setEnabled)
        self.mMapLayerComboSpillvatten.setFilters(QgsMapLayerProxyModel.VectorLayer)
        self.mMapLayerComboSpillvatten.layerChanged.connect(self.mFieldComboMaterialSpillvatten.setLayer)
        self.mMapLayerComboSpillvatten.layerChanged.connect(self.mFieldComboYearSpillvatten.setLayer)
        self.mMapLayerComboSpillvatten.layerChanged.connect(self.mFieldComboDimensionSpillvatten.setLayer)
        self.mMapLayerComboSpillvatten.layerChanged.connect(self.mFieldComboRenoYearSpillvatten.setLayer)
        self.mMapLayerComboSpillvatten.layerChanged.connect(self.mFieldComboRenoMethodSpillvatten.setLayer)
        self.mGroupSpillvatten.setEnabled(False)

        # --- Dagvatten Tab ---
        self.mCheckDagvatten.toggled.connect(self.mGroupDagvatten.setEnabled)
        self.mMapLayerComboDagvatten.setFilters(QgsMapLayerProxyModel.VectorLayer)
        self.mMapLayerComboDagvatten.layerChanged.connect(self.mFieldComboMaterialDagvatten.setLayer)
        self.mMapLayerComboDagvatten.layerChanged.connect(self.mFieldComboYearDagvatten.setLayer)
        self.mMapLayerComboDagvatten.layerChanged.connect(self.mFieldComboDimensionDagvatten.setLayer)
        self.mMapLayerComboDagvatten.layerChanged.connect(self.mFieldComboRenoYearDagvatten.setLayer)
        self.mMapLayerComboDagvatten.layerChanged.connect(self.mFieldComboRenoMethodDagvatten.setLayer)
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
                'dimension_field': self.mFieldComboDimensionVatten.currentField(),
                'reno_year_field': self.mFieldComboRenoYearVatten.currentField(),
                'reno_method_field': self.mFieldComboRenoMethodVatten.currentField()
            })

        # Spillvatten
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

        # Dagvatten
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

    def save_settings(self):
        """Saves the dialog's settings to the current QGIS project."""
        project = QgsProject.instance()

        # Tab settings
        project.writeEntry('reneW', 'vattenEnabled', self.mCheckVatten.isChecked())
        if self.mMapLayerComboVatten.currentLayer():
            project.writeEntry('reneW', 'vattenLayer', self.mMapLayerComboVatten.currentLayer().id())
        project.writeEntry('reneW', 'vattenMaterialField', self.mFieldComboMaterialVatten.currentField())
        project.writeEntry('reneW', 'vattenYearField', self.mFieldComboYearVatten.currentField())
        project.writeEntry('reneW', 'vattenDimensionField', self.mFieldComboDimensionVatten.currentField())
        project.writeEntry('reneW', 'vattenRenoYearField', self.mFieldComboRenoYearVatten.currentField())
        project.writeEntry('reneW', 'vattenRenoMethodField', self.mFieldComboRenoMethodVatten.currentField())

        project.writeEntry('reneW', 'spillvattenEnabled', self.mCheckSpillvatten.isChecked())
        if self.mMapLayerComboSpillvatten.currentLayer():
            project.writeEntry('reneW', 'spillvattenLayer', self.mMapLayerComboSpillvatten.currentLayer().id())
        project.writeEntry('reneW', 'spillvattenMaterialField', self.mFieldComboMaterialSpillvatten.currentField())
        project.writeEntry('reneW', 'spillvattenYearField', self.mFieldComboYearSpillvatten.currentField())
        project.writeEntry('reneW', 'spillvattenDimensionField', self.mFieldComboDimensionSpillvatten.currentField())
        project.writeEntry('reneW', 'spillvattenRenoYearField', self.mFieldComboRenoYearSpillvatten.currentField())
        project.writeEntry('reneW', 'spillvattenRenoMethodField', self.mFieldComboRenoMethodSpillvatten.currentField())

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

        # Helper to find a layer by ID and set it
        def set_layer_if_exists(combo, layer_id):
            if layer_id:
                layer = QgsProject.instance().mapLayer(layer_id)
                if layer:
                    combo.setLayer(layer)

        # Vatten
        self.mCheckVatten.setChecked(project.readBoolEntry('reneW', 'vattenEnabled', False))
        vatten_layer_id = project.readEntry('reneW', 'vattenLayer', '')
        set_layer_if_exists(self.mMapLayerComboVatten, vatten_layer_id)
        self.mFieldComboMaterialVatten.setField(project.readEntry('reneW', 'vattenMaterialField', ''))
        self.mFieldComboYearVatten.setField(project.readEntry('reneW', 'vattenYearField', ''))
        self.mFieldComboDimensionVatten.setField(project.readEntry('reneW', 'vattenDimensionField', ''))
        self.mFieldComboRenoYearVatten.setField(project.readEntry('reneW', 'vattenRenoYearField', ''))
        self.mFieldComboRenoMethodVatten.setField(project.readEntry('reneW', 'vattenRenoMethodField', ''))

        # Spillvatten
        self.mCheckSpillvatten.setChecked(project.readBoolEntry('reneW', 'spillvattenEnabled', False))
        spillvatten_layer_id = project.readEntry('reneW', 'spillvattenLayer', '')
        set_layer_if_exists(self.mMapLayerComboSpillvatten, spillvatten_layer_id)
        self.mFieldComboMaterialSpillvatten.setField(project.readEntry('reneW', 'spillvattenMaterialField', ''))
        self.mFieldComboYearSpillvatten.setField(project.readEntry('reneW', 'spillvattenYearField', ''))
        self.mFieldComboDimensionSpillvatten.setField(project.readEntry('reneW', 'spillvattenDimensionField', ''))
        self.mFieldComboRenoYearSpillvatten.setField(project.readEntry('reneW', 'spillvattenRenoYearField', ''))
        self.mFieldComboRenoMethodSpillvatten.setField(project.readEntry('reneW', 'spillvattenRenoMethodField', ''))

        # Dagvatten
        self.mCheckDagvatten.setChecked(project.readBoolEntry('reneW', 'dagvattenEnabled', False))
        dagvatten_layer_id = project.readEntry('reneW', 'dagvattenLayer', '')
        set_layer_if_exists(self.mMapLayerComboDagvatten, dagvatten_layer_id)
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
