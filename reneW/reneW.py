import os
from datetime import datetime

from qgis.PyQt.QtWidgets import QAction, QProgressDialog
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtCore import QVariant, Qt
from qgis.core import (QgsProject, QgsVectorLayer, QgsField, QgsGeometry,
                     QgsFeature, QgsFillSymbol, QgsSimpleFill)
from qgis.gui import QgsBlurEffect

# Import the code for the dialog and the calculation logic
from .reneW_dialog import ReneWDialog
from .results_dialog import ResultsDialog
from .risk_manager import RiskManager

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
        self.results_dialog = None
        self.risk_manager = RiskManager()

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
                self.iface.messageBar().pushMessage("Info", "Inga lager valdes för analys.", level=0, duration=3)
                return

            processed_layers = 0
            all_high_risk_results = []

            # Create Progress Dialog
            total_steps = len(analysis_configs) * 100
            progress_dialog = QProgressDialog("Analyserar ledningsnät...", "Avbryt", 0, total_steps, self.iface.mainWindow())
            progress_dialog.setWindowModality(Qt.WindowModal)
            progress_dialog.show()

            for i, config in enumerate(analysis_configs):
                if progress_dialog.wasCanceled():
                    break

                layer_name = config['layer'].name()
                progress_dialog.setLabelText(f"Analyserar {layer_name}...")

                def update_progress(percent):
                    # Map 0-100 percent for this layer to the global progress
                    current_base = i * 100
                    progress_dialog.setValue(current_base + percent)

                result = self.risk_manager.execute_analysis(
                    layer=config['layer'],
                    config=config,
                    use_dimension_weighting=use_dimension_weighting,
                    dimension_factor=dimension_factor,
                    progress_callback=update_progress
                )

                if result['status']:
                    self.iface.messageBar().pushMessage("Success", result['message'], level=0, duration=4)
                    processed_layers += 1
                    all_high_risk_results.extend(result['high_risk_results'])
                else:
                    level = 1 if "Error" in result['message'] else 1 # Use Warning/Error level
                    self.iface.messageBar().pushMessage("Error", result['message'], level=level)

            progress_dialog.close()

            if processed_layers > 0:
                self.iface.messageBar().pushMessage("Info", f"Analys slutförd för {processed_layers} lager.", level=0, duration=5)
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
            if all_high_risk_results:
                # Sort results by renewal need, descending
                all_high_risk_results.sort(key=lambda x: x['renewal_need'], reverse=True)

                self.results_dialog = ResultsDialog(parent=self.iface.mainWindow(), hotspot_count=hotspot_count)
                self.results_dialog.zoom_to_feature_signal.connect(self._handle_zoom_to_feature)
                self.results_dialog.populate_table(all_high_risk_results)
                self.results_dialog.show()

    def _run_hotspot_analysis(self, analysis_configs, threshold, distance):
        self.iface.messageBar().pushMessage("Info", "Startar hotspot-analys...", level=0, duration=3)

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

        # 2. Check if we have enough data to find cross-type hotspots
        active_types = [t for t, geoms in high_risk_features.items() if geoms]
        if len(active_types) < 2:
            self.iface.messageBar().pushMessage("Info", "Inte tillräckligt med högriskledningar från olika ledningstyper för att hitta hotspots.", level=0, duration=5)
            return None

        # 3. Create dissolved buffers for each active type
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
            self.iface.messageBar().pushMessage("Info", "Inga hotspots hittades.", level=0, duration=3)
            return None

        # 5. Combine all found hotspot polygons into a single geometry
        final_hotspots_geom = QgsGeometry.collectGeometry(hotspot_polygons)

        self.iface.messageBar().pushMessage("Success", f"{len(hotspot_polygons)} hotspot-områden identifierade.", level=0, duration=4)

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
