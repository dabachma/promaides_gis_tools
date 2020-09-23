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

from .environment import get_ui_path


UI_PATH = get_ui_path('ui_time_viewer.ui')


class PluginDialog(QDialog):

    def __init__(self, iface, parent=None, flags=Qt.WindowFlags()):
        QDialog.__init__(self, parent, flags)
        uic.loadUi(UI_PATH, self)

        self.iface = iface

        #self.FieldIDBox.setFilters(QgsFieldProxyModel.Numeric)
        self.InputLayerBox.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.InputLayerBox.setLayer(None)
        self.InputLayerBox.layerChanged.connect(self.UpdateFrameID)
        self.FieldIDBox.fieldChanged.connect(self.UpdateProcessButton)
        self.TimeSlider.valueChanged.connect(self.SliderUpdated)

        self.SaveBox.addItem('JPEG')
        self.SaveBox.addItem('PNG')
        self.SaveBox.addItem('AVI')
        self.FPSBox.setValue(1)

        self.Displayer.setText("Hello!")

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
        self.PlayButton.setEnabled(False)
        self.PauseButton.setEnabled(False)
        self.StopButton.setEnabled(False)
        self.PreviousButton.setEnabled(False)
        self.NextButton.setEnabled(False)

        self.PlayButton.clicked.connect(self.play1)
        self.NextButton.clicked.connect(self.Next)
        self.PreviousButton.clicked.connect(self.Previous)
        self.ProcessButton.clicked.connect(self.WriteProcessing)
        self.PauseButton.clicked.connect(self.PausePlay)
        self.StopButton.clicked.connect(self.StopPlay)
        self.browseButton.clicked.connect(self.onBrowseButtonClicked)
        self.SaveFrameBox.stateChanged.connect(saveframeclicked)
        self.browseButton.setAutoDefault(False)


    def UpdateFrameID(self, layer):
        self.FieldIDBox.setLayer(self.InputLayer())
        self.PlayButton.setEnabled(False)
        self.NextButton.setEnabled(False)
        self.PreviousButton.setEnabled(False)
        self.ProcessButton.setEnabled(True)

    def WriteProcessing(self):
        self.Displayer.setText("Processing...")
        QTimer.singleShot(10, self.ReadFrameIDs)


    FrameIDs = []
    def ReadFrameIDs(self):
        self.FrameIDs = []
        layer = self.InputLayer()
        layer.setSubsetString('')
        field = self.FieldIDBox.currentText()
        idx = layer.fields().indexOf('{index}'.format(index=field))
        if idx==-1:
            self.iface.messageBar().pushCritical(
                'Time Viewer',
                'Field Does Not Exist !'
            )
            return
        FrameIDvalues = layer.uniqueValues(idx)
        for i in FrameIDvalues:
            self.FrameIDs.append(i)
        self.FrameIDs.sort()
        self.ProcessButton.setEnabled(False)
        self.PlayButton.setEnabled(True)
        self.PreviousButton.setEnabled(True)
        self.NextButton.setEnabled(True)
        self.Displayer.setText("Ready!")
        self.TimeSlider.setMinimum(1)
        self.TimeSlider.setMaximum(len(self.FrameIDs))
        self.TimeSlider.setSingleStep(1)
        self.TimeSlider.setValue(1)
        self.TimeSlider.setTickInterval(len(self.FrameIDs)/5)

    SliderChanged = False
    def SliderUpdated(self):
        if self.NextPressed or self.PreviousPressed:
            return
        else:
            self.count=self.TimeSlider.value()-1
            self.SliderChanged=True
            self.play1()

    def UpdateProcessButton(self):
        self.ProcessButton.setEnabled(True)
        self.PlayButton.setEnabled(False)
        self.NextButton.setEnabled(False)
        self.PreviousButton.setEnabled(False)
        self.Displayer.setText("Hello!")


    def InputLayer(self):
        return self.InputLayerBox.currentLayer()

    def PausePlay(self):
        self.PausePressed=True

    NextPressed = False
    def Next(self):
        if self.count==len(self.FrameIDs)-1:
            self.iface.messageBar().pushCritical(
                'Time Viewer',
                'Next Frame Not Available !'
            )
            return
        else:
            self.NextPressed=True
            self.count=self.count+1
            self.play1()

    PreviousPressed = False
    def Previous(self):
        if self.count==0:
            self.iface.messageBar().pushCritical(
                'Time Viewer',
                'Previous Frame Not Available !'
            )
            return
        else:
            self.PreviousPressed = True
            self.count = self.count - 1
            self.play1()

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
        self.TimeSlider.setValue(self.count+1)
        self.PlayButton.setEnabled(False)
        self.PauseButton.setEnabled(True)
        self.StopButton.setEnabled(True)
        self.PreviousButton.setEnabled(False)
        self.NextButton.setEnabled(False)
        layer = self.InputLayer()
        if self.PausePressed==True:
            self.PlayButton.setEnabled(True)
            self.PauseButton.setEnabled(False)
            self.StopButton.setEnabled(False)
            self.StopPressed = False
            self.PausePressed = False
            self.PreviousButton.setEnabled(True)
            self.NextButton.setEnabled(True)
            self.Displayer.setText("Paused!")
            return
        if self.StopPressed == True:
            self.count=0
            self.PlayButton.setEnabled(True)
            self.PauseButton.setEnabled(False)
            self.StopButton.setEnabled(False)
            self.StopPressed = False
            self.PausePressed = False
            self.PreviousButton.setEnabled(True)
            self.NextButton.setEnabled(True)
            layer.setSubsetString('')
            self.Displayer.setText("Ready!")
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
        self.Displayer.setText("{a}={b}".format(a=field, b=value))
        if str(self.addfilterbox.text()) == "":
            layer.setSubsetString("\"{a}\"=\'{b}\'".format(a=field, b=value))
        else:
            layer.setSubsetString("\"{a}\"=\'{b}\' AND {c}".format(a=field, b=value, c=self.addfilterbox.text()))
        if self.NextPressed or self.PreviousPressed or self.SliderChanged:
            self.NextPressed=False
            self.PreviousPressed=False
            self.SliderChanged=False
            self.PreviousButton.setEnabled(True)
            self.NextButton.setEnabled(True)
            self.PlayButton.setEnabled(True)
            self.PauseButton.setEnabled(False)
            self.StopButton.setEnabled(False)
            return
        QTimer.singleShot(FPS, self.play2)



    def play2(self):
        global count
        layer = self.InputLayer()
        if self.PausePressed==True:
            self.PlayButton.setEnabled(True)
            self.PauseButton.setEnabled(False)
            self.StopButton.setEnabled(False)
            self.StopPressed = False
            self.PausePressed = False
            self.PreviousButton.setEnabled(True)
            self.NextButton.setEnabled(True)
            self.Displayer.setText("Paused!")
            return
        if self.StopPressed == True:
            self.count=0
            self.PlayButton.setEnabled(True)
            self.PauseButton.setEnabled(False)
            self.StopButton.setEnabled(False)
            self.StopPressed = False
            self.PausePressed = False
            self.PreviousButton.setEnabled(True)
            self.NextButton.setEnabled(True)
            layer.setSubsetString('')
            self.Displayer.setText("Ready!")
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
            self.PlayButton.setEnabled(True)
            self.PauseButton.setEnabled(False)
            self.StopButton.setEnabled(False)
            self.PreviousButton.setEnabled(True)
            self.NextButton.setEnabled(True)
            self.StopPressed = False
            self.PausePressed = False
            self.count=0
            self.TimeSlider.setValue(1)

            self.Displayer.setText("Ready!")


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


