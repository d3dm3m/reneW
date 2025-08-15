import sys
from unittest.mock import MagicMock

def setup_qgis_mocks():
    """
    Sets up a robust mock of the QGIS and PyQt environment in sys.modules.
    This prevents import errors and allows for testing of QGIS-dependent code
    without a running QGIS instance.
    """
    # Create a mock for the top-level qgis package
    qgis_mock = MagicMock()

    # Create mocks for the submodules
    qgis_core_mock = MagicMock()
    qgis_gui_mock = MagicMock()
    qgis_symbology_mock = MagicMock()
    qgis_analysis_mock = MagicMock()
    qgis_processing_mock = MagicMock()
    pyqt_mock = MagicMock()
    pyqt_core_mock = MagicMock()
    pyqt_gui_mock = MagicMock()
    pyqt_widgets_mock = MagicMock()

    # Place the mocks in sys.modules to intercept imports
    sys.modules['qgis'] = qgis_mock
    sys.modules['qgis.core'] = qgis_core_mock
    sys.modules['qgis.gui'] = qgis_gui_mock
    sys.modules['qgis.symbology'] = qgis_symbology_mock
    sys.modules['qgis.analysis'] = qgis_analysis_mock
    sys.modules['qgis.processing'] = qgis_processing_mock
    sys.modules['qgis.PyQt'] = pyqt_mock
    sys.modules['qgis.PyQt.QtCore'] = pyqt_core_mock
    sys.modules['qgis.PyQt.QtGui'] = pyqt_gui_mock
    sys.modules['qgis.PyQt.QtWidgets'] = pyqt_widgets_mock

    # Mock specific classes and functions that are used at import time
    # or are required for subclassing in the application code.

    # Mock QDialog as a class 'type' to prevent metaclass conflicts
    mock_qdialog_class = type('MockQDialog', (object,), {
        '__init__': lambda self, parent=None: None,
        'accept': lambda self: None,
        'reject': lambda self: None,
        'exec_': lambda self: None
    })
    pyqt_widgets_mock.QDialog = mock_qdialog_class

    # Mock QgsVectorLayer as a class 'type' with necessary attributes for validation
    mock_qgsvectorlayer_class = type('MockQgsVectorLayer', (object,), {
        # The dialog checks layer.fields().field(name).isNumeric()
        'fields': MagicMock()
    })
    qgis_core_mock.QgsVectorLayer = mock_qgsvectorlayer_class

    # Make QgsFeature return a new mock each time to allow testing feature creation
    qgis_core_mock.QgsFeature.side_effect = lambda *args: MagicMock()

    # Mock the uic loader to return a mock form class and a base class
    def mock_setup_ui(self, widget_instance):
        """
        A mock for the uic-generated setupUi method.
        This function manually creates all the widget attributes on the dialog
        instance that are defined in the .ui file and accessed in __init__.
        """
        widget_instance.mButtonBox = MagicMock()
        widget_instance.mPipeTypeCombo = MagicMock()
        widget_instance.mBtnAddMaterialRow = MagicMock()
        widget_instance.mBtnRemoveMaterialRow = MagicMock()
        widget_instance.mMaterialsTable = MagicMock()
        widget_instance.groupBox = MagicMock()
        widget_instance.verticalLayout_2 = MagicMock()
        widget_instance.mTabWidget = MagicMock()
        widget_instance.mTabWidget.count.return_value = 0
        widget_instance.mMunicipalityFilterCombo = MagicMock()
        widget_instance.mCheckBoxEnableDimensionWeighting = MagicMock()
        widget_instance.mBtnEditParameters = MagicMock()
        widget_instance.mSpinBoxDimensionFactor = MagicMock()
        widget_instance.mStatusLabel = MagicMock()

    mock_form_class = type('MockForm', (object,), {'setupUi': mock_setup_ui})
    pyqt_mock.uic.loadUiType.return_value = (mock_form_class, object)
