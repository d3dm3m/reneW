from qgis.PyQt.QtWidgets import QDialog, QTableWidgetItem, QHeaderView
from qgis.PyQt import uic
import os
from . import intervention_logic


FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'hotspot_explorer_dialog.ui'))


class HotspotExplorerDialog(QDialog, FORM_CLASS):
    def __init__(self, parent=None, iface=None):
        super(HotspotExplorerDialog, self).__init__(parent)
        self.setupUi(self)
        self.iface = iface
        self.layer = None
        self.pipe_layer = None
        self.contributing_pipes = []

        self.btnZoomToHotspot.clicked.connect(self.zoom_to_hotspot)
        self.btnZoomToPipe.clicked.connect(self.zoom_to_pipe)
        self.btnSelectPipes.clicked.connect(self.select_contributing_pipes)
        self.tableWidget.itemSelectionChanged.connect(
            self.on_pipe_selection_changed
        )

    def setLayer(self, layer):
        self.layer = layer

    def setPipeLayer(self, pipe_layer):
        self.pipe_layer = pipe_layer

    def setContributingPipes(self, pipe_ids):
        self.contributing_pipes = pipe_ids

    def populate(self, hotspot_id, pipe_ids_str, materials, length_km,
                 pipe_count, avg_need, avg_age, imputed_count):
        self.lblHotspotId.setText(f"Hotspot ID: {hotspot_id}")
        self.lblPipeCount.setText(f"Pipe Count: {pipe_count}")
        self.lblTotalLength.setText(f"Total Length: {length_km:.2f} km")
        self.lblAvgNeed.setText(f"Average Renewal Need: {avg_need:.2f}")
        self.lblAvgAge.setText(f"Average Age: {avg_age:.1f} years")

        imputed_warning = "⚠️ Contains imputed years" if imputed_count > 0 else ""
        self.lblImputedCount.setText(
            f"Imputed Years: {imputed_count} {imputed_warning}"
        )

        self.lblMaterials.setText(f"Materials: {materials}")

        intervention = intervention_logic.suggest_intervention_for_hotspot(
            avg_need, materials
        )
        self.lblSuggestedIntervention.setText(
            f"Suggested Intervention: {intervention}"
        )

        self.tableWidget.setRowCount(0)
        if not self.pipe_layer:
            return

        header = self.tableWidget.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)

        pipe_ids = [int(pid) for pid in pipe_ids_str.split(',') if pid.strip().isdigit()]
        for i, pid in enumerate(pipe_ids):
            pipe_feature = self.pipe_layer.getFeature(pid)
            self.tableWidget.insertRow(i)
            self.tableWidget.setItem(
                i, 0, QTableWidgetItem(str(pipe_feature.id()))
            )
            self.tableWidget.setItem(
                i, 1, QTableWidgetItem(str(pipe_feature['material']))
            )
            self.tableWidget.setItem(
                i, 2, QTableWidgetItem(f"{pipe_feature['renewal_need']:.2f}")
            )

        self.btnZoomToPipe.setEnabled(False)

    def on_pipe_selection_changed(self):
        self.btnZoomToPipe.setEnabled(len(self.tableWidget.selectedItems()) > 0)

    def zoom_to_hotspot(self):
        if self.layer and self.lblHotspotId.text():
            hotspot_id = int(self.lblHotspotId.text().split(':')[-1].strip())
            self.layer.selectByIds([hotspot_id])
            self.iface.mapCanvas().zoomToSelected(self.layer)

    def zoom_to_pipe(self):
        selected = self.tableWidget.selectedItems()
        if not selected or not self.pipe_layer:
            return

        pipe_id = int(selected[0].text())
        self.pipe_layer.selectByIds([pipe_id])
        self.iface.mapCanvas().zoomToSelected(self.pipe_layer)

    def select_contributing_pipes(self):
        if self.pipe_layer and self.contributing_pipes:
            self.pipe_layer.selectByIds(self.contributing_pipes)
            self.iface.mapCanvas().zoomToSelected(self.pipe_layer)
