# -*- coding: utf-8 -*-
import os
import json
import re

class ParameterLoader:
    """
    Loads calculation parameters from an external JSON file.
    """
    _parameters = None

    @classmethod
    def load_parameters(cls):
        """
        Loads parameters from parameters.json if not already loaded.
        """
        if cls._parameters is None:
            try:
                file_path = os.path.join(os.path.dirname(__file__), 'parameters.json')
                with open(file_path, 'r', encoding='utf-8') as f:
                    cls._parameters = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                # Fallback or re-raise depending on desired robustness.
                # For now, log error and return empty dict or raise.
                # Since the plugin logic depends on it, better to log/print and have an empty dict fallback
                # so it doesn't crash immediately on import, but calculations will fail gracefully (return 0).
                print(f"Error loading parameters.json: {e}")
                cls._parameters = {}
        return cls._parameters

    @classmethod
    def get_parameters(cls, pipeline_type):
        """
        Returns the parameters for a specific pipeline type (e.g., 'Avlopp', 'Vatten').
        """
        params = cls.load_parameters()
        return params.get(pipeline_type, {})

class MaterialNormalizer:
    """
    Normalizes material names using regex patterns to map messy inputs
    to canonical keys used in parameters.json.
    """

    # Regex patterns mapping to internal types
    # Order matters: put specific patterns before generic ones
    PATTERNS = [
        # --- Plastics ---
        (r'(pvc|p\.v\.c|polyvinyl)', 'PVC'),
        (r'(pe|polyeten|pem|pel|peh|ultra|pragma|flexoren)', 'PE'),
        (r'(plast|pp|propen)', 'Plast'), # Generic plastic fallback

        # --- Iron/Metal ---
        (r'(grå|gjj)', 'Gråjärn'),
        (r'(seg|sjj)', 'Segjärn'),
        (r'(järn)', 'Järn'), # Generic iron fallback
        (r'(stål|sta|gal)', 'Stål'),

        # --- Concrete/Cement ---
        (r'(btg|betong|cement)', 'Betong'),
        (r'(asb|eternit)', 'Asbestcement'),

        # --- Clay/Ceramic ---
        (r'(ler|höganäs|tegel)', 'Lergods'),
    ]

    @staticmethod
    def normalize(material, year, layer_type):
        """
        Determines the canonical parameter key based on material string, year, and layer type.
        """
        if not material or not isinstance(material, str):
            return MaterialNormalizer._default_unknown(layer_type)

        mat_lower = material.lower().strip()

        # 1. Identify Material Type
        identified_type = None
        for pattern, mat_type in MaterialNormalizer.PATTERNS:
            if re.search(pattern, mat_lower):
                identified_type = mat_type
                break

        if not identified_type:
            return MaterialNormalizer._default_unknown(layer_type)

        # 2. Map to Specific Parameter Key (Time/Type Logic)

        # --- Vatten Logic ---
        if layer_type == 'Vatten':
            if identified_type == 'PVC':
                return 'PVC <1970' if year < 1970 else 'PVC >=1970'
            if identified_type == 'PE' or identified_type == 'Plast':
                return 'PE'
            if identified_type == 'Gråjärn':
                return 'Gråjärn <1950' if year < 1950 else 'Gråjärn >=1950'
            if identified_type == 'Segjärn':
                return 'Segjärn <1980' if year < 1980 else 'Segjärn >=1980'
            if identified_type == 'Järn':
                return 'Gråjärn >=1950' # Default assumption
            if identified_type == 'Betong':
                return 'Övrigt/okänt' # Vatten mostly doesn't use concrete pipes in this model context, or mapped to unknown
            if identified_type == 'Stål':
                return 'Stål'
            if identified_type == 'Asbestcement':
                return 'Asbestcement'

            return 'Övrigt/okänt'

        # --- Avlopp Logic (Spillvatten/Dagvatten) ---
        elif layer_type in ['Spillvatten', 'Dagvatten']:
            prefix = 'S-' if layer_type == 'Spillvatten' else 'D-'

            if identified_type in ['Plast', 'PVC', 'PE']:
                return f'{prefix}Plast'

            if identified_type == 'Betong':
                if layer_type == 'Spillvatten':
                    if year < 1950: return 'S-Betong <1950'
                    if 1950 <= year < 1970: return 'S-Betong 1950-69'
                    return 'S-Betong >=1970'
                else: # Dagvatten
                    return 'D-Betong <1950' if year < 1950 else 'D-Betong >=1950'

            if identified_type == 'Lergods':
                return f'{prefix}Lergods'

            # If we found a type like "Järn" or "Stål" for Sewer, we currently don't have specific params
            # in the JSON provided for them, so they fall to default/unknown.

            return f'{prefix}Övrigt/okänt'

        return MaterialNormalizer._default_unknown(layer_type)

    @staticmethod
    def _default_unknown(layer_type):
        if layer_type == 'Vatten':
            return 'Övrigt/okänt'
        elif layer_type == 'Spillvatten':
            return 'S-Övrigt/okänt'
        elif layer_type == 'Dagvatten':
            return 'D-Övrigt/okänt'
        return 'Övrigt/okänt'
