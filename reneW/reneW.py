import os
from datetime import datetime

from qgis.PyQt.QtWidgets import QAction, QProgressBar
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtCore import QVariant, QCoreApplication, Qt
from qgis.core import (QgsProject, QgsVectorLayer, QgsField, QgsGeometry,
                     QgsFeature, QgsFillSymbol, QgsSimpleFill, QgsMessageLog, Qgis)
from qgis.gui import QgsBlurEffect

# Import the code for the dialog and the calculation logic
from .reneW_dialog import ReneWDialog
from .results_dialog import ResultsDialog
from . import calculation_logic

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
        # Reload parameters every time the plugin is run.
        # This allows users to edit the JSON file and have it reloaded without restarting QGIS.
        calculation_logic.load_parameters()

        # Check if the parameters were loaded correctly.
        config_error = calculation_logic.get_config_error()
        if config_error:
            self.iface.messageBar().pushMessage(
                tr("Error"),
                tr("reneW Plugin: {0}").format(config_error),
                level=2,
                duration=10)
            return

        if self.dlg is None:
            self.dlg = ReneWDialog(self.iface.mainWindow())

        # Load last used settings
        self.dlg.load_settings()

        self.dlg.show()
        result = self.dlg.exec_()

        if result:
            # Save settings on successful run
            self.dlg.save_settings()

            analysis_configs = self.dlg.get_analysis_configs()
            use_dimension_weighting = self.dlg.useDimensionWeighting()
            dimension_factor = self.dlg.dimensionFactor()

            if not analysis_configs:
                self.iface.messageBar().pushMessage(tr("Info"), tr("No layers were selected for analysis."), level=0, duration=3)
                return

            QgsMessageLog.logMessage(tr("Starting reneW analysis."), 'reneW', Qgis.Info)

            # --- Setup Progress Bar ---
            total_features = 0
            for config in analysis_configs:
                total_features += config['layer'].featureCount()

            progress_bar = QProgressBar()
            progress_bar.setMaximum(total_features)
            progress_bar.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)

            message_bar_item = self.iface.messageBar().createMessage(tr("Calculating renewal need..."))
            message_bar_item.layout().addWidget(progress_bar)
            self.iface.messageBar().pushWidget(message_bar_item, Qgis.Info)

            processed_features = 0
            processed_layers = 0
            high_risk_results = []
            current_year = datetime.now().year

            for config in analysis_configs:
                layer = config['layer']
                QgsMessageLog.logMessage(tr("Processing layer: {0}").format(layer.name()), 'reneW', Qgis.Info)
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
                reno_year_idx = fields.indexFromName(config['reno_year_field'])
                reno_method_idx = fields.indexFromName(config['reno_method_field'])
                output_idx = fields.indexFromName(output_field_name)

                # Only the base fields are strictly required
                if any(idx == -1 for idx in [material_idx, year_idx, dimension_idx]):
                    self.iface.messageBar().pushMessage(
                        tr("Error"),
                        tr("One of the required fields (material, year, dimension) could not be found in layer '{0}'. Skipping.").format(layer.name()),
                        level=1)
                    continue

                layer.startEditing()
                for feature in layer.getFeatures():
                    processed_features += 1
                    progress_bar.setValue(processed_features)
                    attrs = feature.attributes()
                    material = attrs[material_idx]

                    try:
                        installation_year = int(attrs[year_idx])
                    except (ValueError, TypeError, AttributeError):
                        installation_year = current_year

                    # Default age is based on installation year
                    age = max(0, current_year - installation_year)

                    # Check for renovation data and override age if applicable
                    if config.get('reno_method_field') and config.get('reno_year_field'):
                        reno_method_idx = fields.indexFromName(config['reno_method_field'])
                        reno_year_idx = fields.indexFromName(config['reno_year_field'])

                        if reno_method_idx != -1 and reno_year_idx != -1:
                            reno_method = attrs[reno_method_idx]
                            if reno_method and isinstance(reno_method, str):
                                if 'infodring' in reno_method.lower() or 'strumpa' in reno_method.lower():
                                    try:
                                        reno_year = int(attrs[reno_year_idx])
                                        age = max(0, current_year - reno_year)
                                    except (ValueError, TypeError, AttributeError):
                                        pass # Keep original age if reno year is invalid

                    # Handle dimension parsing (e.g., "225_I")
                    dimension_val = attrs[dimension_idx]
                    dimension = 0.0
                    if isinstance(dimension_val, (int, float)):
                        dimension = float(dimension_val)
                    elif isinstance(dimension_val, str):
                        try:
                            # Extract numeric part before any non-numeric characters
                            numeric_part = ''.join(filter(lambda c: c.isdigit() or c == '.', dimension_val.split('_')[0].split('/')[0]))
                            if numeric_part:
                                dimension = float(numeric_part)
                        except (ValueError, TypeError):
                            dimension = 0.0

                    renewal_need = calculation_logic.calculate_renewal_need(
                        pipeline_type=layer_type, # Pass the specific layer type
                        material=material,
                        age=age,
                        year=installation_year,
                        dimension=dimension,
                        use_dimension_weighting=use_dimension_weighting,
                        dimension_factor=dimension_factor
                    )

                    layer.changeAttributeValue(feature.id(), output_idx, renewal_need)

                    # Collect high-risk results for the table
                    # Using a threshold of 0.5 as a default for "high-risk"
                    if renewal_need >= 0.5:
                        high_risk_results.append({
                            'layer_name': layer.name(),
                            'layer_id': layer.id(),
                            'feature_id': feature.id(),
                            'material': material,
                            'age': age,
                            'renewal_need': renewal_need
                        })

                if layer.commitChanges():
                    self.iface.messageBar().pushMessage(
                        tr("Success"),
                        tr("Calculation complete for layer '{0}'.").format(layer.name()),
                        level=0, duration=4)
                    processed_layers += 1
                else:
                    layer.rollBack()
                    self.iface.messageBar().pushMessage(
                        tr("Error"),
                        tr("Could not save changes for layer '{0}'.").format(layer.name()),
                        level=1)

            if processed_layers > 0:
                self.iface.messageBar().pushMessage(
                    tr("Info"),
                    tr("Analysis complete for {0} layers.").format(processed_layers),
                    level=0, duration=5)
                self.iface.mapCanvas().refresh()

            # --- Run hotspot analysis if enabled ---
            hotspot_count = 0
            if self.dlg.isHotspotAnalysisEnabled() and analysis_configs:
                hotspot_threshold = self.dlg.getHotspotThreshold()
                hotspot_distance = self.dlg.getHotspotDistance()

                hotspot_geom = self._run_hotspot_analysis(analysis_configs, hotspot_threshold, hotspot_distance)

                if hotspot_geom:
                    if hotspot_geom.isMultipart():
                        hotspot_count = len(hotspot_geom.asMultiPolygon())
                    else:
                        hotspot_count = 1
                    # Use the CRS of the first analyzed layer for the new hotspot layer
                    first_layer_crs = analysis_configs[0]['layer'].crs()
                    self._create_hotspot_layer(hotspot_geom, first_layer_crs)

            # --- Show results dialog if there are high-risk items ---
            if high_risk_results:
                # Sort results by renewal need, descending
                high_risk_results.sort(key=lambda x: x['renewal_need'], reverse=True)

                self.results_dialog = ResultsDialog(parent=self.iface.mainWindow(), hotspot_count=hotspot_count)
                self.results_dialog.zoom_to_feature_signal.connect(self._handle_zoom_to_feature)
                self.results_dialog.populate_table(high_risk_results)
                self.results_dialog.show()

            self.iface.messageBar().clearWidgets()
            QgsMessageLog.logMessage(tr("reneW analysis finished."), 'reneW', Qgis.Success)

    def _run_hotspot_analysis(self, analysis_configs, threshold, distance):
        QgsMessageLog.logMessage(tr("Starting hotspot analysis."), 'reneW', Qgis.Info)
        self.iface.messageBar().pushMessage(tr("Info"), tr("Starting hotspot analysis..."), level=0, duration=3)

        high_risk_features = {'Vatten': [], 'Spillvatten': [], 'Dagvatten': []}

        # 1. Filter high-risk features
        for config in analysis_configs:
            layer = config['layer']
            layer_type = config['type']

            field_name = 'fornyelsebehov'
            if layer.fields().indexFromName(field_name) == -1:
                continue

            for feature in layer.getFeatures():
                if feature[field_name] is not None and feature[field_name] >= threshold:
                    high_risk_features[layer_type].append(feature.geometry())

        for pipe_type, geoms in high_risk_features.items():
            QgsMessageLog.logMessage(
                tr("{0} high-risk features found for type '{1}'.").format(len(geoms), pipe_type),
                'reneW', Qgis.Info)

        # 2. Check if we have enough data to find cross-type hotspots
        active_types = [t for t, geoms in high_risk_features.items() if geoms]
        if len(active_types) < 2:
            self.iface.messageBar().pushMessage(
                tr("Info"),
                tr("Not enough high-risk pipes from different pipe types to find hotspots."),
                level=0, duration=5)
            return None

        # 3. Create dissolved buffers for each active type
        QgsMessageLog.logMessage(
            tr("Creating buffers with distance {0}m.").format(distance), 'reneW', Qgis.Info)
        buffered_geometries = {}
        for layer_type, geoms in high_risk_features.items():
            if not geoms:
                continue

            combined_geom = QgsGeometry.collectGeometry(geoms)
            buffer_geom = combined_geom.buffer(distance, 5)
            buffered_geometries[layer_type] = buffer_geom

        # 4. Find intersections between the buffered geometries
        hotspot_polygons = []
        type_pairs = [
            ('Vatten', 'Spillvatten'),
            ('Vatten', 'Dagvatten'),
            ('Spillvatten', 'Dagvatten')
        ]

        for type1, type2 in type_pairs:
            if type1 in buffered_geometries and type2 in buffered_geometries:
                geom1 = buffered_geometries[type1]
                geom2 = buffered_geometries[type2]

                intersection = geom1.intersection(geom2)
                if not intersection.isEmpty():
                    hotspot_polygons.append(intersection)

        if not hotspot_polygons:
            QgsMessageLog.logMessage(tr("No intersections found between buffered geometries."), 'reneW', Qgis.Info)
            self.iface.messageBar().pushMessage(tr("Info"), tr("No hotspots were found."), level=0, duration=3)
            return None

        # 5. Combine all found hotspot polygons into a single geometry
        final_hotspots_geom = QgsGeometry.collectGeometry(hotspot_polygons)

        self.iface.messageBar().pushMessage(
            tr("Success"),
            tr("{0} hotspot areas identified.").format(len(hotspot_polygons)),
            level=0, duration=4)

        return final_hotspots_geom

    def _create_hotspot_layer(self, hotspot_geom, crs):
        # 1. Create a new memory layer with the correct CRS
        vl = QgsVectorLayer(f"Polygon?crs={crs.authid()}", "Hotspots", "memory")
        provider = vl.dataProvider()

        # 2. Add the hotspot geometry as a feature
        feature = QgsFeature()
        feature.setGeometry(hotspot_geom)
        provider.addFeatures([feature])

        # 3. Create the "Aura" style
        aura_symbol = QgsFillSymbol()
        aura_symbol.deleteSymbolLayer(0)

        # Glow layers (multiple blurred layers)
        # The blur radius and color can be adjusted for different visual effects
        for blur_radius, opacity, color in [(12, 20, '255,50,50'), (8, 40, '255,0,0'), (4, 70, '200,0,0')]:
            glow_fill = QgsSimpleFill.create({'color': f'{color},{opacity}', 'style': 'solid'})

            blur_effect = QgsBlurEffect()
            blur_effect.setBlurRadius(blur_radius)
            glow_fill.setEffect(blur_effect)

            aura_symbol.appendSymbolLayer(glow_fill)

        # 4. Apply the style to the layer
        renderer = vl.renderer()
        renderer.setSymbol(aura_symbol)
        vl.triggerRepaint() # To make the style apply visually

        # 5. Add the layer to the project
        QgsProject.instance().addMapLayer(vl)
