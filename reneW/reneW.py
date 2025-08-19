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
    QgsRendererCategory,
    QgsSpatialIndex,
    QgsGeometry,
    QgsPointXY
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

    def _pretty_pipe(self, p: str) -> str:
        """Map canonical pipe_type tokens to nice labels for UI."""
        return {
            "water": "Water",
            "wastewater": "Wastewater",
            "stormwater": "Stormwater"
        }.get((p or "").lower(), p)

    def _parse_pipe_type(self, pipe_type_name: str):
        """
        Normalize pipe type string into (domain, subtype, canonical_attr_value).
        canonical_attr_value is one of: 'water', 'wastewater', 'stormwater'
        """
        pt = (pipe_type_name or "").lower().strip()
        if pt == "water":
            return ("water", None, "water")
        elif pt in ("sewer", "sewer/spill", "wastewater", "spill"):
            return ("sewer", "spill", "wastewater")
        elif pt in ("sewer/storm", "storm", "stormwater"):
            return ("sewer", "storm", "stormwater")
        else:
            # fallback — treat as wastewater to stay conservative
            return ("sewer", None, "wastewater")

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

    # --- Imputation: property-based year inference --------------------------
    def _get_property_layer_config(self):
        """
        Safely fetch property layer + year field + parameters from the dialog.
        Returns (layer, year_field_name, k_neighbors:int, fractions:list[float]) or (None, None, 0, []) if unavailable.
        """
        # These dialog getters should exist; if not, we guard with hasattr to avoid runtime errors
        prop_layer = self.dlg.propertyLayer() if hasattr(self.dlg, "propertyLayer") else None
        prop_year_field = self.dlg.propertyYearField() if hasattr(self.dlg, "propertyYearField") else None
        k_neighbors = self.dlg.propertyKNeighbors() if hasattr(self.dlg, "propertyKNeighbors") else 15
        fractions = self.dlg.propertySampleFractions() if hasattr(self.dlg, "propertySampleFractions") else [0.0, 0.25, 0.5, 0.75, 1.0]

        # Basic validity check
        if not prop_layer or not prop_year_field:
            return (None, None, 0, [])
        if prop_layer.fields().indexFromName(prop_year_field) == -1:
            return (None, None, 0, [])
        return (prop_layer, prop_year_field, int(max(1, k_neighbors)), list(fractions))

    def _build_property_spatial_index(self, prop_layer):
        """
        Build (and cache) a spatial index for the property points.
        Cache by layer ID to avoid rebuilding each run.
        """
        if not hasattr(self, "_prop_index_cache"):
            self._prop_index_cache = {}
        lid = prop_layer.id()
        if lid in self._prop_index_cache:
            return self._prop_index_cache[lid]

        idx = QgsSpatialIndex()
        fid_list = []
        for f in prop_layer.getFeatures():
            if not f.geometry() or f.geometry().isEmpty():
                continue
            idx.addFeature(f)
            fid_list.append(f.id())

        self._prop_index_cache[lid] = (idx, set(fid_list))
        return self._prop_index_cache[lid]

    def _sample_points_along_line(self, geom: QgsGeometry, fractions):
        """
        Returns a list of QgsPointXY sampled along a line geometry at the given fractional distances.
        Fractions are clamped to [0,1]. Multi-part lines are supported by using total length and interpolate().
        """
        pts = []
        if not geom or geom.isEmpty() or geom.length() <= 0:
            return pts
        total_len = geom.length()
        for frac in fractions:
            try:
                t = max(0.0, min(1.0, float(frac)))
            except Exception:
                continue
            d = t * total_len
            try:
                pgeom = geom.interpolate(d)
                if pgeom and not pgeom.isEmpty():
                    pt = pgeom.asPoint()
                    pts.append(QgsPointXY(pt))
            except Exception:
                # interpolate can fail on some geometry types; skip gracefully
                continue
        return pts

    def _median(self, values):
        """Simple median for a list of numeric values; returns None if empty."""
        vals = sorted(v for v in values if v is not None)
        n = len(vals)
        if n == 0:
            return None
        mid = n // 2
        if n % 2 == 1:
            return vals[mid]
        return (vals[mid - 1] + vals[mid]) / 2.0

    def _infer_year_from_properties(self, pipe_feat, prop_layer, year_field_name, k_neighbors=15, fractions=None):
        """
        For a pipe feature with missing year, infer via nearest property points around multiple
        samples along its length. Returns an int year or None if it cannot infer.
        """
        if not prop_layer or not year_field_name:
            return None

        # Build or reuse index
        idx, fid_cache = self._build_property_spatial_index(prop_layer)
        year_idx = prop_layer.fields().indexFromName(year_field_name)
        if year_idx == -1:
            return None

        # Sample points along the pipe
        geom = pipe_feat.geometry()
        fractions = fractions or [0.0, 0.25, 0.5, 0.75, 1.0]
        sample_pts = self._sample_points_along_line(geom, fractions)
        if not sample_pts:
            return None

        # Gather nearest property years across all samples
        years = []
        prov = prop_layer.dataProvider()
        for pt in sample_pts:
            try:
                # nearestNeighbor returns FIDs
                fids = idx.nearestNeighbor(pt, k_neighbors)
                if not fids:
                    continue
                # Filter by actual existing fids in cache (stability)
                fids = [fid for fid in fids if fid in fid_cache]
                if not fids:
                    continue
                req = QgsFeatureRequest().setFilterFids(fids)
                for pf in prop_layer.getFeatures(req):
                    yv = pf.attribute(year_idx)
                    if yv in (None, ''):
                        continue
                    try:
                        y = int(yv)
                        # Basic sanity: ignore absurd/sentinel values
                        if 1800 <= y <= datetime.now().year + 1:
                            years.append(y)
                    except Exception:
                        continue
            except Exception:
                # Continue if NN query fails for any sampled point
                continue

        if not years:
            return None

        m = self._median(years)
        if m is None:
            return None
        # Return rounded integer median
        return int(round(m))

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
            friendly_pipe = self._pretty_pipe(pipe_type_name)

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

            # Ensure a flag field exists (optional)
            flag_field_name = "year_imputed"
            if fields.indexFromName(flag_field_name) == -1:
                provider.addAttributes([QgsField(flag_field_name, QVariant.Int)])
                layer.updateFields()
            flag_idx = fields.indexFromName(flag_field_name)

            layer.startEditing()
            for feature in layer.getFeatures():
                processed_features += 1
                progress_bar.setValue(processed_features)
                attrs = feature.attributes()

                if selected_municipality_code is not None and muni_idx != -1 and attrs[muni_idx] != selected_municipality_code:
                    continue

                year_val = attrs[field_indices['year_field']]

                # Try to parse installation year
                installation_year = None
                try:
                    if year_val is not None and str(year_val).strip().lower() not in ['null', '']:
                        y = int(year_val)
                        installation_year = y if y != 1900 else None
                except (ValueError, TypeError):
                    installation_year = None

                # If missing, try property-based imputation
                if installation_year is None:
                    prop_layer, prop_year_field, k_neighbors, fractions = self._get_property_layer_config()
                    if prop_layer and prop_year_field and k_neighbors > 0 and fractions:
                        inferred = self._infer_year_from_properties(
                            feature, prop_layer, prop_year_field, k_neighbors, fractions
                        )
                        if inferred is not None:
                            installation_year = inferred
                            # mark this feature as imputed
                            layer.changeAttributeValue(feature.id(), flag_idx, 1)

                # If still missing, skip this feature
                if installation_year is None:
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
                    # Check if the year was imputed to format the age string
                    is_imputed = feature.attribute(flag_idx) == 1
                    age_display = f"{age} (imputed)" if is_imputed else age

                    high_risk_results.append({
                        'layer_name': layer_name,
                        'layer_id': layer.id(),
                        'feature_id': feature.id(),
                        'pipe_type': friendly_pipe,
                        'material': material_name,
                        'age': age_display,
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

        # Apply styling to the layers that were processed
        for config in analysis_configs:
            self._style_standard_analysis_layer(config['layer'])

        hotspot_layer = None
        if self.dlg.useHotspotAnalysis():
            hotspot_threshold = self.dlg.hotspotThreshold()
            hotspot_radius = self.dlg.hotspotRadius()
            hotspot_layer = self._run_hotspot_analysis(
                analysis_configs, hotspot_threshold, hotspot_radius, output_field_name_for_hotspot
            )
            if hotspot_layer:
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
        fields.append(QgsField("construction_year", QVariant.Int))
        fields.append(QgsField("calc_construction_year", QVariant.Int))
        fields.append(QgsField("years_left", QVariant.Int))
        fields.append(QgsField("length_m", QVariant.Double))

        # Create the memory layer
        temporal_layer = QgsVectorLayer(
            f"LineString?crs={QgsProject.instance().crs().authid()}",
            "Temporal Renewal Need",
            "memory"
        )
        provider = temporal_layer.dataProvider()
        provider.addAttributes(fields)
        temporal_layer.updateFields()

        temporal_layer.setFieldAlias(temporal_layer.fields().indexFromName("construction_year"), "Original Construction Year")
        temporal_layer.setFieldAlias(temporal_layer.fields().indexFromName("calc_construction_year"), "Calculated Construction Year")
        temporal_layer.setFieldAlias(temporal_layer.fields().indexFromName("years_left"), "Years Left")
        temporal_layer.setFieldAlias(temporal_layer.fields().indexFromName("length_m"), "Pipe Length (m)")

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

                installation_year = None
                try:
                    if year_val is not None and str(year_val).strip().lower() not in ['null', '']:
                        y = int(year_val)
                        installation_year = y if y != 1900 else None
                except (ValueError, TypeError):
                    installation_year = None

                if installation_year is None:
                    prop_layer, prop_year_field, k_neighbors, fractions = self._get_property_layer_config()
                    if prop_layer and prop_year_field and k_neighbors > 0 and fractions:
                        inferred = self._infer_year_from_properties(
                            feature, prop_layer, prop_year_field, k_neighbors, fractions
                        )
                        if inferred is not None:
                            installation_year = inferred

                if installation_year is None:
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

                    start_datetime = QDateTime.fromString(f"{year}-01-01T00:00:00", get_iso_format())
                    end_year_for_bin = min(year + step, end_year + 1)
                    end_datetime = QDateTime.fromString(f"{end_year_for_bin}-01-01T00:00:00", get_iso_format())

                    material_val = str(attrs[field_indices['material_field']])
                    dimension_val = None
                    if 'dimension_field' in field_indices and field_indices['dimension_field'] != -1:
                        dimension_val = self._parse_dimension(attrs[field_indices['dimension_field']])
                    age_val = year - effective_install_year

                    years_left = int(params.mu - age)
                    length_m = feature.geometry().length() if feature.geometry() else 0.0

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
                        optimism_factor,
                        installation_year,
                        adjusted_install_year,
                        years_left,
                        round(length_m, 2)
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
                hotspot_layer.selectionChanged.connect(lambda ids, _, __: self._open_hotspot_explorer(hotspot_layer, ids, analysis_configs))
                self.iface.messageBar().pushMessage(
                    tr("Success"),
                    tr("Hotspot analysis complete."),
                    Qgis.Info,
                    duration=4
                )

        QgsMessageLog.logMessage(tr("reneW temporal analysis finished."), 'reneW', Qgis.Success)

    def _configure_temporal_properties(self, temporal_layer):
        """Configure temporal properties across Qt5/Qt6/QGIS master."""
        temporal_props = temporal_layer.temporalProperties()

        if hasattr(QgsVectorLayerTemporalProperties, 'ModeFeatureDateTimeStartAndEndFromFields'):
            temporal_props.setMode(QgsVectorLayerTemporalProperties.ModeFeatureDateTimeStartAndEndFromFields)
        elif hasattr(QgsVectorLayerTemporalProperties, 'ModeFeature'):
            temporal_props.setMode(QgsVectorLayerTemporalProperties.ModeFeature)
        else:
            temporal_props.setMode(QgsVectorLayerTemporalProperties.ModeFeatureBased)

        temporal_props.setStartField("start_time")
        temporal_props.setEndField("end_time")
        temporal_props.setIsActive(True)

    def _style_temporal_layer(self, temporal_layer):
        """
        Rule-based styling for temporal layer.
        - Colors by pipe type (blue/green/red)
        - Line pattern by pipe type (water: dotted, stormwater: dash-dot, wastewater: solid)
        - Halo (outline) matches pipe type color
        - Risk buckets control opacity and width
        Compatible with QGIS 3.99 / Qt6 / Py3.12.
        """
        from qgis.core import QgsRuleBasedRenderer, QgsSymbol
        from qgis.PyQt.QtGui import QColor
        from qgis.PyQt.QtCore import Qt

        type_field = temporal_layer.fields().lookupField("pipe_type")
        if type_field == -1:
            self.iface.messageBar().pushWarning("reneW", "No 'pipe_type' field found in temporal layer.")
            return

        ALL_TYPES = ("water", "stormwater", "wastewater")

        root = QgsRuleBasedRenderer.Rule(QgsSymbol.defaultSymbol(temporal_layer.geometryType()))

        buckets = [
            (0.0, 0.30, "Low Risk",    0.40),
            (0.30, 0.60, "Medium Risk",0.80),
            (0.60, 1.01, "High Risk",  1.20),
        ]

        PIPE_COLOR = {
            "water": QColor("blue"),
            "stormwater": QColor("green"),
            "wastewater": QColor("red"),
        }
        PIPE_PEN = {
            "water": Qt.PenStyle.DotLine,
            "stormwater": Qt.PenStyle.DashDotLine,
            "wastewater": Qt.PenStyle.SolidLine,
        }

        for ptype in ALL_TYPES:
            base_color = PIPE_COLOR[ptype]
            pen_style = PIPE_PEN[ptype]

            for (low, high, label, width_high) in buckets:
                sym = QgsSymbol.defaultSymbol(temporal_layer.geometryType())
                color = QColor(base_color)
                alpha = 0.3 + 0.7 * min(high, 1.0)
                color.setAlphaF(alpha)
                sym.setColor(color)

                lyr = sym.symbolLayer(0)
                if hasattr(lyr, "setStrokeColor"):
                    lyr.setStrokeColor(base_color)
                if hasattr(lyr, "setWidth"):
                    lyr.setWidth(width_high)
                if hasattr(lyr, "setPenStyle"):
                    lyr.setPenStyle(pen_style)

                expr = f"\"pipe_type\" = '{ptype}' AND \"renewal_need\" >= {low} AND \"renewal_need\" < {high}"

                rule = QgsRuleBasedRenderer.Rule(sym)
                rule.setFilterExpression(expr)
                rule.setLabel(f"{ptype.capitalize()} – {label}")
                root.appendChild(rule)

        renderer = QgsRuleBasedRenderer(root)
        temporal_layer.setRenderer(renderer)

        # --- Configure Map Tips (Tooltips) ---
        temporal_layer.setMapTipTemplate(
            "<b>Pipe Type:</b> [% \"pipe_type\" %]<br>"
            "<b>Renewal Need:</b> [% round(\"renewal_need\",2) %]<br>"
            "<b>Original Year:</b> [% \"construction_year\" %]<br>"
            "<b>Calculated Year:</b> [% \"calc_construction_year\" %]<br>"
            "<b>Years Left:</b> [% \"years_left\" %]<br>"
            "<b>Length (m):</b> [% round(\"length_m\",1) %]"
        )
        temporal_layer.setMapTipsEnabled(True)

        temporal_layer.triggerRepaint()

    def _style_standard_analysis_layer(self, layer):
        """
        Applies a rule-based renderer to the output of the standard analysis.
        - Colors pipes by renewal_need (Low, Medium, High).
        - Adds a dashed outline for pipes with an imputed year.
        """
        root_rule = QgsRuleBasedRenderer.Rule(None)

        # --- Renewal Need Rules ---
        field_name = 'renewal_need'
        if layer.fields().indexFromName(field_name) == -1:
            field_name = 'fornyelsebehov' # Fallback to legacy name
            if layer.fields().indexFromName(field_name) == -1:
                return # No field to style on

        renewal_rules = [
            (0.0, 0.33, QColor('green'), 'Low Need'),
            (0.33, 0.66, QColor('orange'), 'Medium Need'),
            (0.66, 1.01, QColor('red'), 'High Need')
        ]

        for lower, upper, color, label in renewal_rules:
            symbol = QgsSymbol.defaultSymbol(layer.geometryType())
            symbol.setColor(color)
            rule = QgsRuleBasedRenderer.Rule(symbol)
            rule.setFilterExpression(f'"{field_name}" >= {lower} AND "{field_name}" < {upper}')
            rule.setLabel(label)
            root_rule.appendChild(rule.clone())

        # --- Imputed Year Rule ---
        imputed_field = 'year_imputed'
        if layer.fields().indexFromName(imputed_field) != -1:
            imputed_symbol = QgsSymbol.defaultSymbol(layer.geometryType())
            # Create a dashed line symbol layer
            line_layer = imputed_symbol.symbolLayer(0)
            line_layer.setPenStyle(Qt.PenStyle.DashLine)
            line_layer.setStrokeColor(QColor('black'))
            line_layer.setWidth(0.5)

            rule = QgsRuleBasedRenderer.Rule(imputed_symbol)
            rule.setFilterExpression(f'"{imputed_field}" = 1')
            rule.setLabel('Imputed Year')
            root_rule.appendChild(rule.clone())

        renderer = QgsRuleBasedRenderer(root_rule)
        layer.setRenderer(renderer)
        layer.triggerRepaint()


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

        # Enrich hotspots with contributing pipe info (robust material lookup)
        stats_layer.startEditing()

        def _ensure_field(vl, name, qvariant_type):
            idx = vl.fields().indexFromName(name)
            if idx == -1:
                vl.addAttribute(QgsField(name, qvariant_type))
                vl.updateFields()
                idx = vl.fields().indexFromName(name)
            return idx

        pipe_ids_idx = _ensure_field(stats_layer, "pipe_ids", QVariant.String)
        material_idx = _ensure_field(stats_layer, "materials", QVariant.String)
        length_idx = _ensure_field(stats_layer, "length_km", QVariant.Double)
        severity_idx = _ensure_field(stats_layer, "severity", QVariant.String)

        material_field_candidates = set()
        for cfg in analysis_configs:
            mf = cfg.get("material_field")
            if mf:
                material_field_candidates.add(mf)
        material_field_candidates |= {"material", "mat", "materialtyp", "material_type"}

        for hotspot in stats_layer.getFeatures():
            geom = hotspot.geometry()
            intersecting = []
            for f in merged_layer.getFeatures(QgsFeatureRequest().setFilterRect(geom.boundingBox())):
                if f.geometry() and f.geometry().intersects(geom):
                    intersecting.append(f)

            pipe_ids = [str(f.id()) for f in intersecting]
            materials_count = {}
            total_length_km = 0.0

            for f in intersecting:
                mat_val = "Unknown"
                for cand in material_field_candidates:
                    idx = f.fieldNameIndex(cand)
                    if idx != -1:
                        mv = f.attributes()[idx]
                        if mv is not None and str(mv).strip():
                            mat_val = str(mv)
                            break
                materials_count[mat_val] = materials_count.get(mat_val, 0) + 1

                g = f.geometry()
                if g:
                    try:
                        total_length_km += (g.length() / 1000.0)
                    except Exception:
                        pass

            stats_layer.changeAttributeValue(hotspot.id(), pipe_ids_idx, ",".join(pipe_ids))
            stats_layer.changeAttributeValue(hotspot.id(), material_idx, ", ".join([f"{m}:{c}" for m, c in materials_count.items()]))
            stats_layer.changeAttributeValue(hotspot.id(), length_idx, total_length_km)

            avg_renewal_need_val = hotspot['avg_renewal_need']
            if avg_renewal_need_val >= 0.75:
                severity = "Severe"
            elif avg_renewal_need_val >= 0.5:
                severity = "Moderate"
            else:
                severity = "Low"
            stats_layer.changeAttributeValue(hotspot.id(), severity_idx, severity)

        stats_layer.commitChanges()


        hotspot_layer = stats_layer
        hotspot_layer.setFieldAlias(hotspot_layer.fields().indexFromName("avg_renewal_need"), "Average Renewal Need")
        hotspot_layer.setFieldAlias(hotspot_layer.fields().indexFromName("pipe_count"), "Pipe Count")
        hotspot_layer.setFieldAlias(hotspot_layer.fields().indexFromName("severity"), "Hotspot Severity")

        hotspot_layer.setMapTipTemplate(
            "<b>Hotspot Severity:</b> [% \"severity\" %]<br>"
            "<b>Avg Renewal Need:</b> [% round(\"avg_renewal_need\",2) %]<br>"
            "<b>Pipe Count:</b> [% \"pipe_count\" %]"
        )

        # --- Rule-based Styling for Hotspots ---
        symbol = QgsFillSymbol.createSimple({"color": "yellow", "outline_color": "black"})
        rule_moderate = QgsRuleBasedRenderer.Rule(symbol)
        rule_moderate.setFilterExpression("\"avg_renewal_need\" >= 0.5 AND \"avg_renewal_need\" < 0.75")
        rule_moderate.setLabel("Moderate Hotspot (0.5–0.75)")

        symbol = QgsFillSymbol.createSimple({"color": "red", "outline_color": "black"})
        rule_severe = QgsRuleBasedRenderer.Rule(symbol)
        rule_severe.setFilterExpression("\"avg_renewal_need\" >= 0.75")
        rule_severe.setLabel("Severe Hotspot (>=0.75)")

        root_rule = QgsRuleBasedRenderer.Rule(None)
        root_rule.appendChild(rule_moderate)
        root_rule.appendChild(rule_severe)

        renderer = QgsRuleBasedRenderer(root_rule)
        hotspot_layer.setRenderer(renderer)
        hotspot_layer.setName(tr("Hotspots"))

        QgsProject.instance().addMapLayer(hotspot_layer)
        QgsMessageLog.logMessage("Hotspot analysis finished successfully", 'reneW', Qgis.Success)
        return hotspot_layer

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

        # Calculate average age and count imputed years
        ages = []
        imputed_count = 0
        for config in analysis_configs:
            layer = config['layer']
            year_field = config['year_field']
            imputed_field_idx = layer.fields().indexFromName("year_imputed")

            for pid in pipe_ids:
                try:
                    pipe_feature = layer.getFeature(pid)
                    year_val = pipe_feature[year_field]
                    install_year = int(year_val)
                    age = datetime.now().year - install_year
                    ages.append(age)

                    if imputed_field_idx != -1 and pipe_feature.attribute(imputed_field_idx) == 1:
                        imputed_count += 1
                except:
                    # Feature not in this layer or other error, continue
                    continue

        avg_age = sum(ages) / len(ages) if ages else 0

        # Open dialog
        dlg = HotspotExplorerDialog(self.iface.mainWindow(), iface=self.iface)
        dlg.populate(feature.id(), pipe_ids_str, materials, length_km, pipe_count, avg_need, avg_age, imputed_count)
        dlg.setLayer(hotspot_layer)
        # For simplicity, we assume the first layer in the config is the pipe layer.
        # This might need to be improved if multiple pipe layers are used.
        if analysis_configs:
            dlg.setPipeLayer(analysis_configs[0]['layer'])
        dlg.setContributingPipes(pipe_ids)
        dlg.exec()
