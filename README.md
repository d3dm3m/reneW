# reneW - QGIS Plugin for Pipeline Renewal Planning

`reneW` is a QGIS plugin designed to help in the planning of utility pipe renewals. It calculates a renewal need score for each pipe based on a survival analysis model, providing a quantitative basis for maintenance and renewal decisions.

## Features

*   Calculates a **renewal need** score for each pipe based on a statistical failure model.
*   Uses a **Normal Distribution CDF model** based on pipe type (water/sewer), material, and age.
*   **Auto-Detect Layers and Fields**: Automatically scans your project and suggests the best layers and fields for the analysis, significantly speeding up the setup process.
*   **Per-Pipe-Type Optimism Factors**: Allows you to set individual optimism factors for Water, Wastewater, and Stormwater pipes to fine-tune the life expectancy assumptions.
*   Includes an **optional and adjustable weighting factor** for pipe dimension to account for consequence of failure.
*   **Hotspot Analysis**: Identifies geographic clusters of high-risk pipes.
*   **Interactive Hotspot Explorer**: A tool to click on hotspots and see detailed statistics, a list of contributing pipes, and suggested interventions.
*   **Temporal Analysis:** Generates a time-aware layer to animate how renewal needs change over a user-defined period, fully integrated with the QGIS Temporal Controller.
*   Features a **Parameter Editor** to customize the underlying statistical model.
*   Supports **filtering by municipality**.
*   UI available in English and Swedish.

## Compatibility

This plugin has been updated to be compatible with a wide range of QGIS versions, including **QGIS 3.x** and the latest development versions **(3.99+).** It uses version-aware API calls to ensure stability across different releases.

## Installation

1.  **Download the Plugin:** Obtain the plugin as a folder (e.g., named `reneW`).
2.  **Find your QGIS Plugins Directory:** In QGIS, go to `Settings -> User Profiles -> Open Active Profile Folder`. Navigate to `python/plugins`.
3.  **Copy Plugin Directory:** Copy the entire `reneW` directory into the `plugins` directory.
4.  **Activate the Plugin:** Restart QGIS. Go to `Plugins -> Manage and Install Plugins...`. In the `Installed` tab, find "reneW" and check the box to enable it.

You should now see the `reneW` icon in the QGIS toolbar.

## Usage

1.  **Launch the Plugin:** Click on the `reneW` icon.
2.  **Auto-Detect (Recommended):** Click the **Auto-Detect** button. The plugin will scan the layers in your project and attempt to automatically select the correct layer and fields for each pipe type tab (Water, Sewer, Stormwater). This is based on a scoring system that analyzes layer and field names.
3.  **Configure Analysis:** Review the auto-detected settings or configure them manually. The main dialog has three tabs: `water`, `sewer`, and `stormwater`.
    *   For each pipe type you want to analyze, check the box.
    *   Select the corresponding **Layer**.
    *   Map the required fields: **Material**, **Construction year**, and **Dimension**.
    *   Optionally, map fields for **Municipality**, **Renovation year**, and **Renovation method**.
4.  **Set Advanced Options (General Settings Tab):**
    *   **Optimism Factors**: Adjust the life expectancy assumptions for each pipe type. A factor > 1.0 means you are optimistic (pipes last longer), while a factor < 1.0 means you are pessimistic (pipes age faster).
    *   **Dimension Weighting**: Optionally enable and set a factor to give higher renewal need scores to larger pipes.
    *   **Hotspot Analysis**: Enable this to generate a hotspot layer showing clusters of high-risk pipes.
    *   **Temporal Analysis**: Enable this to create a time-aware animation of renewal needs.
5.  **Run:** Click `OK`.

## Key Features in Detail

### Auto-Detect Layers and Fields
To speed up the setup process, the plugin includes a powerful auto-detect feature. When you click the "Auto-Detect" button, the plugin:
1.  **Scans all layers** in your QGIS project.
2.  **Scores each layer** for each pipe type (water, wastewater, stormwater) based on its name (e.g., "vatten", "spill", "dagvatten").
3.  For the best-matching layer, it then **scores each field** to find the best candidates for roles like "material", "year", and "dimension".
4.  The scoring uses a comprehensive catalog of keywords and heuristics (e.g., a "year" field is expected to be numeric and have values in a reasonable range).
5.  The best-matching layers and fields are automatically populated in the dialog.
All actions are logged to the **"reneW" tab in the QGIS Log Messages Panel**, so you can see how the selections were made.

### Per-Pipe-Type Optimism Factors
This feature allows you to apply your expert knowledge to the analysis by adjusting the "effective age" of pipes. In the "General Settings" tab, you can set an optimism factor for each pipe type:
*   **Factor > 1.0**: You are optimistic; the pipes are considered "younger" than their chronological age, resulting in a lower renewal need.
*   **Factor = 1.0**: No change (default).
*   **Factor < 1.0**: You are pessimistic; the pipes are considered "older", resulting in a higher renewal need.

The applied factor is stored in the output layers and shown in the results table for full transparency.

### Hotspot Analysis and Interactive Explorer
When **Hotspot Analysis** is enabled, the plugin generates a polygon layer that highlights geographic clusters of high-risk pipes. This layer is styled with a rule-based renderer:
*   **Moderate Hotspots** (average renewal need 0.5–0.75) are shown in **yellow**.
*   **Severe Hotspots** (average renewal need ≥ 0.75) are shown in **red**.

#### Interactive Explorer
This feature makes the hotspot layer interactive. Simply **select a hotspot polygon** on the map, and the **Hotspot Explorer** dialog will automatically open. This dialog shows:
*   **Key Statistics**: Total number of pipes, total length, and average renewal need for the hotspot.
*   **Material Composition**: A summary of the materials of the pipes in the hotspot (e.g., "PVC: 10, Cast Iron: 4").
*   **Suggested Intervention**: A recommended action (e.g., "Full Replacement", "CIPP Lining") based on the hotspot's properties (pipe type, materials, average age, and renewal need).
*   **Contributing Pipes**: When the dialog opens, the individual pipes that make up the hotspot are automatically selected and zoomed to on the map.

### Temporal Analysis (Time-Slider Animation)
This feature generates a new, time-aware layer that is automatically styled and configured for use with the QGIS **Temporal Controller**. You can animate the map to see how renewal needs evolve over a time period you define.

The output layer `Temporal Renewal Need` is styled to show both **pipe type** (by color) and **renewal need** (by color intensity), making it easy to visualize risk progression.

## The Calculation Model
The renewal need is based on the probability of failure for a pipe of a certain age, calculated using the **Cumulative Distribution Function (CDF) of the Normal Distribution**. The `adjusted_age` (chronological age / optimism factor) is used in this calculation.

## Advanced Configuration: Customizing Parameters
The plugin's underlying statistical model is controlled by `parameters.json`. You can edit this file directly or use the built-in **Parameter Editor** (click "Edit Parameters..." in the main dialog) to customize the mean lifetime (`mu`) and standard deviation (`sigma`) for different materials.
