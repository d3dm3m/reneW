# reneW - Risk-Based Asset Management for QGIS

**reneW** is a powerful QGIS plugin designed for strategic renewal planning of water and wastewater infrastructure. It transforms raw asset data into actionable financial risk intelligence.

Unlike simple age-based tools, reneW implements a complete **Risk-Based Asset Management (RBAM)** workflow. It calculates the Probability of Failure (PoF) using advanced survival models, estimates the Consequence of Failure (CoF), and quantifies the **Monetary Risk (SEK)** for every pipe in your network.

![reneW Screenshot](icon.png)

## Key Features

*   **Advanced Risk Modeling:** Combines Herz survival functions with consequence logic.
*   **Financial Quantification:** Estimates the "Expected Annual Cost of Risk" in currency (SEK).
*   **Strategic Visualization:** Automatically highlights high-cost liabilities with intuitive color ramps.
*   **Project Bundling:** Spatially clusters high-risk assets into actionable "Project Zones" to identify neighborhoods ripe for renovation.
*   **Data Resilience:** Built-in sanitization handles messy GIS data (e.g., "1900" dates, typo-ridden materials) without crashing.

## How It Works

reneW performs a sophisticated 4-step analysis on your Water (Vatten), Wastewater (Spillvatten), and Stormwater (Dagvatten) layers.

### Step 1: Data Sanitization
Real-world data is rarely perfect. reneW automatically cleans your inputs before analysis:
*   **Years:** Markers like `1900`, `0`, or `None` are replaced with a configurable default (e.g., `1980`).
*   **Dimensions:** Values like `-` or `--` are safely handled. Complex strings like `225_I` are parsed to extraction the numeric diameter.
*   **Materials:** Typo-tolerant matching maps inputs like `P.V.C`, `Btg`, or `odefinierad` to standard calculation parameters.

### Step 2: Probability of Failure (PoF)
The plugin uses the **Herz Survival Function** model to calculate the likelihood of failure (0.0 - 1.0).
*   Parameters (`a`, `b`, `c`) are calibrated for specific material/age cohorts (e.g., "Concrete pipes from 1950-69").
*   *Renovation Awareness:* If a pipe has been relined ("Strumpa"/"Infordring"), its effective age is reset based on the renovation year.

### Step 3: Consequence & Financial Risk
Risk is more than just probability. reneW calculates the consequences:
*   **Consequence Score (1-5):** Larger pipes (e.g., >400mm) are assigned higher consequence scores due to the greater impact of failure.
*   **Monetary Risk Calculation:**
    ```
    Risk Cost = PoF × Consequence Score × Length × Unit Cost
    ```
    This formula highlights pipes that are not just old, but *expensive* liabilities.

### Step 4: Strategic Planning & Bundling
Finally, the tool translates row-level data into strategic insights:
*   **Auto-Styling:** The map is styled with a "Reds" color ramp based on `RISK_COST`, instantly revealing where the money is at risk.
*   **Project Bundling:** High-risk pipes are spatially buffered (20m) and clustered into "Project Zones". These polygons represent suggested work areas, complete with a summed `TOTAL_RISK` cost, helping planners scope projects effectively.

## Configuration

All calculation parameters are stored in `reneW/parameters.json`. You can customize this file to match your municipality's specific costs and data environment.

### Updating Unit Costs
To change the estimated replacement cost per meter (Currency/m), edit the `unit_costs` section:

```json
"unit_costs": {
    "Vatten": 2500,
    "Spillvatten": 3000,
    "Dagvatten": 2000
}
```

### Configuring Data Defaults
To change how the sanitizer handles missing data, edit the `defaults` section:

```json
"defaults": {
    "unknown_year_substitute": 1980,
    "unknown_dimension_substitute": 150,
    "null_markers": {
        "year": [1900, 0, "0"],
        "dimension": ["-", "--", "0"]
    }
}
```

### Calibrating Herz Parameters
The survival model parameters (`a`, `b`, `c`) for each material cohort can be fine-tuned in the `Avlopp` and `Vatten` sections of the JSON file.

## Installation

1.  Copy the `reneW` folder into your QGIS plugins directory:
    *   **Windows:** `C:\Users\%USERNAME%\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\`
    *   **Mac/Linux:** `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
2.  Restart QGIS.
3.  Enable "reneW" in the **Plugins > Manage and Install Plugins** menu.

## License

[License Name/Type]
