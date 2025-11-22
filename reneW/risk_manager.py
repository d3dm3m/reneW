# -*- coding: utf-8 -*-
from datetime import datetime
from qgis.core import QgsField, QgsVectorLayer, QgsFeature, QgsGeometry
from qgis.PyQt.QtCore import QVariant
from . import calculation_logic
from .utils import ParameterLoader, DataSanitizer
from .strategic_models import ConsequenceCalculator, EconomicModel

class RiskManager:
    """
    Manages the risk analysis workflow.
    UPDATED v2.0: Non-Destructive (Memory Layer) + Smart Renovation Detection.
    """

    def __init__(self):
        """Constructor."""
        self.consequence_calc = ConsequenceCalculator()
        self.economic_model = EconomicModel()
        self.unit_costs = ParameterLoader.get_unit_costs()

    def execute_analysis(self, layer, config, use_dimension_weighting, dimension_factor, progress_callback=None):
        """
        Executes analysis creating a NEW memory layer (Non-destructive).
        """
        layer_type = config['type']
        unit_cost = self.unit_costs.get(layer_type, 0.0)

        # 1. Setup Memory Layer
        # Copy fields from source
        source_fields = layer.fields()
        output_crs = layer.crs().authid()

        # Create memory layer
        mem_layer_name = f"reneW: {layer.name()}"
        mem_layer = QgsVectorLayer(f"LineString?crs={output_crs}", mem_layer_name, "memory")
        mem_pr = mem_layer.dataProvider()

        # Prepare fields (Source + New Risk Fields)
        new_fields = [f for f in source_fields] # Copy existing

        # Add Risk Fields if they don't exist in source (likely won't in memory layer context, but good practice)
        out_field_map = {
            'fornyelsebehov': QgsField('fornyelsebehov', QVariant.Double),
            'RISK_SCORE': QgsField('RISK_SCORE', QVariant.Double),
            'RISK_COST': QgsField('RISK_COST', QVariant.Double)
        }

        for fname, ffield in out_field_map.items():
            new_fields.append(ffield)

        mem_pr.addAttributes(new_fields)
        mem_layer.updateFields()

        # Get Indices for calculation
        try:
            mat_idx = source_fields.indexFromName(config['material_field'])
            year_idx = source_fields.indexFromName(config['year_field'])
            dim_idx = source_fields.indexFromName(config['dimension_field'])
        except KeyError:
             return {'status': False, 'message': "Missing required fields."}

        current_year = datetime.now().year
        high_risk_results = []
        new_features = []

        feature_count = layer.featureCount()

        # 2. Iterate and Calculate
        for i, feature in enumerate(layer.getFeatures()):
            if progress_callback and feature_count > 0 and i % 100 == 0:
                progress_callback(int((i / feature_count) * 100))

            attrs = feature.attributes()

            # --- Logic Extraction ---
            raw_material = attrs[mat_idx] if mat_idx != -1 else ""
            raw_year = attrs[year_idx] if year_idx != -1 else 0
            raw_dim = attrs[dim_idx] if dim_idx != -1 else 0

            # Sanitization
            install_year = DataSanitizer.sanitize_year(raw_year)
            age = max(0, current_year - install_year)
            dimension = DataSanitizer.sanitize_dimension(raw_dim)

            # --- Smart Renovation Logic ---
            # Keywords: u-liner, strumpa, infodring, relining, renovering
            reno_keywords = ['u-liner', 'strumpa', 'infodring', 'relining', 'renovering']
            is_renovated = False
            material_for_calc = raw_material

            # Check explicit field
            if config.get('reno_method_field'):
                rm_idx = source_fields.indexFromName(config['reno_method_field'])
                if rm_idx != -1 and attrs[rm_idx]:
                    if any(k in str(attrs[rm_idx]).lower() for k in reno_keywords):
                        is_renovated = True

            # Check implicit material field (Fallback)
            if not is_renovated and raw_material and isinstance(raw_material, str):
                 if any(k in raw_material.lower() for k in reno_keywords):
                     is_renovated = True

            if is_renovated:
                # Reset Age
                if config.get('reno_year_field'):
                    ry_idx = source_fields.indexFromName(config['reno_year_field'])
                    if ry_idx != -1:
                        ry_val = DataSanitizer.sanitize_year(attrs[ry_idx])
                        if ry_val > 1900:
                            age = max(0, current_year - ry_val)
                # Swap Material Curve
                material_for_calc = 'Plast'

            # --- Calculations ---
            pof = calculation_logic.calculate_renewal_need(
                layer_type, material_for_calc, age, install_year, dimension,
                use_dimension_weighting, dimension_factor
            )

            cof = self.consequence_calc.calculate_score(feature, dimension)

            length = feature.geometry().length() if feature.hasGeometry() else 0
            risk_cost = self.economic_model.calculate_risk_cost(pof, cof, length, unit_cost)
            risk_score = pof * cof

            # Create New Feature
            new_feat = QgsFeature()
            new_feat.setGeometry(feature.geometry())

            # attributes = original + [pof, score, cost]
            new_attrs = list(attrs) + [pof, risk_score, risk_cost]
            new_feat.setAttributes(new_attrs)
            new_features.append(new_feat)

            # High Risk Collection
            if pof >= 0.5:
                high_risk_results.append({
                    'layer_name': mem_layer_name,
                    'layer_id': mem_layer.id(), # Will be valid after add
                    'feature_id': i, # Approx ID
                    'material': raw_material,
                    'age': age,
                    'renewal_need': pof,
                    'risk_score': risk_score,
                    'risk_cost': risk_cost
                })

        # 3. Commit to Memory Layer
        mem_pr.addFeatures(new_features)
        mem_layer.updateExtents()

        return {
            'status': True,
            'count': len(new_features),
            'high_risk_results': high_risk_results,
            'result_layer': mem_layer, # Return the object
            'message': f"Analys klar. Skapade lager: {mem_layer_name}"
        }
