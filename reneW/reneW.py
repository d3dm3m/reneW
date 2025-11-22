import os
from datetime import datetime

from qgis.PyQt.QtWidgets import QAction, QProgressDialog
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtCore import QVariant, Qt
# HOLISTIC IMPORT FIX: All render effects and symbol layers are in qgis.core
from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsField,
    QgsGeometry,
    QgsFeature,
    QgsFillSymbol,
    QgsSimpleFillSymbolLayer,
    QgsSimpleLineSymbolLayer,
    QgsGraduatedSymbolRenderer,
    QgsSymbol,
    QgsRendererRange,
    QgsStyle,
    QgsBlurEffect # Moved from gui to core
)

from .reneW_dialog import ReneWDialog
from .results_dialog import ResultsDialog
from .risk_manager import RiskManager

class ReneW:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor."""
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

        # Connect the Hotspot button signal
        try: self.dlg.mBtnRunHotspot.clicked.disconnect()
        except: pass
        self.dlg.mBtnRunHotspot.clicked.connect(self.run_strategic_hotspots)

        result = self.dlg.exec_()

        if result:
            # If "OK" is clicked, we assume the user wants to run the logic
            # appropriate for the currently active tab.

            # Save settings on successful run
            self.dlg.save_settings()

            current_tab_index = self.dlg.mTabWidget.currentIndex()

            # Tab 0: Risk Calculation
            if current_tab_index == 0:
                self.run_risk_calculation()

            # Tab 1: Coordination & Hotspots
            # (If user clicked OK here, we can also run hotspot analysis,
            # although there is a dedicated button for it)
            elif current_tab_index == 1:
                self.run_strategic_hotspots()

    def run_risk_calculation(self):
        """Executes the risk calculation logic (Tab 1)."""
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

            layer = config['layer']
            layer_name = layer.name()
            progress_dialog.setLabelText(f"Analyserar {layer_name}...")

            def update_progress(percent):
                current_base = i * 100
                progress_dialog.setValue(current_base + percent)

            result = self.risk_manager.execute_analysis(
                layer=layer,
                config=config,
                use_dimension_weighting=use_dimension_weighting,
                dimension_factor=dimension_factor,
                progress_callback=update_progress
            )

            if result['status']:
                self.iface.messageBar().pushMessage("Success", result['message'], level=0, duration=4)
                processed_layers += 1
                all_high_risk_results.extend(result['high_risk_results'])

                # Apply auto-styling to highlight risk
                self._apply_risk_styling(layer)

            else:
                level = 1 if "Error" in result['message'] else 1
                self.iface.messageBar().pushMessage("Error", result['message'], level=level)

        progress_dialog.close()

        if processed_layers > 0:
            self.iface.messageBar().pushMessage("Info", f"Analys slutförd för {processed_layers} lager.", level=0, duration=5)
            self.iface.mapCanvas().refresh()

        # Show results dialog if there are high-risk items
        if all_high_risk_results:
            # Sort by Risk Cost (descending) by default
            all_high_risk_results.sort(key=lambda x: x.get('risk_cost', 0.0), reverse=True)

            self.results_dialog = ResultsDialog(parent=self.iface.mainWindow())
            self.results_dialog.zoom_to_feature_signal.connect(self._handle_zoom_to_feature)
            self.results_dialog.populate_table(all_high_risk_results)
            self.results_dialog.show()

    def run_strategic_hotspots(self):
        """Executes the multi-layer hotspot logic (Tab 2)."""
        # If called via button, we might want to close dialog, or keep it open.
        # If called via "OK", dialog is already closing.
        # Let's assume we run logic and maybe close if triggered by button?
        # Standard practice: "Run" button keeps dialog open?
        # Instruction said: "Click 'Hitta...'" -> implies action.
        # I will run it. If triggered by button, dialog stays open unless I close it.
        # Given the user workflow "Tab 1 Run... Tab 1 Run... Tab 2 Click", keeping it open is fine.

        layers_map = self.dlg.get_hotspot_layers()
        threshold = self.dlg.getHotspotThreshold()
        distance = self.dlg.getHotspotDistance()

        # Filter out None layers
        active_layers = {k: v for k, v in layers_map.items() if v is not None}

        if len(active_layers) < 2:
             self.iface.messageBar().pushMessage("Info", "Välj minst två lager för att hitta samordningsvinster.", level=0, duration=4)
             return

        hotspot_geom = self._run_hotspot_analysis_multi(active_layers, threshold, distance)

        if hotspot_geom:
            first_layer_crs = list(active_layers.values())[0].crs()
            self._create_hotspot_layer(hotspot_geom, first_layer_crs)
            self.iface.messageBar().pushMessage("Success", "Hotspots skapade.", level=0, duration=3)
        else:
            self.iface.messageBar().pushMessage("Info", "Inga hotspots hittades med angivna parametrar.", level=0, duration=3)

    def _run_hotspot_analysis_multi(self, layers_map, threshold, distance):
        """
        Performs intersection analysis on provided layers.
        layers_map: {'Vatten': QgsVectorLayer, ...}
        """
        self.iface.messageBar().pushMessage("Info", "Analyserar samordning...", level=0, duration=3)

        high_risk_geoms = {} # Type -> [QgsGeometry]

        # 1. Filter high-risk features from each layer
        for l_type, layer in layers_map.items():
            field_name = 'fornyelsebehov'
            if layer.fields().indexFromName(field_name) == -1:
                continue

            feats = []
            for feature in layer.getFeatures():
                if feature[field_name] is not None and feature[field_name] >= threshold:
                    if feature.hasGeometry():
                        feats.append(feature.geometry())

            if feats:
                high_risk_geoms[l_type] = feats

        if len(high_risk_geoms) < 2:
            return None

        # 2. Create dissolved buffers
        buffered_geometries = {}
        for l_type, geoms in high_risk_geoms.items():
            combined = QgsGeometry.collectGeometry(geoms)
            buffered = combined.buffer(distance, 5)
            buffered_geometries[l_type] = buffered

        # 3. Intersections
        hotspot_polygons = []
        # Define pairs to check
        pairs = [
            ('Vatten', 'Spillvatten'),
            ('Vatten', 'Dagvatten'),
            ('Spillvatten', 'Dagvatten')
        ]

        for t1, t2 in pairs:
            if t1 in buffered_geometries and t2 in buffered_geometries:
                g1 = buffered_geometries[t1]
                g2 = buffered_geometries[t2]

                intersection = g1.intersection(g2)
                if not intersection.isEmpty():
                    hotspot_polygons.append(intersection)

        if not hotspot_polygons:
            return None

        return QgsGeometry.collectGeometry(hotspot_polygons)

    def _apply_risk_styling(self, layer):
        """Applies a graduated renderer to the layer based on RISK_COST."""
        target_field = 'RISK_COST'
        if layer.fields().indexFromName(target_field) == -1:
            return

        ramp = QgsStyle.defaultStyle().colorRamp('Reds')
        if not ramp:
             ramp = QgsStyle.defaultStyle().colorRamp('Spectral')
             if ramp: ramp.invert()

        renderer = QgsGraduatedSymbolRenderer.createRenderer(
            layer,
            target_field,
            5,
            QgsGraduatedSymbolRenderer.Jenks,
            QgsSymbol.defaultSymbol(layer.geometryType()),
            ramp
        )

        if renderer:
            layer.setRenderer(renderer)
            layer.triggerRepaint()

    def _generate_project_bundles(self, high_risk_results, crs, score_threshold=2.0):
        """
        Clusters high risk features into 'Project Bundles' (Single Layer Logic).
        Kept for Tab 1 individual analysis result generation.
        """
        if not high_risk_results:
            return

        geoms = []
        for item in high_risk_results:
            if item.get('risk_score', 0.0) < score_threshold:
                continue
            layer = QgsProject.instance().mapLayer(item['layer_id'])
            if layer:
                f = layer.getFeature(item['feature_id'])
                if f.hasGeometry():
                    geoms.append(f.geometry())

        if not geoms:
            return

        buffers = [g.buffer(20, 5) for g in geoms]
        combined = QgsGeometry.unaryUnion(buffers)

        if combined.isEmpty():
            return

        project_polygons = []
        if combined.isMultipart():
            project_polygons = combined.asMultiPolygon()
        else:
            project_polygons = [combined.asPolygon()]

        vl = QgsVectorLayer(f"Polygon?crs={crs.authid()}", "Föreslagna Projekt (Enskilda)", "memory")
        pr = vl.dataProvider()
        pr.addAttributes([
            QgsField("TOTAL_RISK", QVariant.Double),
            QgsField("Project_ID", QVariant.Int)
        ])
        vl.updateFields()

        new_features = []
        for i, poly_pts in enumerate(project_polygons):
            poly_geom = QgsGeometry.fromPolygonXY(poly_pts)
            bundle_risk = 0.0

            for item in high_risk_results:
                 layer = QgsProject.instance().mapLayer(item['layer_id'])
                 if layer:
                     f = layer.getFeature(item['feature_id'])
                     if f.hasGeometry() and f.geometry().intersects(poly_geom):
                         bundle_risk += item.get('risk_cost', 0.0)

            feat = QgsFeature()
            feat.setGeometry(poly_geom)
            feat.setAttributes([bundle_risk, i + 1])
            new_features.append(feat)

        pr.addFeatures(new_features)

        symbol = QgsFillSymbol()
        symbol.deleteSymbolLayer(0)
        symbol_layer = QgsSimpleFillSymbolLayer.create({
            'color': '0,0,255,0',
            'outline_color': '0,0,255,255',
            'outline_width': '1.0',
            'style': 'no'
        })
        symbol.appendSymbolLayer(symbol_layer)
        vl.renderer().setSymbol(symbol)

        QgsProject.instance().addMapLayer(vl)
        self.iface.messageBar().pushMessage("Info", f"Skapade {len(new_features)} projektförslag.", level=0, duration=5)

    def _create_hotspot_layer(self, hotspot_geom, crs):
        vl = QgsVectorLayer(f"Polygon?crs={crs.authid()}", "Samordningsvinster (Hotspots)", "memory")
        provider = vl.dataProvider()

        feature = QgsFeature()
        feature.setGeometry(hotspot_geom)
        provider.addFeatures([feature])

        aura_symbol = QgsFillSymbol()
        aura_symbol.deleteSymbolLayer(0)

        for blur_radius, opacity, color in [(12, 20, '255,50,50'), (8, 40, '255,0,0'), (4, 70, '200,0,0')]:
            glow_fill = QgsSimpleFillSymbolLayer.create({'color': f'{color},{opacity}', 'style': 'solid'})
            blur_effect = QgsBlurEffect()
            blur_effect.setBlurRadius(blur_radius)
            glow_fill.setPaintEffect(blur_effect)
            aura_symbol.appendSymbolLayer(glow_fill)

        renderer = vl.renderer()
        renderer.setSymbol(aura_symbol)
        vl.triggerRepaint()

        QgsProject.instance().addMapLayer(vl)
