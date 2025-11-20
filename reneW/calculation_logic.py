# -*- coding: utf-8 -*-
"""
This module contains the calculation logic for the reneW QGIS plugin,
based on the Herz survival function model.
"""

from .utils import ParameterLoader, MaterialNormalizer

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
    # Use the robust normalizer to get the key
    # Note: 'pipeline_type' passed here is now strictly 'Vatten', 'Spillvatten', 'Dagvatten'
    # The logic relies on ParameterLoader returning the correct dict for this type.

    # Normalize material to get the key (e.g. "Betong")
    param_key = MaterialNormalizer.normalize(material, pipeline_type)

    # Load parameters via the loader for the specific system type
    parameters = ParameterLoader.get_parameters(pipeline_type)

    if not param_key or param_key not in parameters:
        # Fallback to Övrigt if key missing but valid system
        if 'Övrigt' in parameters:
            param_key = 'Övrigt'
        else:
            return 0.0

    params = parameters[param_key]
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
