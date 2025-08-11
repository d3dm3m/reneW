import os
import csv
from qgis.PyQt import uic
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import QDialog, QFileDialog, QTableWidgetItem

# This loads your .ui file
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'results_dialog.ui'))

class ResultsDialog(QDialog, FORM_CLASS):
    # Signal to be emitted when user wants to zoom to a feature
    # It will carry the layer_id (str) and feature_id (int)
    zoom_to_feature_signal = pyqtSignal(str, int)

    def __init__(self, parent=None):
        """Constructor."""
        super(ResultsDialog, self).__init__(parent)
        self.setupUi(self)

        self._results_data = []
        self.mBtnZoomTo.clicked.connect(self._zoom_to_selected)
        self.mBtnExport.clicked.connect(self._export_to_csv)

    def populate_table(self, results_data: list):
        """Populates the table with results."""
        self._results_data = results_data

        headers = ["Lagernamn", "Lednings-ID", "Material", "Ålder", "Förnyelsebehov", "Layer ID", "Feature ID"]
        self.mTableWidget.setColumnCount(len(headers))
        self.mTableWidget.setHorizontalHeaderLabels(headers)
        self.mTableWidget.setRowCount(len(results_data))

        for row, item in enumerate(results_data):
            self.mTableWidget.setItem(row, 0, QTableWidgetItem(item.get('layer_name', '')))
            self.mTableWidget.setItem(row, 1, QTableWidgetItem(str(item.get('feature_id', ''))))
            self.mTableWidget.setItem(row, 2, QTableWidgetItem(item.get('material', '')))
            self.mTableWidget.setItem(row, 3, QTableWidgetItem(str(item.get('age', ''))))

            # Format renewal need to a few decimals and make it sortable as a number
            renewal_need_item = QTableWidgetItem()
            renewal_need_item.setData(0, item.get('renewal_need', 0.0))
            self.mTableWidget.setItem(row, 4, renewal_need_item)

            # Store internal IDs in hidden columns
            self.mTableWidget.setItem(row, 5, QTableWidgetItem(item.get('layer_id', '')))
            self.mTableWidget.setItem(row, 6, QTableWidgetItem(str(item.get('feature_id', ''))))

        # Hide the ID columns
        self.mTableWidget.setColumnHidden(5, True)
        self.mTableWidget.setColumnHidden(6, True)
        self.mTableWidget.resizeColumnsToContents()

    def _zoom_to_selected(self):
        """Emits a signal with the layer and feature ID of the selected row."""
        selected_items = self.mTableWidget.selectedItems()
        if not selected_items:
            return

        row = selected_items[0].row()
        layer_id_item = self.mTableWidget.item(row, 5)
        feature_id_item = self.mTableWidget.item(row, 6)

        if layer_id_item and feature_id_item:
            layer_id = layer_id_item.text()
            feature_id = int(feature_id_item.text())
            self.zoom_to_feature_signal.emit(layer_id, feature_id)

    def _export_to_csv(self):
        """Exports the table content to a CSV file."""
        if not self._results_data:
            return

        path, _ = QFileDialog.getSaveFileName(self, "Spara CSV", "", "CSV-filer (*.csv)")
        if not path:
            return

        try:
            with open(path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f, delimiter=';')

                # Write header
                header = [self.mTableWidget.horizontalHeaderItem(i).text() for i in range(self.mTableWidget.columnCount()) if not self.mTableWidget.isColumnHidden(i)]
                writer.writerow(header)

                # Write data
                for row in range(self.mTableWidget.rowCount()):
                    row_data = []
                    for col in range(self.mTableWidget.columnCount()):
                        if not self.mTableWidget.isColumnHidden(col):
                            row_data.append(self.mTableWidget.item(row, col).text())
                    writer.writerow(row_data)
        except Exception as e:
            # In a real app, show a QgsMessageBar message
            print(f"Could not export to CSV: {e}")
