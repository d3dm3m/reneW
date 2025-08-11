import os
from datetime import datetime

from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QVariant
from qgis.core import QgsProject, QgsVectorLayer, QgsField

# Import the code for the dialog and the calculation logic
from .reneW_dialog import ReneWDialog
from . import calculation_logic

class ReneW:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.
        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu = u'&reneW'
        self.toolbar = self.iface.addToolBar(u'reneW')
        self.toolbar.setObjectName(u'reneW')
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
            self.iface.addPluginToMenu(self.menu, action)
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
            self.iface.removePluginMenu(u'&reneW', action)
            self.iface.removeToolBarIcon(action)
        del self.toolbar

    def run(self):
        """Run method that performs all the real work"""
        if self.dlg is None:
            self.dlg = ReneWDialog()

        self.dlg.show()
        result = self.dlg.exec_()

        if result:
            analysis_configs = self.dlg.get_analysis_configs()
            use_dimension_weighting = self.dlg.useDimensionWeighting()
            dimension_factor = self.dlg.dimensionFactor()

            if not analysis_configs:
                self.iface.messageBar().pushMessage("Info", "Inga lager valdes för analys.", level=0, duration=3)
                return

            processed_layers = 0
            current_year = datetime.now().year

            for config in analysis_configs:
                layer = config['layer']
                layer_type = config['type'] # Vatten, Spillvatten, or Dagvatten

                # Map dialog type to calculation logic type
                if layer_type in ['Spillvatten', 'Dagvatten']:
                    calc_pipeline_type = 'Avlopp'
                else:
                    calc_pipeline_type = 'Vatten'

                output_field_name = 'fornyelsebehov'
                provider = layer.dataProvider()
                fields = provider.fields()

                if fields.indexFromName(output_field_name) == -1:
                    provider.addAttributes([QgsField(output_field_name, QVariant.Double)])
                    layer.updateFields()

                material_idx = fields.indexFromName(config['material_field'])
                year_idx = fields.indexFromName(config['year_field'])
                dimension_idx = fields.indexFromName(config['dimension_field'])
                output_idx = fields.indexFromName(output_field_name)

                if any(idx == -1 for idx in [material_idx, year_idx, dimension_idx]):
                    self.iface.messageBar().pushMessage("Error", f"Fält kunde inte hittas i lagret '{layer.name()}'. Hoppar över.", level=1)
                    continue

                layer.startEditing()
                for feature in layer.getFeatures():
                    attrs = feature.attributes()
                    material = attrs[material_idx]

                    try:
                        installation_year = int(attrs[year_idx])
                    except (ValueError, TypeError, AttributeError):
                        installation_year = current_year

                    try:
                        dimension = float(attrs[dimension_idx])
                    except (ValueError, TypeError, AttributeError):
                        dimension = 0.0

                    age = max(0, current_year - installation_year)

                    renewal_need = calculation_logic.calculate_renewal_need(
                        pipeline_type=calc_pipeline_type,
                        material=material,
                        age=age,
                        year=installation_year,
                        dimension=dimension,
                        use_dimension_weighting=use_dimension_weighting,
                        dimension_factor=dimension_factor
                    )

                    layer.changeAttributeValue(feature.id(), output_idx, renewal_need)

                if layer.commitChanges():
                    self.iface.messageBar().pushMessage("Success", f"Beräkning klar för lagret '{layer.name()}'.", level=0, duration=4)
                    processed_layers += 1
                else:
                    layer.rollBack()
                    self.iface.messageBar().pushMessage("Error", f"Kunde inte spara ändringar för lagret '{layer.name()}'.", level=1)

            if processed_layers > 0:
                self.iface.messageBar().pushMessage("Info", f"Analys slutförd för {processed_layers} lager.", level=0, duration=5)
                self.iface.mapCanvas().refresh()
