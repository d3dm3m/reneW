import re
from datetime import datetime
import unicodedata
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor
from qgis.core import (
    QgsMessageLog,
    Qgis,
    QgsSpatialIndex,
    QgsFeatureRequest,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsVectorLayer
)


def tr(message):
    """Get the translation for a string using Qt translation API."""
    from qgis.PyQt.QtCore import QCoreApplication
    return QCoreApplication.translate('ReneW', message)


def log_info(message):
    QgsMessageLog.logMessage(message, 'reneW', Qgis.Info)


def log_warning(message):
    QgsMessageLog.logMessage(message, 'reneW', Qgis.Warning)


def log_error(message):
    QgsMessageLog.logMessage(message, 'reneW', Qgis.Critical)


def log_success(message):
    QgsMessageLog.logMessage(message, 'reneW', Qgis.Success)


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


def pretty_pipe(p: str) -> str:
    """Map canonical pipe_type tokens to nice labels for UI."""
    return {
        "water": "Water",
        "wastewater": "Wastewater",
        "stormwater": "Stormwater"
    }.get((p or "").lower(), p)


def parse_pipe_type(pipe_type_name: str):
    """
    Normalize pipe type string into (domain, subtype, canonical_attr_value).
    """
    pt = (pipe_type_name or "").lower().strip()
    if pt == "water":
        return "water", None, "water"
    elif pt in ("sewer", "sewer/spill", "wastewater", "spill"):
        return "sewer", "spill", "wastewater"
    elif pt in ("sewer/storm", "storm", "stormwater"):
        return "sewer", "storm", "stormwater"
    else:
        return "sewer", None, "wastewater"


def parse_dimension(dim_val) -> float:
    """Extracts a numeric dimension from a string value."""
    if isinstance(dim_val, (int, float)):
        return float(dim_val)
    if not isinstance(dim_val, str):
        return 0.0

    match = re.search(r'(\d+)', dim_val)
    if match:
        return float(match.group(1))
    return 0.0


def build_property_spatial_index(prop_layer, cache):
    """
    Build (and cache) a spatial index for the property points.
    """
    lid = prop_layer.id()
    if lid in cache:
        return cache[lid]

    idx = QgsSpatialIndex()
    fid_list = []
    for f in prop_layer.getFeatures():
        if not f.geometry() or f.geometry().isEmpty():
            continue
        idx.addFeature(f)
        fid_list.append(f.id())

    cache[lid] = (idx, set(fid_list))
    return cache[lid]


