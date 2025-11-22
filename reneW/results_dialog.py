import os
import csv
from qgis.PyQt import uic
from qgis.PyQt.QtCore import pyqtSignal, QRectF, Qt
from qgis.PyQt.QtWidgets import QDialog, QFileDialog, QTableWidgetItem
from qgis.core import (QgsProject, QgsPrintLayout, QgsLayoutItemLabel,
                     QgsLayoutExporter, QgsUnitTypes)

# This loads your .ui file
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'results_dialog.ui'))

class NumericSortItem(QTableWidgetItem):
    """
    A QTableWidgetItem that sorts numerically but displays text.
    """
    def __init__(self, value, display_text):
        super().__init__(display_text)
        self.value = value

    def __lt__(self, other):
        return self.value < other.value

class ResultsDialog(QDialog, FORM_CLASS):
    # Signal to be emitted when user wants to zoom to a feature
    # It will carry the layer_id (str) and feature_id (int)
    zoom_to_feature_signal = pyqtSignal(str, int)

    def __init__(self, parent=None, hotspot_count=0):
        """Constructor."""
        super(ResultsDialog, self).__init__(parent)
        self.setupUi(self)

        self._results_data = []
        self._hotspot_count = hotspot_count
        self.mBtnZoomTo.clicked.connect(self._zoom_to_selected)
        self.mBtnExport.clicked.connect(self._export_to_csv)
        self.mBtnExportPdf.clicked.connect(self._export_to_pdf)

    def populate_table(self, results_data: list):
        """Populates the table with results."""
        self._results_data = results_data

        headers = ["Lagernamn", "Lednings-ID", "Material", "Ålder", "Förnyelsebehov",
                   "Riskpoäng", "Riskkostnad (SEK)", "Layer ID", "Feature ID"]
        self.mTableWidget.setColumnCount(len(headers))
        self.mTableWidget.setHorizontalHeaderLabels(headers)
        self.mTableWidget.setRowCount(len(results_data))

        for row, item in enumerate(results_data):
            self.mTableWidget.setItem(row, 0, QTableWidgetItem(item.get('layer_name', '')))
            self.mTableWidget.setItem(row, 1, QTableWidgetItem(str(item.get('feature_id', ''))))
            self.mTableWidget.setItem(row, 2, QTableWidgetItem(item.get('material', '')))
            self.mTableWidget.setItem(row, 3, QTableWidgetItem(str(item.get('age', ''))))

            # PoF (Numeric Sort)
            renewal_need = item.get('renewal_need', 0.0)
            self.mTableWidget.setItem(row, 4, NumericSortItem(renewal_need, f"{renewal_need:.2f}"))

            # Risk Score (Numeric Sort)
            risk_score = item.get('risk_score', 0.0)
            self.mTableWidget.setItem(row, 5, NumericSortItem(risk_score, f"{risk_score:.1f}"))

            # Risk Cost (Currency Format, Numeric Sort)
            risk_cost = item.get('risk_cost', 0.0)
            cost_str = "{:,.0f} kr".format(risk_cost).replace(',', ' ')
            self.mTableWidget.setItem(row, 6, NumericSortItem(risk_cost, cost_str))

            self.mTableWidget.setItem(row, 7, QTableWidgetItem(item.get('layer_id', '')))
            self.mTableWidget.setItem(row, 8, QTableWidgetItem(str(item.get('feature_id', ''))))

        self.mTableWidget.setColumnHidden(7, True)
        self.mTableWidget.setColumnHidden(8, True)
        self.mTableWidget.resizeColumnsToContents()

    def _zoom_to_selected(self):
        """Emits a signal with the layer and feature ID of the selected row."""
        selected_items = self.mTableWidget.selectedItems()
        if not selected_items:
            return

        row = selected_items[0].row()
        layer_id_item = self.mTableWidget.item(row, 7)
        feature_id_item = self.mTableWidget.item(row, 8)

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
                header = [self.mTableWidget.horizontalHeaderItem(i).text() for i in range(self.mTableWidget.columnCount()) if not self.mTableWidget.isColumnHidden(i)]
                writer.writerow(header)
                for row in range(self.mTableWidget.rowCount()):
                    row_data = [self.mTableWidget.item(row, col).text() for col in range(self.mTableWidget.columnCount()) if not self.mTableWidget.isColumnHidden(col)]
                    writer.writerow(row_data)
        except Exception as e:
            print(f"Could not export to CSV: {e}")

    def _export_to_pdf(self):
        """Exports a simple summary report to a PDF file."""
        path, _ = QFileDialog.getSaveFileName(self, "Spara PDF-rapport", "", "PDF-filer (*.pdf)")
        if not path:
            return

        project = QgsProject.instance()
        layout_name = "reneW Report"
        layout_manager = project.layoutManager()

        # Remove layout if it already exists to avoid duplicates
        if layout_manager.layoutByName(layout_name):
            layout_manager.removeLayout(layout_manager.layoutByName(layout_name))

        layout = QgsPrintLayout(project)
        layout.initializeDefaults()
        layout.setName(layout_name)

        # Add Title
        title = QgsLayoutItemLabel(layout)
        title.setText("Sammanfattande Rapport - reneW Analys")
        title.setFont(self.font()) # Use dialog's font
        title.setFontSize(18)
        title.adjustSizeToText()
        layout.addLayoutItem(title)
        title.attemptMove(QRectF(10, 10, 200, 20))

        # Calculate total risk cost
        total_risk_cost = sum(item.get('risk_cost', 0.0) for item in self._results_data)

        # Add Summary Text
        summary_text = f"""
        <b>Sammanfattning:</b><br>
        <ul>
        <li>Antal högriskledningar: {len(self._results_data)} st</li>
        <li>Antal identifierade hotspots: {self._hotspot_count} st</li>
        <li>Total beräknad riskkostnad: {total_risk_cost:,.0f} kr</li>
        </ul>
        """
        summary = QgsLayoutItemLabel(layout)
        summary.setText(summary_text)
        summary.setFont(self.font())
        summary.setFontSize(12)
        layout.addLayoutItem(summary)
        summary.attemptMove(QRectF(10, 40, 300, 60))

        # Export
        exporter = QgsLayoutExporter(layout)
        settings = QgsLayoutExporter.PdfExportSettings()
        exporter.exportToPdf(path, settings)

        # Clean up the temporary layout
        layout_manager.addLayout(layout) # needs to be added to be removed
        layout_manager.removeLayout(layout)

        # Optionally, notify the user
        print(f"Rapport sparad till {path}")
