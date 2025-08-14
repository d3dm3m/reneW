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

A new memory layer named `Temporal Renewal Need` will be added to your project. This layer is styled to show two variables at once:

*   **Pipe Type:** The color of the pipe indicates its type (Blue for water, Red for wastewater, Green for stormwater).
*   **Renewal Need:** The intensity of the color indicates the renewal need. A pale, light color means a low need, while a bright, saturated color means a high need.
*   **Critical Pipes:** The pipes with the highest need will have a yellow "glow" effect, making them easy to spot.

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

The file contains a nested dictionary structure for the different pipe domains.

```json
{
  "metadata": { ... },
  "municipalities": [ ... ],
  "water": {
    "grajarn_<1950": { "mu": 85, "sigma": 25 },
    "segjarn_>=1980": { "mu": 135, "sigma": 28 },
    "ovrigt": { "mu": 100, "sigma": 40 }
  },
  "sewer": {
    "spill": {
      "betong_<1950": { "mu": 80, "sigma": 20 },
      "ovrigt": { "mu": 90, "sigma": 35 }
    },
    "storm": {
      "betong_<1950": { "mu": 100, "sigma": 30 },
      "ovrigt": { "mu": 100, "sigma": 40 }
    }
  }
}
```

*   The main keys are `water` and `sewer`. `sewer` is further divided into `spill` and `storm`.
*   Inside each section is a dictionary of material parameter sets.
*   The **keys** of this dictionary (e.g., `"grajarn_<1950"`) are internal identifiers used by the plugin.
*   The **values** are objects containing the `"mu"` and `"sigma"` for that material class.

### How Material Matching Works

You do not need to have material names in your data that exactly match the keys in `parameters.json`. The plugin uses a flexible matching system (`reneW/material_lookup.py`) to map your data to the correct parameters.

1.  **Alias Matching:** The system first normalizes your material string (e.g., "Segjärnsrör") and compares it against a vocabulary of common synonyms. For example, "segjärn", "ductile iron", and "dci" all map to the internal base key `segjarn`.
2.  **Year-based Selection:** For materials that have different properties depending on age (e.g., PVC before and after 1970), the system uses the pipe's construction year to select the correct parameter key (e.g., `pvc_<1970` or `pvc_>=1970`).
3.  **Fallback:** If no specific material is matched, the system uses the parameters defined for the `ovrigt` (other/unknown) key for that pipe domain.

To customize the logic, you can either edit the `mu` and `sigma` values in the **Parameter Editor** or directly in the `parameters.json` file.
