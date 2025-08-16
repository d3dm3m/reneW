# reneW - QGIS Plugin for Pipeline Renewal Planning

> [!WARNING]
> **Development Status**: This plugin is currently being tested under the following development environment. Compatibility with other versions is not guaranteed.
>
> - **QGIS Version**: 3.99.0-Master (Unstable, pre-release version)
> - **Operating System**: Windows 11 (Version 24H2)
> - **Special Note**: This is a "debug" build of QGIS, designed for developers.
>
> **Core Components:**
> - **Python**: 3.12.11
> - **GDAL**: ~3.12.0 (development version)
> - **PROJ**: ~9.5.0
> - **Qt**: 6.8.1

reneW is a QGIS plugin designed to help in the planning of utility pipe renewals. It calculates a renewal need score for each pipe, providing a quantitative basis for maintenance and renewal decisions.

## Features

*   Calculates a **renewal need** score for each pipe.
*   For standard analysis, uses a **Normal Distribution CDF model** based on pipe type, material, and age.
*   For temporal analysis, uses a simplified **bucket-based scoring model** (Low, Medium, High).
*   Includes an **optional and adjustable weighting factor** for pipe dimension to account for consequence of failure.
*   Features a **Parameter Editor** to customize the underlying statistical model for standard analysis.
*   Supports **filtering by municipality**, with the list of municipalities populated dynamically from the selected layer.
*   User-friendly dialog to select layers and map the necessary attributes.
*   Adds the calculated score to a new field (`fornyelsebehov` or `renewal_need`) in your data.
*   **Temporal Analysis:** Generates a time-aware layer to animate how renewal needs change over a user-defined period, fully integrated with the QGIS Temporal Controller.
*   UI available in English and Swedish.

## Compatibility

This plugin has been updated to be compatible with a wide range of QGIS versions, including **QGIS 3.x** and development versions **(3.99+).** It uses version-aware API calls to ensure stability across different releases.

## Installation

1.  **Download the Plugin:** Obtain the plugin as a folder (e.g., named reneW).
2.  **Find your QGIS Plugins Directory:** In QGIS, go to Settings -> User Profiles -> Open Active Profile Folder. Navigate to `python/plugins`.
3.  **Copy Plugin Directory:** Copy the entire `reneW` directory into the plugins directory.
4.  **Activate the Plugin:** Restart QGIS. Go to Plugins -> Manage and Install Plugins.... In the `Installed` tab, find "reneW" and check the box to enable it.

You should now see the reneW icon in the QGIS toolbar.

## Usage

1.  **Launch the Plugin:** Click on the reneW icon.
2.  **Configure Analysis:** The main dialog has three tabs: water, sewer, and stormwater.
    *   For each pipe type you want to analyze, check the box.
    *   Select the corresponding **Layer**.
    *   Map the required fields: **Material**, **Construction year**, and **Dimension**.
    *   Optionally, map a field for **Municipality**. The municipality filter dropdown will be populated with the unique values from this field.
    *   Optionally, map fields for **Renovation year**, and **Renovation method**.
3.  **Run:** Click OK. A new field for the renewal score will be added to your layer(s). You can use this field to style the layer to visually identify high-risk pipes.

## Temporal Analysis (Time-Slider Animation)

When enabled, this feature generates a new, time-aware layer that is automatically styled and configured for use with the QGIS **Temporal Controller**.

### How to Use It

1.  In the main plugin dialog, find the **Temporal Analysis** group box.
2.  Check the box to enable the feature.
3.  Specify the time period for the analysis:
    *   **Start Year:** The first year of the simulation.
    *   **End Year:** The last year of the simulation.
    *   **Step (Years):** The interval for calculations.
4.  Run the analysis as usual by clicking OK.

### Understanding the Output

A new memory layer named `Temporal Renewal Need` will be added to your project. This layer is styled with a rule-based renderer to show two variables at once:

*   **Pipe Type:** The general pipe type (e.g., Water, Sewer, Stormwater).
*   **Renewal Need:** The color indicates the renewal need, categorized into **Low Risk** (green), **Medium Risk** (orange), and **High Risk** (red).

The legend is automatically generated to be clear and descriptive (e.g., "water - Low Risk").

### Animating the Map

1.  Open the QGIS Temporal Controller by clicking the clock icon in the map navigation toolbar.
2.  Click the "Animated Temporal Navigation" button (the one with the green play icon).
3.  The map is now linked to the time slider. You can press play, or drag the slider, to see the renewal needs change across the map for each year in your specified range.

## The Calculation Model

### 1. Standard Analysis (Normal Distribution Model)

The renewal need for the standard analysis is based on the probability of failure for a pipe of a certain age. This is calculated using the **Cumulative Distribution Function (CDF) of the Normal Distribution**, denoted as Φ.

The probability of a pipe having failed by age `t` is given by:
`F(t) = Φ((t - μ) / σ)`

Where:
*   `t` is the age of the pipe.
*   `μ` (mu) is the **mean lifetime** of the material.
*   `σ` (sigma) is the **standard deviation**.

### 2. Temporal Analysis (Simplified Bucket Model)

For temporal analysis, a simplified scoring model is used to categorize pipes into **Low**, **Medium**, and **High** risk buckets based on age, dimension, and pipe type factors. This model is intended for visualization and may not reflect the precise statistical failure probability.

### 3. Optional Dimension Weighting

If enabled, the base renewal need is multiplied by a consequence factor:
`Final Score = Renewal Need * (1 + (Dimension * Factor))`

## Advanced Configuration: Customizing Parameters

The plugin's calculations are controlled by `parameters.json`, located in the plugin's directory. You can edit this file directly or use the built-in **Parameter Editor**.

### parameters.json Structure

The file contains a nested dictionary structure where material parameters (`mu` and `sigma`) for the **Standard Analysis** are defined.

```json
{
  "metadata": { "...": "..." },
  "municipalities": [],
  "renovation_method_mapping": {
    "1": "Lining",
    "2": "Pipe Bursting"
  },
  "water": {
    "gjutjarn": { "mu": 60.0, "sigma": 10.0 },
    "...": {}
  },
  "sewer": {
    "spill": {
      "gjutjarn": { "mu": 70.0, "sigma": 10.0 },
      "...": {}
    },
    "storm": {
      "gjutjarn": { "mu": 75.0, "sigma": 10.0 },
      "...": {}
    }
  },
  "liners": {
     "default": { "mu": 50.0, "sigma": 5.0 }
  }
}
```

*   The main keys are `water` and `sewer`. `sewer` is further divided into `spill` (wastewater) and `storm` (stormwater).
*   The `municipalities` list is **no longer used** by the plugin; the filter is now populated dynamically from your layer data.
*   The `renovation_method_mapping` allows you to map numeric codes from your data to descriptive renovation methods.
*   The `liners` section defines parameters for renovated pipes.
