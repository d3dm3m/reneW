from qgis.PyQt.QtWidgets import QDialog, QTableWidgetItem, QAbstractItemView, QHeaderView
from qgis.PyQt import uic
from qgis.PyQt.QtCore import pyqtSignal
import os

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'results_dialog.ui'))

class ResultsDialog(QDialog, FORM_CLASS):
    # Signal for zoom-to-feature
    zoom_to_feature_signal = pyqtSignal(str, int)

    def __init__(self, parent=None, hotspot_count=0):
        """Constructor."""
        super(ResultsDialog, self).__init__(parent)
        self.setupUi(self)
        self.resultsTable.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.resultsTable.setSelectionMode(QAbstractItemView.SingleSelection)
        self.resultsTable.horizontalHeader().setStretchLastSection(True)
        self.resultsTable.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        self.hotspotLabel.setText(f"Hotspots detected: {hotspot_count}")

        self.resultsTable.doubleClicked.connect(self._on_double_click)

    def populate_table(self, results):
        """Populate the results table with high-risk features."""

        headers = ["Layer", "Pipe Type", "Material", "Age", "Renewal Need"]
        self.resultsTable.setColumnCount(len(headers))
        self.resultsTable.setHorizontalHeaderLabels(headers)
        self.resultsTable.setRowCount(len(results))

        for row_idx, result in enumerate(results):
            row = [
                result.get('layer_name', ''),
                result.get('pipe_type', ''),  # now shows friendly label
                result.get('material', ''),
                str(result.get('age', '')),
                f"{result.get('renewal_need', 0.0):.3f}"
            ]
            for col_idx, value in enumerate(row):
                item = QTableWidgetItem(value)
                self.resultsTable.setItem(row_idx, col_idx, item)

            # Store layer/feature IDs for zoom
            self.resultsTable.setRowHeight(row_idx, 20)
            self.resultsTable.item(row_idx, 0).setData(1000, result.get('layer_id'))
            self.resultsTable.item(row_idx, 0).setData(1001, result.get('feature_id'))

    def _on_double_click(self, index):
        """Handle double-click on a row to zoom to the feature."""
        row = index.row()
        layer_id = self.resultsTable.item(row, 0).data(1000)
        feature_id = self.resultsTable.item(row, 0).data(1001)
        if layer_id and feature_id is not None:
            self.zoom_to_feature_signal.emit(layer_id, int(feature_id))
