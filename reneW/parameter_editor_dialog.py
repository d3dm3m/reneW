import os
import json
from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDialog, QTableWidgetItem

# This loads your .ui file
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'parameter_editor_dialog.ui'))


class ParameterEditorDialog(QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(ParameterEditorDialog, self).__init__(parent)
        self.setupUi(self)

        self.param_file = os.path.join(
            os.path.dirname(__file__), 'parameters.json')
        self.data = {}
        self._load_data()
        self._populate_combo()
        self._populate_municipalities_table()

        # Connect signals
        self.mPipeTypeCombo.currentIndexChanged.connect(self._populate_table)
        self.mBtnAddMaterialRow.clicked.connect(self._add_material_row)
        self.mBtnRemoveMaterialRow.clicked.connect(self._remove_material_row)
        self.mBtnAddMunicipalityRow.clicked.connect(self._add_municipality_row)
        self.mBtnRemoveMunicipalityRow.clicked.connect(self._remove_municipality_row)
        self.mButtonBox.accepted.connect(self.accept)

        # Initial population
        self._populate_table()

    def _load_data(self):
        """Loads the parameters.json file."""
        try:
            with open(self.param_file, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
        except (IOError, json.JSONDecodeError):
            # In case of error, start with empty data
            self.data = {"parameter_sets": [], "municipalities": []}

    def _populate_combo(self):
        """Populates the pipe type combo box."""
        self.mPipeTypeCombo.clear()
        for param_set in self.data.get('parameter_sets', []):
            self.mPipeTypeCombo.addItem(param_set.get('name'))

    def _populate_table(self):
        """Populates the materials table based on the selected pipe type."""
        self.mMaterialsTable.setRowCount(0)  # Clear table

        selected_type = self.mPipeTypeCombo.currentText()
        if not selected_type:
            return

        # Find the selected parameter set
        param_set = next((s for s in self.data.get(
            'parameter_sets', []) if s['name'] == selected_type), None)
        if not param_set:
            return

        materials = param_set.get('materials', [])
        self.mMaterialsTable.setRowCount(len(materials))

        for row_idx, material in enumerate(materials):
            self.mMaterialsTable.setItem(
                row_idx, 0, QTableWidgetItem(material.get('key', '')))
            self.mMaterialsTable.setItem(row_idx, 1, QTableWidgetItem(
                ",".join(material.get('keywords', []))))
            self.mMaterialsTable.setItem(
                row_idx, 2, QTableWidgetItem(str(material.get('year_min', ''))))
            self.mMaterialsTable.setItem(
                row_idx, 3, QTableWidgetItem(str(material.get('year_max', ''))))
            self.mMaterialsTable.setItem(row_idx, 4, QTableWidgetItem(
                str(material.get('params', {}).get('a', ''))))
            self.mMaterialsTable.setItem(row_idx, 5, QTableWidgetItem(
                str(material.get('params', {}).get('b', ''))))
            self.mMaterialsTable.setItem(row_idx, 6, QTableWidgetItem(
                str(material.get('params', {}).get('c', ''))))

        self.mMaterialsTable.resizeColumnsToContents()

    def _populate_municipalities_table(self):
        """Populates the municipalities table."""
        self.mMunicipalitiesTable.setRowCount(0)
        municipalities = self.data.get('municipalities', [])
        self.mMunicipalitiesTable.setRowCount(len(municipalities))

        for row_idx, municipality in enumerate(municipalities):
            self.mMunicipalitiesTable.setItem(
                row_idx, 0, QTableWidgetItem(str(municipality.get('code', ''))))
            self.mMunicipalitiesTable.setItem(
                row_idx, 1, QTableWidgetItem(municipality.get('name', '')))

        self.mMunicipalitiesTable.resizeColumnsToContents()

    def _add_material_row(self):
        """Adds a new empty row to the materials table."""
        row_count = self.mMaterialsTable.rowCount()
        self.mMaterialsTable.insertRow(row_count)

    def _remove_material_row(self):
        """Removes the currently selected row from the materials table."""
        current_row = self.mMaterialsTable.currentRow()
        if current_row >= 0:
            self.mMaterialsTable.removeRow(current_row)

    def _add_municipality_row(self):
        """Adds a new empty row to the municipalities table."""
        row_count = self.mMunicipalitiesTable.rowCount()
        self.mMunicipalitiesTable.insertRow(row_count)

    def _remove_municipality_row(self):
        """Removes the currently selected row from the municipalities table."""
        current_row = self.mMunicipalitiesTable.currentRow()
        if current_row >= 0:
            self.mMunicipalitiesTable.removeRow(current_row)

    def accept(self):
        """Saves all data back to the json file and closes."""
        # Save materials data
        selected_type = self.mPipeTypeCombo.currentText()
        if selected_type:
            param_set = next((s for s in self.data.get(
                'parameter_sets', []) if s['name'] == selected_type), None)
            if param_set:
                new_materials = []
                for row in range(self.mMaterialsTable.rowCount()):
                    material = {}
                    try:
                        material['key'] = self.mMaterialsTable.item(row, 0).text()
                        material['keywords'] = [
                            k.strip() for k in self.mMaterialsTable.item(row, 1).text().split(',')]

                        year_min = self.mMaterialsTable.item(row, 2).text()
                        if year_min:
                            material['year_min'] = int(year_min)

                        year_max = self.mMaterialsTable.item(row, 3).text()
                        if year_max:
                            material['year_max'] = int(year_max)

                        material['params'] = {
                            'a': float(self.mMaterialsTable.item(row, 4).text()),
                            'b': float(self.mMaterialsTable.item(row, 5).text()),
                            'c': float(self.mMaterialsTable.item(row, 6).text())
                        }
                        new_materials.append(material)
                    except (ValueError, AttributeError):
                        continue
                param_set['materials'] = new_materials

        # Save municipalities data
        new_municipalities = []
        for row in range(self.mMunicipalitiesTable.rowCount()):
            municipality = {}
            try:
                code_item = self.mMunicipalitiesTable.item(row, 0)
                name_item = self.mMunicipalitiesTable.item(row, 1)

                if code_item and name_item and code_item.text() and name_item.text():
                    municipality['code'] = int(code_item.text())
                    municipality['name'] = name_item.text()
                    new_municipalities.append(municipality)
            except (ValueError, AttributeError):
                continue
        self.data['municipalities'] = new_municipalities

        # Save the updated data back to the file
        try:
            with open(self.param_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except IOError:
            # Handle save error, maybe show a message box
            pass

        super(ParameterEditorDialog, self).accept()
