def classFactory(iface):
  """Load reneW class from file reneW.
  :param iface: A QGIS interface instance.
  :type iface: QgsInterface
  """
  from .reneW import ReneW
  return ReneW(iface)
