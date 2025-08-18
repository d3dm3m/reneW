from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QLabel, QTextEdit, QPushButton
from qgis.core import QgsProject, Qgis
from . import intervention_logic

class HotspotExplorerDialog(QDialog):
    def __init__(self, parent=None, iface=None):
        super().__init__(parent)
        self.iface = iface
        self.setWindowTitle("Hotspot Explorer")
        self.resize(400, 300)
        self.layout = QVBoxLayout(self)

        self.info_label = QLabel(self)
        self.layout.addWidget(self.info_label)

        self.details_text = QTextEdit(self)
        self.details_text.setReadOnly(True)
        self.layout.addWidget(self.details_text)

        self.lblIntervention = QLabel()
        self.layout.addWidget(self.lblIntervention)

        self.zoom_button = QPushButton("Zoom to Hotspot", self)
        self.zoom_button.clicked.connect(self._zoom)
        self.layout.addWidget(self.zoom_button)

        self.feature_id = None
        self.layer = None
        self.contributing_pipe_ids = []
        self.pipe_layer = None  # Will point to combined pipe layer

    def populate(self, fid, pipe_ids, materials, length_km, pipe_count, avg_need, avg_age):
        self.feature_id = fid
        self.info_label.setText(f"Hotspot ID: {fid}")
        self.details_text.setPlainText(
            f"Pipe Count: {pipe_count}\n"
            f"Avg Renewal Need: {avg_need:.2f}\n"
            f"Total Length: {length_km:.2f} km\n"
            f"Materials: {materials}\n"
            f"Pipes: {pipe_ids}"
        )

        # Compute suggestion
        sample_pipe_type = "wastewater" if "spill" in materials.lower() else (
            "stormwater" if "storm" in materials.lower() else "water"
        )
        suggestion = intervention_logic.suggest_intervention(
            sample_pipe_type, materials, avg_age, avg_need
        )
        self.lblIntervention.setText(f"Suggested Intervention: {suggestion}")


    def setLayer(self, layer):
        self.layer = layer

    def setContributingPipes(self, pipe_ids):
        self.contributing_pipe_ids = pipe_ids

    def setPipeLayer(self, layer):
        self.pipe_layer = layer

    def _zoom(self):
        if self.iface and self.layer and self.feature_id is not None:
            self.layer.selectByIds([self.feature_id])
            self.iface.mapCanvas().zoomToSelected(self.layer)
        # Also zoom/highlight contributing pipes
        if self.iface and self.pipe_layer and self.contributing_pipe_ids:
            self.pipe_layer.removeSelection()
            self.pipe_layer.selectByIds(self.contributing_pipe_ids)
            self.iface.mapCanvas().zoomToSelected(self.pipe_layer)
