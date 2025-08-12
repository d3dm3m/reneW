# -*- coding: utf-8 -*-
"""
This module contains the calculation logic for the reneW QGIS plugin,
based on the Herz survival function model.
"""

# Parameters for each pipeline material, provided by the user.
# These are the 'a', 'b', and 'c' parameters for the Herz model.
# NOTE: Parameters for 'Stål', 'Asbestcement', and 'Lergods' are placeholders
# based on other materials and should be calibrated with real-world data.
PARAMETERS = {
    'Avlopp': {
        'S-Betong <1950': {'a': 12.394630847256085, 'b': 0.053337105584475054, 'c': 30},
        'S-Betong 1950-69': {'a': 2.2095582333960015, 'b': 0.0261337765364261, 'c': 30},
        'S-Betong >=1970': {'a': 61.29814935110069, 'b': 0.043661643079612622, 'c': 30},
        'S-Plast': {'a': 61.29814935110069, 'b': 0.043661643079612622, 'c': 30},
        'S-Lergods': {'a': 19.156047145198428, 'b': 0.035905009195958362, 'c': 30}, # Placeholder, as Övrigt/okänt A
        'S-Övrigt/okänt': {'a': 19.156047145198428, 'b': 0.035905009195958362, 'c': 30}, # Using S-Övrigt/okänt A

        'D-Betong <1950': {'a': 4.8243258238197129, 'b': 0.0274356222257029, 'c': 30},
        'D-Betong >=1950': {'a': 5.101654542374197, 'b': 0.02063502937932888, 'c': 30},
        'D-Plast': {'a': 61.29814935110069, 'b': 0.043661643079612622, 'c': 30},
        'D-Lergods': {'a': 1.9366525983057512, 'b': 0.022838846131023077, 'c': 30}, # Placeholder, as Övrigt/okänt C
        'D-Övrigt/okänt': {'a': 1.9366525983057512, 'b': 0.022838846131023077, 'c': 30}, # Using D-Övrigt/okänt C
    },
    'Vatten': {
        'Gråjärn <1950': {'a': 55.490601649355284, 'b': 0.062332638228731335, 'c': 30},
        'Gråjärn >=1950': {'a': 55.490601649355284, 'b': 0.062332638228731335, 'c': 40},
        'Segjärn <1980': {'a': 55.490601649355284, 'b': 0.062332638228731335, 'c': 5},
        'Segjärn >=1980': {'a': 106.9383234418553, 'b': 0.062543758427977422, 'c': 50},
        'PE': {'a': 106.9383234418553, 'b': 0.062543758427977422, 'c': 50},
        'PVC <1970': {'a': 5.9999999999999982, 'b': 0.1039720770839918, 'c': 30},
        'PVC >=1970': {'a': 55.490601649355284, 'b': 0.062332638228731335, 'c': 40},
        'Stål': {'a': 55.490601649355284, 'b': 0.062332638228731335, 'c': 30}, # Placeholder, as Gråjärn <1950
        'Asbestcement': {'a': 55.490601649355284, 'b': 0.062332638228731335, 'c': 30}, # Placeholder, as Gråjärn <1950
        'Övrigt/okänt': {'a': 55.490601649355284, 'b': 0.062332638228731335, 'c': 30}, # Using Övrigt/okänt A
    }
}

def get_parameter_key(material: str, year: int, layer_type: str) -> str:
    """
    Determines the correct parameter dictionary key based on material, installation year, and layer type.
    """
    if not material or not isinstance(material, str):
        return 'Övrigt/okänt'

    mat_lower = material.lower().strip()

    # Plastics
    if any(p in mat_lower for p in ['pvc', 'pe', 'pp', 'pem', 'pel', 'peh', 'polyeten', 'ultra', 'pragma', 'flexoren']):
        if layer_type == 'Vatten':
            if 'pvc' in mat_lower:
                return 'PVC <1970' if year < 1970 else 'PVC >=1970'
            return 'PE' # Group all other plastics under PE for Vatten
        elif layer_type in ['Spillvatten', 'Dagvatten']:
            return 'S-Plast' if layer_type == 'Spillvatten' else 'D-Plast'

    # Iron pipes
    if 'järn' in mat_lower or mat_lower in ['gjj', 'sjj', 'segj', 'seg']:
        if 'grå' in mat_lower or mat_lower == 'gjj':
            return 'Gråjärn <1950' if year < 1950 else 'Gråjärn >=1950'
        if 'seg' in mat_lower or mat_lower == 'sjj':
            return 'Segjärn <1980' if year < 1980 else 'Segjärn >=1980'
        return 'Gråjärn >=1950' # Default for generic 'järn'

    # Concrete pipes
    if 'btg' in mat_lower:
        if layer_type == 'Spillvatten':
            if year < 1950: return 'S-Betong <1950'
            if 1950 <= year < 1970: return 'S-Betong 1950-69'
            return 'S-Betong >=1970'
        elif layer_type == 'Dagvatten':
            return 'D-Betong <1950' if year < 1950 else 'D-Betong >=1950'

    # Steel pipes
    if 'stål' in mat_lower or 'sta' in mat_lower or 'gal' in mat_lower:
        return 'Stål'

    # Asbestos cement
    if 'asb' in mat_lower or 'eternit' in mat_lower:
        return 'Asbestcement'

    # Clay pipes
    if 'ler' in mat_lower or 'höganäs' in mat_lower or 'tegel' in mat_lower:
        return 'S-Lergods' if layer_type == 'Spillvatten' else 'D-Lergods'

    # Default to 'unknown'
    if layer_type == 'Vatten':
        return 'Övrigt/okänt'
    else: # Spillvatten or Dagvatten
        return 'S-Övrigt/okänt' if layer_type == 'Spillvatten' else 'D-Övrigt/okänt'


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
    # Map the UI layer type ('Vatten', 'Spillvatten', 'Dagvatten') to the
    # parameter dictionary keys ('Vatten', 'Avlopp')
    calc_pipeline_type = 'Avlopp' if pipeline_type in ['Spillvatten', 'Dagvatten'] else 'Vatten'

    param_key = get_parameter_key(material, year, pipeline_type)

    if not param_key or calc_pipeline_type not in PARAMETERS or param_key not in PARAMETERS[calc_pipeline_type]:
        return 0.0

    params = PARAMETERS[calc_pipeline_type][param_key]
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

    if use_dimension_weighting and dimension > 0 and dimension_factor > 0:
        final_need = renewal_need * (1 + (dimension * dimension_factor))
        return final_need

    return renewal_need
