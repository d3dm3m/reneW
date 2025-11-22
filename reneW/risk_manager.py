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
    UPDATED v2.0: Non-Destructive (Memory Layer) + Smart Renovation Detection + Parametric Cost.
    """

    def __init__(self):
        """Constructor."""
        self.consequence_calc = ConsequenceCalculator()
        self.economic_model = EconomicModel()
        # unit_costs kept for legacy, but economic_model now handles detailed cost
        self.unit_costs = ParameterLoader.get_unit_costs()

    def execute_analysis(self, layer, config, use_dimension_weighting, dimension_factor, progress_callback=None):
        """
        Executes analysis creating a NEW memory layer (Non-destructive).
        """
        layer_type = config['type']

        # Cost Parameters from Config
        cost_depth_std = config.get('cost_depth', 2.5)
        cost_slope = config.get('cost_slope', 1.0)
        cost_trench_box = config.get('cost_trench_box', False)
        cost_include_asphalt = config.get('cost_include_asphalt', True)
        cost_exc_price = config.get('cost_excavation_price', 350.0)

        # Override slope if Trench Box is active
        if cost_trench_box:
            cost_slope = 0.0

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

        # Add Risk Fields if they don't exist in source
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

        # Indices for Depth Calculation (if they exist)
        # Try to find fields: vg_start / vg_slut / mark_start / mark_slut (case-insensitive)
        def find_idx(names):
            for n in names:
                idx = source_fields.indexFromName(n)
                if idx != -1: return idx
            return -1

        vg_start_idx = find_idx(['vg_start', 'VG_START', 'z1', 'Z1'])
        vg_end_idx = find_idx(['vg_slut', 'VG_SLUT', 'z2', 'Z2'])
        mark_start_idx = find_idx(['mark_start', 'MARK_START', 'mz1', 'MZ1'])
        mark_end_idx = find_idx(['mark_slut', 'MARK_SLUT', 'mz2', 'MZ2'])

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

            # --- Depth Logic ---
            # Calculate feature-specific depth if fields exist
            calc_depth = cost_depth_std
            if all(idx != -1 for idx in [vg_start_idx, vg_end_idx, mark_start_idx, mark_end_idx]):
                try:
                    vg_avg = (float(attrs[vg_start_idx]) + float(attrs[vg_end_idx])) / 2.0
                    mark_avg = (float(attrs[mark_start_idx]) + float(attrs[mark_end_idx])) / 2.0
                    d = mark_avg - vg_avg
                    if d > 0:
                        calc_depth = d
                except (ValueError, TypeError):
                    pass # Fallback to std

            # --- Smart Renovation Logic ---
            reno_keywords = ['u-liner', 'strumpa', 'infodring', 'relining', 'renovering']
            is_renovated = False
            material_for_calc = raw_material

            if config.get('reno_method_field'):
                rm_idx = source_fields.indexFromName(config['reno_method_field'])
                if rm_idx != -1 and attrs[rm_idx]:
                    if any(k in str(attrs[rm_idx]).lower() for k in reno_keywords):
                        is_renovated = True

            if not is_renovated and raw_material and isinstance(raw_material, str):
                 if any(k in raw_material.lower() for k in reno_keywords):
                     is_renovated = True

            if is_renovated:
                if config.get('reno_year_field'):
                    ry_idx = source_fields.indexFromName(config['reno_year_field'])
                    if ry_idx != -1:
                        ry_val = DataSanitizer.sanitize_year(attrs[ry_idx])
                        if ry_val > 1900:
                            age = max(0, current_year - ry_val)
                material_for_calc = 'Plast'

            # --- Calculations ---
            pof = calculation_logic.calculate_renewal_need(
                layer_type, material_for_calc, age, install_year, dimension,
                use_dimension_weighting, dimension_factor
            )

            cof = self.consequence_calc.calculate_score(feature, dimension)

            length = feature.geometry().length() if feature.hasGeometry() else 0

            # Parametric Cost Calculation
            risk_cost = self.economic_model.calculate_risk_cost(
                pof=pof,
                consequence_score=cof,
                length=length,
                pipeline_type=layer_type,
                dimension=dimension,
                depth=calc_depth,
                slope=cost_slope,
                include_asphalt=cost_include_asphalt,
                excavation_price=cost_exc_price
            )

            risk_score = pof * cof

            # Create New Feature
            new_feat = QgsFeature()
            new_feat.setGeometry(feature.geometry())
            new_attrs = list(attrs) + [pof, risk_score, risk_cost]
            new_feat.setAttributes(new_attrs)
            new_features.append(new_feat)

            # High Risk Collection
            if pof >= 0.5:
                high_risk_results.append({
                    'layer_name': mem_layer_name,
                    'layer_id': mem_layer.id(), # Will be valid after add
                    'feature_id': i,
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
            'result_layer': mem_layer,
            'message': f"Analys klar. Skapade lager: {mem_layer_name}"
        }
