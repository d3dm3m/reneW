import os
import json
from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import (QDialog, QTableWidgetItem, QMessageBox,
                                 QInputDialog, QHeaderView)
from qgis.PyQt.QtGui import QFont, QColor


FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'parameter_editor_dialog.ui'))


class ParameterEditorDialog(QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(ParameterEditorDialog, self).__init__(parent)
        self.setupUi(self)

        self.mBtnAddMaterialRow.setText("Add/Override Material")
        self.mBtnRemoveMaterialRow.setText("Remove Override/Material")

        self.param_file = os.path.join(
            os.path.dirname(__file__), 'parameters.json')
        self.data = {}
        self._load_data()
        self._populate_combo()

        self.mPipeTypeCombo.currentIndexChanged.connect(self._populate_table)
        self.mBtnAddMaterialRow.clicked.connect(self._add_row)
        self.mBtnRemoveMaterialRow.clicked.connect(self._remove_row)
        self.mButtonBox.accepted.connect(self.accept)

        self._populate_table()

    def _load_data(self):
        """Loads the parameters.json file."""
        try:
            with open(self.param_file, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
        except (IOError, json.JSONDecodeError):
            self.data = {
                "material_defaults": {},
                "water": {},
                "sewer": {"spill": {}, "storm": {}},
                "municipalities": []
            }

    def _populate_combo(self):
        """Populates the pipe type combo box."""
        self.mPipeTypeCombo.clear()
        self.mPipeTypeCombo.addItem("water")
        self.mPipeTypeCombo.addItem("sewer/spill")
        self.mPipeTypeCombo.addItem("sewer/storm")
        self.mPipeTypeCombo.insertSeparator(3)
        self.mPipeTypeCombo.addItem("--- Edit Defaults ---")
        self.mPipeTypeCombo.setCurrentIndex(0)

    def _get_current_buckets(self):
        """Gets the domain-specific and default buckets for the current selection."""
        selected_path = self.mPipeTypeCombo.currentText()
        default_bucket = self.data.get("material_defaults", {})

        if selected_path == "--- Edit Defaults ---":
            return default_bucket, None

        path_parts = selected_path.split('/')
        domain_bucket = self.data
        for part in path_parts:
            domain_bucket = domain_bucket.get(part, {})

        return domain_bucket, default_bucket

    def _populate_table(self):
        """Populates the materials table based on the selected pipe type."""
        self.mMaterialsTable.setRowCount(0)
        domain_bucket, default_bucket = self._get_current_buckets()

        if default_bucket is None:
            default_bucket = {}
            self.mBtnAddMaterialRow.setText("Add Material")
            self.mBtnRemoveMaterialRow.setText("Remove Material")
        else:
            self.mBtnAddMaterialRow.setText("Add/Override Material")
            self.mBtnRemoveMaterialRow.setText("Remove Override")

        all_keys = sorted(
            list(set(domain_bucket.keys()) | set(default_bucket.keys()))
        )
        self.mMaterialsTable.setRowCount(len(all_keys))

        italic_font = QFont()
        italic_font.setItalic(True)
        default_color = QColor('gray')

        for row_idx, key in enumerate(all_keys):
            is_override = key in domain_bucket
            params = domain_bucket.get(key, default_bucket.get(key, {}))
            mu = str(params.get('mu', ''))
            sigma = str(params.get('sigma', ''))

            key_item = QTableWidgetItem(key)
            mu_item = QTableWidgetItem(mu)
            sigma_item = QTableWidgetItem(sigma)

            if not is_override and default_bucket:
                key_item.setFont(italic_font)
                mu_item.setFont(italic_font)
                sigma_item.setFont(italic_font)
                key_item.setForeground(default_color)
                mu_item.setForeground(default_color)
                sigma_item.setForeground(default_color)

            self.mMaterialsTable.setItem(row_idx, 0, key_item)
            self.mMaterialsTable.setItem(row_idx, 1, mu_item)
            self.mMaterialsTable.setItem(row_idx, 2, sigma_item)

        self.mMaterialsTable.resizeColumnsToContents()

    def _add_row(self):
        """Adds a new empty row to the table for a custom override."""
        row_count = self.mMaterialsTable.rowCount()
        self.mMaterialsTable.insertRow(row_count)
        self.mMaterialsTable.scrollToBottom()
        self.mMaterialsTable.editItem(self.mMaterialsTable.item(row_count, 0))

    def _remove_row(self):
        """Removes the currently selected row from the table."""
        current_row = self.mMaterialsTable.currentRow()
        if current_row < 0:
            return

        key_item = self.mMaterialsTable.item(current_row, 0)
        if not key_item:
            self.mMaterialsTable.removeRow(current_row)
            return

        key = key_item.text()
        domain_bucket, default_bucket = self._get_current_buckets()

        if key in domain_bucket:
            del domain_bucket[key]

        if default_bucket is None and key in domain_bucket:
            del domain_bucket[key]

        self._populate_table()

    def accept(self):
        """Saves the table data back to the json file and closes."""
        selected_path = self.mPipeTypeCombo.currentText()
        if not selected_path:
            super(ParameterEditorDialog, self).accept()
            return

        default_bucket = self.data.get("material_defaults", {})

        if selected_path == "--- Edit Defaults ---":
            new_materials = {}
            for row in range(self.mMaterialsTable.rowCount()):
                try:
                    key = self.mMaterialsTable.item(row, 0).text().strip()
                    mu = float(self.mMaterialsTable.item(row, 1).text())
                    sigma = float(self.mMaterialsTable.item(row, 2).text())
                    if key:
                        new_materials[key] = {'mu': mu, 'sigma': sigma}
                except (ValueError, AttributeError, TypeError, IndexError):
                    continue
            self.data["material_defaults"] = new_materials
        else:
            path_parts = selected_path.split('/')
            parent_dict = self.data
            for part in path_parts[:-1]:
                parent_dict = parent_dict.setdefault(part, {})
            leaf_key = path_parts[-1]

            new_overrides = {}
            for row in range(self.mMaterialsTable.rowCount()):
                try:
                    key = self.mMaterialsTable.item(row, 0).text().strip()
                    mu = float(self.mMaterialsTable.item(row, 1).text())
                    sigma = float(self.mMaterialsTable.item(row, 2).text())

                    if not key:
                        continue

                    default_params = default_bucket.get(key)
                    is_override = not default_params
                    if default_params:
                        same_mu = abs(mu - default_params.get('mu', float('nan'))) < 1e-9
                        same_sigma = abs(sigma - default_params.get('sigma', float('nan'))) < 1e-9
                        if not (same_mu and same_sigma):
                            is_override = True

                    if is_override:
                        new_overrides[key] = {'mu': mu, 'sigma': sigma}

                except (ValueError, AttributeError, TypeError, IndexError):
                    continue
            parent_dict[leaf_key] = new_overrides

        try:
            with open(self.param_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2,
                          ensure_ascii=False, sort_keys=True)
        except IOError:
            pass

        super(ParameterEditorDialog, self).accept()
