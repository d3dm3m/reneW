import os
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QCoreApplication

from .reneW_dialog import ReneWDialog
from .api import ReneWApi


def tr(message):
    """Get the translation for a string using Qt translation API."""
    return QCoreApplication.translate("ReneW", message)


class ReneW:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor."""
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu = tr("&reneW")
        self.toolbar = self.iface.addToolBar(tr("reneW"))
        self.toolbar.setObjectName("reneW")
        self.dlg = None
        self.api = ReneWApi(self.iface)

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None,
    ):
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
        icon_path = os.path.join(self.plugin_dir, "icon.png")
        self.add_action(
            icon_path,
            text=tr("Run reneW"),
            callback=self.run,
            parent=self.iface.mainWindow(),
        )

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(tr("&reneW"), action)
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
            self.api.dlg = self.dlg
            analysis_configs = self.dlg.get_analysis_configs()

            if self.dlg.useTemporalAnalysis():
                self.api.temporal_analysis(
                    configs=analysis_configs,
                    start_year=self.dlg.temporalStartYear(),
                    end_year=self.dlg.temporalEndYear(),
                    step=self.dlg.temporalStep(),
                )
            else:
                for cfg in analysis_configs:
                    self.api.calculate_renewal_need(cfg["layer"], cfg)

            if self.dlg.useHotspotAnalysis():
                hotspot = self.api.hotspot_analysis(
                    configs=analysis_configs,
                    threshold=float(self.dlg.hotspotThreshold()),
                    radius=float(self.dlg.hotspotRadius()),
                    field_name="renewal_need",
                )
                if hotspot:
                    hotspot.selectionChanged.connect(
                        lambda ids, _, __: self._open_hotspot_explorer(
                            hotspot, ids, analysis_configs
                        )
                    )

    def _open_hotspot_explorer(self, hotspot_layer, selected_ids, analysis_configs):
        pass
