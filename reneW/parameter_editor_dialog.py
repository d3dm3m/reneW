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

        # Connect signals
        self.mPipeTypeCombo.currentIndexChanged.connect(self._populate_table)
        self.mBtnAddRow.clicked.connect(self._add_row)
        self.mBtnRemoveRow.clicked.connect(self._remove_row)
        self.mButtonBox.accepted.connect(self.accept)

        # Initial population
        self._populate_table()

    def _load_data(self):
        """Loads the parameters.json file."""
        try:
            with open(self.param_file, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
        except (IOError, json.JSONDecodeError):
            self.data = {"water": {}, "sewer": {"spill": {}, "storm": {}}}

    def _populate_combo(self):
        """Populates the pipe type combo box."""
        self.mPipeTypeCombo.clear()
        self.mPipeTypeCombo.addItem("water")
        self.mPipeTypeCombo.addItem("sewer/spill")
        self.mPipeTypeCombo.addItem("sewer/storm")

    def _populate_table(self):
        """Populates the materials table based on the selected pipe type."""
        self.mMaterialsTable.setRowCount(0)

        selected_path = self.mPipeTypeCombo.currentText()
        if not selected_path:
            return

        # Get the materials dictionary from the nested structure
        path_parts = selected_path.split('/')
        materials_dict = self.data
        for part in path_parts:
            materials_dict = materials_dict.get(part, {})

        if not isinstance(materials_dict, dict):
            return

        self.mMaterialsTable.setRowCount(len(materials_dict))

        for row_idx, (key, params) in enumerate(materials_dict.items()):
            self.mMaterialsTable.setItem(row_idx, 0, QTableWidgetItem(key))
            self.mMaterialsTable.setItem(row_idx, 1, QTableWidgetItem(str(params.get('mu', ''))))
            self.mMaterialsTable.setItem(row_idx, 2, QTableWidgetItem(str(params.get('sigma', ''))))

        self.mMaterialsTable.resizeColumnsToContents()

    def _add_row(self):
        """Adds a new empty row to the table."""
        row_count = self.mMaterialsTable.rowCount()
        self.mMaterialsTable.insertRow(row_count)

    def _remove_row(self):
        """Removes the currently selected row from the table."""
        current_row = self.mMaterialsTable.currentRow()
        if current_row >= 0:
            self.mMaterialsTable.removeRow(current_row)

    def accept(self):
        """Saves the table data back to the json file and closes."""
        selected_path = self.mPipeTypeCombo.currentText()
        if not selected_path:
            super(ParameterEditorDialog, self).accept()
            return

        # Get the parent dictionary to update
        path_parts = selected_path.split('/')
        parent_dict = self.data
        for part in path_parts[:-1]:
            parent_dict = parent_dict.get(part, {})

        leaf_key = path_parts[-1]

        new_materials = {}
        for row in range(self.mMaterialsTable.rowCount()):
            try:
                key_item = self.mMaterialsTable.item(row, 0)
                mu_item = self.mMaterialsTable.item(row, 1)
                sigma_item = self.mMaterialsTable.item(row, 2)

                if key_item and mu_item and sigma_item and key_item.text():
                    key = key_item.text()
                    mu = float(mu_item.text())
                    sigma = float(sigma_item.text())
                    new_materials[key] = {'mu': mu, 'sigma': sigma}
            except (ValueError, AttributeError):
                continue

        parent_dict[leaf_key] = new_materials

        # Save the updated data back to the file
        try:
            with open(self.param_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except IOError:
            pass

        super(ParameterEditorDialog, self).accept()
