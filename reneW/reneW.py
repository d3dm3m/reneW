import os
import re
from datetime import datetime

from qgis.PyQt.QtWidgets import QAction, QProgressBar
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QCoreApplication, Qt, QVariant
from qgis.PyQt.QtGui import QColor
# --- Core QGIS Modules ---
from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsField,
    QgsFields,
    QgsFeature,
    QgsFeatureRequest,
    QgsProcessing,
    QgsProcessingFeedback,
    QgsVectorLayerTemporalProperties,
    QgsMessageLog,
    Qgis,
    QgsSymbol,
    QgsFillSymbol,
    QgsCategorizedSymbolRenderer,
    QgsGraduatedSymbolRenderer,
    QgsRendererRange,
    QgsRuleBasedRenderer,
    QgsStyle
)

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

    def _friendly_pipe_label(self, pipe_type: str) -> str:
        """Return a user-friendly label for pipe types."""
        mapping = {
            'water': 'Water',
            'sewer/spill': 'Wastewater',
            'sewer/storm': 'Stormwater'
        }
        return mapping.get(pipe_type.lower(), pipe_type)

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
        """Run method that configures and dispatches the analysis."""
        try:
            param_path = os.path.join(self.plugin_dir, 'parameters.json')
            params_data = material_lookup.load_parameters(param_path)
        except Exception as e:
            self.iface.messageBar().pushMessage(
                tr("Error"),
                tr("Failed to load or parse parameters.json: {0}").format(e),
                Qgis.Critical, duration=10)
            return

        if self.dlg is None:
            self.dlg = ReneWDialog(self.iface.mainWindow())

        self.dlg.load_settings()
        self.dlg.show()
        result = self.dlg.exec()

        if result:
            self.dlg.save_settings()
            if self.dlg.useTemporalAnalysis():
                self._run_temporal_analysis(params_data)
            else:
                self._run_standard_analysis(params_data)

    def _run_standard_analysis(self, params_data):
        """Performs the standard, single-year renewal need analysis."""
        analysis_configs = self.dlg.get_analysis_configs()
        if not analysis_configs:
            self.iface.messageBar().pushMessage(tr("Info"), tr("No layers selected for analysis."), Qgis.Info, duration=3)
            return

        QgsMessageLog.logMessage(tr("Starting reneW standard analysis."), 'reneW', Qgis.Info)
        # ... (rest of the standard analysis logic)
        use_dimension_weighting = self.dlg.useDimensionWeighting()
        dimension_factor = self.dlg.dimensionFactor()
        selected_municipality_code = self.dlg.get_selected_municipality_code()

        total_features = sum(config['layer'].featureCount() for config in analysis_configs)
        progress_bar = QProgressBar()
        progress_bar.setMaximum(total_features)
        progress_bar.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
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

            domain = 'water' if 'water' in config['type'].lower() else 'sewer'
            subtype = 'spill' if 'spill' in config['type'].lower() else ('storm' if 'storm' in config['type'].lower() else None)
            pipe_type_name = config['type']
            friendly_pipe = self._friendly_pipe_label(pipe_type_name)

            output_field_name = 'fornyelsebehov'
            provider = layer.dataProvider()
            fields = provider.fields()

            if fields.indexFromName(output_field_name) == -1:
                provider.addAttributes([QgsField(output_field_name, QVariant.Double)])
                layer.updateFields()

            required_fields = ['material_field', 'year_field', 'dimension_field']
            if not all(config.get(f) for f in required_fields):
                self.iface.messageBar().pushMessage(tr("Error"), tr("A required field is not selected for layer '{0}'. Skipping.").format(layer_name), Qgis.Warning)
                continue

            field_indices = {f: fields.indexFromName(config[f]) for f in required_fields if config.get(f)}
            if config.get('reno_year_field'):
                field_indices['reno_year_field'] = fields.indexFromName(config['reno_year_field'])
            if config.get('reno_method_field'):
                field_indices['reno_method_field'] = fields.indexFromName(config['reno_method_field'])

            muni_idx = fields.indexFromName(config['municipality_field']) if config.get('municipality_field') else -1
            output_idx = fields.indexFromName(output_field_name)

            layer.startEditing()
            for feature in layer.getFeatures():
                processed_features += 1
                progress_bar.setValue(processed_features)
                attrs = feature.attributes()

                if selected_municipality_code is not None and muni_idx != -1 and attrs[muni_idx] != selected_municipality_code:
                    continue

                year_val = attrs[field_indices['year_field']]
                if year_val is None or str(year_val).strip() in ['1900', 'null', 'NULL']:
                    continue
                try:
                    installation_year = int(year_val)
                except (ValueError, TypeError):
                    continue

                effective_install_year = installation_year
                has_been_renovated = False
                if 'reno_year_field' in field_indices:
                    reno_year_val = attrs[field_indices['reno_year_field']]
                    if reno_year_val:
                        try:
                            renovation_year = int(reno_year_val)
                            if renovation_year > installation_year:
                                effective_install_year = renovation_year
                                has_been_renovated = True
                        except (ValueError, TypeError):
                            pass

                age = max(0, current_year - effective_install_year)
                material_name = attrs[field_indices['material_field']]
                try:
                    key, params = material_lookup.find_material_key(params_data, domain=domain, subtype=subtype, material_name=str(material_name))
                except KeyError as e:
                    QgsMessageLog.logMessage(f"Material lookup failed for '{material_name}': {e}", 'reneW', Qgis.Warning)
                    continue

                if has_been_renovated and 'reno_method_field' in field_indices:
                    reno_method_val = attrs[field_indices['reno_method_field']]

                    # Handle both numeric codes and string values for renovation method
                    reno_method_str = ''
                    if isinstance(reno_method_val, (int, float)):
                        # It's a numeric code, try to look it up
                        mapping = params_data.get('renovation_method_mapping', {})
                        reno_method_str = mapping.get(str(int(reno_method_val)))
                    elif isinstance(reno_method_val, str):
                        # It's already a string
                        reno_method_str = reno_method_val

                    if reno_method_str and reno_method_str.strip():
                        liner_result = material_lookup.find_liner_key(params_data, domain=domain, subtype=subtype, method_name=reno_method_str)
                        if liner_result:
                            key, params = liner_result
                            material_name = f"{material_name} (Lined: {reno_method_str})"

                cohort = calculation_logic.Cohort(length_km=1.0, install_year=effective_install_year, material_key=key)
                renewal_need = calculation_logic.renewal_for_cohort_period(cohort, current_year, current_year + 1, params)

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
                        'pipe_type': friendly_pipe,
                        'material': material_name,
                        'age': age,
                        'renewal_need': renewal_need
                    })

            if layer.commitChanges():
                self.iface.messageBar().pushMessage(tr("Success"), tr("Calculation complete for layer '{0}'.").format(layer_name), Qgis.Info, duration=4)
                processed_layers += 1
            else:
                layer.rollBack()
                self.iface.messageBar().pushMessage(tr("Error"), tr("Could not save changes for layer '{0}'.").format(layer_name), Qgis.Warning)

        self.iface.messageBar().clearWidgets()
        if processed_layers > 0:
            self.iface.messageBar().pushMessage(tr("Info"), tr("Analysis complete for {0} layers.").format(processed_layers), Qgis.Info, duration=5)
            self.iface.mapCanvas().refresh()

        hotspot_layer = None
        if self.dlg.useHotspotAnalysis():
            hotspot_threshold = self.dlg.hotspotThreshold()
            hotspot_radius = self.dlg.hotspotRadius()
            hotspot_layer = self._run_hotspot_analysis(analysis_configs, hotspot_threshold, hotspot_radius)
            if hotspot_layer:
                QgsProject.instance().addMapLayer(hotspot_layer)
                self.iface.messageBar().pushMessage(tr("Success"), tr("Hotspot analysis complete."), Qgis.Info, duration=4)

        if high_risk_results:
            high_risk_results.sort(key=lambda x: x['renewal_need'], reverse=True)
            hotspot_count = hotspot_layer.featureCount() if hotspot_layer else 0
            self.results_dialog = ResultsDialog(parent=self.iface.mainWindow(), hotspot_count=hotspot_count)
            self.results_dialog.zoom_to_feature_signal.connect(self._handle_zoom_to_feature)
            self.results_dialog.populate_table(high_risk_results)
            self.results_dialog.show()

        QgsMessageLog.logMessage(tr("reneW standard analysis finished."), 'reneW', Qgis.Success)

    def _run_temporal_analysis(self, params_data):
        """Performs the time-series analysis and creates a new time-aware layer."""
        analysis_configs = self.dlg.get_analysis_configs()
        if not analysis_configs:
            self.iface.messageBar().pushMessage(tr("Info"), tr("No layers selected for analysis."), Qgis.Info, duration=3)
            return

        QgsMessageLog.logMessage(tr("Starting reneW temporal analysis."), 'reneW', Qgis.Info)

        start_year = self.dlg.temporalStartYear()
        end_year = self.dlg.temporalEndYear()
        step = self.dlg.temporalStep()

        # Define fields for the new layer
        fields = QgsFields()
        fields.append(QgsField("pipe_id", QVariant.String))
        fields.append(QgsField("source_layer", QVariant.String))
        fields.append(QgsField("year", QVariant.Int))
        fields.append(QgsField("pipe_type", QVariant.String))
        fields.append(QgsField("renewal_need", QVariant.Double))

        # Create the memory layer
        temporal_layer = QgsVectorLayer(f"LineString?crs={QgsProject.instance().crs().authid()}", "Temporal Renewal Need", "memory")
        provider = temporal_layer.dataProvider()
        provider.addAttributes(fields)
        temporal_layer.updateFields()

        # --- Progress Bar Setup ---
        total_calcs = 0
        for config in analysis_configs:
            total_calcs += config['layer'].featureCount() * len(range(start_year, end_year + 1, step))

        progress_bar = QProgressBar()
        progress_bar.setMaximum(total_calcs)
        progress_bar.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        message_bar_item = self.iface.messageBar().createMessage(tr("Calculating temporal renewal need..."))
        message_bar_item.layout().addWidget(progress_bar)
        self.iface.messageBar().pushWidget(message_bar_item, Qgis.Info)
        processed_calcs = 0

        # --- Main Processing Loop ---
        temporal_layer.startEditing()
        for config in analysis_configs:
            layer = config['layer']
            layer_name = layer.name()

            domain = 'water' if 'water' in config['type'].lower() else 'sewer'
            subtype = 'spill' if 'spill' in config['type'].lower() else ('storm' if 'storm' in config['type'].lower() else None)
            pipe_type_name = config['type']

            required_fields = ['material_field', 'year_field']
            if not all(config.get(f) for f in required_fields):
                continue # Skip if essential fields are missing

            field_indices = {f: layer.fields().indexFromName(config[f]) for f in required_fields if config.get(f)}
            if config.get('reno_year_field'):
                field_indices['reno_year_field'] = layer.fields().indexFromName(config['reno_year_field'])
            if config.get('reno_method_field'):
                field_indices['reno_method_field'] = layer.fields().indexFromName(config['reno_method_field'])

            for feature in layer.getFeatures():
                attrs = feature.attributes()

                year_val = attrs[field_indices['year_field']]
                if year_val is None or str(year_val).strip() in ['1900', 'null', 'NULL']:
                    continue
                try:
                    installation_year = int(year_val)
                except (ValueError, TypeError):
                    continue

                effective_install_year = installation_year
                if 'reno_year_field' in field_indices:
                    reno_year_val = attrs[field_indices['reno_year_field']]
                    if reno_year_val:
                        try:
                            renovation_year = int(reno_year_val)
                            if renovation_year > installation_year:
                                effective_install_year = renovation_year
                        except (ValueError, TypeError):
                            pass

                material_name = str(attrs[field_indices['material_field']])
                try:
                    key, params = material_lookup.find_material_key(params_data, domain=domain, subtype=subtype, material_name=material_name)
                except KeyError as e:
                    QgsMessageLog.logMessage(f"Material lookup failed for '{material_name}': {e}", 'reneW', Qgis.Warning)
                    continue

                for year in range(start_year, end_year + 1, step):
                    processed_calcs += 1
                    progress_bar.setValue(processed_calcs)

                    cohort = calculation_logic.Cohort(length_km=1.0, install_year=effective_install_year, material_key=key)
                    renewal_need = calculation_logic.renewal_for_cohort_period(cohort, year, year + 1, params)

                    # Create a new feature for the temporal layer
                    out_feat = QgsFeature(fields)
                    out_feat.setGeometry(feature.geometry())
                    out_feat.setAttributes([
                        feature.id(),
                        layer_name,
                        year,
                        pipe_type_name,
                        renewal_need
                    ])
                    provider.addFeature(out_feat)

        temporal_layer.commitChanges()
        self.iface.messageBar().clearWidgets()

        self._style_temporal_layer(temporal_layer)
        QgsProject.instance().addMapLayer(temporal_layer)
        self.iface.messageBar().pushMessage(tr("Success"), tr("Temporal analysis layer created."), Qgis.Info, duration=5)

        QgsMessageLog.logMessage(tr("reneW temporal analysis finished."), 'reneW', Qgis.Success)

    def _style_temporal_layer(self, layer):
        """
        Applies a rule-based bivariate renderer and temporal configuration to the output layer.
        Fully version-aware and robust against future QGIS API changes for QgsRuleBasedRenderer.
        """

        from qgis.core import Qgis, QgsSymbol, QgsRuleBasedRenderer, QgsVectorLayerTemporalProperties
        from qgis.PyQt.QtGui import QColor

        # --- 1. Create the root rule ---
        root_symbol = QgsSymbol.defaultSymbol(layer.geometryType())
        root_rule = QgsRuleBasedRenderer.Rule(root_symbol)

        # --- 2. Create the renderer with a resilient version-aware approach ---
        renderer = None

        if Qgis.QGIS_VERSION_INT >= 39900:
            # Known API change in QGIS 3.99+ — requires root rule
            try:
                renderer = QgsRuleBasedRenderer(root_rule)
            except TypeError:
                # If future QGIS removes the constructor, try using a factory method if present
                if hasattr(QgsRuleBasedRenderer, "create"):
                    renderer = QgsRuleBasedRenderer.create(root_rule)
                else:
                    raise
        else:
            # Pre-3.99 path — still prefer passing a root rule for consistency
            try:
                renderer = QgsRuleBasedRenderer(root_rule)
            except TypeError:
                if hasattr(QgsRuleBasedRenderer, "create"):
                    renderer = QgsRuleBasedRenderer.create(root_rule)
                else:
                    raise

        # --- 3. Define categories and color ramps ---
        categories = {
            'water': {
                'label': 'Water',
                'colors': ['#eff3ff', '#bdd7e7', '#6baed6', '#3182bd', '#08519c']
            },
            'sewer/spill': {
                'label': 'Wastewater',
                'colors': ['#fee5d9', '#fcae91', '#fb6a4a', '#de2d26', '#a50f15']
            },
            'sewer/storm': {
                'label': 'Stormwater',
                'colors': ['#e5f5e0', '#a1d99b', '#74c476', '#31a354', '#006d2c']
            }
        }

        range_data = [
            (0.0, 0.2, 'Very Low Need (0.0 - 0.2)'),
            (0.2, 0.4, 'Low Need (0.2 - 0.4)'),
            (0.4, 0.6, 'Medium Need (0.4 - 0.6)'),
            (0.6, 0.8, 'High Need (0.6 - 0.8)'),
            (0.8, 1.01, 'Very High Need (0.8 - 1.0)')
        ]

        # --- 4. Build rules ---
        # Ensure clean slate
        try:
            root_rule.deleteChildren()
        except Exception:
            # If method not available, manually remove children
            while getattr(root_rule, "children", lambda: [])():
                root_rule.removeChildAt(0)

        for pipe_type, style_info in categories.items():
            parent_rule = root_rule.clone()
            parent_rule.setLabel(style_info['label'])
            parent_rule.setSymbol(None)

            for i, (lower, upper, label) in enumerate(range_data):
                expression = (
                    f"\"pipe_type\" = '{pipe_type}' AND "
                    f"\"renewal_need\" >= {lower} AND \"renewal_need\" < {upper}"
                )

                symbol = QgsSymbol.defaultSymbol(layer.geometryType())
                if symbol:
                    # QColor hex works across Qt5/Qt6
                    symbol.setColor(QColor(style_info['colors'][i]))
                    # setWidth exists for line symbols; for other geometries, it's ignored
                    try:
                        symbol.setWidth(0.5)
                    except Exception:
                        pass

                child_rule = QgsRuleBasedRenderer.Rule(symbol, filterExp=expression, label=label)
                parent_rule.appendChild(child_rule)

            root_rule.appendChild(parent_rule)

        # Remove any initial placeholder rule if present
        try:
            if root_rule.children():
                root_rule.removeChildAt(0)
        except Exception:
            pass

        # --- 5. Apply renderer ---
        layer.setRenderer(renderer)

        # --- 6. Configure temporal properties ---
        temporal_props = layer.temporalProperties()

        # Handle QGIS API differences in temporal mode
        if hasattr(QgsVectorLayerTemporalProperties, "ModeFeature"):
            # Older QGIS (<= 3.30)
            temporal_props.setMode(QgsVectorLayerTemporalProperties.ModeFeature)
        elif hasattr(QgsVectorLayerTemporalProperties, "ModeFeatureBased"):
            # Newer QGIS (>= 3.99)
            temporal_props.setMode(QgsVectorLayerTemporalProperties.ModeFeatureBased)
        else:
            # Graceful fallback if enum renamed again
            QgsMessageLog.logMessage(
                "reneW: Could not determine temporal mode enum; layer may not animate correctly.",
                "reneW",
                Qgis.Warning
            )

        temporal_props.setStartField("year")
        temporal_props.setEndField("year")
        temporal_props.setIsActive(True)

    def _run_hotspot_analysis(self, analysis_configs, threshold, distance):
        """
        Runs a hotspot analysis on the layers that have been processed.
        """

        # Choose processing runner with graceful fallback
        try:
            import processing  # QGIS processing plugin
            run_algo = processing.run
        except Exception:
            # Fallback to core API helper if available
            from qgis.core import QgsProcessing
            run_algo = QgsProcessing.run
        feedback = QgsProcessingFeedback()
        high_risk_layers = []
        project_crs = QgsProject.instance().crs()

        # Step 1: Create temporary layers of high-risk features for each input layer
        for config in analysis_configs:
            layer = config['layer']
            expr = f"\"fornyelsebehov\" >= {threshold}"

            # Create a memory layer with only the features matching the expression
            temp_layer = layer.clone()
            temp_layer.setName(f"high_risk_{layer.name()}")

            # Request features with the filter
            request = QgsFeatureRequest().setFilterExpression(expr)

            # Use a data provider to add features to the temp layer
            temp_provider = temp_layer.dataProvider()
            temp_layer.startEditing()
            temp_provider.addFeatures(layer.getFeatures(request))
            temp_layer.commitChanges()

            if temp_layer.featureCount() > 0:
                high_risk_layers.append(temp_layer)

        if not high_risk_layers:
            self.iface.messageBar().pushMessage(tr("Info"), tr("No features found above the risk threshold for hotspot analysis."), Qgis.Info)
            return None

        # Step 2: Merge high-risk feature layers into one
        merged_layer_path = 'memory:merged_high_risk'
        merge_params = {'LAYERS': high_risk_layers, 'CRS': project_crs, 'OUTPUT': merged_layer_path}
        merged_result = run_algo("native:mergevectorlayers", merge_params, feedback=feedback)
        merged_layer = merged_result['OUTPUT']

        # Step 3: Buffer the merged layer
        buffered_layer_path = 'memory:buffered'
        buffer_params = {'INPUT': merged_layer, 'DISTANCE': distance, 'SEGMENTS': 8, 'DISSOLVE': False, 'OUTPUT': buffered_layer_path}
        buffered_result = run_algo("native:buffer", buffer_params, feedback=feedback)
        buffered_layer = buffered_result['OUTPUT']

        # Step 4: Dissolve the buffered layer to create hotspots
        dissolved_layer_path = 'memory:dissolved_hotspots'
        dissolve_params = {'INPUT': buffered_layer, 'OUTPUT': dissolved_layer_path}
        dissolved_result = run_algo("native:dissolve", dissolve_params, feedback=feedback)
        dissolved_layer = dissolved_result['OUTPUT']

        # Step 5: Calculate statistics for each hotspot
        stats_layer_path = 'memory:hotspots_with_stats'
        stats_params = {
            'INPUT': dissolved_layer,
            'JOIN': merged_layer,
            'PREDICATE': [0],  # Intersects
            'JOIN_FIELDS': ['fornyelsebehov'],
            'SUMMARIES': [5, 6],  # Count, Mean
            'DISCARD_NONMATCHING': True,
            'OUTPUT': stats_layer_path
        }
        stats_result = run_algo("native:joinattributesbylocation", stats_params, feedback=feedback)
        stats_layer = stats_result['OUTPUT']

        # Rename fields for clarity
        stats_layer.startEditing()
        stats_layer.renameAttribute(stats_layer.fields().lookupField('fornyelsebehov_count'), 'pipe_count')
        stats_layer.renameAttribute(stats_layer.fields().lookupField('fornyelsebehov_mean'), 'avg_renewal_need')
        stats_layer.commitChanges()

        # Final styling
        symbol = QgsFillSymbol.createSimple({'color': '255,0,0,70', 'outline_color': 'red', 'outline_width': '0.5'})
        stats_layer.renderer().setSymbol(symbol)
        stats_layer.setName(tr("Hotspots"))

        return stats_layer
