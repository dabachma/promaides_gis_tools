from __future__ import unicode_literals
from __future__ import absolute_import

# system modules
import math
import os
import tempfile
import time
import subprocess
import sys


# QGIS modules
from qgis.core import *
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import *
from qgis.PyQt import uic
from PyQt5.QtCore import QTimer
from qgis.utils import iface

from shapely.geometry import MultiLineString, mapping, shape

# This plugin resamples the vertices of a polyline; use it for a higher point density of a line;
from .environment import get_ui_path


UI_PATH = get_ui_path('ui_time_viewer.ui')


class PluginDialog(QDialog):

    def __init__(self, iface, parent=None, flags=Qt.WindowFlags()):
        QDialog.__init__(self, parent, flags)
        uic.loadUi(UI_PATH, self)

        self.iface = iface

        self.FieldIDBox.setFilters(QgsFieldProxyModel.Numeric)
        self.InputLayerBox.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.InputLayerBox.setLayer(None)
        self.InputLayerBox.layerChanged.connect(self.UpdateFrameID)

        self.SaveBox.addItem('JPEG')
        self.SaveBox.addItem('PNG')
        self.SaveBox.addItem('AVI')
        self.FPSBox.setValue(1)

        def saveframeclicked(state):
            if state > 0:
                self.SaveBox.setEnabled(True)
                self.folderEdit.setEnabled(True)
                self.browseButton.setEnabled(True)
            else:
                self.SaveBox.setEnabled(False)
                self.folderEdit.setEnabled(False)
                self.browseButton.setEnabled(False)

        self.SaveBox.setEnabled(False)
        self.folderEdit.setEnabled(False)
        self.browseButton.setEnabled(False)
        self.PauseButton.setEnabled(False)
        self.StopButton.setEnabled(False)

        self.PlayButton.clicked.connect(self.ReadFrameIDs)
        self.PauseButton.clicked.connect(self.PausePlay)
        self.StopButton.clicked.connect(self.StopPlay)
        self.browseButton.clicked.connect(self.onBrowseButtonClicked)
        self.SaveFrameBox.stateChanged.connect(saveframeclicked)
        self.browseButton.setAutoDefault(False)


    def UpdateFrameID(self, layer):
        self.FieldIDBox.setLayer(self.InputLayer())

    FrameIDs = []
    def ReadFrameIDs(self):
        self.PauseButton.setEnabled(True)
        self.StopButton.setEnabled(True)
        layer = self.InputLayer()
        layer.setSubsetString('')
        self.FrameIDs, ok = QgsVectorLayerUtils.getValues(layer, self.FieldIDBox.expression(), False)
        if not ok:
            self.iface.messageBar().pushCritical(
                'Time Viewer',
                'Invalid expression for Frame ID !'
            )
            return
        self.FrameIDs = list(dict.fromkeys(self.FrameIDs))
        self.FrameIDs.sort()
        self.play1()


    def InputLayer(self):
        return self.InputLayerBox.currentLayer()

    def PausePlay(self):
        self.PausePressed=True

    def StopPlay(self):
        self.StopPressed=True

    def onBrowseButtonClicked(self):
        currentFolder = self.folderEdit.text()
        folder = QFileDialog.getExistingDirectory(self.iface.mainWindow(), 'Time Viewer', currentFolder)
        if folder != '':
            self.folderEdit.setText(folder)
            self.folderEdit.editingFinished.emit()

    def outFolder(self):
        return self.folderEdit.text()

    def check_fps(self,value):
        if value <= 0:
            return 1
        else:
            return 0

    count = 0
    StopPressed=False
    PausePressed=False
    def play1(self):
        layer = self.InputLayer()
        if self.PausePressed==True:
            self.PauseButton.setEnabled(False)
            self.StopButton.setEnabled(False)
            self.StopPressed = False
            self.PausePressed = False
            return
        if self.StopPressed == True:
            self.count=0
            self.PauseButton.setEnabled(False)
            self.StopButton.setEnabled(False)
            self.StopPressed = False
            self.PausePressed = False
            layer.setSubsetString('')
            return
        if self.check_fps(self.FPSBox.value())==1:
            self.iface.messageBar().pushCritical(
                'Time Viewer',
                'Invalid Value for FPS !'
            )
            return
        else:
            FPS = 1000 / self.FPSBox.value()
        field = self.FieldIDBox.currentText()
        value = self.FrameIDs[self.count]
        if str(self.addfilterbox.text()) == "":
            layer.setSubsetString("\"{a}\"={b}".format(a=field, b=value))
        else:
            layer.setSubsetString("\"{a}\"={b} AND {c}".format(a=field, b=value, c=self.addfilterbox.text()))
        QTimer.singleShot(FPS, self.play2)



    def play2(self):
        global count
        layer = self.InputLayer()
        if self.PausePressed==True:
            self.PauseButton.setEnabled(False)
            self.StopButton.setEnabled(False)
            self.StopPressed = False
            self.PausePressed = False
            return
        if self.StopPressed == True:
            self.count=0
            self.PauseButton.setEnabled(False)
            self.StopButton.setEnabled(False)
            self.StopPressed = False
            self.PausePressed = False
            layer.setSubsetString('')
            return
        layer.setSubsetString('')
        layername = self.InputLayer().name()
        if self.SaveFrameBox.isChecked():
            if self.SaveBox.currentText()=="PNG":
                iface.mapCanvas().saveAsImage(str(self.outFolder()) + "/" + str(layername) + "_" + str(self.count) + ".png")
                os.remove(str(self.outFolder()) + "/" + str(layername) + "_" + str(self.count) + ".pgw")

            elif self.SaveBox.currentText()=="JPEG":
                iface.mapCanvas().saveAsImage(str(self.outFolder()) + "/" + str(layername) + "_" + str(self.count) + ".jpg")
                os.remove(str(self.outFolder()) + "/" + str(layername) + "_" + str(self.count) + ".jgw")

        if self.count <= len(self.FrameIDs)-2:
            QTimer.singleShot(0.1, self.play1) # Wait a second and prepare next map
            self.count += 1
        else:
            self.PauseButton.setEnabled(False)
            self.StopButton.setEnabled(False)
            self.StopPressed = False
            self.PausePressed = False
            self.count=0


class TimeViewer(object):

    def __init__(self, iface):
        self.iface = iface
        self.dialog = None
        self.cancel = False
        self.act = QAction('Time Viewer', iface.mainWindow())
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
        self.dialog.setModal(False)
        self.act.setEnabled(False)
        self.dialog.show()

    def scheduleAbort(self):
        self.cancel = True


