# -*- coding: utf-8 -*-
"""
This module contains the calculation logic for the reneW QGIS plugin,
based on the Herz survival function model.
"""
import os
import json

# Global variable to hold the loaded parameters
CONFIG_DATA = None
CONFIG_ERROR = None


def load_parameters():
    """
    Loads calculation parameters from the parameters.json file.
    This function is executed when the module is first imported.
    """
    global CONFIG_DATA, CONFIG_ERROR

    # Reset state
    CONFIG_DATA = None
    CONFIG_ERROR = None

    try:
        # Construct the path to the parameters.json file relative to this script
        plugin_dir = os.path.dirname(__file__)
        config_path = os.path.join(plugin_dir, 'parameters.json')

        if not os.path.exists(config_path):
            raise FileNotFoundError("parameters.json not found.")

        with open(config_path, 'r', encoding='utf-8') as f:
            CONFIG_DATA = json.load(f)

    except (FileNotFoundError, json.JSONDecodeError, Exception) as e:
        CONFIG_ERROR = f"Failed to load or parse 'parameters.json': {e}"
        CONFIG_DATA = None


def get_config_error():
    """Returns the configuration error message, if any."""
    return CONFIG_ERROR


def find_material_params(material: str, year: int, pipeline_type: str) -> dict:
    """
    Finds the Herz parameters for a given material, installation year,
    and pipeline type by searching through the loaded configuration data.
    """
    if not CONFIG_DATA or not isinstance(material, str):
        return None

    mat_lower = material.lower().strip()

    # Find the correct parameter set for the pipeline type
    param_set = next((s for s in CONFIG_DATA.get('parameter_sets', [])
                      if s['name'] == pipeline_type), None)

    if not param_set:
        return None

    # Search through the materials in the set
    for mat_config in param_set.get('materials', []):
        # Check for keyword match
        if not any(keyword in mat_lower for keyword in
                   mat_config.get('keywords', [])):
            continue

        # Check for year constraints
        year_min = mat_config.get('year_min')
        year_max = mat_config.get('year_max')

        if year_min and year >= year_min and (not year_max or year <= year_max):
            return mat_config.get('params')
        elif year_max and year <= year_max and not year_min:
            return mat_config.get('params')
        elif not year_min and not year_max:
            return mat_config.get('params')

    # If no specific material matched, return the default for the set
    return param_set.get('default_material', {}).get('params')


def calculate_renewal_need(
        pipeline_type: str,
        material: str,
        age: int,
        year: int,
        dimension: float,
        use_dimension_weighting: bool,
        dimension_factor: float) -> float:
    """
    Calculates the renewal need for a pipe based on its type, material,
    age, using the Herz survival model, and optionally applies a
    dimension-based weighting.
    """
    params = find_material_params(material, year, pipeline_type)

    if not params:
        return 0.0

    a = params.get('a')
    b = params.get('b')
    c = params.get('c')

    if None in [a, b, c] or age <= c:
        return 0.0

    try:
        # Ensure 'a' is not zero to prevent division by zero
        if a == 0:
            return 0.0

        base = (age - c) / a

        # The base of the power should not be negative
        if base < 0:
            return 0.0

        survival_probability = 1.0 / (1.0 + base**b)
    except (ValueError, ZeroDivisionError, OverflowError):
        return 0.0

    renewal_need = 1.0 - survival_probability

    if use_dimension_weighting and dimension > 0 and dimension_factor > 0:
        # Apply weighting factor, ensuring it doesn't lead to an excessive score
        # The formula is Renewal Need * (1 + (Dimension * Factor))
        # The factor is typically small (e.g., 0.001)
        weight = 1.0 + (dimension * dimension_factor)
        final_need = renewal_need * weight
        return final_need

    return renewal_need


# --- Initial load of parameters when the module is imported ---
load_parameters()
