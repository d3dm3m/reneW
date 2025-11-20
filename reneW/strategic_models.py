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
    Calculates the monetary risk associated with a failure.
    """

    def __init__(self):
        pass

    def calculate_risk_cost(self, pof, consequence_score, length, unit_cost):
        """
        Estimates the Expected Annual Cost of risk.
        Risk_Cost = PoF * (Consequence_Score * Length * Unit_Cost)
        """
        return pof * (consequence_score * length * unit_cost)
