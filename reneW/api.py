import os
from datetime import datetime
from typing import Optional

from qgis.core import (
    QgsVectorLayer,
    QgsField,
    QgsProject,
    QgsFields,
    QgsFeature,
    QgsFeatureRequest,
    QgsProcessingFeedback,
)
from qgis.PyQt.QtCore import QVariant, Qt

try:
    from PyQt6.QtCore import QDateTime
except ImportError:
    from PyQt5.QtCore import QDateTime
from . import utils, calculation_logic, material_lookup


class ReneWApi:
    """
    Public API for reneW plugin.
    """

    def __init__(self, iface, dlg=None):
        self.iface = iface
        self.dlg = dlg
        self._prop_index_cache = {}

    def calculate_renewal_need(
        self, layer: QgsVectorLayer, config: dict
    ) -> QgsVectorLayer:
        """
        Mutates `layer`: adds/updates 'renewal_need' and 'year_imputed' fields.
        Applies standard styling. Returns the input layer for convenience.
        """
        if not utils.is_line_layer(layer):
            raise ValueError(f"Layer '{layer.name()}' is not a line layer.")

        provider = layer.dataProvider()
        fields = provider.fields()

        out_name = "renewal_need"
        legacy = "fornyelsebehov"
        if fields.indexFromName(out_name) == -1:
            if fields.indexFromName(legacy) != -1:
                out_name = legacy
            else:
                provider.addAttributes([QgsField(out_name, QVariant.Double)])
                layer.updateFields()

        if fields.indexFromName("year_imputed") == -1:
            provider.addAttributes([QgsField("year_imputed", QVariant.Int)])
            layer.updateFields()

        req = ["material_field", "year_field"]
        if not all(config.get(f) for f in req):
            raise ValueError(
                f"Missing required config fields for layer '{layer.name()}': " f"{req}"
            )

        idx_mat = layer.fields().indexFromName(config["material_field"])
        idx_year = layer.fields().indexFromName(config["year_field"])
        idx_dim = -1
        if config.get("dimension_field"):
            idx_dim = layer.fields().indexFromName(config["dimension_field"])
        idx_out = layer.fields().indexFromName(out_name)
        idx_imputed = layer.fields().indexFromName("year_imputed")

        domain, subtype, _ = utils._parse_pipe_type(config["type"])
        optimism_factor = utils.optimism_from(domain, subtype, self.dlg)

        current_year = datetime.now().year
        layer.startEditing()

        for f in layer.getFeatures():
            yv = f.attribute(idx_year)
            installation_year = None
            try:
                if yv is not None and str(yv).strip().lower() not in ("", "null"):
                    y = int(yv)
                    if y != 1900 and utils.valid_year(y):
                        installation_year = y
            except Exception:
                installation_year = None

            if (
                installation_year is None
                and self.dlg
                and hasattr(self.dlg, "propertyLayer")
            ):
                prop_layer = self.dlg.propertyLayer()
                prop_year_field = self.dlg.propertyYearField()
                k_neighbors = getattr(self.dlg, "propertyKNeighbors", lambda: 15)()
                fractions = getattr(
                    self.dlg,
                    "propertySampleFractions",
                    lambda: [0, 0.25, 0.5, 0.75, 1.0],
                )()
                if prop_layer and prop_year_field:
                    inferred = self._infer_year_from_properties(
                        f, prop_layer, prop_year_field, k_neighbors, fractions
                    )
                    if inferred is not None and utils.valid_year(inferred):
                        installation_year = int(inferred)
                        layer.changeAttributeValue(f.id(), idx_imputed, 1)

            if installation_year is None:
                continue

            age = max(0, current_year - installation_year)
            adjusted_age = age / (optimism_factor or 1.0)
            adjusted_install_year = current_year - int(adjusted_age)

            material_name = str(f.attribute(idx_mat))
            try:
                key, params = material_lookup.find_material_key(
                    self._params(),
                    domain=domain,
                    subtype=subtype,
                    material_name=material_name,
                )
            except Exception as e:
                utils.log_warn(
                    f"Material lookup failed for '{material_name}' on "
                    f"{layer.name()}: {e}"
                )
                continue

            cohort = calculation_logic.Cohort(
                length_km=1.0, install_year=adjusted_install_year, material_key=key
            )
            renewal_need = calculation_logic.renewal_for_cohort_period(
                cohort, current_year, current_year + 1, params
            )

            if idx_dim != -1 and self.dlg and self.dlg.useDimensionWeighting():
                dim = utils.parse_dimension(f.attribute(idx_dim))
                dfac = float(self.dlg.dimensionFactor() or 0.0)
                if dim > 0 and dfac > 0:
                    renewal_need *= 1.0 + dim * dfac

            layer.changeAttributeValue(f.id(), idx_out, float(renewal_need))

        layer.commitChanges()
        utils.style_standard_analysis_layer(layer)
        return layer

    def temporal_analysis(
        self, configs: list, start_year: int, end_year: int, step: int
    ) -> QgsVectorLayer:
        crs = QgsProject.instance().crs().authid()
        vl = QgsVectorLayer(f"LineString?crs={crs}", "Temporal Renewal Need", "memory")
        pr = vl.dataProvider()

        fields = QgsFields()
        for name, qtype in [
            ("pipe_id", QVariant.String),
            ("source_layer", QVariant.String),
            ("year", QVariant.Int),
            ("pipe_type", QVariant.String),
            ("renewal_need", QVariant.Double),
            ("start_time", QVariant.DateTime),
            ("end_time", QVariant.DateTime),
            ("material", QVariant.String),
            ("dimension", QVariant.Double),
            ("age", QVariant.Int),
            ("optimism_factor", QVariant.Double),
            ("construction_year", QVariant.Int),
            ("calc_construction_year", QVariant.Int),
            ("years_left", QVariant.Int),
            ("length_m", QVariant.Double),
        ]:
            fields.append(QgsField(name, qtype))
        pr.addAttributes(fields)
        vl.updateFields()

        vl.setFieldAlias(
            vl.fields().indexFromName("construction_year"),
            "Original Construction Year",
        )
        vl.setFieldAlias(
            vl.fields().indexFromName("calc_construction_year"),
            "Calculated Construction Year",
        )
        vl.setFieldAlias(vl.fields().indexFromName("years_left"), "Years Left")
        vl.setFieldAlias(vl.fields().indexFromName("length_m"), "Pipe Length (m)")

        vl.startEditing()

        for cfg in configs:
            layer = cfg["layer"]
            if not utils.is_line_layer(layer):
                utils.log_warn(f"Skipping non-line layer: {layer.name()}")
                continue

            parts = cfg["type"].split("/")
            domain = parts[0]
            subtype = parts[1] if len(parts) > 1 else None
            pipe_type_name = cfg["type"]
            optimism = utils.optimism_from(domain, subtype, self.dlg)

            idx_mat = (
                layer.fields().indexFromName(cfg["material_field"])
                if cfg.get("material_field")
                else -1
            )
            idx_year = (
                layer.fields().indexFromName(cfg["year_field"])
                if cfg.get("year_field")
                else -1
            )
            idx_dim = (
                layer.fields().indexFromName(cfg["dimension_field"])
                if cfg.get("dimension_field")
                else -1
            )

            for feat in layer.getFeatures():
                yv = feat.attribute(idx_year) if idx_year != -1 else None
                install_year = None
                try:
                    if yv is not None and str(yv).strip().lower() not in ("", "null"):
                        yi = int(yv)
                        if yi != 1900 and utils.valid_year(yi):
                            install_year = yi
                except Exception:
                    install_year = None

                if install_year is None:
                    continue

                mat_val = str(feat.attribute(idx_mat)) if idx_mat != -1 else ""
                dim_val = (
                    utils.parse_dimension(feat.attribute(idx_dim))
                    if idx_dim != -1
                    else None
                )
                length_m = (
                    round(feat.geometry().length(), 2) if feat.geometry() else 0.0
                )

                for yr in range(start_year, end_year + 1, max(1, step)):
                    age = max(0, yr - install_year)
                    adjusted_age = age / (optimism or 1.0)
                    calc_install_year = yr - int(adjusted_age)

                    try:
                        key, params = material_lookup.find_material_key(
                            self._params(),
                            domain=domain,
                            subtype=subtype,
                            material_name=mat_val,
                        )
                    except KeyError:
                        utils.log_warn(
                            f"Missing parameters for {domain}/{mat_val}; using defaults."
                        )
                        params = material_lookup.MaterialParams(mu=80, sigma=20)
                        key = "default"
                    cohort = calculation_logic.Cohort(
                        length_km=1.0, install_year=calc_install_year, material_key=key
                    )
                    renewal_need = calculation_logic.cumulative_failure_probability(
                        cohort, yr, params
                    )
                    years_left = (
                        int(max(0, params.mu - age)) if hasattr(params, "mu") else None
                    )

                    f = QgsFeature(fields)
                    f.setGeometry(feat.geometry())
                    f.setAttributes(
                        [
                            str(feat.id()),
                            layer.name(),
                            yr,
                            pipe_type_name,
                            float(renewal_need),
                            QDateTime.fromString(f"{yr}-01-01T00:00:00", Qt.ISODate),
                            QDateTime.fromString(
                                f"{min(yr + max(1, step), end_year + 1)}-01-01T00:00:00",  # noqa
                                Qt.ISODate,
                            ),
                            mat_val,
                            dim_val,
                            age,
                            float(optimism),
                            install_year,
                            calc_install_year,
                            years_left,
                            length_m,
                        ]
                    )
                    pr.addFeatures([f])

        vl.commitChanges()
        utils.configure_temporal_properties(vl)
        utils.style_temporal_layer(vl)
        QgsProject.instance().addMapLayer(vl)
        utils.log_success("Temporal analysis layer created.")
        return vl

    def hotspot_analysis(
        self,
        configs: list,
        threshold: float,
        radius: float,
        field_name: str,
    ) -> Optional[QgsVectorLayer]:
        if not (0.0 <= float(threshold) <= 1.0):
            raise ValueError("Threshold must be in [0,1].")
        if float(radius) <= 0:
            raise ValueError("Radius must be > 0.")

        try:
            import processing

            run_algo = processing.run
        except Exception:
            from qgis.core import QgsProcessing

            run_algo = QgsProcessing.run

        fb = QgsProcessingFeedback()  # type: ignore
        high_risk = []
        for cfg in configs:
            layer = cfg["layer"]
            if field_name not in [f.name() for f in layer.fields()]:
                continue
            req = QgsFeatureRequest().setFilterExpression(
                f'"{field_name}" >= {threshold}'
            )
            feats = [f for f in layer.getFeatures(req)]
            if not feats:
                continue
            temp = layer.clone()
            temp.setName(f"high_risk_{layer.name()}")
            temp.startEditing()
            temp.dataProvider().addFeatures(feats)
            temp.commitChanges()
            if temp.featureCount() > 0:
                high_risk.append(temp)

        if not high_risk:
            utils.log_info("No features over threshold; no hotspots created.")
            return None

        crs = QgsProject.instance().crs()
        merged = run_algo(
            "native:mergevectorlayers",
            {"LAYERS": high_risk, "CRS": crs, "OUTPUT": "memory:merged_high"},
            feedback=fb,
        )["OUTPUT"]
        buffered = run_algo(
            "native:buffer",
            {
                "INPUT": merged,
                "DISTANCE": float(radius),
                "SEGMENTS": 8,
                "DISSOLVE": False,
                "OUTPUT": "memory:buf",
            },
            feedback=fb,
        )["OUTPUT"]
        dissolved = run_algo(
            "native:dissolve", {"INPUT": buffered, "OUTPUT": "memory:diss"}, feedback=fb
        )["OUTPUT"]

        stats = run_algo(
            "native:joinattributesbylocation",
            {
                "INPUT": dissolved,
                "JOIN": merged,
                "PREDICATE": [0],
                "JOIN_FIELDS": [field_name],
                "SUMMARIES": [5, 6],
                "DISCARD_NONMATCHING": True,
                "OUTPUT": "memory:hotspots",
            },
            feedback=fb,
        )["OUTPUT"]

        stats.startEditing()
        try:
            stats.renameAttribute(
                stats.fields().lookupField(f"{field_name}_count"), "pipe_count"
            )
            stats.renameAttribute(
                stats.fields().lookupField(f"{field_name}_mean"), "avg_renewal_need"
            )
        except Exception:
            pass

        if stats.fields().indexFromName("severity") == -1:
            stats.addAttribute(QgsField("severity", QVariant.String))
            stats.updateFields()
        idx_sev = stats.fields().indexFromName("severity")
        idx_avg = stats.fields().indexFromName("avg_renewal_need")

        for h in stats.getFeatures():
            avg = h[idx_avg]
            sev = (
                "Severe"
                if (avg and float(avg) >= 0.75)
                else ("Moderate" if (avg and float(avg) >= 0.5) else "Low")
            )
            stats.changeAttributeValue(h.id(), idx_sev, sev)

        stats.commitChanges()
        utils.style_hotspot_layer(stats)
        QgsProject.instance().addMapLayer(stats)
        utils.log_success("Hotspot analysis complete.")
        return stats

    def _params(self):
        try:
            param_path = os.path.join(self.plugin.plugin_dir, "parameters.json")
            return material_lookup.load_parameters(param_path)
        except Exception:
            return {}

    def _infer_year_from_properties(
        self,
        pipe_feat,
        prop_layer,
        year_field_name,
        k_neighbors=15,
        fractions=None,
    ):
        if hasattr(self.dlg, "_infer_year_from_properties"):
            try:
                return self.dlg._infer_year_from_properties(
                    pipe_feat,
                    prop_layer,
                    year_field_name,
                    k_neighbors,
                    fractions or [0, 0.25, 0.5, 0.75, 1.0],
                )
            except Exception:
                return None
        return None
