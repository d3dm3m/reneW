import os
from datetime import datetime

from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QVariant
from qgis.core import QgsProject, QgsVectorLayer, QgsField

# Import the code for the dialog
from .reneW_dialog import ReneWDialog

class ReneW:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)

        # Declare instance attributes
        self.actions = []
        self.menu = u'&reneW'
        self.toolbar = self.iface.addToolBar(u'reneW')
        self.toolbar.setObjectName(u'reneW')

        # Initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)

        # Create the dialog (after translation) and keep reference
        self.dlg = None


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons for the plugin."""
        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        self.add_action(
            icon_path,
            text=u'Run reneW',
            callback=self.run,
            parent=self.iface.mainWindow())

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                u'&reneW',
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar

    def run(self):
        """Run method that performs all the real work"""
        if self.dlg is None:
            self.dlg = ReneWDialog()

        self.dlg.show()
        result = self.dlg.exec_()

        if result:
            layer = self.dlg.selectedLayer()
            material_field = self.dlg.materialField()
            year_field = self.dlg.yearField()
            dimension_field = self.dlg.dimensionField()

            if not layer:
                self.iface.messageBar().pushMessage("Error", "No layer selected.", level=1)
                return

            if not isinstance(layer, QgsVectorLayer):
                self.iface.messageBar().pushMessage("Error", "Please select a vector layer.", level=1)
                return

            provider = layer.dataProvider()
            fields = provider.fields()
            risk_field_name = 'risk_score'

            if fields.indexFromName(risk_field_name) == -1:
                provider.addAttributes([QgsField(risk_field_name, QVariant.Int)])
                layer.updateFields()

            material_idx = fields.indexFromName(material_field)
            year_idx = fields.indexFromName(year_field)
            dimension_idx = fields.indexFromName(dimension_field)
            risk_score_idx = fields.indexFromName(risk_field_name)

            if any(idx == -1 for idx in [material_idx, year_idx, dimension_idx]):
                self.iface.messageBar().pushMessage("Error", f"One or more selected fields ('{material_field}', '{year_field}', '{dimension_field}') not found.", level=1)
                return

            material_risk = {
                'GJUTJÄRN': 10, 'GJ': 10, 'GG': 10,
                'PE': 2, 'PEM': 2,
                'STÅL': 5,
                'PVC': 3,
                'AV': 8, 'AC': 8
            }

            current_year = datetime.now().year

            layer.startEditing()
            for feature in layer.getFeatures():
                attrs = feature.attributes()
                material = str(attrs[material_idx]).upper().strip()

                try:
                    installation_year = int(attrs[year_idx])
                except (ValueError, TypeError):
                    installation_year = current_year

                try:
                    dimension = int(attrs[dimension_idx])
                except (ValueError, TypeError):
                    dimension = 0

                age_score = max(0, current_year - installation_year)
                material_score = material_risk.get(material, 0)
                dimension_score = dimension / 20 if dimension > 0 else 0

                total_risk_score = int(age_score + material_score + dimension_score)

                layer.changeAttributeValue(feature.id(), risk_score_idx, total_risk_score)

            if layer.commitChanges():
                self.iface.messageBar().pushMessage("Success", f"Risk calculation complete. Field '{risk_field_name}' was added/updated.", level=0, duration=5)
            else:
                layer.rollBack()
                self.iface.messageBar().pushMessage("Error", "Could not commit changes to the layer.", level=1)

            self.iface.mapCanvas().refresh()
