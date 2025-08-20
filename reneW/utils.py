# reneW/utils.py

from datetime import datetime
import re
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtCore import Qt
from qgis.core import (
    Qgis,
    QgsMessageLog,
    QgsWkbTypes,
    QgsVectorLayerTemporalProperties,
    QgsSymbol,
    QgsRuleBasedRenderer,
    QgsFillSymbol,
)

# ---- Styling constants (shared) ----
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

RISK_BUCKETS = [
    (0.0, 0.30, "Low Risk", 0.40),
    (0.30, 0.60, "Medium Risk", 0.80),
    (0.60, 1.01, "High Risk", 1.20),
]


# ---- Logging helpers ----
def log_info(msg: str):
    QgsMessageLog.logMessage(msg, "reneW", Qgis.Info)


def log_warn(msg: str):
    QgsMessageLog.logMessage(msg, "reneW", Qgis.Warning)


def log_success(msg: str):
    QgsMessageLog.logMessage(msg, "reneW", Qgis.Success)


def log_crit(msg: str):
    QgsMessageLog.logMessage(msg, "reneW", Qgis.Critical)


# ---- Validation helpers ----
def is_line_layer(layer) -> bool:
    try:
        return layer.geometryType() == QgsWkbTypes.LineGeometry
    except Exception:
        return False


def valid_year(y) -> bool:
    try:
        iy = int(y)
        yr = datetime.now().year
        return 1800 <= iy <= (yr + 1)
    except Exception:
        return False


def parse_dimension(val) -> float:
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val)
    m = re.search(r"(\d+(\.\d+)?)", s)
    return float(m.group(1)) if m else 0.0


def optimism_from(domain: str, subtype: str, dlg) -> float:
    try:
        if domain == "water":
            return float(dlg.waterOptimismFactor())
        elif domain == "sewer" and subtype == "spill":
            return float(dlg.wastewaterOptimismFactor())
        elif domain == "sewer" and subtype == "storm":
            return float(dlg.stormwaterOptimismFactor())
    except Exception:
        pass
    return 1.0


def configure_temporal_properties(vl):
    props = vl.temporalProperties()
    if hasattr(
        QgsVectorLayerTemporalProperties, "ModeFeatureDateTimeStartAndEndFromFields"
    ):
        props.setMode(
            QgsVectorLayerTemporalProperties.ModeFeatureDateTimeStartAndEndFromFields
        )
    elif hasattr(QgsVectorLayerTemporalProperties, "ModeFeature"):
        props.setMode(QgsVectorLayerTemporalProperties.ModeFeature)
    else:
        props.setMode(QgsVectorLayerTemporalProperties.ModeFeatureBased)
    props.setStartField("start_time")
    props.setEndField("end_time")
    props.setIsActive(True)


# ---- Rule-based styling builders ----
def style_temporal_layer(vl):
    type_field = vl.fields().lookupField("pipe_type")
    need_field = vl.fields().lookupField("renewal_need")
    if type_field == -1 or need_field == -1:
        log_warn("Temporal layer missing 'pipe_type' or 'renewal_need'; skip styling.")
        return

    root = QgsRuleBasedRenderer.Rule(QgsSymbol.defaultSymbol(vl.geometryType()))

    for ptype, base_color in PIPE_COLOR.items():
        pen_style = PIPE_PEN[ptype]
        for low, high, label, width_high in RISK_BUCKETS:
            sym = QgsSymbol.defaultSymbol(vl.geometryType())
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

            expr = (
                f"\"pipe_type\" = '{ptype}' AND "
                f'"renewal_need" >= {low} AND '
                f'"renewal_need" < {high}'
            )
            rule = QgsRuleBasedRenderer.Rule(sym)
            rule.setFilterExpression(expr)
            rule.setLabel(f"{ptype.capitalize()} – {label}")
            root.appendChild(rule)

    vl.setRenderer(QgsRuleBasedRenderer(root))
    # Maptips (rich)
    vl.setMapTipTemplate(
        '<b>Pipe Type:</b> [% "pipe_type" %]<br>'
        '<b>Renewal Need:</b> [% round("renewal_need",2) %]<br>'
        '<b>Original Year:</b> [% "construction_year" %]<br>'
        '<b>Calculated Year:</b> [% "calc_construction_year" %]<br>'
        '<b>Years Left:</b> [% "years_left" %]<br>'
        '<b>Length (m):</b> [% round("length_m",1) %]'
    )
    vl.setMapTipsEnabled(True)
    vl.triggerRepaint()


def style_standard_analysis_layer(layer):
    root = QgsRuleBasedRenderer.Rule(None)
    field_name = "renewal_need"
    if layer.fields().indexFromName(field_name) == -1:
        field_name = "fornyelsebehov"
        if layer.fields().indexFromName(field_name) == -1:
            log_warn("No renewal_need/fornyelsebehov field; skip standard styling.")
            return

    rules = [
        (0.0, 0.33, QColor("green"), "Low Need"),
        (0.33, 0.66, QColor("orange"), "Medium Need"),
        (0.66, 1.01, QColor("red"), "High Need"),
    ]
    for lower, upper, color, label in rules:
        sym = QgsSymbol.defaultSymbol(layer.geometryType())
        sym.setColor(color)
        rule = QgsRuleBasedRenderer.Rule(sym)
        rule.setFilterExpression(
            f'"{field_name}" >= {lower} AND "{field_name}" < {upper}'
        )
        rule.setLabel(label)
        root.appendChild(rule)

    # Overlay rule if imputed
    imputed_field = "year_imputed"
    if layer.fields().indexFromName(imputed_field) != -1:
        im_sym = QgsSymbol.defaultSymbol(layer.geometryType())
        ll = im_sym.symbolLayer(0)
        if hasattr(ll, "setPenStyle"):
            ll.setPenStyle(Qt.PenStyle.DashLine)
        if hasattr(ll, "setStrokeColor"):
            ll.setStrokeColor(QColor("black"))
        if hasattr(ll, "setWidth"):
            ll.setWidth(0.5)
        r = QgsRuleBasedRenderer.Rule(im_sym)
        r.setFilterExpression(f'"{imputed_field}" = 1')
        r.setLabel("Imputed Year")
        root.appendChild(r)

    layer.setRenderer(QgsRuleBasedRenderer(root))
    layer.triggerRepaint()


def style_hotspot_layer(vl):
    # Moderate
    sym_mod = QgsFillSymbol.createSimple({"color": "yellow", "outline_color": "black"})
    r_mod = QgsRuleBasedRenderer.Rule(sym_mod)
    r_mod.setFilterExpression('"avg_renewal_need" >= 0.5 AND "avg_renewal_need" < 0.75')
    r_mod.setLabel("Moderate Hotspot (0.5–0.75)")
    # Severe
    sym_sev = QgsFillSymbol.createSimple({"color": "red", "outline_color": "black"})
    r_sev = QgsRuleBasedRenderer.Rule(sym_sev)
    r_sev.setFilterExpression('"avg_renewal_need" >= 0.75')
    r_sev.setLabel("Severe Hotspot (>=0.75)")

    root = QgsRuleBasedRenderer.Rule(None)
    root.appendChild(r_mod)
    root.appendChild(r_sev)
    vl.setRenderer(QgsRuleBasedRenderer(root))
    # Tooltip
    vl.setMapTipTemplate(
        '<b>Hotspot Severity:</b> [% "severity" %]<br>'
        '<b>Avg Renewal Need:</b> [% round("avg_renewal_need",2) %]<br>'
        '<b>Pipe Count:</b> [% "pipe_count" %]'
    )
    vl.setName("Hotspots")
    vl.triggerRepaint()
