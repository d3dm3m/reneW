import os
import csv
from qgis.PyQt import uic
from qgis.PyQt.QtCore import pyqtSignal, QRectF, QCoreApplication
from qgis.PyQt.QtWidgets import (QDialog, QFileDialog, QTableWidgetItem, QTabWidget,
                                 QWidget, QVBoxLayout)
from qgis.core import (QgsProject, QgsPrintLayout, QgsLayoutItemLabel,
                     QgsLayoutExporter, QgsVectorLayer)


def tr(message):
    """Get the translation for a string using Qt translation API."""
    return QCoreApplication.translate('ResultsDialog', message)


# This loads your .ui file
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'results_dialog.ui'))


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
        self._hotspot_layer = None

        # --- Create Tabbed Interface ---
        self.mTabWidget = QTabWidget()
        self.verticalLayout.insertWidget(0, self.mTabWidget) # Add tabs to the top

        # Tab 1: High-Risk Pipes (the original table)
        pipes_tab = QWidget()
        pipes_layout = QVBoxLayout(pipes_tab)
        self.mPipesTable = self.mTableWidget # Rename for clarity
        pipes_layout.addWidget(self.mPipesTable)
        self.mTabWidget.addTab(pipes_tab, tr("High-Risk Pipes"))

        # Tab 2: Hotspots
        hotspots_tab = QWidget()
        hotspots_layout = QVBoxLayout(hotspots_tab)
        self.mHotspotTable = QTableWidget()
        self.mHotspotTable.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.mHotspotTable.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.mHotspotTable.setSelectionMode(QAbstractItemView.SingleSelection)
        hotspots_layout.addWidget(self.mHotspotTable)
        self.mTabWidget.addTab(hotspots_tab, tr("Hotspots"))
        # --- End of Tabbed Interface ---

        self.mBtnZoomTo.clicked.connect(self._zoom_to_selected)
        self.mBtnExport.clicked.connect(self._export_to_csv)
        self.mBtnExportPdf.clicked.connect(self._export_to_pdf)

        if self._hotspot_count > 0:
            self._find_and_populate_hotspots()
        else:
            self.mTabWidget.setTabEnabled(1, False)

    def populate_table(self, results_data: list):
        """Populates the table with results."""
        self._results_data = results_data

        headers = [
            tr("Layer Name"), tr("Pipe ID"), tr("Material"), tr("Age"),
            tr("Renewal Need"), tr("Layer ID"), tr("Feature ID")
        ]
        self.mPipesTable.setColumnCount(len(headers))
        self.mPipesTable.setHorizontalHeaderLabels(headers)
        self.mPipesTable.setRowCount(len(results_data))

        for row, item in enumerate(results_data):
            self.mPipesTable.setItem(
                row, 0, QTableWidgetItem(item.get('layer_name', '')))
            self.mPipesTable.setItem(row, 1, QTableWidgetItem(
                str(item.get('feature_id', ''))))
            self.mPipesTable.setItem(
                row, 2, QTableWidgetItem(item.get('material', '')))
            self.mPipesTable.setItem(
                row, 3, QTableWidgetItem(str(item.get('age', ''))))

            renewal_need_item = QTableWidgetItem()
            renewal_need_item.setData(0, item.get('renewal_need', 0.0))
            self.mPipesTable.setItem(row, 4, renewal_need_item)

            self.mPipesTable.setItem(
                row, 5, QTableWidgetItem(item.get('layer_id', '')))
            self.mPipesTable.setItem(row, 6, QTableWidgetItem(
                str(item.get('feature_id', ''))))

        self.mPipesTable.setColumnHidden(5, True)
        self.mPipesTable.setColumnHidden(6, True)
        self.mPipesTable.resizeColumnsToContents()

    def _find_and_populate_hotspots(self):
        """Finds the 'Hotspots' layer and populates the hotspot table."""
        # Find the layer named "Hotspots"
        layers = QgsProject.instance().mapLayersByName(tr("Hotspots"))
        if not layers:
            self.mTabWidget.setTabEnabled(1, False)
            return
        self._hotspot_layer = layers[0]

        headers = [tr("Hotspot ID"), tr("Pipe Count"), tr("Avg. Renewal Need")]
        self.mHotspotTable.setColumnCount(len(headers))
        self.mHotspotTable.setHorizontalHeaderLabels(headers)
        self.mHotspotTable.setRowCount(self._hotspot_layer.featureCount())

        for i, feature in enumerate(self._hotspot_layer.getFeatures()):
            self.mHotspotTable.setItem(i, 0, QTableWidgetItem(str(feature.id())))
            self.mHotspotTable.setItem(i, 1, QTableWidgetItem(str(feature['pipe_count'])))

            avg_need_item = QTableWidgetItem()
            avg_need_item.setData(0, feature['avg_renewal_need'])
            self.mHotspotTable.setItem(i, 2, avg_need_item)

        self.mHotspotTable.resizeColumnsToContents()

    def _zoom_to_selected(self):
        """Emits a signal with the layer and feature ID of the selected row in the active table."""
        current_tab_index = self.mTabWidget.currentIndex()

        if current_tab_index == 0: # High-Risk Pipes
            table = self.mPipesTable
            selected_items = table.selectedItems()
            if not selected_items: return

            row = selected_items[0].row()
            layer_id_item = table.item(row, 5)
            feature_id_item = table.item(row, 6)

            if layer_id_item and feature_id_item:
                layer_id = layer_id_item.text()
                feature_id = int(feature_id_item.text())
                self.zoom_to_feature_signal.emit(layer_id, feature_id)

        elif current_tab_index == 1: # Hotspots
            table = self.mHotspotTable
            selected_items = table.selectedItems()
            if not selected_items: return

            row = selected_items[0].row()
            feature_id = int(table.item(row, 0).text())

            if self._hotspot_layer:
                self.zoom_to_feature_signal.emit(self._hotspot_layer.id(), feature_id)

    def _export_to_csv(self):
        """Exports the active table content to a CSV file."""
        current_tab_index = self.mTabWidget.currentIndex()
        table = self.mPipesTable if current_tab_index == 0 else self.mHotspotTable

        if table.rowCount() == 0:
            return

        path, _ = QFileDialog.getSaveFileName(
            self, tr("Save CSV"), "", tr("CSV files (*.csv)"))
        if not path:
            return

        try:
            with open(path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f, delimiter=';')
                header = [table.horizontalHeaderItem(i).text() for i in range(
                    table.columnCount()) if not table.isColumnHidden(i)]
                writer.writerow(header)
                for row in range(table.rowCount()):
                    row_data = [table.item(row, col).text() for col in range(
                        table.columnCount()) if not table.isColumnHidden(col)]
                    writer.writerow(row_data)
        except Exception as e:
            print(f"Could not export to CSV: {e}")

    def _export_to_pdf(self):
        """Exports a simple summary report to a PDF file."""
        path, _ = QFileDialog.getSaveFileName(
            self, tr("Save PDF Report"), "", tr("PDF files (*.pdf)"))
        if not path:
            return

        project = QgsProject.instance()
        layout_name = "reneW Report"
        layout_manager = project.layoutManager()

        # Remove layout if it already exists to avoid duplicates
        if layout_manager.layoutByName(layout_name):
            layout_manager.removeLayout(
                layout_manager.layoutByName(layout_name))

        layout = QgsPrintLayout(project)
        layout.initializeDefaults()
        layout.setName(layout_name)

        # Add Title
        title = QgsLayoutItemLabel(layout)
        title.setText(tr("Summary Report - reneW Analysis"))
        title.setFont(self.font())  # Use dialog's font
        title.setFontSize(18)
        title.adjustSizeToText()
        layout.addLayoutItem(title)
        title.attemptMove(QRectF(10, 10, 200, 20))

        # Add Summary Text
        summary_text = tr(
            """
            <b>Summary:</b><br>
            <ul>
            <li>Number of high-risk pipes (need > 0.5): {0}</li>
            <li>Number of identified hotspots: {1}</li>
            </ul>
            """
        ).format(len(self._results_data), self._hotspot_count)

        summary = QgsLayoutItemLabel(layout)
        summary.setText(summary_text)
        summary.setFont(self.font())
        summary.setFontSize(12)
        layout.addLayoutItem(summary)
        summary.attemptMove(QRectF(10, 40, 200, 50))

        # Export
        exporter = QgsLayoutExporter(layout)
        settings = QgsLayoutExporter.PdfExportSettings()
        exporter.exportToPdf(path, settings)

        # Clean up the temporary layout
        layout_manager.addLayout(layout)  # needs to be added to be removed
        layout_manager.removeLayout(layout)

        # Optionally, notify the user
        print(f"Rapport sparad till {path}")
