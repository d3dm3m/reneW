# Changelog

All notable changes to this project will be documented in this file.

## [2.0.0] - 2024-10-27

### Major Release: Risk-Based Architecture
This release marks a significant shift from simple renewal probability calculation to a comprehensive Risk-Based Asset Management (RBAM) system.

### Added
- **Financial Risk Calculation:**
  - New `EconomicModel` estimates the monetary risk (`RISK_COST`) for every pipe.
  - New `ConsequenceCalculator` assigns risk scores based on pipe dimension.
- **Strategic Visualization:**
  - Automatic styling of layers using a "Reds" graduated renderer based on risk cost.
  - **Project Bundling:** New spatial analysis feature that clusters high-risk pipes into actionable "Suggested Project" polygons with aggregated costs.
- **Data Sanitization:**
  - Robust handling of "dirty" GIS data (e.g., `1900` dates, `P.V.C` typos, null markers).
  - New `DataSanitizer` and `MaterialNormalizer` modules.
- **Configuration:**
  - Externalized all calculation parameters to `parameters.json`.
  - Added support for defining Unit Costs and Default Substitutions via JSON.
- **Results Interface:**
  - Added "Risk Score" and "Estimated Risk Cost" columns to the results table.
  - Implemented currency formatting and smart numeric sorting.
- **Responsiveness:**
  - Added progress bars to long-running analysis tasks to prevent UI freezing.

### Changed
- **Architecture:** Refactored the monolithic controller into a modular design with `RiskManager`, `StrategicModels`, and `Utils`.
- **Logic:** Probability of Failure (PoF) calculation now cleanly separated from the UI logic.

### Fixed
- Fixed crashes caused by non-numeric dimension values (e.g., `225_I`).
- Fixed false positives caused by placeholder years (e.g., `0` or `1900`).
