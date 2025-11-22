# -*- coding: utf-8 -*-
from datetime import datetime
from qgis.core import QgsField
from qgis.PyQt.QtCore import QVariant
from . import calculation_logic
from .utils import ParameterLoader, DataSanitizer
from .strategic_models import ConsequenceCalculator, EconomicModel

class RiskManager:
    """
    Manages the risk analysis workflow, decoupling business logic from the UI controller.
    """

    def __init__(self):
        """Constructor."""
        self.consequence_calc = ConsequenceCalculator()
        self.economic_model = EconomicModel()
        self.unit_costs = ParameterLoader.get_unit_costs()

    def execute_analysis(self, layer, config, use_dimension_weighting, dimension_factor, progress_callback=None):
        """
        Executes the renewal need analysis for a single layer.

        :param layer: QgsVectorLayer to analyze.
        :param config: Dictionary containing field mappings and layer type.
        :param use_dimension_weighting: Boolean flag for weighting.
        :param dimension_factor: Float factor for weighting.
        :param progress_callback: Optional callable accepting an integer (0-100) for progress updates.
        :return: Dictionary containing 'status' (bool), 'count' (int), 'high_risk_results' (list), 'message' (str).
        """

        layer_type = config['type']

        # Determine unit cost for this layer type
        unit_cost = self.unit_costs.get(layer_type, 0.0)

        output_field_name = 'fornyelsebehov'
        risk_score_field = 'RISK_SCORE'
        risk_cost_field = 'RISK_COST'

        provider = layer.dataProvider()
        fields = provider.fields()

        # Ensure output fields exist
        new_fields = []
        if fields.indexFromName(output_field_name) == -1:
            new_fields.append(QgsField(output_field_name, QVariant.Double))
        if fields.indexFromName(risk_score_field) == -1:
            new_fields.append(QgsField(risk_score_field, QVariant.Double))
        if fields.indexFromName(risk_cost_field) == -1:
            new_fields.append(QgsField(risk_cost_field, QVariant.Double))

        if new_fields:
            provider.addAttributes(new_fields)
            layer.updateFields()
            fields = layer.fields() # Refresh

        # Get field indices
        material_idx = fields.indexFromName(config['material_field'])
        year_idx = fields.indexFromName(config['year_field'])
        dimension_idx = fields.indexFromName(config['dimension_field'])
        output_idx = fields.indexFromName(output_field_name)
        risk_score_idx = fields.indexFromName(risk_score_field)
        risk_cost_idx = fields.indexFromName(risk_cost_field)

        # Validation
        if any(idx == -1 for idx in [material_idx, year_idx, dimension_idx]):
            return {
                'status': False,
                'count': 0,
                'high_risk_results': [],
                'message': f"Något av grundfälten (material, anläggningsår, dimension) kunde inte hittas i lagret '{layer.name()}'."
            }

        current_year = datetime.now().year
        high_risk_results = []

        feature_count = layer.featureCount()
        processed_count = 0

        layer.startEditing()

        try:
            for i, feature in enumerate(layer.getFeatures()):
                # Progress update
                if progress_callback and feature_count > 0:
                    if i % max(1, int(feature_count / 100)) == 0:
                        percent = int((i / feature_count) * 100)
                        progress_callback(percent)

                attrs = feature.attributes()

                # --- DATA SANITIZATION SPRINT 3.5 ---

                # 1. Material
                material = attrs[material_idx]
                # MaterialNormalizer handles logic later, but we pass raw string.

                # 2. Year (Sanitized)
                raw_year = attrs[year_idx]
                installation_year = DataSanitizer.sanitize_year(raw_year)

                age = max(0, current_year - installation_year)

                # Renovation Logic (Semantic Keyword Detection)
                # Keywords: u-liner, strumpa, infodring, relining, renovering
                reno_keywords = ['u-liner', 'strumpa', 'infodring', 'relining', 'renovering']
                is_renovated = False

                # 1. Check Explicit Renovation Method Field
                if config.get('reno_method_field'):
                    reno_method_idx = fields.indexFromName(config['reno_method_field'])
                    if reno_method_idx != -1:
                        reno_method = attrs[reno_method_idx]
                        if reno_method and isinstance(reno_method, str):
                            if any(k in reno_method.lower() for k in reno_keywords):
                                is_renovated = True

                # 2. Check Material Field (Implicit Renovation)
                if not is_renovated and material and isinstance(material, str):
                     if any(k in material.lower() for k in reno_keywords):
                         is_renovated = True

                # Apply Renovation Actions
                if is_renovated:
                    # Action A: Reset Age if valid reno_year exists
                    if config.get('reno_year_field'):
                        reno_year_idx = fields.indexFromName(config['reno_year_field'])
                        if reno_year_idx != -1:
                            raw_reno_year = attrs[reno_year_idx]
                            reno_year = DataSanitizer.sanitize_year(raw_reno_year)
                            if reno_year > 1900:
                                age = max(0, current_year - reno_year)

                    # Action B: Material Swap (Liner = New Plastic Pipe)
                    material = 'Plast'

                # 3. Dimension (Sanitized)
                raw_dimension = attrs[dimension_idx]
                dimension = DataSanitizer.sanitize_dimension(raw_dimension)

                # --- END SANITIZATION ---

                # 1. PoF Calculation
                renewal_need = calculation_logic.calculate_renewal_need(
                    pipeline_type=layer_type,
                    material=material,
                    age=age,
                    year=installation_year,
                    dimension=dimension,
                    use_dimension_weighting=use_dimension_weighting,
                    dimension_factor=dimension_factor
                )

                # 2. CoF Calculation
                cof_score = self.consequence_calc.calculate_score(feature, dimension)

                # 3. Risk Cost Calculation
                length = 0.0
                if feature.hasGeometry():
                    length = feature.geometry().length()

                risk_cost = self.economic_model.calculate_risk_cost(
                    pof=renewal_need,
                    consequence_score=cof_score,
                    length=length,
                    unit_cost=unit_cost
                )

                # 4. Combined Risk Score
                risk_score = renewal_need * cof_score

                # Update Attributes
                layer.changeAttributeValue(feature.id(), output_idx, renewal_need)
                layer.changeAttributeValue(feature.id(), risk_score_idx, risk_score)
                layer.changeAttributeValue(feature.id(), risk_cost_idx, risk_cost)

                # Collect High Risk
                if renewal_need >= 0.5:
                    high_risk_results.append({
                        'layer_name': layer.name(),
                        'layer_id': layer.id(),
                        'feature_id': feature.id(),
                        'material': material,
                        'age': age,
                        'renewal_need': renewal_need,
                        'risk_score': risk_score,
                        'risk_cost': risk_cost
                    })

            if layer.commitChanges():
                processed_count = layer.featureCount()
                if progress_callback:
                    progress_callback(100)
                return {
                    'status': True,
                    'count': processed_count,
                    'high_risk_results': high_risk_results,
                    'message': f"Beräkning klar för lagret '{layer.name()}'."
                }
            else:
                layer.rollBack()
                return {
                    'status': False,
                    'count': 0,
                    'high_risk_results': [],
                    'message': f"Kunde inte spara ändringar för lagret '{layer.name()}'."
                }

        except Exception as e:
            layer.rollBack()
            return {
                'status': False,
                'count': 0,
                'high_risk_results': [],
                'message': f"Ett oväntat fel inträffade: {str(e)}"
            }
