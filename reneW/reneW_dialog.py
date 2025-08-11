import os
from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDialog
from qgis.core import QgsMapLayerProxyModel

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'reneW_dialog_base.ui'))


class ReneWDialog(QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(ReneWDialog, self).__init__(parent)
        self.setupUi(self)

        self.mMapLayerComboBox.setFilters(QgsMapLayerProxyModel.VectorLayer)
        self.mMapLayerComboBox.layerChanged.connect(self.mFieldComboBox_material.setLayer)
        self.mMapLayerComboBox.layerChanged.connect(self.mFieldComboBox_year.setLayer)
        self.mMapLayerComboBox.layerChanged.connect(self.mFieldComboBox_dimension.setLayer)

        # Connect checkbox to enable/disable spinbox
        self.mCheckBoxEnableDimensionWeighting.toggled.connect(self.mSpinBoxDimensionFactor.setEnabled)

    def useDimensionWeighting(self) -> bool:
        """Returns True if dimension weighting is enabled."""
        return self.mCheckBoxEnableDimensionWeighting.isChecked()

    def dimensionFactor(self) -> float:
        """Returns the value of the dimension weighting factor."""
        return self.mSpinBoxDimensionFactor.value()

    def selectedLayer(self):
        """Returns the selected layer."""
        return self.mMapLayerComboBox.currentLayer()

    def materialField(self):
        """Returns the selected material field."""
        return self.mFieldComboBox_material.currentField()

    def yearField(self):
        """Returns the selected year field."""
        return self.mFieldComboBox_year.currentField()

    def dimensionField(self):
        """Returns the selected dimension field."""
        return self.mFieldComboBox_dimension.currentField()

    def pipelineType(self) -> str:
        """Returns the selected pipeline type."""
        return self.mComboBoxPipeType.currentText()
