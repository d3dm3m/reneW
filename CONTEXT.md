# Project Context & Developer Handover (v2.0.0)

## 1. Project Structure
```
.
├── reneW/
│   ├── LICENSE
│   ├── __init__.py               # Plugin entry point wrapper
│   ├── calculation_logic.py      # Core Herz model implementation (PoF)
│   ├── icon.png
│   ├── metadata.txt              # QGIS plugin metadata
│   ├── parameters.json           # Externalized configuration (Herz params, costs, defaults)
│   ├── reneW.py                  # Main controller & UI coordination
│   ├── reneW_dialog.py           # Main configuration dialog logic
│   ├── reneW_dialog_base.ui      # Main configuration dialog UI
│   ├── results_dialog.py         # Results table dialog logic
│   ├── results_dialog.ui         # Results table dialog UI
│   ├── risk_manager.py           # Business logic orchestrator
│   ├── strategic_models.py       # Consequence & Economic risk models
│   └── utils.py                  # Data sanitization, normalization, & loading utils
├── CHANGELOG.md
└── README.md
```

## 2. Tech Stack
*   **Language:** Python 3
*   **Framework:** QGIS API (PyQGIS)
*   **UI Library:** PyQt5
*   **Dependencies:** Standard Python libraries (`os`, `datetime`, `csv`, `json`, `re`). No external PyPI dependencies to ensure easy deployment.

## 3. Architecture Overview
*   **Pattern:** Controller-Manager-Model.
*   **Controller (`reneW.py`):** Manages the plugin lifecycle, UI interaction, map canvas updates, and visualization (styling/bundling). It delegates heavy analysis to `RiskManager` via a background-friendly loop (using `QProgressDialog`).
*   **Manager (`risk_manager.py`):** The "Workhorse". It orchestrates the analysis loop:
    1.  Sanitizes data.
    2.  Calculates Probability (PoF).
    3.  Calculates Consequence (CoF).
    4.  Calculates Financial Risk.
    5.  Updates layer attributes.
*   **Models:**
    *   `calculation_logic.py`: Herz Survival Model (Probability).
    *   `strategic_models.py`: Consequence & Economic Risk Models.
*   **Utilities (`utils.py`):** Handles `DataSanitizer` (cleaning inputs), `MaterialNormalizer` (regex matching), and `ParameterLoader` (JSON config).

## 4. Key Components
*   **`RiskManager` (risk_manager.py):**
    *   Decoupled from the UI.
    *   Executes `execute_analysis()` for a given layer.
    *   Uses callbacks to report progress.
*   **`DataSanitizer` (utils.py):**
    *   Prevents calculation errors by cleaning dirty data (e.g., "1900" -> 1980, "-" -> 150).
*   **`ConsequenceCalculator` (strategic_models.py):**
    *   Calculates a score (1-5) based on pipe dimension thresholds (>400mm = Score 5).
*   **`EconomicModel` (strategic_models.py):**
    *   Calculates `RISK_COST` (SEK) = `PoF * CoF * Length * Unit_Cost`.
*   **`ReneW` (reneW.py):**
    *   Handles post-analysis visualization:
        *   **Auto-Styling:** Applies 'Reds' graduated renderer to `RISK_COST`.
        *   **Project Bundling:** Clusters high-risk pipes into "Suggested Project" polygons.

## 5. Data Flow (The Pipeline)
1.  **Configuration:** User selects layers and maps fields in `ReneWDialog`.
2.  **Analysis Loop (RiskManager):**
    *   **Sanitization:** Input attributes (Year, Material, Dimension) are cleaned via `DataSanitizer` and `MaterialNormalizer`.
    *   **Probability (PoF):** `calculation_logic` computes failure likelihood (0.0-1.0) using Herz parameters from `parameters.json`.
    *   **Consequence (CoF):** `ConsequenceCalculator` assigns a score (1-5) based on dimension.
    *   **Financial Risk:** `EconomicModel` calculates the expected cost impact.
    *   **Write-back:** Updates attributes: `fornyelsebehov`, `RISK_SCORE`, `RISK_COST`.
3.  **Visualization (Controller):**
    *   **Styling:** Layer is styled by `RISK_COST` (Red = High Cost).
    *   **Bundling:** High-risk pipes (`RISK_SCORE >= 2.0`) are buffered (20m) and dissolved into project zones.
4.  **Review:**
    *   `ResultsDialog` displays a table sorted by **Risk Cost (SEK)**, allowing users to prioritize the most expensive liabilities.

## 6. Current Capabilities (v2.0.0)
*   **Risk-Based Asset Management (RBAM):** Transitioned from simple renewal needs to full financial risk quantification.
*   **Monetary Risk Estimation:** outputs estimated risk costs in SEK.
*   **Robust Data Handling:** Can process "dirty" municipal GIS data without crashing or producing statistical outliers.
*   **Strategic Visualization:**
    *   **Heatmaps:** Cost-based styling.
    *   **Project Bundling:** Spatially clusters individual pipe risks into actionable project polygons.
*   **Configurable:** All core parameters (Herz curves, Unit Costs, Defaults) are externalized in `parameters.json`.
*   **Responsive UI:** Handles large datasets with progress feedback.
