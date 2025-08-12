# reneW - QGIS Plugin for Pipeline Renewal Planning

`reneW` is a QGIS plugin designed to help in the planning of utility pipe renewals. It calculates a renewal need score for each pipe based on a survival analysis model, providing a quantitative basis for maintenance and renewal decisions.

## Features

*   Calculates a **renewal need** score (from 0.0 to 1.0+) for each pipe.
*   Uses a **Herz survival model** based on pipe type (water/sewage), material, and age.
*   Includes an **optional and adjustable weighting factor** for pipe dimension to account for consequence of failure.
*   User-friendly dialog to select the layer and map the necessary attributes.
*   Adds the calculated score to a new field (`fornyelsebehov`) in your data.

## Installation

To install the `reneW` plugin in QGIS, follow these steps:

1.  **Download the Plugin:**
    If you have the plugin as a folder (e.g., named `reneW`), you can proceed to the next step. This folder should contain all the plugin files (`__init__.py`, `reneW.py`, etc.).

2.  **Find your QGIS Plugins Directory:**
    Open QGIS. Go to the `Settings` menu -> `User Profiles` -> `Open Active Profile Folder`. This will open a file explorer window. Inside this folder, navigate to `python/plugins`.

    The full path is typically something like:
    *   **Windows:** `C:\\Users\\<YourUsername>\\AppData\\Roaming\\QGIS\\QGIS3\\profiles\\default\\python\\plugins`
    *   **macOS:** `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins`
    *   **Linux:** `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins`

3.  **Copy Plugin Directory:**
    Copy the entire `reneW` directory into the `plugins` directory you located in the previous step.

4.  **Activate the Plugin in QGIS:**
    *   Restart QGIS.
    *   Go to the `Plugins` menu -> `Manage and Install Plugins...`.
    *   In the `Installed` tab, you should see "reneW". Make sure the checkbox next to it is ticked to enable it.

You should now see the `reneW` icon in the QGIS toolbar.

## Usage

1.  **Open Your Project:**
    Start QGIS and load the vector layer containing your pipeline data. Make sure this layer has attributes for installation year, material, and dimension.

2.  **Launch the Plugin:**
    Click on the `reneW` icon in the toolbar or go to the `Plugins` menu -> `reneW` -> `Run reneW`.

3.  **Configure the Calculation:**
    The `reneW - Riskkalkylering` dialog will appear.
    *   **Välj ledningslager:** Select your pipeline layer.
    *   **Välj ledningstyp:** Select 'Vatten' (Water) or 'Avlopp' (Sewage/Stormwater).
    *   **Fält för material:** Choose the field with the material information.
    *   **Fält för årtal:** Choose the field with the installation year.
    *   **Fält för dimension:** Choose the field with the dimension information.
    *   **Använd dimensionsviktning:** Check this box to apply a consequence weighting based on dimension.
    *   **Faktor:** If weighting is enabled, adjust this factor to control the influence of the dimension. A higher factor gives dimension a greater impact.

4.  **Run the Calculation:**
    Click the `OK` button.

5.  **View the Results:**
    *   A new field named `fornyelsebehov` will be added to your layer's attribute table.
    *   You can now use this field to style your layer (e.g., using a graduated symbology) to visually identify high-risk pipes.

## The Calculation Model

### 1. Base Renewal Need (Herz Model)

The base renewal need is calculated from a survival function, `S(t)`, based on the Herz model. The renewal need is `1 - S(t)`. The survival probability `S(t)` is calculated as:

`S(t) = 1 / (1 + ((t - c) / a)^b)`

Where:
*   `t` is the age of the pipe.
*   `a`, `b`, and `c` are parameters that depend on the pipe's material and installation year, based on the tables provided by the user.

### 2. Optional Dimension Weighting

If enabled, the base renewal need is multiplied by a consequence factor based on the pipe's dimension. The formula is:

`Final Score = Renewal Need * (1 + (Dimension * Factor))`

This allows you to give a higher weight to larger pipes, where a failure would have a greater consequence.
