# -*- coding: utf-8 -*-
from .utils import ParameterLoader

class ConsequenceCalculator:
    """
    Calculates the Consequence of Failure (CoF) score for a utility feature.
    """

    def __init__(self):
        pass

    def calculate_score(self, feature, dimension):
        """
        Calculates a consequence score based on pipe dimension.
        Uses thresholds from parameters.json if available, else defaults.
        """
        # Load weights from JSON or default
        data = ParameterLoader.load_parameters()
        weights = data.get('consequence_weights', {})

        thresh_small = weights.get('dimension_threshold_small', 150)
        thresh_large = weights.get('dimension_threshold_large', 400)
        score_small = weights.get('score_small', 1.0)
        score_medium = weights.get('score_medium', 2.0)
        score_large = weights.get('score_large', 5.0)

        if dimension > thresh_large:
            return score_large
        elif dimension >= thresh_small:
            return score_medium
        else:
            return score_small

class EconomicModel:
    """
    Calculates the monetary risk associated with a failure using a Parametric Trench Model.
    """

    def __init__(self):
        self.params = ParameterLoader.load_parameters().get('cost_parameters', {})
        self.prices = self.params.get('prices', {})
        self.trench = self.params.get('trench_defaults', {})

    def calculate_trench_volume(self, length, depth, diameter, slope):
        """
        Calculates the volume of excavation based on a trapezoidal trench.

        Base_Width = Diameter (m) + Padding.
        Top_Width = Base_Width + (2 * Slope * Depth).
        Area = (Base_Width + Top_Width) / 2 * Depth.
        Volume = Area * Length.
        """
        diameter_m = diameter / 1000.0 # Convert mm to m
        base_width = diameter_m + self.trench.get('width_base_padding', 0.6)
        top_width = base_width + (2 * slope * depth)

        area = ((base_width + top_width) / 2) * depth
        volume = area * length

        return volume, top_width

    def calculate_advanced_cost(self, pipeline_type, length, dimension):
        """
        Calculates total replacement cost using parametric inputs.
        """
        depth = self.trench.get('depth', 2.5)
        slope = self.trench.get('slope_ratio', 1.0)

        # 1. Excavation & Filling
        excavation_vol, top_width = self.calculate_trench_volume(length, depth, dimension, slope)
        excavation_cost = excavation_vol * self.prices.get('excavation_m3', 350)
        filling_cost = excavation_vol * self.prices.get('filling_m3', 250) # Simplified: Assume filling = excavation volume

        # 2. Pipe Material
        pipe_price = self.prices.get('pipe_material_per_m', {}).get(pipeline_type, 800)
        pipe_cost = length * pipe_price

        # 3. Surface Restoration
        surface_cost = 0.0
        if self.trench.get('include_asphalt', True):
            extra_width = self.trench.get('restoration_width_extra', 1.0)
            surface_area = (top_width + extra_width) * length
            surface_cost = surface_area * self.prices.get('asphalt_m2', 400)

        total_cost = excavation_cost + filling_cost + pipe_cost + surface_cost
        return total_cost

    def calculate_risk_cost(self, pof, consequence_score, length, unit_cost_deprecated=None, pipeline_type="Vatten", dimension=150):
        """
        Estimates the Expected Annual Cost of risk using the advanced model.

        Note: unit_cost_deprecated is kept for backward compatibility signatures
        but ignored in favor of advanced calculation.
        """
        total_replacement_cost = self.calculate_advanced_cost(pipeline_type, length, dimension)

        # Risk Cost = PoF * CoF_Score * Replacement_Cost
        # Note: In the previous model, CoF was a multiplier on top of length*unit_cost.
        # Here, total_replacement_cost is the base financial impact.
        # CoF score is a dimensionless multiplier representing SOCIAL/strategic impact.

        return pof * consequence_score * total_replacement_cost
