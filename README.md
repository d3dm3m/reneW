# reneW - QGIS Plugin for Pipeline Renewal Planning

`reneW` is a QGIS plugin designed to help in the planning of utility pipe renewals. It calculates a renewal need score for each pipe based on a survival analysis model, providing a quantitative basis for maintenance and renewal decisions.

## Features

*   Calculates a **renewal need** score for each pipe based on a statistical failure model.
*   **Property-Based Year Imputation**: Automatically infers missing pipe construction years from nearby property data to improve data completeness.
*   **Auto-Detect Layers and Fields**: Scans your project and suggests the best layers and fields for the analysis, significantly speeding up setup.
*   **Per-Pipe-Type Optimism Factors**: Allows you to set individual optimism factors for Water, Wastewater, and Stormwater pipes to fine-tune life expectancy assumptions.
*   Includes an **optional and adjustable weighting factor** for pipe dimension to account for consequence of failure.
*   **Hotspot Analysis**: Identifies geographic clusters of high-risk pipes.
*   **Interactive Hotspot Explorer**: A tool to click on hotspots and see detailed statistics, a list of contributing pipes, and suggested interventions.
*   **Temporal Analysis:** Generates a time-aware layer to animate how renewal needs change over a user-defined period.
*   Features a **Parameter Editor** to customize the underlying statistical model.
*   Supports **filtering by municipality**.
*   UI available in English and Swedish.

## Compatibility

This plugin has been updated to be compatible with a wide range of QGIS versions, including **QGIS 3.x** and the latest development versions **(3.99+).**

## Installation

1.  **Download the Plugin:** Obtain the plugin as a folder (e.g., named `reneW`).
2.  **Find your QGIS Plugins Directory:** In QGIS, go to `Settings -> User Profiles -> Open Active Profile Folder`. Navigate to `python/plugins`.
3.  **Copy Plugin Directory:** Copy the entire `reneW` directory into the `plugins` directory.
4.  **Activate the Plugin:** Restart QGIS. Go to `Plugins -> Manage and Install Plugins...`. In the `Installed` tab, find "reneW" and check the box to enable it.

You should now see the `reneW` icon in the QGIS toolbar.

## Usage

1.  **Launch the Plugin:** Click on the `reneW` icon.
2.  **Auto-Detect (Recommended):** Click the **Auto-Detect** button. The plugin will scan the layers in your project and attempt to automatically select the correct layer and fields for each pipe type tab (Water, Sewer, Stormwater).
3.  **Configure Pipe Layers:** Review the auto-detected settings or configure them manually in the `Water`, `Sewer`, and `Stormwater` tabs.
4.  **Configure Imputation (Optional):** In the **General Settings** tab, find the **Property-based Year Imputation** section.
    *   If you have pipes with missing construction years, select a point layer representing properties or buildings.
    *   Select the field in that layer that contains the construction year.
    *   Adjust the K-Neighbors and Sampling Fractions if needed. If no layer is selected, this feature is skipped.
5.  **Set Advanced Options (General Settings Tab):**
    *   **Optimism Factors**: Adjust the life expectancy assumptions for each pipe type.
    *   **Dimension Weighting**: Optionally enable and set a factor to give higher renewal need scores to larger pipes.
    *   **Hotspot Analysis**: Enable this to generate a hotspot layer.
    *   **Temporal Analysis**: Enable this to create a time-aware animation.
6.  **Run:** Click `OK`.

## Key Features in Detail

### Property-Based Year Imputation
To handle incomplete data, `reneW` can infer missing pipe construction years. If a pipe's year is missing or set to a sentinel value (like 1900), this feature uses a nearby property/building layer to make an educated guess.

**How it Works:**
1.  **Multi-Point Sampling**: Instead of just using the pipe's center, the plugin samples multiple points along the pipe's geometry (e.g., at 25%, 50%, and 75% of its length).
2.  **Nearest Neighbors**: For each sample point, it finds the 'K' nearest property features from your selected property layer.
3.  **Median Calculation**: It collects the construction years from all found neighbors and calculates the **median year**. The median is used to provide a robust estimate that is not easily skewed by outlier property ages.

