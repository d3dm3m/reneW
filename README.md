# reneW - QGIS Plugin for Pipeline Renewal Planning

`reneW` is a QGIS plugin designed to help in the planning of utility pipe renewals. It calculates a renewal need score for each pipe based on a survival analysis model, providing a quantitative basis for maintenance and renewal decisions.

## Features

*   Calculates a **renewal need** score for each pipe based on a statistical failure model.
*   Uses a **Normal Distribution CDF model** based on pipe type (water/sewer), material, and age.
*   Includes an **optional and adjustable weighting factor** for pipe dimension to account for consequence of failure.
*   Features a **Parameter Editor** to customize the underlying statistical model.
*   Supports **filtering by municipality**.
*   User-friendly dialog to select layers and map the necessary attributes.
*   Adds the calculated score to a new field (`fornyelsebehov`) in your data.
*   **Temporal Analysis:** Generates a time-aware layer to animate how renewal needs change over a user-defined period, fully integrated with the QGIS Temporal Controller.
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
2.  **Configure Analysis:** The main dialog has three tabs: `water`, `sewer/spill`, and `sewer/storm`.
    *   For each pipe type you want to analyze, check the box.
    *   Select the corresponding **Layer**.
    *   Map the required fields: **Material**, **Construction year**, and **Dimension**.
    *   Optionally, map fields for **Municipality**, **Renovation year**, and **Renovation method**.
3.  **Run:** Click `OK`. A new field `fornyelsebehov` will be added to your layer(s). You can use this field to style the layer to visually identify high-risk pipes.

## Temporal Analysis (Time-Slider Animation)

Beyond calculating the renewal need for the current year, reneW includes a powerful temporal analysis feature to visualize how renewal needs evolve over time.

When enabled, this feature generates a new, time-aware layer that is automatically styled and configured for use with the QGIS **Temporal Controller** (the time-slider).

### How to Use It

1.  In the main plugin dialog, find the **Temporal Analysis** group box.
2.  Check the box to enable the feature.
3.  Specify the time period for the analysis:
    *   **Start Year:** The first year of the simulation.
    *   **End Year:** The last year of the simulation.
    *   **Step (Years):** The interval for calculations (e.g., a step of 5 will calculate the need for 2025, 2030, 2035, etc.).
4.  Run the analysis as usual by clicking `OK`.

### Understanding the Output

A new memory layer named `Temporal Renewal Need` will be added to your project. This layer is styled with a dynamic, rule-based renderer to show two variables at once:

*   **Pipe Type:** The color of the pipe indicates its type (e.g., Blue for water, Red for wastewater, Green for stormwater). The renderer dynamically discovers the pipe types present in your data and styles them.
*   **Renewal Need:** The intensity of the color indicates the renewal need. For each pipe type, a pale, light color means a low need, while a bright, saturated color means a high need.

The legend is automatically generated to be clear and descriptive (e.g., "Water – High Need (0.6 – 0.8)").

### Animating the Map

1.  Open the QGIS Temporal Controller by clicking the clock icon in the map navigation toolbar.
2.  Click the "Animated Temporal Navigation" button (the one with the green play icon).
3.  The map is now linked to the time slider. You can press play, or drag the slider, to see the renewal needs change across the map for each year in your specified range.

## The Calculation Model

### 1. Base Renewal Need (Normal Distribution Model)

The renewal need is based on the probability of failure for a pipe of a certain age. This is calculated using the **Cumulative Distribution Function (CDF) of the Normal Distribution**, denoted as `Φ`.

The probability of a pipe having failed by age `t` is given by:
`F(t) = Φ((t - μ) / σ)`

Where:
*   `t` is the age of the pipe.
*   `μ` (mu) is the **mean lifetime** of the material. This is the age at which 50% of pipes of that material are expected to have failed.
*   `σ` (sigma) is the **standard deviation**. This parameter controls how spread out the failures are around the mean. A smaller sigma means failures are more tightly clustered around the mean age.

The plugin calculates the renewal need for the next year, which is the increase in failure probability from the current year to the next.

### 2. Optional Dimension Weighting

If enabled, the base renewal need is multiplied by a consequence factor:
`Final Score = Renewal Need * (1 + (Dimension * Factor))`

## Advanced Configuration: Customizing Parameters

The plugin's calculations are controlled by `parameters.json`, located in the plugin's directory. You can edit this file directly or use the built-in **Parameter Editor** (click "Edit Parameters..." in the main dialog).

### `parameters.json` Structure

The file contains a nested dictionary structure where material parameters (`mu` and `sigma`) are defined for each pipe domain. The plugin ships with a comprehensive set of pre-defined materials and their expected lifetimes, but you can customize them.

```json
{
  "metadata": { "...": "..." },
  "municipalities": [ ],
  "renovation_method_mapping": {
    "1": "Lining",
    "2": "Pipe Bursting"
  },
  "water": {
    "blyror": { "mu": 90.0, "sigma": 5.0 },
    "gjutjarn": { "mu": 60.0, "sigma": 10.0 },
    "segjarn": { "mu": 95.0, "sigma": 10.0 },
    "...": {}
  },
  "sewer": {
    "spill": {
      "gjutjarn": { "mu": 70.0, "sigma": 10.0 },
      "betongror": { "mu": 92.5, "sigma": 12.5 },
      "...": {}
    },
    "storm": {
      "gjutjarn": { "mu": 75.0, "sigma": 10.0 },
      "betongror": { "mu": 97.5, "sigma": 12.5 },
      "...": {}
    }
  },
  "liners": {
     "default": { "mu": 50.0, "sigma": 5.0 }
  }
}
```

*   The main keys are `water` and `sewer`. `sewer` is further divided into `spill` (wastewater) and `storm` (stormwater).
*   Inside each domain is a dictionary where each key is a material identifier (e.g., `"gjutjarn"`) and the value contains its `"mu"` (mean lifetime) and `"sigma"` (standard deviation).
*   The `renovation_method_mapping` allows you to map numeric codes from your data to descriptive renovation methods.
*   The `liners` section defines parameters for renovated pipes. If a renovation method is identified (e.g., "Lining"), the plugin will use these parameters instead of the original material's parameters, effectively resetting the pipe's age.

### How Material Matching Works

You do not need to have material names in your data that exactly match the keys in `parameters.json`. The plugin uses a flexible matching system (`reneW/material_lookup.py`) to map your data to the correct parameters.

The system first normalizes your material string (e.g., "Segjärnsrör" becomes "segjarn") and compares it against a comprehensive vocabulary of common synonyms and abbreviations. This allows for a wide range of input data to be correctly identified.

If a specific material from your data is not found in the vocabulary, the system will use the parameters defined for the `ovrigt` (other/unknown) key for that pipe domain.

To customize the logic, you can either edit the `mu` and `sigma` values in the **Parameter Editor** or directly in the `parameters.json` file.
