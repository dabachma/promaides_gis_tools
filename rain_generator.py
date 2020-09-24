from __future__ import unicode_literals
from __future__ import absolute_import

# system modules
import math
import os
import tempfile

# QGIS modules
from qgis.core import *
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import *
from qgis.PyQt import uic

from shapely.geometry import MultiLineString, mapping, shape

from .environment import get_ui_path


UI_PATH = get_ui_path('ui_rain_generator.ui')


class PluginDialog(QDialog):

    def __init__(self, iface, parent=None, flags=Qt.WindowFlags()):
        QDialog.__init__(self, parent, flags)
        uic.loadUi(UI_PATH, self)

        self.iface = iface
        self.input_layer = None

        self.RainGaugeLayer.setFilters(QgsMapLayerProxyModel.PointLayer)
        self.GenerationAreaLayer.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.DataAddressField.setFilters(QgsFieldProxyModel.String)

        self.RainGaugeLayer.layerChanged.connect(self.UpdateDataAddressField)

        self.RainGaugeLayer.setLayer(None)
        self.GenerationAreaLayer.setLayer(None)

        self.DataTypeBox.addItem('minutely')
        self.DataTypeBox.addItem('Hourly')
        self.DataTypeBox.addItem('Monthly')


    def UpdateDataAddressField(self, layer):
        self.DataAddressField.setLayer(self.RainGaugeLayer.currentLayer())


class RainGenerator(object):

    def __init__(self, iface):
        self.iface = iface
        self.dialog = None
        self.cancel = False
        self.act = QAction('Rain Generator', iface.mainWindow())
        self.act.triggered.connect(self.execDialog)

    def initGui(self, menu=None):
        if menu is not None:
            menu.addAction(self.act)
        else:
            self.iface.addToolBarIcon(self.act)

    def unload(self, menu=None):
        if menu is None:
            menu.removeAction(self.act)
        else:
            self.iface.removeToolBarIcon(self.act)

    def execDialog(self):
        """
        """
        self.dialog = PluginDialog(self.iface, self.iface.mainWindow())
        self.dialog.accepted.connect(self.execTool)
        self.dialog.rejected.connect(self.quitDialog)
        self.dialog.setModal(False)
        self.act.setEnabled(False)
        self.dialog.show()

    def scheduleAbort(self):
        self.cancel = True

    def quitDialog(self):
        self.dialog = None
        self.act.setEnabled(True)
        self.cancel = False

    def execTool(self):
        primt("hello")