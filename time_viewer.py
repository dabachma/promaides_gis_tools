from __future__ import unicode_literals
from __future__ import absolute_import

# system modules
import math
import os
import tempfile
import time
import subprocess
import sys
import glob


# QGIS modules
from qgis.core import *
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtWidgets import *
from qgis.PyQt import uic
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import *
from PyQt5 import *
from qgis.utils import iface

from .environment import get_ui_path


UI_PATH = get_ui_path('ui_time_viewer.ui')

class PluginDialog(QDockWidget):
    
    ClosingSignal = pyqtSignal()

    def __init__(self, iface, parent=None, flags=Qt.WindowFlags()):
        QDockWidget.__init__(self, parent, flags)
        uic.loadUi(UI_PATH, self)

        self.iface = iface

        self.InputLayerBox.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.InputLayerBox.setLayer(None)
        self.InputLayerBox.layerChanged.connect(self.UpdateFrameID)
        self.FieldIDBox.fieldChanged.connect(self.UpdateProcessButton)
        self.TimeSlider.valueChanged.connect(self.SliderUpdated)

        #reads if the plugin was open or not
        s = QgsSettings()
        pluginstatus = s.value("TimeViewer", "default text")
        if pluginstatus=="open":
            QTimer.singleShot(1000, self.ReadSettings)

        #sets the plugin status to open
        s.setValue("TimeViewer", "open")


        self.SaveBox.addItem('PNG')
        self.SaveBox.addItem('JPEG')
        #self.FPSBox.setValue(1)

        self.Displayer.setText("Hello!")
        self.LayerDisplayer.setText("No Layer Selected")
            
        def saveframeclicked(state):
            if state > 0:
                self.SaveBox.setEnabled(True)

            else:
                self.SaveBox.setEnabled(False)

        self.SaveBox.setEnabled(False)
        self.folderEdit.setEnabled(False)
        self.browseButton.setEnabled(False)
        self.PlayButton.setEnabled(False)
        self.PauseButton.setEnabled(False)
        self.StopButton.setEnabled(False)
        self.PreviousButton.setEnabled(False)
        self.NextButton.setEnabled(False)
        self.TimeSlider.setEnabled(False)
        self.ProcessButton.setEnabled(False)
        self.ExportVideoButton.setEnabled(False)

        self.AddButton.clicked.connect(self.AddLayer)
        self.RemoveButton.clicked.connect(self.RemoveLayer)

        self.PlayButton.clicked.connect(self.play1)
        self.NextButton.clicked.connect(self.Next)
        self.PreviousButton.clicked.connect(self.Previous)
        self.ProcessButton.clicked.connect(self.WriteProcessing)
        self.PauseButton.clicked.connect(self.PausePlay)
        self.StopButton.clicked.connect(self.StopPlay)
        self.browseButton.clicked.connect(self.onBrowseButtonClicked)
        self.SaveFrameBox.stateChanged.connect(saveframeclicked)
        self.ExportVideoButton.clicked.connect(self.OpenVideoExportDialog)
        self.SavePreferenceButton.clicked.connect(self.SaveSettings)
        self.RestorePreferenceButton.clicked.connect(self.ReadSettings)
        self.browseButton.setAutoDefault(False)

    def closeEvent(self, event):
        if type(self.InputLayerBox.currentLayer()) != type(None):
            for n, layer in enumerate(self.layers):
                if len(self.InitialFilters) > 0:
                    if n <= (len(self.InitialFilters) - 1):
                        layer.setSubsetString(self.InitialFilters[n])
        del self.layers[:]
        del self.InitialFilters[:]
        self.layers=[]
        self.InitialFilters=[]
        self.StopPlay()
        self.ExportVideoState = False
        self.scrollArea.setEnabled(True)
        self.ExportVideoButton.setEnabled(True)
        self.SavePreferenceButton.setEnabled(True)
        self.RestorePreferenceButton.setEnabled(True)
        self.ClosingSignal.emit()


    def SaveSettings(self):
        proj = QgsProject.instance()
        proj.writeEntry("TimeViewer", "Counter" , self.count)
        proj.writeEntry("TimeViewer", "Field", self.FieldIDBox.currentText())
        for n, layer in enumerate(self.layers):
            proj.writeEntry("TimeViewer", "LayersList" + str(n), layer.name())
        for n, frameid in enumerate(self.FrameIDs):
            proj.writeEntry("TimeViewer", "FrameIDs" + str(n), frameid)
        for n, initialfilter in enumerate(self.InitialFilters):
            proj.writeEntry("TimeViewer", "InitialFilters" + str(n), initialfilter)

        proj.writeEntry("TimeViewer", "NFrameIDs", len(self.FrameIDs))
        proj.writeEntry("TimeViewer", "Nlayers", len(self.layers))
        proj.writeEntry("TimeViewer", "FPS", self.FPSBox.value())
        proj.writeEntry("TimeViewer", "ffmpegaddress", self.ffmpegaddress)
        proj.writeEntry("TimeViewer", "Output", self.folderEdit.text())

        self.iface.messageBar().pushSuccess(
            'Time Viewer',
            'Session Saved Successfully  !'
        )
        return


    def ReadSettings(self):
        try:
            proj = QgsProject.instance()
            field=proj.readEntry("TimeViewer","Field")
            self.FieldIDBox.setField(str(field[0]))
            self.count, type_conversion_ok = proj.readNumEntry("TimeViewer", "Counter")
            self.TimeSlider.setValue(self.count + 1)
            Nlayers, type_conversion_ok = proj.readNumEntry("TimeViewer", "Nlayers")
            Nframeids, type_conversion_ok = proj.readNumEntry("TimeViewer", "NFrameIDs")
            fps, type_conversion_ok = proj.readNumEntry("TimeViewer", "FPS")
            self.FPSBox.setValue(fps)
            outputlocation, type_conversion_ok = proj.readEntry("TimeViewer", "Output")
            self.folderEdit.setText(outputlocation)
            self.layers=[]
            self.layerlist2=[]
            self.FrameIDs=[]
            #self.InitialFilters = []
            self.layerlist = ""
            for i in range(Nlayers):
                layer, type_conversion_ok = proj.readEntry("TimeViewer","LayersList" + str(i))
                initialfilter, type_conversion_ok = proj.readEntry("TimeViewer","InitialFilters" + str(i))
                self.layerlist2.append(layer)
                self.InitialFilters.append(initialfilter)


            for i in range(Nframeids):
                frameid, type_conversion_ok = proj.readEntry("TimeViewer", "FrameIDs" + str(i))
                self.FrameIDs.append(frameid)
            self.FrameIDs.sort()
            self.ffmpegaddress, type_conversion_ok = proj.readEntry("TimeViewer", "ffmpegaddress")


            for layername in self.layerlist2:
                layer = QgsProject.instance().mapLayersByName(layername)[0]
                self.layers.append(layer)
                self.InputLayerBox.setLayer(layer)
                #self.InitialFilters.append("")
                newlayername = layer.name() + "\n"
                self.layerlist = self.layerlist + newlayername
            self.LayerDisplayer.setText(self.layerlist)

            for n, layer in enumerate(self.layers):
                layer.setSubsetString('')
                field = self.FieldIDBox.currentText()
                self.value = self.FrameIDs[self.count]
                self.Displayer.setText("{a}={b}".format(a=field, b=self.value))
                if str(self.InitialFilters[n]) == "":
                    layer.setSubsetString("\"{a}\"=\'{b}\'".format(a=field, b=self.value))
                else:
                    layer.setSubsetString("\"{a}\"=\'{b}\' AND {c}".format(a=field, b=self.value, c=self.InitialFilters[n]))
                self.Displayer.setText("{a}={b}".format(a=field, b=self.value))

            self.ProcessButton.setEnabled(True)
            self.PlayButton.setEnabled(True)
            self.TimeSlider.setEnabled(True)
            self.PreviousButton.setEnabled(True)
            self.NextButton.setEnabled(True)
            self.folderEdit.setEnabled(True)
            self.browseButton.setEnabled(True)
            self.ExportVideoButton.setEnabled(True)

            self.TimeSlider.setMinimum(1)
            self.TimeSlider.setMaximum(len(self.FrameIDs))
            self.TimeSlider.setSingleStep(1)

            self.iface.messageBar().pushSuccess(
                'Time Viewer',
                'Session Restored Successfully  !'
            )
            return
        except:
            self.iface.messageBar().pushCritical(
                'Time Viewer',
                'Cannot Restore Preference  !'
            )
            return



    layerlist=""
    layers=[]
    def AddLayer(self):
        if type(self.InputLayerBox.currentLayer()) == type(None):
            self.iface.messageBar().pushCritical(
                'Time Viewer',
                'No Layer Selected !'
            )
            return
        else:
            layer = self.InputLayer()

        if layer in self.layers:
            self.iface.messageBar().pushCritical(
                'Time Viewer',
                'Layer Already Selected !'
            )
            return

        newlayername = layer.name() + "\n"
        self.layerlist = self.layerlist + newlayername
        self.LayerDisplayer.setText(self.layerlist)
        self.layers.append(layer)
        self.ProcessButton.setEnabled(True)
        self.PlayButton.setEnabled(False)
        self.PauseButton.setEnabled(False)
        self.StopButton.setEnabled(False)
        self.NextButton.setEnabled(False)
        self.TimeSlider.setEnabled(False)
        self.PreviousButton.setEnabled(False)
        self.folderEdit.setEnabled(False)
        self.browseButton.setEnabled(False)
        for n, layer in enumerate(self.layers):
            if len(self.InitialFilters)>0:
                if n <= (len(self.InitialFilters)-1):
                    layer.setSubsetString(self.InitialFilters[n])

        self.InitialFilters = []



    def RemoveLayer(self):
        if type(self.InputLayerBox.currentLayer()) == type(None):
            self.iface.messageBar().pushCritical(
                'Time Viewer',
                'No Layer Selected !'
            )
            return
        else:
            layer = self.InputLayer()

        if layer not in self.layers:
            self.iface.messageBar().pushCritical(
                'Time Viewer',
                'Layer Not Selected !'
            )
            return

        for n, l in enumerate(self.layers):
            if len(self.InitialFilters)>0:
                if n <= (len(self.InitialFilters) - 1):
                    l.setSubsetString(self.InitialFilters[n])

        newlayername = layer.name() + "\n"
        self.layerlist=self.layerlist.replace(newlayername,"")
        self.LayerDisplayer.setText(self.layerlist)
        self.layers.remove(layer)
        self.ProcessButton.setEnabled(True)
        self.PlayButton.setEnabled(False)
        self.PauseButton.setEnabled(False)
        self.StopButton.setEnabled(False)
        self.NextButton.setEnabled(False)
        self.TimeSlider.setEnabled(False)
        self.PreviousButton.setEnabled(False)
        self.folderEdit.setEnabled(False)
        self.browseButton.setEnabled(False)

        self.InitialFilters = []
        if self.layerlist=="":
            self.LayerDisplayer.setText("No Layer Selected")
            self.ProcessButton.setEnabled(False)



    def UpdateFrameID(self, layer):
        self.FieldIDBox.setLayer(self.InputLayer())
        self.PlayButton.setEnabled(False)
        self.NextButton.setEnabled(False)
        self.TimeSlider.setEnabled(False)
        self.PreviousButton.setEnabled(False)
        self.folderEdit.setEnabled(False)
        self.browseButton.setEnabled(False)


    def WriteProcessing(self):
        self.Displayer.setText("Processing...")
        self.StopPlay()
        self.count = 0
        if type(self.InputLayerBox.currentLayer()) != type(None) and len(self.FrameIDs)>0:
            for n, layer in enumerate(self.layers):
                layer.setSubsetString('')

        QTimer.singleShot(10, self.ReadFrameIDs)


    FrameIDs = []
    InitialFilters = []
    def ReadFrameIDs(self):
        self.FrameIDs = []
        for layer in self.layers:
            InitialFilter = layer.subsetString()
            self.InitialFilters.append(layer.subsetString())
            layer.setSubsetString(InitialFilter)
            field = self.FieldIDBox.currentText()
            idx = layer.fields().indexOf('{index}'.format(index=field))
            if idx==-1:
                self.Displayer.setText("Ready!")
                self.iface.messageBar().pushCritical(
                    'Time Viewer',
                    'Field Does Not Exist in {} '.format(layer.name())
                )
                return
            FrameIDvalues = layer.uniqueValues(idx)
            for i in FrameIDvalues:
                self.FrameIDs.append(i)
        self.FrameIDs = list(dict.fromkeys(self.FrameIDs))
        self.FrameIDs.sort()
        self.ProcessButton.setEnabled(True)
        self.PlayButton.setEnabled(True)
        self.TimeSlider.setEnabled(True)
        self.PreviousButton.setEnabled(True)
        self.NextButton.setEnabled(True)
        self.folderEdit.setEnabled(True)
        self.browseButton.setEnabled(True)
        self.ExportVideoButton.setEnabled(True)
        self.Displayer.setText("Ready!")
        self.TimeSlider.setMinimum(1)
        self.TimeSlider.setMaximum(len(self.FrameIDs))
        self.TimeSlider.setSingleStep(1)
        self.TimeSlider.setValue(1)


    def SliderUpdated(self):
        self.count = self.TimeSlider.value() - 1
        if self.Playing==True:
            return
        else:
            if type(self.InputLayerBox.currentLayer()) != type(None):
                for n, layer in enumerate(self.layers):
                    layer.setSubsetString('')
                    field = self.FieldIDBox.currentText()
                    self.value = self.FrameIDs[self.count]
                    self.Displayer.setText("{a}={b}".format(a=field, b=self.value))
                    if str(self.InitialFilters[n]) == "":
                        layer.setSubsetString("\"{a}\"=\'{b}\'".format(a=field, b=self.value))
                    else:
                        layer.setSubsetString("\"{a}\"=\'{b}\' AND {c}".format(a=field, b=self.value, c=self.InitialFilters[n]))

    def UpdateProcessButton(self):
        if len(self.layers)>0:
            self.ProcessButton.setEnabled(True)
        self.PlayButton.setEnabled(False)
        self.TimeSlider.setEnabled(False)
        self.NextButton.setEnabled(False)
        self.PreviousButton.setEnabled(False)
        self.Displayer.setText("Hello!")


    def InputLayer(self):
        return self.InputLayerBox.currentLayer()

    def PausePlay(self):
        self.PausePressed=True

    def Next(self):
        if self.count == len(self.FrameIDs) - 1:
            self.iface.messageBar().pushCritical(
                'Time Viewer',
                'Next Frame Not Available !'
            )
            return
        self.count = self.count + 1
        self.TimeSlider.setValue(self.count + 1)
        for n, layer in enumerate(self.layers):
            layer.setSubsetString(self.InitialFilters[n])
            field = self.FieldIDBox.currentText()
            self.value = self.FrameIDs[self.count]
            self.Displayer.setText("{a}={b}".format(a=field, b=self.value))
            if str(self.InitialFilters[n]) == "":
                layer.setSubsetString("\"{a}\"=\'{b}\'".format(a=field, b=self.value))
            else:
                layer.setSubsetString("\"{a}\"=\'{b}\' AND {c}".format(a=field, b=self.value, c=self.InitialFilters[n]))


    def Previous(self):
        if self.count == 0:
            self.iface.messageBar().pushCritical(
                'Time Viewer',
                'Previous Frame Not Available !'
            )
            return
        self.count = self.count - 1
        self.TimeSlider.setValue(self.count+1)
        for n, layer in enumerate(self.layers):
            layer.setSubsetString(self.InitialFilters[n])
            field = self.FieldIDBox.currentText()
            self.value = self.FrameIDs[self.count]
            self.Displayer.setText("{a}={b}".format(a=field, b=self.value))
            if str(self.InitialFilters[n]) == "":
                layer.setSubsetString("\"{a}\"=\'{b}\'".format(a=field, b=self.value))
            else:
                layer.setSubsetString("\"{a}\"=\'{b}\' AND {c}".format(a=field, b=self.value, c=self.InitialFilters[n]))

    def StopPlay(self):
        if self.Playing == True:
            self.TimeSlider.setValue(1)
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
    Playing = False
    value=0
    def play1(self):
        self.Playing=True
        self.TimeSlider.setValue(self.count+1)
        self.PlayButton.setEnabled(False)
        self.PauseButton.setEnabled(True)
        self.StopButton.setEnabled(True)
        self.PreviousButton.setEnabled(False)
        self.NextButton.setEnabled(False)
        self.AddButton.setEnabled(False)
        self.RemoveButton.setEnabled(False)
        self.ExportVideoButton.setEnabled(False)
        self.SavePreferenceButton.setEnabled(False)
        self.RestorePreferenceButton.setEnabled(False)
        for n, layer in enumerate(self.layers):
            if self.PausePressed==True:
                self.Playing = False
                self.PlayButton.setEnabled(True)
                self.PauseButton.setEnabled(False)
                self.StopButton.setEnabled(False)
                self.StopPressed = False
                self.PausePressed = False
                self.PreviousButton.setEnabled(True)
                self.NextButton.setEnabled(True)
                self.AddButton.setEnabled(True)
                self.RemoveButton.setEnabled(True)
                self.ExportVideoButton.setEnabled(True)
                self.SavePreferenceButton.setEnabled(True)
                self.RestorePreferenceButton.setEnabled(True)
                self.Displayer.setText("Paused!")
                return
            if self.StopPressed == True:
                self.Playing = False
                self.count=0
                self.PlayButton.setEnabled(True)
                self.PauseButton.setEnabled(False)
                self.StopButton.setEnabled(False)
                self.StopPressed = False
                self.PausePressed = False
                self.PreviousButton.setEnabled(True)
                self.NextButton.setEnabled(True)
                self.AddButton.setEnabled(True)
                self.RemoveButton.setEnabled(True)
                self.ExportVideoButton.setEnabled(True)
                self.SavePreferenceButton.setEnabled(True)
                self.RestorePreferenceButton.setEnabled(True)
                layer.setSubsetString(self.InitialFilters[n])
                self.Displayer.setText("Ready!")
                return
            field = self.FieldIDBox.currentText()
            self.value = self.FrameIDs[self.count]
            self.Displayer.setText("{a}={b}".format(a=field, b=self.value))
            if str(self.InitialFilters[n]) == "":
                layer.setSubsetString("\"{a}\"=\'{b}\'".format(a=field, b=self.value))
            else:
                layer.setSubsetString("\"{a}\"=\'{b}\' AND {c}".format(a=field, b=self.value, c=self.InitialFilters[n]))

        FPS = 1000 / self.FPSBox.value()
        canvas = iface.mapCanvas()
        canvas.waitWhileRendering()
        self.iface.mapCanvas().renderComplete.connect(self.renderLabel)
        QTimer.singleShot(FPS, self.play2)


    def play2(self):
        global count
        if self.ExportVideoState==True:
            self.iface.messageBar().pushInfo(
                'Time Viewer',
                'Exporting Video, Please Wait !'
            )
            iface.mapCanvas().saveAsImage(str(self.VideoTempFolder) + "/" + "TimeViewer" + str(self.count + 1) + ".png")
            os.remove(str(self.VideoTempFolder) + "/" + "TimeViewer" + str(self.count + 1) + ".pgw")
        if self.SaveFrameBox.isChecked():
            if self.SaveBox.currentText()=="PNG":
                if str(self.outFolder()) != "":
                    iface.mapCanvas().saveAsImage(str(self.outFolder()) + "/" + "TimeViewer"  + str(self.count+1) + ".png")
                    os.remove(str(self.outFolder()) + "/" + "TimeViewer"  + str(self.count+1) + ".pgw")
            if self.SaveBox.currentText()=="JPEG":
                if str(self.outFolder()) != "":
                    iface.mapCanvas().saveAsImage(str(self.outFolder()) + "/" + "TimeViewer" + str(self.count+1) + ".jpg")
                    os.remove(str(self.outFolder()) + "/" + "TimeViewer"  + str(self.count+1) + ".jgw")
        for n, layer in enumerate(self.layers):
            if self.PausePressed==True:
                self.Playing = False
                self.PlayButton.setEnabled(True)
                self.PauseButton.setEnabled(False)
                self.StopButton.setEnabled(False)
                self.StopPressed = False
                self.PausePressed = False
                self.PreviousButton.setEnabled(True)
                self.NextButton.setEnabled(True)
                self.AddButton.setEnabled(True)
                self.RemoveButton.setEnabled(True)
                self.ExportVideoButton.setEnabled(True)
                self.SavePreferenceButton.setEnabled(True)
                self.RestorePreferenceButton.setEnabled(True)
                self.Displayer.setText("Paused!")
                return
            if self.StopPressed == True:
                self.Playing = False
                self.count=0
                self.PlayButton.setEnabled(True)
                self.PauseButton.setEnabled(False)
                self.StopButton.setEnabled(False)
                self.StopPressed = False
                self.PausePressed = False
                self.PreviousButton.setEnabled(True)
                self.NextButton.setEnabled(True)
                self.AddButton.setEnabled(True)
                self.RemoveButton.setEnabled(True)
                self.ExportVideoButton.setEnabled(True)
                self.SavePreferenceButton.setEnabled(True)
                self.RestorePreferenceButton.setEnabled(True)
                layer.setSubsetString(self.InitialFilters[n])
                self.Displayer.setText("Ready!")
                return
            #layer.setSubsetString(self.InitialFilters[n])

        if self.count <= len(self.FrameIDs)-2:
            QTimer.singleShot(1, self.play1) # Wait a second (1000) and prepare next map
            self.count += 1
        else:
            if self.LoopBox.isChecked() and self.ExportVideoState==False:
                self.count=0
                self.play1()
                return
            if self.ExportVideoState==True:
                try:
                    if os.path.isfile(self.VideoTempFolder + "TimeViewerOutput.mp4"):
                        os.remove(self.VideoTempFolder + "TimeViewerOutput.mp4")
                    os.chdir(self.VideoTempFolder)
                    Executable = os.path.normpath(self.ffmpegaddress)
                    myCommand = "\""+ "\""+ Executable + "\"" + " -r 15 -f image2 -s 1920x1080" + " -i " + " TimeViewer%d.png"  +  " -vcodec libx264 -crf 25  -pix_fmt yuv420p -vf \"crop=trunc(iw/2)*2:trunc(ih/2)*2\"" + " TimeViewerOutput.mp4"+"\""
                    os.system(myCommand)
                    if os.path.isfile(str(self.outFolder()) + "/TimeViewerOutput.mp4"):
                        os.remove(str(self.outFolder()) + "/TimeViewerOutput.mp4")
                    os.rename(self.VideoTempFolder + "TimeViewerOutput.mp4" , str(self.outFolder()) + "/TimeViewerOutput.mp4")
                    files = glob.glob(self.VideoTempFolder+"*")
                    for f in files:
                        os.remove(f)
                    self.iface.messageBar().pushSuccess(
                        'Time Viewer',
                        'Video Export Successful !'
                    )
                except:
                    self.iface.messageBar().pushCritical(
                        'Time Viewer',
                        'Failed to Export Video !'
                    )

                self.ExportVideoState=False
                self.scrollArea.setEnabled(True)
                self.FPSBox.setValue(15)

            self.Playing = False
            self.PlayButton.setEnabled(True)
            self.PauseButton.setEnabled(False)
            self.StopButton.setEnabled(False)
            self.PreviousButton.setEnabled(True)
            self.NextButton.setEnabled(True)
            self.AddButton.setEnabled(True)
            self.RemoveButton.setEnabled(True)
            self.ExportVideoButton.setEnabled(True)
            self.SavePreferenceButton.setEnabled(True)
            self.RestorePreferenceButton.setEnabled(True)
            self.StopPressed = False
            self.PausePressed = False
            self.count=0
            self.TimeSlider.setValue(1)
            self.Displayer.setText("Ready!")
            for n, layer in enumerate(self.layers):
                layer.setSubsetString(self.InitialFilters[n])


    def renderLabel(self, painter):
        font = "Arial"
        size = 25
        color = 'black'
        bgcolor = 'white'
        flags = Qt.AlignRight | Qt.AlignBottom
        pixelRatio = painter.device().devicePixelRatio()
        width = painter.device().width() / pixelRatio
        height = painter.device().height() / pixelRatio
        labelString=str(self.value)

        painter.setRenderHint(painter.Antialiasing, True)
        txt = QTextDocument()
        html = """<span style="background-color:%s; padding: 5px; font-size: %spx;">
                       <font face="%s" color="%s">&nbsp;%s</font>
                     </span> """ \
               % (bgcolor, size, font,
                  color, labelString)
        txt.setHtml(html)
        layout = txt.documentLayout()
        size = layout.documentSize()

        if flags & Qt.AlignRight:
            x = width - 5 - size.width()
        elif flags & Qt.AlignLeft:
            x = 5
        else:
            x = width / 2 - size.width() / 2

        if flags & Qt.AlignBottom:
            y = height - 5 - size.height()
        elif flags & Qt.AlignTop:
            y = 5
        else:
            y = height / 2 - size.height() / 2

        painter.translate(x, y)
        layout.draw(painter, QAbstractTextDocumentLayout.PaintContext())
        painter.translate(-x, -y)

    def OpenVideoExportDialog(self):
        if str(self.outFolder()) == "":
            self.iface.messageBar().pushCritical(
                'Time Viewer',
                'No Output Location Set !'
            )
            return
        if self.ffmpegaddress == "":
            try:
                if os.path.isfile(os.path.dirname(os.path.realpath(__file__)) + "/ffmpegpath.ini"):
                    settingsfile = open(os.path.dirname(os.path.realpath(__file__)) + "/ffmpegpath.ini", 'r')
                    tempaddress = settingsfile.read()
                    if os.path.isfile(tempaddress):
                        self.ffmpegaddress=tempaddress
            except:
                pass
        if self.ffmpegaddress=="":
            new_filename, __ = QFileDialog.getOpenFileName(self.iface.mainWindow(), 'Please select ffmpeg.exe', "*ffmpeg.exe")
            if new_filename != '':
                self.ffmpegaddress=new_filename
                try:
                    settingsfile = os.path.dirname(os.path.realpath(__file__)) + "/ffmpegpath.ini"
                    with open(settingsfile, 'w') as file:
                        file.write(new_filename)
                except:
                    pass
            else:
                self.iface.messageBar().pushCritical(
                    'Time Viewer',
                    'Invalid Location for ffmpeg !'
                )
                return
        else:
            self.ExportVideo()


    ExportVideoState=False
    VideoTempFolder=""
    ffmpegaddress=""
    def ExportVideo(self):

        if self.ffmpegaddress=="":
            self.iface.messageBar().pushCritical(
                'Time Viewer',
                'Invalid Location for ffmpeg.exe !'
            )
            return
        self.VideoTempFolder = tempfile.gettempdir() + "\TimeViewerTemp/"
        if os.path.exists(self.VideoTempFolder):
            print("")
        else:
            os.mkdir(self.VideoTempFolder)
        self.count=0
        self.ExportVideoState=True
        self.FPSBox.setValue(60)
        self.Displayer.setText("Exporting Video... Please Wait")
        self.scrollArea.setEnabled(False)
        self.play1()



class TimeViewer(object):

    def __init__(self, iface):
        self.iface = iface
        self.dialog = None
        self.cancel = False
        self.act = QAction('Time Viewer', iface.mainWindow())
        self.act.triggered.connect(self.execDialog)

        s = QgsSettings()
        pluginstatus=s.value("TimeViewer", "default text")
        if pluginstatus=="open":
            QTimer.singleShot(6000, self.execDialog)
            #self.execDialog()


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
        #self.dialog.setModal(False)
        #self.act.setEnabled(False)
        iface.addDockWidget(Qt.BottomDockWidgetArea, self.dialog)
        self.dialog.ClosingSignal.connect(self.quitDialog)


    def scheduleAbort(self):
        self.cancel = True

    def quitDialog(self):

        s = QgsSettings()
        s.setValue("TimeViewer", "closed")

        #self.dialog = None
        self.act.setEnabled(True)
        self.cancel = False
        self.dialog.hide()


