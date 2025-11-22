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
        data = cls.load_parameters()
        # Check if 'parameters' key exists (new v2 structure), else fallback
        params_root = data.get('parameters', data)
        return params_root.get(pipeline_type, {})

    @classmethod
    def get_unit_costs(cls):
        """
        Returns the unit costs dictionary.
        """
        data = cls.load_parameters()
        return data.get('unit_costs', {})

    @classmethod
    def get_defaults(cls):
        """
        Returns the defaults configuration dictionary.
        """
        data = cls.load_parameters()
        return data.get('defaults', {})

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

        val_to_check = raw_year

        if val_to_check in null_markers:
            return substitute

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

        try:
            if isinstance(raw_dim, (int, float)):
                return float(raw_dim)
            elif isinstance(raw_dim, str):
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
        # --- Explicit Unknowns ---
        (r'(odefinierad|okänt|unknown|övrigt)', 'Övrigt'),

        # --- Plastics ---
        (r'(pvc|p\.v\.c|polyvinyl)', 'PVC'),
        (r'(pe|polyeten|pem|pel|peh|ultra|pragma|flexoren)', 'PE'),
        (r'(plast|pp|propen)', 'Plast'),

        # --- Iron/Metal ---
        (r'(grå|gjj)', 'Gråjärn'),
        (r'(seg|sjj)', 'Segjärn'),
        (r'(gjut)', 'Gjutjärn'),
        (r'(järn)', 'Gjutjärn'), # Default generic iron to Cast Iron if not specific
        (r'(stål|sta|gal)', 'Stål'),

        # --- Concrete/Cement ---
        (r'(btg|betong|cement)', 'Betong'),
        (r'(asb|eternit)', 'Asbestcement'),

        # --- Clay/Ceramic ---
        (r'(ler|höganäs|tegel)', 'Tegel'), # Map Lergods/Tegel to "Tegel" for Spillvatten, or generic
    ]

    @staticmethod
    def normalize(material, layer_type):
        """
        Determines the canonical parameter key based on material string and layer type.
        Now maps to clean keys like 'Betong', 'Plast', etc.
        """
        if not material or not isinstance(material, str):
            return 'Övrigt'

        mat_lower = material.lower().strip()

        # 1. Identify Material Type
        identified_type = None
        for pattern, mat_type in MaterialNormalizer.PATTERNS:
            if re.search(pattern, mat_lower):
                identified_type = mat_type
                break

        if not identified_type:
            return 'Övrigt'

        # 2. Map to Specific Key available in JSON for that layer type

        # --- Vatten ---
        if layer_type == 'Vatten':
            if identified_type in ['Gråjärn', 'Segjärn', 'PVC', 'PE', 'Stål', 'Asbestcement', 'Övrigt']:
                return identified_type
            if identified_type == 'Plast': return 'PE' # Default Vatten plastic
            if identified_type == 'Gjutjärn': return 'Gråjärn'
            # Vatten usually doesn't use Concrete/Tegel in this model, map to Övrigt?
            return 'Övrigt'

        # --- Spillvatten ---
        elif layer_type == 'Spillvatten':
            if identified_type in ['Betong', 'Plast', 'Gjutjärn', 'Tegel', 'Övrigt']:
                return identified_type
            if identified_type in ['PVC', 'PE']: return 'Plast'
            if identified_type in ['Gråjärn', 'Segjärn']: return 'Gjutjärn'
            if identified_type == 'Asbestcement': return 'Övrigt' # Or map to Betong? Stick to Övrigt.
            return 'Övrigt'

        # --- Dagvatten ---
        elif layer_type == 'Dagvatten':
            if identified_type in ['Betong', 'Plast', 'Övrigt']:
                return identified_type
            if identified_type in ['PVC', 'PE']: return 'Plast'
            # Dagvatten usually doesn't use Iron/Tegel in this model
            return 'Övrigt'

        return 'Övrigt'
