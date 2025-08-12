import os
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication

def classFactory(iface):
  """Load reneW class from file reneW.
  :param iface: A QGIS interface instance.
  :type iface: QgsInterface
  """
  # Get the system locale
  locale = QSettings().value('locale/userLocale', 'en')[0:2]
  plugin_dir = os.path.dirname(__file__)
  locale_path = os.path.join(
      plugin_dir,
      'i18n',
      f'{locale}.qm')

  # Load the translation file
  if os.path.exists(locale_path):
      translator = QTranslator()
      translator.load(locale_path)
      QCoreApplication.installTranslator(translator)

  from .reneW import ReneW
  return ReneW(iface)
