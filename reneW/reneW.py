import os
from datetime import datetime

from qgis.PyQt.QtWidgets import QAction, QProgressDialog
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtCore import QVariant, Qt

# HOLISTIC IMPORTS: Core, Gui, and Analysis
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
    QgsCategorizedSymbolRenderer,
    QgsRendererCategory,
    QgsSymbol,
    QgsRendererRange,
    QgsStyle
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

    def add_action(self, icon_path, text, callback, enabled_flag=True, add_to_menu=True, add_to_toolbar=True, status_tip=None, whats_this=None, parent=None):
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
        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        self.add_action(
            icon_path,
            text=u'Run reneW',
            callback=self.run,
            parent=self.iface.mainWindow())

    def unload(self):
        for action in self.actions:
            self.iface.removePluginMenu(u'&reneW', action)
            self.iface.removeToolBarIcon(action)
        del self.toolbar

    def _handle_zoom_to_feature(self, layer_id, feature_id):
        layer = QgsProject.instance().mapLayer(layer_id)
        if not layer: return
        layer.selectByIds([feature_id])
        self.iface.mapCanvas().zoomToSelected(layer)
        self.iface.mapCanvas().refresh()

    def run(self):
        """Main entry point."""
        if self.dlg is None:
            self.dlg = ReneWDialog()

        self.dlg.load_settings()

        # Safe connection of the hotspot button (disconnect first to avoid duplicates)
        try: self.dlg.mBtnRunHotspot.clicked.disconnect()
        except: pass
        self.dlg.mBtnRunHotspot.clicked.connect(self.run_strategic_hotspots)

        self.dlg.show()
        result = self.dlg.exec_()

        if result:
            self.dlg.save_settings()
            # Only run calculation if we are on the Risk tab (Index 0)
            if self.dlg.mTabWidget.currentIndex() == 0:
                self._run_single_layer_analysis()

    def _run_single_layer_analysis(self):
        """Handles the Tab 1 (Risk Calculation) logic."""
        analysis_configs = self.dlg.get_analysis_configs()
        use_dim_weight = self.dlg.useDimensionWeighting()
        dim_factor = self.dlg.dimensionFactor()

        if not analysis_configs:
            self.iface.messageBar().pushMessage("Info", "Inga lager valdes för analys.", level=0, duration=3)
            return

        processed = 0
        all_results = []

        # Progress Dialog
        steps = len(analysis_configs) * 100
        pd = QProgressDialog("Analyserar ledningsnät...", "Avbryt", 0, steps, self.iface.mainWindow())
        pd.setWindowModality(Qt.WindowModal)
        pd.show()

        for i, config in enumerate(analysis_configs):
            if pd.wasCanceled(): break

            def update_p(p): pd.setValue(i * 100 + p)

            res = self.risk_manager.execute_analysis(
                layer=config['layer'],
                config=config,
                use_dimension_weighting=use_dim_weight,
                dimension_factor=dim_factor,
                progress_callback=update_p
            )

            if res['status']:
                self.iface.messageBar().pushMessage("Success", res['message'], level=0, duration=4)
                processed += 1
                all_results.extend(res['high_risk_results'])
                self._apply_risk_styling(config['layer'])
            else:
                self.iface.messageBar().pushMessage("Error", res['message'], level=1)

        pd.close()

        if all_results:
            self._generate_project_bundles(all_results, analysis_configs[0]['layer'].crs())
            all_results.sort(key=lambda x: x.get('risk_cost', 0.0), reverse=True)
            self.results_dialog = ResultsDialog(parent=self.iface.mainWindow(), hotspot_count=0)
            self.results_dialog.zoom_to_feature_signal.connect(self._handle_zoom_to_feature)
            self.results_dialog.populate_table(all_results)
            self.results_dialog.show()

    def run_strategic_hotspots(self):
        """Handles the Tab 2 (Coordination) logic."""
        layers_map = self.dlg.get_hotspot_layers() # Returns dict {'Vatten': layer, ...}
        threshold = self.dlg.getHotspotThreshold()
        distance = self.dlg.getHotspotDistance()

        # Filter out None layers
        valid_layers = [l for l in layers_map.values() if l is not None]

        if len(valid_layers) < 2:
            self.iface.messageBar().pushMessage("Info", "Välj minst 2 lager för samordning.", level=0, duration=3)
            return

        self.iface.messageBar().pushMessage("Info", "Beräknar samordningsvinster...", level=0, duration=3)

        hotspot_features = self._run_hotspot_analysis_multi(valid_layers, threshold, distance)

        if hotspot_features:
            self._create_hotspot_layer_categorized(hotspot_features, valid_layers[0].crs())
            self.iface.messageBar().pushMessage("Success", "Samordningslager skapat!", level=0, duration=3)
        else:
            self.iface.messageBar().pushMessage("Info", "Inga överlapp hittades.", level=0, duration=3)

    def _run_hotspot_analysis_multi(self, layers, threshold, distance):
        """
        Calculates Triple (Level 3) and Pairwise (Level 2) intersections.
        """
        # 1. Extract High Risk Geometries per Layer
        layer_geoms = {} # {layer_id: QgsGeometry(Dissolved Buffer)}

        for layer in layers:
            idx = layer.fields().indexFromName('fornyelsebehov')
            if idx == -1: continue

            raw_geoms = []
            for f in layer.getFeatures():
                if f[idx] is not None and f[idx] >= threshold and f.hasGeometry():
                    raw_geoms.append(f.geometry())

            if raw_geoms:
                # Collect -> Buffer -> Dissolve (UnaryUnion)
                combined = QgsGeometry.unaryUnion(raw_geoms)
                buffered = combined.buffer(distance, 5)
                layer_geoms[layer.id()] = buffered

        if len(layer_geoms) < 2: return []

        keys = list(layer_geoms.keys())
        results = [] # List of (geometry, synergy_level)

        # 2. Triple Intersection (If 3 layers exist)
        triple_geom = None
        if len(keys) == 3:
            g1, g2, g3 = layer_geoms[keys[0]], layer_geoms[keys[1]], layer_geoms[keys[2]]
            triple_geom = g1.intersection(g2).intersection(g3)

            if not triple_geom.isEmpty():
                results.append((triple_geom, 3))

        # 3. Pairwise Intersections (Difference from Triple)
        import itertools
        for id1, id2 in itertools.combinations(keys, 2):
            g1 = layer_geoms[id1]
            g2 = layer_geoms[id2]

            pair_geom = g1.intersection(g2)

            # Subtract triple overlap if it exists to avoid double-counting
            if triple_geom and not triple_geom.isEmpty():
                pair_geom = pair_geom.difference(triple_geom)

            if not pair_geom.isEmpty():
                results.append((pair_geom, 2))

        return results

    def _create_hotspot_layer_categorized(self, features_data, crs):
        """Creates a memory layer styled by Synergy Level (3=Purple, 2=Red)."""
        vl = QgsVectorLayer(f"Polygon?crs={crs.authid()}", "Strategiska Hotspots", "memory")
        pr = vl.dataProvider()
        pr.addAttributes([QgsField("Synergy_Level", QVariant.Int)])
        vl.updateFields()

        new_feats = []
        for geom, level in features_data:
            if geom.isMultipart():
                parts = geom.asMultiPolygon()
            else:
                parts = [geom.asPolygon()]

            for poly in parts:
                f = QgsFeature()
                f.setGeometry(QgsGeometry.fromPolygonXY(poly))
                f.setAttributes([level])
                new_feats.append(f)

        pr.addFeatures(new_feats)

        # Styling: Categorized
        categories = []

        # Level 3: Purple (Triple Win)
        sym3 = QgsSymbol.defaultSymbol(vl.geometryType())
        sym3.setColor(QColor(128, 0, 128, 150)) # Purple, semi-transparent
        cat3 = QgsRendererCategory(3, sym3, "3 Discipliner (Högst Prio)")
        categories.append(cat3)

        # Level 2: Red (Double Win)
        sym2 = QgsSymbol.defaultSymbol(vl.geometryType())
        sym2.setColor(QColor(255, 0, 0, 150)) # Red, semi-transparent
        cat2 = QgsRendererCategory(2, sym2, "2 Discipliner")
        categories.append(cat2)

        renderer = QgsCategorizedSymbolRenderer("Synergy_Level", categories)
        vl.setRenderer(renderer)

        QgsProject.instance().addMapLayer(vl)

    def _apply_risk_styling(self, layer):
        target_field = 'RISK_COST'
        if layer.fields().indexFromName(target_field) == -1: return

        ramp = QgsStyle.defaultStyle().colorRamp('Reds')
        if not ramp:
             ramp = QgsStyle.defaultStyle().colorRamp('Spectral')
             if ramp: ramp.invert()

        renderer = QgsGraduatedSymbolRenderer.createRenderer(
            layer, target_field, 5,
            QgsGraduatedSymbolRenderer.Jenks,
            QgsSymbol.defaultSymbol(layer.geometryType()), ramp
        )
        if renderer:
            layer.setRenderer(renderer)
            layer.triggerRepaint()

    def _generate_project_bundles(self, high_risk_results, crs, score_threshold=2.0):
        """Clusters individual high risk features (Tab 1)."""
        if not high_risk_results: return

        geoms = []
        for item in high_risk_results:
            if item.get('risk_score', 0.0) < score_threshold: continue
            layer = QgsProject.instance().mapLayer(item['layer_id'])
            if layer:
                f = layer.getFeature(item['feature_id'])
                if f.hasGeometry(): geoms.append(f.geometry())

        if not geoms: return

        buffers = [g.buffer(20, 5) for g in geoms]
        combined = QgsGeometry.unaryUnion(buffers)
        if combined.isEmpty(): return

        project_polygons = []
        if combined.isMultipart(): project_polygons = combined.asMultiPolygon()
        else: project_polygons = [combined.asPolygon()]

        vl = QgsVectorLayer(f"Polygon?crs={crs.authid()}", "Föreslagna Projekt (Enskilda)", "memory")
        pr = vl.dataProvider()
        pr.addAttributes([QgsField("TOTAL_RISK", QVariant.Double), QgsField("Project_ID", QVariant.Int)])
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
            'color': '0,0,255,0', 'outline_color': '0,0,255,255', 'outline_width': '1.0', 'style': 'no'
        })
        symbol.appendSymbolLayer(symbol_layer)
        vl.renderer().setSymbol(symbol)
        QgsProject.instance().addMapLayer(vl)
