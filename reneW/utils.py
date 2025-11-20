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

    @classmethod
    def get_unit_costs(cls):
        """
        Returns the unit costs dictionary.
        """
        params = cls.load_parameters()
        return params.get('unit_costs', {})

    @classmethod
    def get_defaults(cls):
        """
        Returns the defaults configuration dictionary.
        """
        params = cls.load_parameters()
        return params.get('defaults', {})

class DataSanitizer:
    """
    Sanitizes input data by handling null markers and substituting default values.
    """

    @staticmethod
    def sanitize_year(raw_year):
        """
        Sanitizes the installation year.
        Checks for null markers (1900, 0) and returns substitute (1980) if found.
        """
        defaults = ParameterLoader.get_defaults()
        substitute = defaults.get("unknown_year_substitute", 1980)
        null_markers = defaults.get("null_markers", {}).get("year", [])

        # Convert input to check against markers
        val_to_check = raw_year

        # Check if it's a marker
        if val_to_check in null_markers:
            return substitute

        # Also check string representation if raw_year is int/float
        if str(val_to_check) in [str(m) for m in null_markers]:
             return substitute

        try:
            year = int(raw_year)
            if year in null_markers:
                return substitute
            return year
        except (ValueError, TypeError, AttributeError):
            return substitute

    @staticmethod
    def sanitize_dimension(raw_dim):
        """
        Sanitizes the dimension.
        Handles null markers ("-", "--") and parsing of complex strings ("225_I").
        Returns float or substitute (150).
        """
        defaults = ParameterLoader.get_defaults()
        substitute = defaults.get("unknown_dimension_substitute", 150.0)
        null_markers = defaults.get("null_markers", {}).get("dimension", [])

        if raw_dim in null_markers:
            return float(substitute)

        if str(raw_dim) in [str(m) for m in null_markers]:
            return float(substitute)

        if raw_dim is None:
            return float(substitute)

        # Attempt parse
        try:
            if isinstance(raw_dim, (int, float)):
                return float(raw_dim)
            elif isinstance(raw_dim, str):
                 # Clean string logic moved from risk_manager
                 # Extract numeric part before any non-numeric characters (except dot)
                 # e.g. "225_I" -> 225
                 numeric_part = ''.join(filter(lambda c: c.isdigit() or c == '.', raw_dim.split('_')[0].split('/')[0]))
                 if numeric_part:
                     return float(numeric_part)
        except (ValueError, TypeError):
            pass

        return float(substitute)

class MaterialNormalizer:
    """
    Normalizes material names using regex patterns to map messy inputs
    to canonical keys used in parameters.json.
    """

    # Regex patterns mapping to internal types
    PATTERNS = [
        # --- Explicit Unknowns (Sanitization Sprint 3.5) ---
        (r'(odefinierad|okänt|unknown)', 'Unknown'),

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

        if not identified_type or identified_type == 'Unknown':
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
                return 'Övrigt/okänt'
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
