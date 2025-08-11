# reneW - QGIS Plugin for Pipeline Renewal Planning

`reneW` is a QGIS plugin designed to help in the planning of utility pipe renewals. It calculates a risk score for each pipe based on its age, material, and dimension, providing a quantitative basis for maintenance and renewal decisions.

## Features

*   Calculates a risk score for each pipe in a vector layer.
*   Risk model based on pipe age, material, and dimension.
*   User-friendly dialog to select layer and map attributes.
*   Adds the calculated score to a new field (`risk_score`) in your data.

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
    Start QGIS and load the vector layer containing your pipeline data. Make sure this layer has attributes for installation year, material, and dimension. The data should be clean (e.g., year should be a number).

2.  **Launch the Plugin:**
    Click on the `reneW` icon in the toolbar or go to the `Plugins` menu -> `reneW` -> `Run reneW`.

3.  **Configure the Calculation:**
    The `reneW - Riskkalkylering` dialog will appear.
    *   **Välj ledningslager:** Select your pipeline layer from the dropdown menu.
    *   **Fält för material:** Choose the field that contains the material information.
    *   **Fält för årtal:** Choose the field that contains the installation year.
    *   **Fält för dimension:** Choose the field that contains the dimension information.

4.  **Run the Calculation:**
    Click the `OK` button. The plugin will now perform the calculation. A message will appear in the message bar when it's complete.

5.  **View the Results:**
    *   A new field named `risk_score` will be added to your layer's attribute table.
    *   You can open the attribute table (right-click on the layer -> `Open Attribute Table`) to see the calculated scores for each pipe.
    *   You can now use this `risk_score` field to style your layer (e.g., using a graduated symbology) to visually identify high-risk pipes.

## The Risk Model

The current risk score is calculated using a simple formula:

`Risk Score = Age Score + Material Score + Dimension Score`

*   **Age Score:** Based on the number of years since installation.
*   **Material Score:** Based on a predefined risk value for different materials (e.g., cast iron has a higher score than PE).
*   **Dimension Score:** A score component based on the pipe's dimension.

This model is a starting point and will be expanded upon in future versions.
