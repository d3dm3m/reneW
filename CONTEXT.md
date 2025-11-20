# Project Context & Developer Handover

## 1. Project Structure
```
.
├── reneW/
│   ├── LICENSE
│   ├── __init__.py               # Plugin entry point wrapper
│   ├── calculation_logic.py      # Core Herz model implementation
│   ├── icon.png
│   ├── metadata.txt              # QGIS plugin metadata
│   ├── reneW.py                  # Main controller & processing logic
│   ├── reneW_dialog.py           # Main configuration dialog logic
│   ├── reneW_dialog_base.ui      # Main configuration dialog UI (Qt Designer)
│   ├── results_dialog.py         # Results table dialog logic
│   └── results_dialog.ui         # Results table dialog UI (Qt Designer)
└── README.md
```

## 2. Tech Stack
*   **Language:** Python 3
*   **Framework:** QGIS API (PyQGIS)
    *   `qgis.core`: Data access, geometry processing, spatial analysis.
    *   `qgis.gui`: Map canvas interaction, custom widgets (FieldComboBox, MapLayerComboBox).
*   **UI Library:** PyQt5 (imported via `qgis.PyQt`). UI layouts defined in `.ui` files.
*   **Dependencies:** Standard Python libraries (`os`, `datetime`, `csv`).

## 3. Architecture Overview
*   **Entry Point:** The `classFactory` method in `__init__.py` instantiates the `ReneW` class from `reneW.py`.
*   **Controller (`reneW.py`):** The `ReneW` class is the central orchestrator. It initializes the GUI, connects signals, and contains the `run()` method which executes the primary analysis loop.
*   **Logic Separation:**
    *   **GUI Logic:** Handled in `reneW_dialog.py` (input configuration) and `results_dialog.py` (output display).
    *   **Business Logic:** `calculation_logic.py` contains the pure mathematical models (Herz survival function) and parameter lookups.
    *   **Spatial Logic:** Hotspot analysis (buffering/intersection) is performed directly in `reneW.py` (`_run_hotspot_analysis`).
*   **UI Loading:** `.ui` files are loaded dynamically at runtime using `uic.loadUiType`.

## 4. Key Components
*   **`ReneW` (reneW.py):**
    *   Manages the plugin lifecycle (init/unload).
    *   Orchestrates the analysis: iterates layers, updates attributes, triggers hotspot analysis.
    *   Creates the "Hotspots" memory layer.
*   **`ReneWDialog` (reneW_dialog.py):**
    *   Manages the tabbed interface for Water (Vatten), Wastewater (Spillvatten), and Stormwater (Dagvatten).
    *   Handles QSettings persistence (saving/loading configuration to the QGIS Project).
    *   Validates user inputs (layer selection, field mapping).
*   **`calculation_logic` (calculation_logic.py):**
    *   Stores the `PARAMETERS` dictionary (Herz constants `a`, `b`, `c`) for various materials/ages.
    *   `calculate_renewal_need()`: Returns a float (0.0-1.0) representing probability of failure/renewal need.
*   **`ResultsDialog` (results_dialog.py):**
    *   Displays high-risk features in a sortable table.
    *   Provides functionality to zoom to features on the map.
    *   Handles data export (CSV, PDF).

## 5. Data Flow
1.  **Configuration:** User opens the plugin dialog. They select vector layers for specific utilities and map attribute fields (Material, Year, Dimension, Renovation info).
2.  **Execution:**
    *   The plugin iterates through features in the selected layers.
    *   **Normalization:** Material strings are parsed and matched to known types (e.g., "PVC" -> "S-Plast").
    *   **Calculation:** `calculation_logic` computes a score based on age and material properties.
    *   **Write-back:** The score is written to a new attribute field `fornyelsebehov` in the source layer.
3.  **Hotspot Analysis (if enabled):**
    *   Features with `fornyelsebehov >= threshold` are collected.
    *   Geometries are buffered by a user-defined distance.
    *   Intersections between buffers of *different* utility types are calculated.
    *   Resulting polygons are added to a new "Hotspots" layer with a visual "glow" effect.
4.  **Review:**
    *   A results table pops up listing the highest risk pipes.
    *   User can export this list or generate a PDF summary.

## 6. Current Capabilities (v1.0.3)
*   **Multi-Utility Analysis:** Supports separate configurations for Water, Wastewater, and Stormwater networks.
*   **Advanced Risk Modeling:** Implements the Herz survival model with calibrated parameters for common Swedish pipe materials (Betong, Gråjärn, Segjärn, Plast, etc.).
*   **Renovation Awareness:** Detects "Infordring/Strumpa" (relining) methods to reset the effective age of pipes.
*   **Dimension Weighting:** Optional capability to prioritize larger pipes by applying a weighting factor to the risk score.
*   **Spatial Hotspot Detection:** Identifies geographic clusters where high-risk pipes from multiple systems overlap (e.g., a risky water pipe near a risky sewer pipe).
*   **Report Generation:** Integrated PDF generator for summary reports and CSV export for raw data.
*   **QGIS Integration:** Uses native QGIS widgets (FieldComboBox) and respects project CRS. Settings are saved per-project.
