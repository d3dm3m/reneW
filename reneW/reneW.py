import os

from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QCoreApplication

# --- Core QGIS Modules ---
from qgis.core import (
    Qgis,
)

# Import the code for the dialog and the calculation logic
from .reneW_dialog import ReneWDialog
from .api import ReneWApi


def tr(message):
    """Get the translation for a string using Qt translation API."""
    return QCoreApplication.translate('ReneW', message)


class ReneW:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor."""
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu = tr(u'&reneW')
        self.toolbar = self.iface.addToolBar(tr(u'reneW'))
        self.toolbar.setObjectName(u'reneW')
        self.dlg = None
        self.results_dialog = None
        self.api = ReneWApi(self)

    def add_action(self, icon_path, text, callback, enabled_flag=True, add_to_menu=True,
                   add_to_toolbar=True, status_tip=None, whats_this=None, parent=None):
        """Add a toolbar icon to the toolbar."""
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)
        if status_tip is not None:
            action.setStatusTip(status_tip)
        if whats_this is not None:
            action.setWhatsThis(whats_this)
        if add_to_toolbar:
            self.toolbar.addAction(action)
        if add_to_menu:
            self.iface.addPluginToMenu(self.menu, action)
        self.actions.append(action)
        return action

    def initGui(self):
        """Create the menu entries and toolbar icons for the plugin."""
        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        self.add_action(
            icon_path,
            text=tr(u'Run reneW'),
            callback=self.run,
            parent=self.iface.mainWindow())

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(tr(u'&reneW'), action)
            self.iface.removeToolBarIcon(action)
        del self.toolbar

    def run(self):
        """Run method that configures and dispatches the analysis."""
        if self.dlg is None:
            self.dlg = ReneWDialog(self.iface.mainWindow())

        self.dlg.load_settings()
        self.dlg.show()
        result = self.dlg.exec()

        if result:
            self.dlg.save_settings()
            analysis_configs = self.dlg.get_analysis_configs()
            if not analysis_configs:
                self.iface.messageBar().pushMessage(
                    tr("Info"),
                    tr("No layers selected for analysis."),
                    Qgis.Info, duration=3
                )
                return

            if self.dlg.useTemporalAnalysis():
                start_year = self.dlg.temporalStartYear()
                end_year = self.dlg.temporalEndYear()
                step = self.dlg.temporalStep()
                self.api.temporal_analysis(analysis_configs, start_year, end_year, step)
            else:
                for config in analysis_configs:
                    self.api.calculate_renewal_need(config['layer'], config)

            if self.dlg.useHotspotAnalysis():
                hotspot_threshold = self.dlg.hotspotThreshold()
                hotspot_radius = self.dlg.hotspotRadius()
                self.api.hotspot_analysis(analysis_configs, hotspot_threshold, hotspot_radius, 'renewal_need')