#### Transparency of Imputed Data
To ensure you always know which data is original versus inferred, imputed years are clearly flagged:
*   **On the Map**: Pipes with imputed years are given a **dashed outline** in the standard analysis output.
*   **In the Results Table**: The 'Age' column will show **(imputed)** next to the age.
*   **In the Hotspot Explorer**: A warning (⚠️) will appear if a hotspot contains pipes with imputed years.

### Auto-Detect Layers and Fields
This feature dramatically speeds up setup. When you click "Auto-Detect", the plugin:
1.  **Scans and scores** all layers in your project to find the best candidates for water, wastewater, and stormwater pipes based on their names.
2.  For the best-matching layers, it then **scores each field** to find the best candidates for roles like "material", "year", and "dimension" using a comprehensive catalog of keywords and data-type heuristics.
3.  The best-matching layers and fields are automatically populated in the dialog. All actions are logged to the **"reneW" tab in the QGIS Log Messages Panel**.

### Per-Pipe-Type Optimism Factors
This feature allows you to apply your expert knowledge by adjusting the "effective age" of pipes.
*   **Factor > 1.0**: Optimistic; pipes are considered "younger," resulting in a lower renewal need.
*   **Factor = 1.0**: No change (default).
*   **Factor < 1.0**: Pessimistic; pipes are considered "older," resulting in a higher renewal need.

### Hotspot Analysis and Interactive Explorer
When enabled, this generates a polygon layer highlighting geographic clusters of high-risk pipes, styled by severity (yellow for moderate, red for severe).

When you **select a hotspot polygon**, the **Hotspot Explorer** dialog opens, showing:
*   **Key Statistics**: Pipe count, total length, average renewal need.
*   **Material Composition**: A summary of materials in the hotspot.
*   **Suggested Intervention**: A recommended action (e.g., "Full Replacement", "CIPP Lining").
*   **Contributing Pipes**: The individual pipes are automatically selected and zoomed to on the map.

### Temporal Analysis (Time-Slider Animation)
This feature generates a new, time-aware layer styled to show both **pipe type** (by color) and **renewal need** (by color intensity), ready for use with the QGIS Temporal Controller.

## The Calculation Model
The renewal need is based on a statistical survival model that calculates the probability of failure for a pipe of a certain age. The model uses the **Cumulative Distribution Function (CDF) of the Normal Distribution**, often referred to as `Phi(z)`, to describe the failure curve of a pipe cohort.

### Key Concepts
*   **Failure Curve**: For any group of pipes made of the same material, not all will fail at once. Some will fail early, and some will last longer than average. A failure curve describes this distribution over time. `reneW` assumes this follows a Normal (or "Gaussian") Distribution.
*   **`mu` (μ)**: This parameter represents the **mean lifetime** of a material cohort. It is the age (in years) at which 50% of the pipes in that cohort are expected to have failed.
*   **`sigma` (σ)**: This parameter represents the **standard deviation** of the lifetime. It controls the "steepness" of the failure curve. A small sigma means most failures cluster tightly around the mean lifetime, while a large sigma means failures are more spread out over time.
*   **`adjusted_age`**: To account for expert knowledge or local conditions, the plugin uses an `adjusted_age` in its calculations, which is determined by the **Optimism Factor** you set: `adjusted_age = chronological_age / optimism_factor`.

### The Formula
The cumulative probability of a pipe having failed by a certain age (`t`) is calculated by standardizing the age and looking up the value from the Normal CDF:

1.  Calculate the Z-score: `z = (t - μ) / σ`
2.  Calculate the CDF: `F(t) = Phi(z)`

The plugin uses this core formula in two different ways depending on the analysis mode:

*   **Standard Analysis (Annual Need)**: This mode calculates the probability of failure occurring *in the next year*. It represents the immediate renewal need. The formula is:
    `Annual_Probability = F(age + 1) - F(age)`

*   **Temporal Analysis (Cumulative Need)**: This mode shows the total accumulated risk up to a given year. The value at any point in time is the cumulative probability of failure:
    `Cumulative_Probability = F(age)`

These parameters (`mu` and `sigma`) can be customized for each material in the **Parameter Editor**.

## Advanced Configuration: Customizing Parameters
The plugin's underlying statistical model is controlled by `parameters.json`. You can edit this file directly or use the built-in **Parameter Editor** (click "Edit Parameters..." in the main dialog) to customize the mean lifetime (`mu`) and standard deviation (`sigma`) for different materials.
