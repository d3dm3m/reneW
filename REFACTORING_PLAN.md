# Refactoring Plan: reneW Risk-Based Asset Management Upgrade

## 1. Data Integrity & Normalization
**Finding:**
Current normalization logic in `calculation_logic.py` is fragile.
-   "P.V.C" defaults to `Övrigt/okänt` because strict substring matching (`'pvc' in 'p.v.c'`) fails.
-   "Betong" defaults to `Övrigt/okänt` because the code only looks for "btg".

**Recommendation:**
Create a dedicated `MaterialNormalizer` class.
-   **Mechanism:** Use a dictionary mapping regular expressions or list of synonyms to canonical material keys.
-   **Example:**
    ```python
    normalization_rules = {
        "PVC": [r"pvc", r"p\.v\.c", r"polyvinyl"],
        "Betong": [r"btg", r"betong", r"cement"],
        ...
    }
    ```
-   **Action:** Replace the `get_parameter_key` logic with this robust normalizer.

## 2. Parameter Extraction
**Finding:**
`PARAMETERS` in `calculation_logic.py` is hardcoded, making calibration difficult without code changes.

**Recommendation:**
Extract parameters to an external configuration file: `parameters.json`.
-   **Format:**
    ```json
    {
      "Avlopp": {
        "S-Betong <1950": {"a": 12.39, "b": 0.053, "c": 30},
        ...
      }
    }
    ```
-   **Loader:** Create a `ParameterLoader` class to read this file on plugin startup.

## 3. Architectural Expansion (CoF & Risk)
**Goal:** Transition from `PoF` (Probability of Failure) to `Risk = PoF * CoF`.

**Proposed Classes:**

### A. `ConsequenceCalculator`
*   **Responsibility:** Calculate the Consequence of Failure (CoF) score (0.0 - 1.0 or 1-5 scale).
*   **Inputs:** `QgsFeature`, `Config` (weights for location, dimension, etc.).
*   **Logic:**
    *   Check attributes (e.g., `dimension` - larger pipes = higher consequence).
    *   Check spatial context (future feature: is it near a hospital? road?).
*   **Integration:** Inject into `reneW.py` loop.

### B. `EconomicModel`
*   **Responsibility:** Convert technical metrics into monetary values.
*   **Methods:**
    *   `calculate_replacement_cost(material, dimension, length)`
    *   `calculate_risk_cost(pof, cof, replacement_cost)`

### C. `RiskManager` (New Service Class)
*   **Responsibility:** Decouple the analysis loop from the `ReneW` main class (UI Controller).
*   **Refactoring:** Move the massive loop inside `reneW.py:run()` into `RiskManager.execute_analysis(layer, config)`.
*   **Flow:**
    ```python
    pof = self.pof_calculator.calculate(...)
    cof = self.cof_calculator.calculate(...)
    risk = pof * cof
    ```

## 4. Implementation Steps

1.  **Extract Parameters:** Move dicts to JSON and update `calculation_logic.py`.
2.  **Harden Normalization:** Implement `MaterialNormalizer` and fix "P.V.C"/"Betong" issues.
3.  **Refactor Controller:** Move the `run()` loop to a new `RiskManager` class to prepare for complexity.
4.  **Implement CoF:** Add `ConsequenceCalculator` and call it within `RiskManager`.
5.  **Update UI:** Add CoF weighting settings to `ReneWDialog`.
