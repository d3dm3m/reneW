import os
import re
from datetime import datetime

from qgis.PyQt.QtWidgets import QAction, QProgressBar
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QVariant, QCoreApplication, Qt
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsField, QgsGeometry, QgsFeature,
    QgsFillSymbol, QgsSimpleFillSymbolLayer, QgsMessageLog, Qgis, QgsBlurEffect)

# Import the code for the dialog and the calculation logic
from .reneW_dialog import ReneWDialog
from .results_dialog import ResultsDialog
from . import calculation_logic
from . import material_lookup

def tr(message):
    """Get the translation for a string using Qt translation API."""
    return QCoreApplication.translate('ReneW', message)


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
        self.menu = tr(u'&reneW')
        self.toolbar = self.iface.addToolBar(tr(u'reneW'))
        self.toolbar.setObjectName(u'reneW')
        self.dlg = None
        self.results_dialog = None

    def _handle_zoom_to_feature(self, layer_id, feature_id):
        """Zooms the map canvas to a specific feature."""
        layer = QgsProject.instance().mapLayer(layer_id)
        if not layer:
            return

        layer.selectByIds([feature_id])
        self.iface.mapCanvas().zoomToSelected(layer)
        self.iface.mapCanvas().refresh()

    def _parse_dimension(self, dim_val) -> float:
        """Extracts a numeric dimension from a string value."""
        if isinstance(dim_val, (int, float)):
            return float(dim_val)
        if not isinstance(dim_val, str):
            return 0.0

        match = re.search(r'(\d+)', dim_val)
        if match:
            return float(match.group(1))
        return 0.0

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
            text=tr(u'Run reneW'),
            callback=self.run,
            parent=self.iface.mainWindow())

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(tr(u'&reneW'), action)
            self.iface.removeToolBarIcon(action)
        del self.toolbar

    def run(self):
        """Run method that performs all the real work"""
        try:
            param_path = os.path.join(self.plugin_dir, 'parameters.json')
            params_data = material_lookup.load_parameters(param_path)
        except Exception as e:
            self.iface.messageBar().pushMessage(
                tr("Error"),
                tr("Failed to load or parse parameters.json: {0}").format(e),
                level=2,
                duration=10)
            return

        if self.dlg is None:
            self.dlg = ReneWDialog(self.iface.mainWindow())

        self.dlg.load_settings()
        self.dlg.show()
        result = self.dlg.exec_()

        if result:
            self.dlg.save_settings()

            analysis_configs = self.dlg.get_analysis_configs()
            use_dimension_weighting = self.dlg.useDimensionWeighting()
            dimension_factor = self.dlg.dimensionFactor()
            selected_municipality_code = self.dlg.get_selected_municipality_code()

            if not analysis_configs:
                self.iface.messageBar().pushMessage(tr("Info"), tr("No layers selected for analysis."), level=0, duration=3)
                return

            QgsMessageLog.logMessage(tr("Starting reneW analysis."), 'reneW', Qgis.Info)

            total_features = sum(config['layer'].featureCount() for config in analysis_configs)
            progress_bar = QProgressBar()
            progress_bar.setMaximum(total_features)
            progress_bar.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            message_bar_item = self.iface.messageBar().createMessage(tr("Calculating renewal need..."))
            message_bar_item.layout().addWidget(progress_bar)
            self.iface.messageBar().pushWidget(message_bar_item, Qgis.Info)

            processed_features = 0
            processed_layers = 0
            high_risk_results = []
            current_year = datetime.now().year

            for config in analysis_configs:
                layer = config['layer']
                layer_name = layer.name()
                QgsMessageLog.logMessage(tr("Processing layer: {0}").format(layer_name), 'reneW', Qgis.Info)

                domain = 'water' if 'vatten' in config['type'].lower() else 'sewer'
                subtype = 'spill' if 'spill' in config['type'].lower() else ('storm' if 'dag' in config['type'].lower() else None)

                output_field_name = 'fornyelsebehov'
                provider = layer.dataProvider()
                fields = provider.fields()

                if fields.indexFromName(output_field_name) == -1:
                    provider.addAttributes([QgsField(output_field_name, QVariant.Double)])
                    layer.updateFields()

                required_fields = ['material_field', 'year_field', 'dimension_field']
                if not all(config.get(f) for f in required_fields):
                    self.iface.messageBar().pushMessage(tr("Error"), tr("A required field is not selected for layer '{0}'. Skipping.").format(layer_name), level=1)
                    continue

                field_indices = {f: fields.indexFromName(config[f]) for f in required_fields if config.get(f)}
                # Add optional renovation fields
                if config.get('reno_year_field'):
                    field_indices['reno_year_field'] = fields.indexFromName(config['reno_year_field'])

                muni_idx = fields.indexFromName(config['municipality_field']) if config.get('municipality_field') else -1
                output_idx = fields.indexFromName(output_field_name)

                layer.startEditing()
                for feature in layer.getFeatures():
                    processed_features += 1
                    progress_bar.setValue(processed_features)
                    attrs = feature.attributes()

                    if selected_municipality_code is not None and muni_idx != -1:
                        if attrs[muni_idx] != selected_municipality_code:
                            continue

                    year_val = attrs[field_indices['year_field']]
                    if year_val is None or str(year_val).strip() in ['1900', 'null', 'NULL']:
                        continue

                    try:
                        installation_year = int(year_val)
                    except (ValueError, TypeError):
                        continue

                    effective_install_year = installation_year
                    # --- Renovation Logic ---
                    # Check if a renovation has occurred that resets the pipe's age
                    if 'reno_year_field' in field_indices:
                        reno_year_val = attrs[field_indices['reno_year_field']]
                        if reno_year_val:
                            try:
                                renovation_year = int(reno_year_val)
                                # A valid renovation must happen after installation
                                if renovation_year > installation_year:
                                    effective_install_year = renovation_year
                            except (ValueError, TypeError):
                                pass # Ignore non-integer renovation years

                    age = max(0, current_year - effective_install_year)
                    material_name = attrs[field_indices['material_field']]

                    try:
                        # Material properties are based on the original installation year
                        key, params = material_lookup.find_material_key(
                            params_data,
                            domain=domain,
                            subtype=subtype,
                            material_name=str(material_name),
                            year=installation_year
                        )
                    except KeyError as e:
                        QgsMessageLog.logMessage(f"Material lookup failed for '{material_name}': {e}", 'reneW', Qgis.Warning)
                        continue

                    # The new calculation logic is based on cohorts and periods.
                    # The cohort's age is determined by the effective_install_year (post-renovation).
                    cohort = calculation_logic.Cohort(length_km=1.0, install_year=effective_install_year, material_key=key)

                    # Calculate renewal need for the next year
                    renewal_need = calculation_logic.renewal_for_cohort_period(
                        cohort, current_year, current_year + 1, params
                    )

                    # The old logic had dimension weighting. The new model does not explicitly include it.
                    # For now, we apply it on top, as before.
                    if use_dimension_weighting:
                        dimension_val = attrs[field_indices['dimension_field']]
                        parsed_dimension = self._parse_dimension(dimension_val)
                        if parsed_dimension > 0 and dimension_factor > 0:
                            weight = 1.0 + (parsed_dimension * dimension_factor)
                            renewal_need *= weight

                    layer.changeAttributeValue(feature.id(), output_idx, renewal_need)

                    if renewal_need >= 0.5:
                        high_risk_results.append({
                            'layer_name': layer_name,
                            'layer_id': layer.id(),
                            'feature_id': feature.id(),
                            'material': material_name,
                            'age': age,
                            'renewal_need': renewal_need
                        })

                if layer.commitChanges():
                    self.iface.messageBar().pushMessage(tr("Success"), tr("Calculation complete for layer '{0}'.").format(layer_name), level=0, duration=4)
                    processed_layers += 1
                else:
                    layer.rollBack()
                    self.iface.messageBar().pushMessage(tr("Error"), tr("Could not save changes for layer '{0}'.").format(layer_name), level=1)

            self.iface.messageBar().clearWidgets()
            if processed_layers > 0:
                self.iface.messageBar().pushMessage(tr("Info"), tr("Analysis complete for {0} layers.").format(processed_layers), level=0, duration=5)
                self.iface.mapCanvas().refresh()

            if high_risk_results:
                high_risk_results.sort(key=lambda x: x['renewal_need'], reverse=True)
                self.results_dialog = ResultsDialog(parent=self.iface.mainWindow(), hotspot_count=0) # Hotspot removed for now
                self.results_dialog.zoom_to_feature_signal.connect(self._handle_zoom_to_feature)
                self.results_dialog.populate_table(high_risk_results)
                self.results_dialog.show()

            QgsMessageLog.logMessage(tr("reneW analysis finished."), 'reneW', Qgis.Success)

    def _run_hotspot_analysis(self, analysis_configs, threshold, distance):
        # This function needs to be updated to work with the new logic if needed.
        # For now, it is effectively disabled as the main `run` method no longer calls it.
        return None

    def _create_hotspot_layer(self, hotspot_geom, crs):
        # This function is also effectively disabled.
        return None