def sample_points_along_line(geom: QgsGeometry, fractions):
    """
    Returns a list of QgsPointXY sampled along a line geometry.
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
            continue
    return pts


def median(values):
    """Simple median for a list of numeric values; returns None if empty."""
    vals = sorted(v for v in values if v is not None)
    n = len(vals)
    if n == 0:
        return None
    mid = n // 2
    if n % 2 == 1:
        return vals[mid]
    return (vals[mid - 1] + vals[mid]) / 2.0


def infer_year_from_properties(pipe_feat, prop_layer, year_field_name,
                               k_neighbors, fractions, cache):
    """
    For a pipe feature with missing year, infer via nearest property points.
    """
    if not prop_layer or not year_field_name:
        return None

    idx, fid_cache = build_property_spatial_index(prop_layer, cache)
    year_idx = prop_layer.fields().indexFromName(year_field_name)
    if year_idx == -1:
        return None

    geom = pipe_feat.geometry()
    sample_pts = sample_points_along_line(geom, fractions)
    if not sample_pts:
        return None

    years = []
    for pt in sample_pts:
        try:
            fids = idx.nearestNeighbor(pt, k_neighbors)
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
                    if 1800 <= y <= datetime.now().year + 1:
                        years.append(y)
                except Exception:
                    continue
        except Exception:
            continue

    if not years:
        return None

    m = median(years)
    return int(round(m)) if m is not None else None


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


LAYER_HINTS = {
    "water": ["vatten", "drick", "dricksvatten", "water", "potable", "tap",
              "clean", "tryckvatten", "pressurewater", "vattenledning",
              "v-led"],
    "wastewater": ["spill", "spillv", "spillvatten", "sanitary", "foul",
                   "waste", "wastewater", "sewer", "sw", "san", "spill-led",
                   "spillledning", "spillled"],
    "stormwater": ["storm", "stormwater", "dagv", "dagvatten", "rain",
                   "drain", "surface", "stormdrain", "storm sewer",
                   "stormledning", "d-led"],
}

FIELD_HINTS_UNIVERSAL = {
    "material_field": ["material", "mat", "mater", "matl", "rörmat", "rormat",
                       "rortyp", "pipe_mat", "pipemat", "matklass",
                       "matclass", "materialtyp", "mtrl"],
    "year_field": ["year", "yr", "bygg", "bygr", "install", "inst", "lägg",
                   "lagg", "construction", "construct", "constr", "built",
                   "build", "anl", "anlag"],
    "dimension_field": ["dim", "dimension", "diam", "diameter", "dn", "size",
                        "storlek", "innerdia", "inner_dia", "invand", "inv",
                        "od", "id", "ytter", "utv"],
    "municipality_field": ["kommun", "kommunkod", "kommun_kod", "muni",
                           "municip", "municipality", "city", "stad", "knr",
                           "komkod"],
}

FIELD_HINTS_BY_TYPE = {
    "water": {"year_field": ["tryck", "press"]},
    "wastewater": {
        "reno_year_field": ["reno", "renov", "rehab", "reha", "lining",
                            "cipp", "relining", "spraylin", "burst",
                            "bursting", "renover"],
        "reno_method_field": ["method", "metod", "liner", "lining", "cipp",
                              "relining", "strump", "strumpinf",
                              "schaktfri", "no-dig"],
    },
    "stormwater": {},
}

YEAR_MIN, YEAR_MAX = 1850, 2100
DIM_MM_MIN, DIM_MM_MAX = 20, 4000
SAMPLE_CHECK = 80


def _strip_accents(s: str) -> str:
    try:
        return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    except Exception:
        return s


def _norm(s: str) -> str:
    if s is None:
        return ""
    s = str(s).lower()
    s = _strip_accents(s)
    s = s.replace("_", "").replace("-", "").strip()
    s = re.sub(r"\s+", "", s)
    return s


def score_layer_for_pipe_type(layer, pipe_type: str) -> int:
    score = 0
    lname = _norm(layer.name())
    for frag in LAYER_HINTS.get(pipe_type, []):
        if _norm(frag) in lname:
            score += 10
    f_names = [_norm(f.name()) for f in layer.fields()]
    if any(k in f_names for k in ["material", "mat", "matl", "rormat",
                                  "rortyp", "pipemat"]):
        score += 2
    if any(k in f_names for k in ["dim", "diam", "diameter", "dn", "size"]):
        score += 2
    if any(k in f_names for k in ["year", "yr", "bygg", "install",
                                  "construct", "built"]):
        score += 2
    return score


def pick_best_layer(pipe_type: str):
    best = None
    best_score = 0
    for layer in QgsProject.instance().mapLayers().values():
        if not isinstance(layer, QgsVectorLayer):
            continue
        sc = score_layer_for_pipe_type(layer, pipe_type)
        if sc > best_score:
            best, best_score = layer, sc
    return best, best_score


def _sample_field_values_numeric(layer, field_name: str, limit=SAMPLE_CHECK):
    idx = layer.fields().indexFromName(field_name)
    if idx < 0:
        return None, None, 0
    mn, mx, cnt = None, None, 0
    for i, f in enumerate(layer.getFeatures()):
        if i >= limit:
            break
        v = f[idx]
        if isinstance(v, (int, float)):
            cnt += 1
            if mn is None or v < mn:
                mn = v
            if mx is None or v > mx:
                mx = v
    return mn, mx, cnt


def score_field_for_role(layer, field, role: str, pipe_type: str) -> int:
    score = 0
    fname = field.name()
    fnorm = _norm(fname)
    frags = list(FIELD_HINTS_UNIVERSAL.get(role, []))
    frags += FIELD_HINTS_BY_TYPE.get(pipe_type, {}).get(role, [])
    for frag in frags:
        frag_norm = _norm(frag)
        if fnorm.startswith(frag_norm):
            score += 6
        elif frag_norm in fnorm:
            score += 4

    qvtype = field.type()
    qvt_is_str = qvtype in (10, 12, 13)
    qvt_is_num = qvtype in (2, 3, 4, 5, 6, 8)

    if role in ("material_field", "reno_method_field", "municipality_field"):
        if qvt_is_str:
            score += 3
        else:
            score -= 2
    if role in ("year_field", "reno_year_field"):
        if qvt_is_num:
            score += 3
        mn, mx, cnt = _sample_field_values_numeric(layer, fname)
        if cnt > 0 and mn is not None and mx is not None:
            if (YEAR_MIN <= mn <= YEAR_MAX) or (YEAR_MIN <= mx <= YEAR_MAX):
                score += 3
    if role == "dimension_field":
        if qvt_is_num:
            score += 3
            mn, mx, cnt = _sample_field_values_numeric(layer, fname)
            if cnt > 0 and mn is not None and mx is not None:
                if (DIM_MM_MIN <= mn <= DIM_MM_MAX) or \
                   (DIM_MM_MIN <= mx <= DIM_MM_MAX):
                    score += 3
    return score


def pick_best_field(layer, role: str, pipe_type: str, min_score: int = 5):
    best = None
    best_score = 0
    for field in layer.fields():
        sc = score_field_for_role(layer, field, role, pipe_type)
        if sc > best_score:
            best, best_score = field.name(), sc
    return (best, best_score) if best_score >= min_score else (None, 0)


def style_standard_analysis_layer(layer):
    """
    Applies a rule-based renderer to the output of the standard analysis.
    """
    from qgis.core import QgsRuleBasedRenderer, QgsSymbol

    root_rule = QgsRuleBasedRenderer.Rule(None)
    field_name = 'renewal_need'
    if layer.fields().indexFromName(field_name) == -1:
        field_name = 'fornyelsebehov'
        if layer.fields().indexFromName(field_name) == -1:
            return

    renewal_rules = [
        (0.0, 0.33, QColor('green'), 'Low Need'),
        (0.33, 0.66, QColor('orange'), 'Medium Need'),
        (0.66, 1.01, QColor('red'), 'High Need')
    ]

    for lower, upper, color, label in renewal_rules:
        symbol = QgsSymbol.defaultSymbol(layer.geometryType())
        symbol.setColor(color)
        rule = QgsRuleBasedRenderer.Rule(symbol)
        expression = f'"{field_name}" >= {lower} AND "{field_name}" < {upper}'
        rule.setFilterExpression(expression)
        rule.setLabel(label)
        root_rule.appendChild(rule.clone())

    imputed_field = 'year_imputed'
    if layer.fields().indexFromName(imputed_field) != -1:
        imputed_symbol = QgsSymbol.defaultSymbol(layer.geometryType())
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


def style_temporal_layer(temporal_layer):
    """
    Rule-based styling for temporal layer.
    """
    from qgis.core import QgsRuleBasedRenderer, QgsSymbol

    type_field = temporal_layer.fields().lookupField("pipe_type")
    if type_field == -1:
        log_warning("No 'pipe_type' field found in temporal layer.")
        return

    ALL_TYPES = ("water", "stormwater", "wastewater")
    root = QgsRuleBasedRenderer.Rule(
        QgsSymbol.defaultSymbol(temporal_layer.geometryType())
    )
    buckets = [
        (0.0, 0.30, "Low Risk", 0.40),
        (0.30, 0.60, "Medium Risk", 0.80),
        (0.60, 1.01, "High Risk", 1.20),
    ]

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

            expression = (f"\"pipe_type\" = '{ptype}' AND "
                          f"\"renewal_need\" >= {low} AND "
                          f"\"renewal_need\" < {high}")
            rule = QgsRuleBasedRenderer.Rule(sym)
            rule.setFilterExpression(expression)
            rule.setLabel(f"{ptype.capitalize()} – {label}")
            root.appendChild(rule)

    renderer = QgsRuleBasedRenderer(root)
    temporal_layer.setRenderer(renderer)
    temporal_layer.triggerRepaint()
