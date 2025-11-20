# -*- coding: utf-8 -*-

class ConsequenceCalculator:
    """
    Calculates the Consequence of Failure (CoF) score for a utility feature.
    """

    def __init__(self):
        pass

    def calculate_score(self, feature, dimension):
        """
        Calculates a consequence score (1.0 - 5.0) based on pipe dimension.

        Rule:
        - Dim > 400mm -> Score 5.0
        - Dim 300-400mm -> Score 4.0
        - Dim 200-300mm -> Score 3.0
        - Dim 100-200mm -> Score 2.0
        - Dim < 100mm -> Score 1.0

        :param feature: The QgsFeature being analyzed (reserved for future spatial checks).
        :param dimension: The diameter of the pipe in mm.
        :return: Float score between 1.0 and 5.0.
        """
        if dimension > 400:
            return 5.0
        elif dimension >= 300:
            return 4.0
        elif dimension >= 200:
            return 3.0
        elif dimension >= 100:
            return 2.0
        else:
            return 1.0

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

        :param pof: Probability of Failure (0.0 - 1.0).
        :param consequence_score: Consequence score (e.g., 1.0 - 5.0).
        :param length: Length of the pipe segment in meters.
        :param unit_cost: Replacement/Repair cost per meter (SEK).
        :return: Float estimated risk cost in currency.
        """
        # Using the formula provided: Risk_Cost = PoF * (Consequence_Score * Length * Unit_Cost)
        # Note: Consequence_Score acts as a multiplier here. A score of 5.0 implies the cost impact
        # is 5x the base unit replacement cost (reflecting social/environmental costs etc.)

        return pof * (consequence_score * length * unit_cost)
