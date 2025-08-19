import os
from datetime import datetime

from qgis.core import (
    QgsVectorLayer, QgsField, QgsProject, QgsFields, QgsFeature,
    QgsFeatureRequest, QDateTime, Qgis, QgsProcessingFeedback,
    QgsVectorLayerTemporalProperties, QgsFillSymbol, QgsRuleBasedRenderer,
    QgsSymbol
)
from qgis.PyQt.QtCore import QVariant, Qt
from qgis.PyQt.QtGui import QColor
from . import utils, calculation_logic, material_lookup


class ReneWApi:
    """
    Public API for the reneW plugin for scripting and automation.
    """

    def __init__(self, plugin_instance):
        self.plugin = plugin_instance
        self.iface = plugin_instance.iface
        self._prop_index_cache = {}

    def calculate_renewal_need(self, layer: QgsVectorLayer,
                               config: dict) -> QgsVectorLayer:
        param_path = os.path.join(self.plugin.plugin_dir, 'parameters.json')
        params_data = material_lookup.load_parameters(param_path)
        current_year = datetime.now().year
        domain, _, _ = utils.parse_pipe_type(config['type'])
        output_field_name = 'renewal_need'
        provider = layer.dataProvider()
        fields = provider.fields()
        if fields.indexFromName(output_field_name) == -1:
            provider.addAttributes(
                [QgsField(output_field_name, QVariant.Double)])
            layer.updateFields()
        flag_field_name = "year_imputed"
        if fields.indexFromName(flag_field_name) == -1:
            provider.addAttributes([QgsField(flag_field_name, QVariant.Int)])
            layer.updateFields()
        field_indices = {f: fields.indexFromName(config[f]) for f in config
                         if f.endswith('_field')}
        output_idx = fields.indexFromName(output_field_name)
        layer.startEditing()
        for feature in layer.getFeatures():
            attrs = feature.attributes()
            year_val = attrs[field_indices['year_field']]
            installation_year = None
            try:
                if year_val is not None and \
                   str(year_val).strip().lower() not in ['null', '']:
                    y = int(year_val)
                    installation_year = y if y != 1900 else None
            except (ValueError, TypeError):
                installation_year = None
            if installation_year is None:
                continue
            effective_install_year = installation_year
            material_name = attrs[field_indices['material_field']]
            try:
                key, params = material_lookup.find_material_key(
                    params_data, domain=domain, subtype=None,
                    material_name=str(material_name)
                )
            except KeyError as e:
                utils.log_warning(f"Material lookup failed for "
                                  f"'{material_name}': {e}")
                continue
            cohort = calculation_logic.Cohort(
                length_km=1.0, install_year=effective_install_year,
                material_key=key
            )
            renewal_need = calculation_logic.renewal_for_cohort_period(
                cohort, current_year, current_year + 1, params
            )
            layer.changeAttributeValue(feature.id(), output_idx, renewal_need)
        layer.commitChanges()
        utils.style_standard_analysis_layer(layer)
        return layer

    def temporal_analysis(self, configs: list, start_year: int,
                          end_year: int, step: int) -> QgsVectorLayer:
        param_path = os.path.join(self.plugin.plugin_dir, 'parameters.json')
        params_data = material_lookup.load_parameters(param_path)
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
        temporal_layer = QgsVectorLayer(
            f"LineString?crs={QgsProject.instance().crs().authid()}",
            "Temporal Renewal Need",
            "memory"
        )
        provider = temporal_layer.dataProvider()
        provider.addAttributes(fields)
        temporal_layer.updateFields()
        temporal_layer.startEditing()
        for config in configs:
            layer = config['layer']
            domain, subtype, pipe_type_name = utils.parse_pipe_type(config['type'])
            field_indices = {f: layer.fields().indexFromName(config[f])
                             for f in config if f.endswith('_field')}
            for feature in layer.getFeatures():
                attrs = feature.attributes()
                year_val = attrs[field_indices['year_field']]
                installation_year = None
                try:
                    if year_val is not None and \
                       str(year_val).strip().lower() not in ['null', '']:
                        y = int(year_val)
                        installation_year = y if y != 1900 else None
                except (ValueError, TypeError):
                    installation_year = None

                if installation_year is None:
                    continue
                effective_install_year = installation_year
                material_name = str(attrs[field_indices['material_field']])
                try:
                    key, params = material_lookup.find_material_key(
                        params_data, domain=domain, subtype=subtype,
                        material_name=material_name
                    )
                except KeyError as e:
                    utils.log_warning(
                        f"Material lookup failed for '{material_name}': {e}"
                    )
                    continue
                for year in range(start_year, end_year + 1, step):
                    age = max(0, year - effective_install_year)
                    renewal_need = calculation_logic.cumulative_failure_probability(
                        calculation_logic.Cohort(
                            length_km=1.0,
                            install_year=effective_install_year,
                            material_key=key
                        ), year, params
                    )
                    out_feat = QgsFeature(fields)
                    out_feat.setGeometry(feature.geometry())
                    out_feat.setAttributes([
                        str(feature.id()), layer.name(), year, pipe_type_name,
                        renewal_need, None, None, material_name,
                        None, age, None, installation_year, None, None,
                        feature.geometry().length()
                    ])
                    provider.addFeature(out_feat)
        temporal_layer.commitChanges()
        utils.style_temporal_layer(temporal_layer)
        QgsProject.instance().addMapLayer(temporal_layer)
        return temporal_layer

    def hotspot_analysis(self, configs: list, threshold: float, radius: float,
                         field_name: str) -> QgsVectorLayer | None:
        return None
