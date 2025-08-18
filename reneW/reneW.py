# CRITICAL STRUCTURAL FIXES for reneW.py

import os
import re
from datetime import datetime

from qgis.PyQt.QtWidgets import QAction, QProgressBar
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtCore import QCoreApplication, Qt, QVariant, QDate, QTime, QDateTime

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
    QgsStyle,
    QgsClassificationQuantile,
    QgsRendererCategory
)

# Import the code for the dialog and the calculation logic
from .reneW_dialog import ReneWDialog
from .results_dialog import ResultsDialog
from .hotspot_explorer_dialog import HotspotExplorerDialog
from . import calculation_logic
from . import material_lookup

def tr(message):
    """Get the translation for a string using Qt translation API."""
    return QCoreApplication.translate('ReneW', message)


# --- Helper for Qt5/Qt6 alignment ---
def get_alignment():
    try:
        return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
    except AttributeError:
        return Qt.AlignLeft | Qt.AlignVCenter

def get_iso_format():
    try:
        return Qt.DateFormat.ISODate  # Qt6+
    except AttributeError:
        return Qt.ISODate  # Qt5 fallback

class ReneW:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor."""
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

    def _parse_pipe_type(self, pipe_type_name: str):
        """Normalize pipe type string into (domain, subtype, friendly_type)."""
        pt = pipe_type_name.lower().strip()
        if pt == "water":
            return ("water", None, "water")
        elif pt in ("sewer", "sewer/spill", "wastewater"):
            return ("sewer", "spill", "sewer")
        elif pt in ("sewer/storm", "stormwater"):
            return ("sewer", "storm", "stormwater")
        else:
            # fallback
            return ("sewer", None, pipe_type_name)

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

    def _calculate_score(self, pipe_type, feature, pipe_age, dim_field=None):
        """
        Compute renewal need score as a normalized risk value [0–100],
        then bucket it into discrete levels: Low, Medium, High.
        """
        # Base score factors
        age_factor = min(pipe_age / 100.0, 1.0) * 50  # up to 50 points
        dim_factor = 0

        if dim_field and feature[dim_field]:
            try:
                dim_val = float(feature[dim_field])
                # smaller diameters get higher risk
                if dim_val < 200:
                    dim_factor = 30
                elif dim_val < 400:
                    dim_factor = 15
            except (ValueError, TypeError):
                pass

        type_factor = {
            "water": 10,
            "sewer": 20,  # Fixed: was "spill"
            "stormwater": 15,  # Fixed: was "storm"
        }.get(pipe_type.lower(), 5)

        raw_score = age_factor + dim_factor + type_factor
        score = min(raw_score, 100)

        # Bucket into categories
        if score < 33:
            bucket = 1  # Low
        elif score < 66:
            bucket = 2  # Medium
        else:
            bucket = 3  # High

        return bucket

    def add_action(self, icon_path, text, callback, enabled_flag=True, add_to_menu=True,
                   add_to_toolbar=True, status_tip=None, whats_this=None, parent=None):
        """Add a toolbar icon to the toolbar."""
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
            self.iface.messageBar().pushMessage(
                tr("Info"),
                tr("No layers selected for analysis."),
                Qgis.Info, duration=3
            )
            return

        QgsMessageLog.logMessage(tr("Starting reneW standard analysis."), 'reneW', Qgis.Info)

        use_dimension_weighting = self.dlg.useDimensionWeighting()
        dimension_factor = self.dlg.dimensionFactor()
        selected_municipality_code = self.dlg.get_selected_municipality_code()

        total_features = sum(config['layer'].featureCount() for config in analysis_configs)
        progress_bar = QProgressBar()
        progress_bar.setMaximum(total_features)
        progress_bar.setAlignment(get_alignment())
        message_bar_item = self.iface.messageBar().createMessage(tr("Calculating renewal need..."))
        message_bar_item.layout().addWidget(progress_bar)
        self.iface.messageBar().pushWidget(message_bar_item, Qgis.Info)

        processed_features = 0
        processed_layers = 0
        high_risk_results = []
        current_year = datetime.now().year
        output_field_name_for_hotspot = 'renewal_need'

        for config in analysis_configs:
            layer = config['layer']
            layer_name = layer.name()
            QgsMessageLog.logMessage(tr("Processing layer: {0}").format(layer_name), 'reneW', Qgis.Info)

            domain, subtype, pipe_type_name = self._parse_pipe_type(config['type'])
            friendly_pipe = self._friendly_pipe_label(pipe_type_name)

            output_field_name = 'renewal_need'
            legacy_field_name = 'fornyelsebehov'
            provider = layer.dataProvider()
            fields = provider.fields()

            # Backward compatibility: if legacy field exists, reuse it
            if fields.indexFromName(output_field_name) == -1:
                if fields.indexFromName(legacy_field_name) != -1:
                    output_field_name = legacy_field_name
                    output_field_name_for_hotspot = legacy_field_name
                else:
                    provider.addAttributes([QgsField(output_field_name, QVariant.Double)])
                    layer.updateFields()

            required_fields = ['material_field', 'year_field', 'dimension_field']
            if not all(config.get(f) for f in required_fields):
                self.iface.messageBar().pushMessage(
                    tr("Error"),
                    tr("A required field is not selected for layer '{0}'. Skipping.").format(layer_name),
                    Qgis.Warning
                )
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

                if domain == "water":
                    optimism_factor = self.dlg.waterOptimismFactor()
                elif domain == "sewer" and subtype == "spill":
                    optimism_factor = self.dlg.wastewaterOptimismFactor()
                elif domain == "sewer" and subtype == "storm":
                    optimism_factor = self.dlg.stormwaterOptimismFactor()
                else:
                    optimism_factor = 1.0  # fallback

                age = max(0, current_year - effective_install_year)
                adjusted_age = age / optimism_factor
                adjusted_install_year = current_year - int(adjusted_age)

                material_name = attrs[field_indices['material_field']]
                try:
                    key, params = material_lookup.find_material_key(
                        params_data, domain=domain, subtype=subtype, material_name=str(material_name)
                    )
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
                        liner_result = material_lookup.find_liner_key(
                            params_data, domain=domain, subtype=subtype, method_name=reno_method_str
                        )
                        if liner_result:
                            key, params = liner_result
                            material_name = f"{material_name} (Lined: {reno_method_str})"

                cohort = calculation_logic.Cohort(
                    length_km=1.0, install_year=adjusted_install_year, material_key=key
                )
                renewal_need = calculation_logic.renewal_for_cohort_period(
                    cohort, current_year, current_year + 1, params
                )

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
                        'renewal_need': renewal_need,
                        'optimism_factor': optimism_factor
                    })

            if layer.commitChanges():
                self.iface.messageBar().pushMessage(
                    tr("Success"),
                    tr("Calculation complete for layer '{0}'.").format(layer_name),
                    Qgis.Info, duration=4
                )
                processed_layers += 1
            else:
                layer.rollBack()
                self.iface.messageBar().pushMessage(
                    tr("Error"),
                    tr("Could not save changes for layer '{0}'.").format(layer_name),
                    Qgis.Warning
                )

        self.iface.messageBar().clearWidgets()
        if processed_layers > 0:
            self.iface.messageBar().pushMessage(
                tr("Info"),
                tr("Analysis complete for {0} layers.").format(processed_layers),
                Qgis.Info, duration=5
            )
            self.iface.mapCanvas().refresh()

        hotspot_layer = None
        if self.dlg.useHotspotAnalysis():
            hotspot_threshold = self.dlg.hotspotThreshold()
            hotspot_radius = self.dlg.hotspotRadius()
            hotspot_layer = self._run_hotspot_analysis(
                analysis_configs, hotspot_threshold, hotspot_radius, output_field_name_for_hotspot
            )
            if hotspot_layer:
                QgsProject.instance().addMapLayer(hotspot_layer)
                hotspot_layer.selectionChanged.connect(lambda ids, _, __: self._open_hotspot_explorer(hotspot_layer, ids, analysis_configs))
                self.iface.messageBar().pushMessage(
                    tr("Success"),
                    tr("Hotspot analysis complete."),
                    Qgis.Info, duration=4
                )

        if high_risk_results:
            high_risk_results.sort(key=lambda x: x['renewal_need'], reverse=True)
            hotspot_count = hotspot_layer.featureCount() if hotspot_layer else 0
            self.results_dialog = ResultsDialog(parent=self.iface.mainWindow(), hotspot_count=hotspot_count)
            self.results_dialog.zoom_to_feature_signal.connect(self._handle_zoom_to_feature)
            self.results_dialog.populate_table(high_risk_results)
            self.results_dialog.show()

        QgsMessageLog.logMessage(tr("reneW standard analysis finished."), 'reneW', Qgis.Success)

    def _run_temporal_analysis(self, params_data):
        """
        Performs the time-series analysis and creates a new time-aware layer.
        FIXED: Now properly indented as a class method.
        """
        analysis_configs = self.dlg.get_analysis_configs()
        if not analysis_configs:
            self.iface.messageBar().pushMessage(
                tr("Info"),
                tr("No layers selected for analysis."),
                Qgis.Info, duration=3
            )
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
        fields.append(QgsField("start_time", QVariant.DateTime))
        fields.append(QgsField("end_time", QVariant.DateTime))
        fields.append(QgsField("material", QVariant.String))
        fields.append(QgsField("dimension", QVariant.Double))
        fields.append(QgsField("age", QVariant.Int))
        fields.append(QgsField("optimism_factor", QVariant.Double))

        # Create the memory layer
        temporal_layer = QgsVectorLayer(
            f"LineString?crs={QgsProject.instance().crs().authid()}",
            "Temporal Renewal Need",
            "memory"
        )
        provider = temporal_layer.dataProvider()
        provider.addAttributes(fields)
        temporal_layer.updateFields()

        # Progress tracking
        total_calcs = sum(
            config['layer'].featureCount() * len(range(start_year, end_year + 1, step))
            for config in analysis_configs
        )

        progress_bar = QProgressBar()
        progress_bar.setMaximum(total_calcs)
        progress_bar.setAlignment(get_alignment())
        message_bar_item = self.iface.messageBar().createMessage(tr("Calculating temporal renewal need..."))
        message_bar_item.layout().addWidget(progress_bar)
        self.iface.messageBar().pushWidget(message_bar_item, Qgis.Info)

        processed_calcs = 0
        temporal_layer.startEditing()

        for config in analysis_configs:
            layer = config['layer']
            layer_name = layer.name()

            domain, subtype, pipe_type_name = self._parse_pipe_type(config['type'])

            required_fields = ['material_field', 'year_field']
            if not all(config.get(f) for f in required_fields):
                continue

            field_indices = {
                f: layer.fields().indexFromName(config[f])
                for f in required_fields if config.get(f)
            }

            if config.get('reno_year_field'):
                field_indices['reno_year_field'] = layer.fields().indexFromName(config['reno_year_field'])
            if config.get('reno_method_field'):
                field_indices['reno_method_field'] = layer.fields().indexFromName(config['reno_method_field'])
            if 'dimension_field' in config:
                field_indices['dimension_field'] = layer.fields().indexFromName(config['dimension_field'])

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

                if domain == "water":
                    optimism_factor = self.dlg.waterOptimismFactor()
                elif domain == "sewer" and subtype == "spill":
                    optimism_factor = self.dlg.wastewaterOptimismFactor()
                elif domain == "sewer" and subtype == "storm":
                    optimism_factor = self.dlg.stormwaterOptimismFactor()
                else:
                    optimism_factor = 1.0

                material_name = str(attrs[field_indices['material_field']])
                try:
                    key, params = material_lookup.find_material_key(
                        params_data, domain=domain, subtype=subtype, material_name=material_name
                    )
                except KeyError as e:
                    QgsMessageLog.logMessage(
                        f"Material lookup failed for '{material_name}': {e}",
                        'reneW', Qgis.Warning
                    )
                    continue

                for year in range(start_year, end_year + 1, step):
                    processed_calcs += 1
                    progress_bar.setValue(processed_calcs)

                    age = max(0, year - effective_install_year)
                    adjusted_age = age / optimism_factor
                    adjusted_install_year = year - int(adjusted_age)

                    cohort = calculation_logic.Cohort(
                        length_km=1.0,
                        install_year=adjusted_install_year,
                        material_key=key
                    )
                    renewal_need = calculation_logic.cumulative_failure_probability(
                        cohort, year, params
                    )

                    # Create temporal feature with proper datetime fields
                    out_feat = QgsFeature(fields)
                    out_feat.setGeometry(feature.geometry())

                    # Create datetime objects for temporal controller
                    start_datetime = QDateTime.fromString(f"{year}-01-01T00:00:00", get_iso_format())
                    end_datetime = QDateTime.fromString(f"{year + step}-01-01T00:00:00", get_iso_format())

                    material_val = str(attrs[field_indices['material_field']])
                    dimension_val = None
                    if 'dimension_field' in field_indices and field_indices['dimension_field'] != -1:
                        dimension_val = self._parse_dimension(attrs[field_indices['dimension_field']])
                    age_val = year - effective_install_year

                    out_feat.setAttributes([
                        str(feature.id()),
                        layer_name,
                        year,
                        pipe_type_name,
                        renewal_need,
                        start_datetime,
                        end_datetime,
                        material_val,
                        dimension_val,
                        age_val,
                        optimism_factor
                    ])
                    provider.addFeature(out_feat)

        temporal_layer.commitChanges()
        self.iface.messageBar().clearWidgets()

        # Configure temporal properties
        self._configure_temporal_properties(temporal_layer)

        # Apply styling
        self._style_temporal_layer(temporal_layer)

        # Add to project
        QgsProject.instance().addMapLayer(temporal_layer)
        self.iface.messageBar().pushMessage(
            tr("Success"),
            tr("Temporal analysis layer created."),
            Qgis.Info, duration=5
        )

        # --- Hotspot Analysis (for temporal mode) ---
        hotspot_layer = None
        if self.dlg.useHotspotAnalysis():
            hotspot_threshold = self.dlg.hotspotThreshold()
            hotspot_radius = self.dlg.hotspotRadius()
            hotspot_layer = self._run_hotspot_analysis(
                analysis_configs,
                hotspot_threshold,
                hotspot_radius,
                "renewal_need"
            )
            if hotspot_layer:
                QgsProject.instance().addMapLayer(hotspot_layer)
                hotspot_layer.selectionChanged.connect(lambda ids, _, __: self._open_hotspot_explorer(hotspot_layer, ids, analysis_configs))
                self.iface.messageBar().pushMessage(
                    tr("Success"),
                    tr("Hotspot analysis complete."),
                    Qgis.Info,
                    duration=4
                )

        QgsMessageLog.logMessage(tr("reneW temporal analysis finished."), 'reneW', Qgis.Success)

    def _configure_temporal_properties(self, temporal_layer):
        """Configure temporal properties with Qt6 compatibility."""
        temporal_props = temporal_layer.temporalProperties()

        # Qt6 compatible temporal mode setting
        try:
            # Try new Qt6 enum first
            if hasattr(QgsVectorLayerTemporalProperties, 'ModeFeatureDateTimeInstantFromField'):
                temporal_props.setMode(QgsVectorLayerTemporalProperties.ModeFeatureDateTimeInstantFromField)
            elif hasattr(QgsVectorLayerTemporalProperties, 'ModeFeature'):
                temporal_props.setMode(QgsVectorLayerTemporalProperties.ModeFeature)
            else:
                # Fallback for older versions
                temporal_props.setMode(QgsVectorLayerTemporalProperties.ModeFeatureBased)
        except AttributeError:
            QgsMessageLog.logMessage(
                "Could not set temporal mode - using default",
                'reneW', Qgis.Warning
            )

        temporal_props.setStartField("start_time")
        temporal_props.setEndField("end_time")
        temporal_props.setIsActive(True)

    def _style_temporal_layer(self, temporal_layer):
        """
        Apply styling to the temporal renewal need layer.
        Compatible with QGIS 3.99 (Qt6 / Python 3.12).
        Adds halos matching pipe type and scales halo thickness by risk level.
        """
        from qgis.core import QgsRuleBasedRenderer, QgsSymbol
        from qgis.PyQt.QtGui import QColor

        # Grab field index for pipe type
        type_field = temporal_layer.fields().lookupField("pipe_type")
        if type_field == -1:
            self.iface.messageBar().pushWarning("reneW", "No 'pipe_type' field found in temporal layer.")
            return

        # Collect unique pipe types
        unique_types = temporal_layer.uniqueValues(type_field)

        # Root rule for all categories
        symbol = QgsSymbol.defaultSymbol(temporal_layer.geometryType())
        root_rule = QgsRuleBasedRenderer.Rule(symbol)

        # Risk buckets (low, high, label, halo width)
        buckets = [
            (0.0, 0.3, "Low Risk", 0.4),
            (0.3, 0.6, "Medium Risk", 0.8),
            (0.6, 1.0, "High Risk", 1.2),
        ]

        for pipe_type in unique_types:
            ptype = str(pipe_type).lower()
            if ptype in ("sewer", "spill", "sewer/spill", "wastewater"):
                base_color = QColor("red")
            elif ptype in ("storm", "stormwater"):
                base_color = QColor("green")
            elif ptype == "water":
                base_color = QColor("blue")
            else:
                base_color = QColor("gray")

            for (low, high, label, halo_width) in buckets:
                # Create a symbol for this pipe type + risk bucket
                symbol = QgsSymbol.defaultSymbol(temporal_layer.geometryType())
                color = QColor(base_color)
                # Opacity based on risk level
                color.setAlphaF(0.3 + 0.7 * high)

                symbol.setColor(color)

                # Add halo (outline) in same pipe-type color, scale thickness by risk
                layer0 = symbol.symbolLayer(0)
                if hasattr(layer0, "setStrokeColor"):
                    layer0.setStrokeColor(base_color)
                if hasattr(layer0, "setWidth"):  # QGIS 3.99 compatible
                    layer0.setWidth(halo_width)

                # Rule expression
                expr = f"\"pipe_type\" = '{pipe_type}' AND \"renewal_need\" >= {low} AND \"renewal_need\" < {high}"

                # Safe rule creation for QGIS 3.99
                rule = QgsRuleBasedRenderer.Rule(symbol)
                rule.setFilterExpression(expr)
                rule.setLabel(f"{pipe_type} – {label}")
                root_rule.appendChild(rule)

        renderer = QgsRuleBasedRenderer(root_rule)
        temporal_layer.setRenderer(renderer)
        temporal_layer.triggerRepaint()


    def _run_hotspot_analysis(self, analysis_configs, threshold, distance, output_field_name):
        """
        Runs a hotspot analysis on the layers that have been processed.
        Adds debug logging to confirm the field used and how many features match.
        """

        try:
            import processing
            run_algo = processing.run
        except Exception:
            from qgis.core import QgsProcessing
            run_algo = QgsProcessing.run

        feedback = QgsProcessingFeedback()
        high_risk_layers = []
        project_crs = QgsProject.instance().crs()

        QgsMessageLog.logMessage(
            f"Hotspot analysis started. Using field '{output_field_name}' with threshold {threshold}",
            'reneW', Qgis.Info
        )

        # Step 1: Collect high-risk features per layer
        for config in analysis_configs:
            layer = config['layer']
            expr = f"\"{output_field_name}\" >= {threshold}"
            QgsMessageLog.logMessage(
                f"Layer {layer.name()}: applying filter {expr}", 'reneW', Qgis.Info
            )

            request = QgsFeatureRequest().setFilterExpression(expr)
            matching = [f for f in layer.getFeatures(request)]
            QgsMessageLog.logMessage(
                f"Layer {layer.name()}: found {len(matching)} matching features", 'reneW', Qgis.Info
            )

            if not matching:
                continue

            temp_layer = layer.clone()
            temp_layer.setName(f"high_risk_{layer.name()}")

            temp_layer.startEditing()
            temp_layer.dataProvider().addFeatures(matching)
            temp_layer.commitChanges()

            if temp_layer.featureCount() > 0:
                high_risk_layers.append(temp_layer)

        if not high_risk_layers:
            self.iface.messageBar().pushMessage(
                tr("Info"),
                tr("No features found above the risk threshold for hotspot analysis."),
                Qgis.Info
            )
            return None

        # Step 2: Merge layers
        merge_params = {'LAYERS': high_risk_layers, 'CRS': project_crs, 'OUTPUT': 'memory:merged_high_risk'}
        merged_result = run_algo("native:mergevectorlayers", merge_params, feedback=feedback)
        merged_layer = merged_result['OUTPUT']

        # Step 3: Buffer
        buffer_params = {'INPUT': merged_layer, 'DISTANCE': distance, 'SEGMENTS': 8, 'DISSOLVE': False, 'OUTPUT': 'memory:buffered'}
        buffered_result = run_algo("native:buffer", buffer_params, feedback=feedback)
        buffered_layer = buffered_result['OUTPUT']

        # Step 4: Dissolve
        dissolve_params = {'INPUT': buffered_layer, 'OUTPUT': 'memory:dissolved_hotspots'}
        dissolved_result = run_algo("native:dissolve", dissolve_params, feedback=feedback)
        dissolved_layer = dissolved_result['OUTPUT']

        # Step 5: Join stats
        stats_params = {
            'INPUT': dissolved_layer,
            'JOIN': merged_layer,
            'PREDICATE': [0],  # Intersects
            'JOIN_FIELDS': [output_field_name],
            'SUMMARIES': [5, 6],  # Count, Mean
            'DISCARD_NONMATCHING': True,
            'OUTPUT': 'memory:hotspots_with_stats'
        }
        stats_result = run_algo("native:joinattributesbylocation", stats_params, feedback=feedback)
        stats_layer = stats_result['OUTPUT']

        # Rename fields for clarity
        stats_layer.startEditing()
        try:
            stats_layer.renameAttribute(stats_layer.fields().lookupField(f'{output_field_name}_count'), 'pipe_count')
            stats_layer.renameAttribute(stats_layer.fields().lookupField(f'{output_field_name}_mean'), 'avg_renewal_need')
        except Exception as e:
            QgsMessageLog.logMessage(f"Could not rename hotspot fields: {e}", 'reneW', Qgis.Warning)
        stats_layer.commitChanges()

        # Enrich hotspots with contributing pipe info
        stats_layer.startEditing()
        pipe_ids_idx = stats_layer.fields().indexFromName("pipe_ids")
        if pipe_ids_idx == -1:
            stats_layer.addAttribute(QgsField("pipe_ids", QVariant.String))
            pipe_ids_idx = stats_layer.fields().indexFromName("pipe_ids")
        material_idx = stats_layer.fields().indexFromName("materials")
        if material_idx == -1:
            stats_layer.addAttribute(QgsField("materials", QVariant.String))
            material_idx = stats_layer.fields().indexFromName("materials")
        length_idx = stats_layer.fields().indexFromName("length_km")
        if length_idx == -1:
            stats_layer.addAttribute(QgsField("length_km", QVariant.Double))
            length_idx = stats_layer.fields().indexFromName("length_km")
        stats_layer.updateFields()

        for hotspot in stats_layer.getFeatures():
            # collect contributing pipes
            intersecting = [f for f in merged_layer.getFeatures(QgsFeatureRequest().setFilterRect(hotspot.geometry().boundingBox())) if f.geometry().intersects(hotspot.geometry())]
            pipe_ids = [str(f.id()) for f in intersecting]
            materials = {}
            total_length = 0.0
            for f in intersecting:
                # This assumes 'material_field' is present in the merged layer.
                # A more robust implementation would get the material field name from the config.
                mat = str(f["material"]) if "material" in f.attributeMap() else "Unknown"
                materials[mat] = materials.get(mat, 0) + 1
                if f.geometry().length() > 0:
                    total_length += f.geometry().length() / 1000.0  # convert to km

            stats_layer.changeAttributeValue(hotspot.id(), pipe_ids_idx, ",".join(pipe_ids))
            stats_layer.changeAttributeValue(hotspot.id(), material_idx, ", ".join([f"{m}:{c}" for m, c in materials.items()]))
            stats_layer.changeAttributeValue(hotspot.id(), length_idx, total_length)
        stats_layer.commitChanges()


        # --- Rule-based Styling for Hotspots ---
        from qgis.core import QgsRuleBasedRenderer, QgsSymbol

        root_rule = QgsRuleBasedRenderer.Rule(None)

        # Moderate Hotspots (0.5–0.75)
        moderate_symbol = QgsFillSymbol.createSimple({
            'color': '255,255,0,100',   # yellow, semi-transparent
            'outline_color': 'black',
            'outline_width': '0.5'
        })
        rule_moderate = QgsRuleBasedRenderer.Rule(moderate_symbol)
        rule_moderate.setLabel(tr("Moderate Hotspots"))
        rule_moderate.setFilterExpression(f"\"avg_renewal_need\" >= 0.5 AND \"avg_renewal_need\" < 0.75")
        root_rule.appendChild(rule_moderate)

        # Severe Hotspots (>=0.75)
        severe_symbol = QgsFillSymbol.createSimple({
            'color': '255,0,0,100',     # red, semi-transparent
            'outline_color': 'black',
            'outline_width': '0.5'
        })
        rule_severe = QgsRuleBasedRenderer.Rule(severe_symbol)
        rule_severe.setLabel(tr("Severe Hotspots"))
        rule_severe.setFilterExpression(f"\"avg_renewal_need\" >= 0.75")
        root_rule.appendChild(rule_severe)

        # Apply renderer
        renderer = QgsRuleBasedRenderer(root_rule)
        stats_layer.setRenderer(renderer)
        stats_layer.setName(tr("Hotspots"))

        QgsMessageLog.logMessage("Hotspot analysis finished successfully", 'reneW', Qgis.Success)
        return stats_layer

    def _open_hotspot_explorer(self, hotspot_layer, selected_ids, analysis_configs):
        if not selected_ids:
            return
        feature = hotspot_layer.getFeature(selected_ids[0])
        pipe_ids_str = feature["pipe_ids"]
        pipe_ids = [int(pid) for pid in pipe_ids_str.split(",") if pid.strip().isdigit()]
        materials = feature["materials"]
        length_km = feature["length_km"]
        pipe_count = feature["pipe_count"]
        avg_need = feature["avg_renewal_need"]

        # Calculate average age
        ages = []
        for config in analysis_configs:
            # This assumes that the pipe IDs are unique across all layers in the analysis.
            # A more robust implementation might need to store layer ID along with pipe ID.
            layer = config['layer']
            year_field = config['year_field']
            for pid in pipe_ids:
                try:
                    pipe_feature = layer.getFeature(pid)
                    year_val = pipe_feature[year_field]
                    install_year = int(year_val)
                    age = datetime.now().year - install_year
                    ages.append(age)
                except:
                    # Feature not in this layer or other error, continue
                    continue

        avg_age = sum(ages) / len(ages) if ages else 0

        # Open dialog
        dlg = HotspotExplorerDialog(self.iface.mainWindow())
        dlg.populate(feature.id(), pipe_ids_str, materials, length_km, pipe_count, avg_need, avg_age)
        dlg.setLayer(hotspot_layer)
        # For simplicity, we assume the first layer in the config is the pipe layer.
        # This might need to be improved if multiple pipe layers are used.
        if analysis_configs:
            dlg.setPipeLayer(analysis_configs[0]['layer'])
        dlg.setContributingPipes(pipe_ids)
        dlg.exec()
