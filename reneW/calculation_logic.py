# -*- coding: utf-8 -*-
"""
This module contains the calculation logic for the reneW QGIS plugin,
based on the Herz survival function model.
"""

# Parameters for each pipeline material, provided by the user.
# These are the 'a', 'b', and 'c' parameters for the Herz model.
PARAMETERS = {
    'Avlopp': {
        'S-Betong <1950': {'a': 12.394630847256085, 'b': 0.053337105584475054, 'c': 30},
        'S-Betong 1950-69': {'a': 2.2095582333960015, 'b': 0.0261337765364261, 'c': 30},
        'S-Betong >=1970': {'a': 61.29814935110069, 'b': 0.043661643079612622, 'c': 30},
        'S-Plast': {'a': 61.29814935110069, 'b': 0.043661643079612622, 'c': 30},
        'S-Övrigt/ okänt A': {'a': 19.156047145198428, 'b': 0.035905009195958362, 'c': 30},
        'S-Övrigt/ okänt B': {'a': 19.156047145198428, 'b': 0.035905009195958362, 'c': 30},
        'D-Betong <1950': {'a': 4.8243258238197129, 'b': 0.0274356222257029, 'c': 30},
        'D-Betong >=1950': {'a': 5.101654542374197, 'b': 0.02063502937932888, 'c': 30},
        'D-Plast': {'a': 61.29814935110069, 'b': 0.043661643079612622, 'c': 30},
        'D-Övrigt/ okänt C': {'a': 1.9366525983057512, 'b': 0.022838846131023077, 'c': 30},
        'D-Övrigt/ okänt D': {'a': 1.9366525983057512, 'b': 0.022838846131023077, 'c': 30},
        # Placeholder for relined pipes, assuming similar properties to new plastic pipes
        'Relined': {'a': 61.29814935110069, 'b': 0.043661643079612622, 'c': 30},
    },
    'Vatten': {
        # Placeholder for relined pipes, assuming similar properties to new PE pipes
        'Relined': {'a': 106.9383234418553, 'b': 0.062543758427977422, 'c': 50},
        'Gråjärn <1950': {'a': 55.490601649355284, 'b': 0.062332638228731335, 'c': 30},
        'Gråjärn >=1950': {'a': 55.490601649355284, 'b': 0.062332638228731335, 'c': 40},
        'Segjärn <1980': {'a': 55.490601649355284, 'b': 0.062332638228731335, 'c': 5},
        'Segjärn >=1980': {'a': 106.9383234418553, 'b': 0.062543758427977422, 'c': 50},
        'PE': {'a': 106.9383234418553, 'b': 0.062543758427977422, 'c': 50},
        'PVC <1970': {'a': 5.9999999999999982, 'b': 0.1039720770839918, 'c': 30},
        'PVC >=1970': {'a': 55.490601649355284, 'b': 0.062332638228731335, 'c': 40},
        'Övrigt/okänt A': {'a': 55.490601649355284, 'b': 0.062332638228731335, 'c': 30},
        'Övrigt/okänt B': {'a': 55.490601649355284, 'b': 0.062332638228731335, 'c': 30},
        'Förnyade pga status': {'a': 106.9383234418553, 'b': 0.062543758427977422, 'c': 50},
        'Förnyade utöver status': {'a': 106.9383234418553, 'b': 0.062543758427977422, 'c': 50},
        'Utökade': {'a': 106.9383234418553, 'b': 0.062543758427977422, 'c': 50},
        'Övrigt/okänt C': {'a': 55.490601649355284, 'b': 0.062332638228731335, 'c': 30},
        'Övrigt/okänt D': {'a': 55.490601649355284, 'b': 0.062332638228731335, 'c': 30},
    }
}

def get_parameter_key(pipeline_type: str, material: str, year: int) -> str:
    """
    Determines the correct parameter dictionary key based on material and installation year.
    It tries to match common abbreviations and names to the specific keys in the
    PARAMETERS dictionary.
    """
    if not material or not isinstance(material, str):
        return None

    mat_lower = material.lower().strip()

    # Check for relining keywords first, as this should override the base material
    if 'relin' in mat_lower or 'strumpa' in mat_lower:
        return 'Relined'

    if pipeline_type == 'Vatten':
        if 'gråjärn' in mat_lower or mat_lower in ['gj', 'gg']:
            return 'Gråjärn <1950' if year < 1950 else 'Gråjärn >=1950'
        if 'segjärn' in mat_lower or mat_lower in ['seg', 'sgj']:
            return 'Segjärn <1980' if year < 1980 else 'Segjärn >=1980'
        if 'pe' in mat_lower or 'pem' in mat_lower:
            return 'PE'
        if 'pvc' in mat_lower:
            return 'PVC <1970' if year < 1970 else 'PVC >=1970'

    elif pipeline_type == 'Avlopp':
        if 'betong' in mat_lower:
            if mat_lower.startswith('s-'):
                if year < 1950: return 'S-Betong <1950'
                if 1950 <= year < 1970: return 'S-Betong 1950-69'
                return 'S-Betong >=1970'
            elif mat_lower.startswith('d-'):
                return 'D-Betong <1950' if year < 1950 else 'D-Betong >=1950'
        if 'plast' in mat_lower:
            if mat_lower.startswith('s-'): return 'S-Plast'
            if mat_lower.startswith('d-'): return 'D-Plast'

    # Fallback for exact matches (e.g., for 'Övrigt/okänt' categories)
    if pipeline_type in PARAMETERS:
        for key in PARAMETERS[pipeline_type]:
            if mat_lower == key.lower():
                return key

    return None

def calculate_renewal_need(
    pipeline_type: str,
    material: str,
    age: int,
    year: int,
    dimension: float,
    use_dimension_weighting: bool,
    dimension_factor: float
) -> float:
    """
    Calculates the renewal need for a pipe based on its type, material, and age,
    using the Herz survival model, and optionally applies a dimension-based weighting.
    """
    param_key = get_parameter_key(pipeline_type, material, year)

    if not param_key or pipeline_type not in PARAMETERS or param_key not in PARAMETERS[pipeline_type]:
        return 0.0

    params = PARAMETERS[pipeline_type][param_key]
    a = params['a']
    b = params['b']
    c = params['c']

    if age <= c:
        return 0.0

    try:
        base = (age - c) / a
        if base < 0:
            return 0.0
        survival_probability = 1.0 / (1.0 + base**b)
    except (ValueError, ZeroDivisionError):
        return 0.0

    renewal_need = 1.0 - survival_probability

    # Apply optional dimension weighting as a consequence factor
    if use_dimension_weighting and dimension > 0 and dimension_factor > 0:
        # The formula increases the score for larger dimensions.
        # The user-provided factor controls the strength of this influence.
        # Formula: final_need = renewal_need * (1 + dimension * factor)
        final_need = renewal_need * (1 + (dimension * dimension_factor))
        return final_need

    return renewal_need
