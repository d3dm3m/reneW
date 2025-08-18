from qgis.PyQt.QtWidgets import QDialog, QTableWidgetItem, QAbstractItemView, QHeaderView
from qgis.PyQt import uic
from qgis.PyQt.QtCore import pyqtSignal, Qt
import os
import re

class NumericStringTableWidgetItem(QTableWidgetItem):
    """A QTableWidgetItem that sorts numerically, even if text is present."""
    def __lt__(self, other):
        # Extract the first number found in the string for comparison
        val1_str = re.search(r"[-+]?\d*\.\d+|\d+", self.text())
        val2_str = re.search(r"[-+]?\d*\.\d+|\d+", other.text())

        val1 = float(val1_str.group()) if val1_str else 0.0
        val2 = float(val2_str.group()) if val2_str else 0.0

        return val1 < val2

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
        self.resultsTable.setColumnCount(8)
        self.resultsTable.setHorizontalHeaderLabels([
            "Layer", "Pipe Type", "Material", "Age",
            "Renewal Need", "Optimism Factor", "Feature ID", "Layer ID"
        ])
        self.resultsTable.setRowCount(0) # Clear the table

        for row_idx, result in enumerate(results):
            self.resultsTable.insertRow(row_idx)
            self.resultsTable.setItem(row_idx, 0, QTableWidgetItem(result.get('layer_name', '')))
            self.resultsTable.setItem(row_idx, 1, QTableWidgetItem(result.get('pipe_type', '')))
            self.resultsTable.setItem(row_idx, 2, QTableWidgetItem(result.get('material', '')))
            self.resultsTable.setItem(row_idx, 3, NumericStringTableWidgetItem(str(result.get('age', ''))))
            self.resultsTable.setItem(row_idx, 4, NumericStringTableWidgetItem(f"{result.get('renewal_need', 0.0):.2f}"))
            self.resultsTable.setItem(row_idx, 5, NumericStringTableWidgetItem(f"{result.get('optimism_factor', 1.0):.2f}"))
            self.resultsTable.setItem(row_idx, 6, QTableWidgetItem(str(result.get('feature_id', ''))))
            self.resultsTable.setItem(row_idx, 7, QTableWidgetItem(str(result.get('layer_id', ''))))

            # Store layer/feature IDs for zoom on the first item
            self.resultsTable.item(row_idx, 0).setData(1000, result.get('layer_id'))
            self.resultsTable.item(row_idx, 0).setData(1001, result.get('feature_id'))

    def _on_double_click(self, index):
        """Handle double-click on a row to zoom to the feature."""
        row = index.row()
        layer_id = self.resultsTable.item(row, 0).data(1000)
        feature_id = self.resultsTable.item(row, 0).data(1001)
        if layer_id and feature_id is not None:
            self.zoom_to_feature_signal.emit(layer_id, int(feature_id))
