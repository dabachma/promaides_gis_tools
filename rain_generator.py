from __future__ import unicode_literals
from __future__ import absolute_import

# system modules
import math
import os
import tempfile
import pandas as pd
from numpy import random
from random import sample
import matplotlib.pyplot as plt
from scipy import stats
import scipy.stats as ss
import csv

import numpy as np
import scipy.linalg

# QGIS modules
from qgis.core import *
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import *
from qgis.PyQt import uic
from PyQt5.QtCore import *

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

        self.RainGaugeLayer.layerChanged.connect(self.UpdateFields)
        self.AnalyzeAllDataBox.stateChanged.connect(self.UpdateUntilFromBoxes)
        self.SpatialInterpolationMethodBox.activated.connect(self.UpdateExponentFactorField)
        self.SaveSpatialInterpolationBox.stateChanged.connect(self.UpdateOutputLocation)
        self.SaveStormStatisticsBox.stateChanged.connect(self.UpdateOutputLocation)
        self.groupBox_7.toggled.connect(self.GriddedDataChecked)

        self.RainGaugeLayer.setLayer(None)
        self.GenerationAreaLayer.setLayer(None)

        self.SpatialInterpolationMethodBox.addItem("Inversed Distance Weighting")
        self.SpatialInterpolationMethodBox.addItem("Trend Surface Analysis (Polynomial 1st Order)")
        self.SpatialInterpolationMethodBox.addItem("Trend Surface Analysis (Polynomial 2nd Order)")
        # self.SpatialInterpolationMethodBox.setCurrentIndex(-1)

        self.DelimiterBox.addItem("space")
        self.DelimiterBox.addItem(",")
        self.DelimiterBox.addItem("-")
        self.DelimiterBox_2.addItem("space")
        self.DelimiterBox_2.addItem(",")
        self.DelimiterBox_2.addItem("-")
        self.InputDataUnitBox.addItem("minutely")
        self.InputDataUnitBox.addItem("10-minutely")
        self.InputDataUnitBox.addItem("30-minutely")
        self.InputDataUnitBox.addItem("hourly")
        self.InputDataUnitBox.addItem("daily")

        self.dxBox.setValue(5000)
        self.dyBox.setValue(5000)

        self.browseButton.clicked.connect(self.onBrowseButtonClicked)
        self.browseButton_dataanalysis.clicked.connect(self.onBrowseButtonClicked_dataanalysis)
        self.browseButton_griddeddata.clicked.connect(self.onBrowseButtonClicked_griddeddata)
        self.browseButton_coordinates.clicked.connect(self.onBrowseButtonClicked_coordinates)
        self.browseButton.setAutoDefault(False)
        self.browseButton_dataanalysis.setAutoDefault(False)

        self.FromBox.setEnabled(False)
        self.UntilBox.setEnabled(False)
        self.CheckButton2.setEnabled(False)
        self.label_30.setEnabled(False)
        self.label_31.setEnabled(False)
        self.folderEdit_dataanalysis.setEnabled(False)
        self.browseButton_dataanalysis.setEnabled(False)
        self.ProcessButton.setEnabled(False)
        self.CheckButton.setEnabled(False)

        self.ExponentFactorBox.setEnabled(False)
        self.label_32.setEnabled(False)

        self.groupBox_2.setEnabled(False)
        self.groupBox_3.setEnabled(False)
        self.groupBox_5.setEnabled(False)

    def UpdateFields(self, layer):
        self.DataAddressField.setLayer(self.RainGaugeLayer.currentLayer())
        self.FromBox.clear()
        self.UntilBox.clear()
        self.groupBox_2.setEnabled(False)
        self.groupBox_3.setEnabled(False)
        self.groupBox_5.setEnabled(False)
        self.ProcessButton.setEnabled(False)

    def UpdateOutputLocation(self):
        if self.SaveSpatialInterpolationBox.isChecked() or self.SaveStormStatisticsBox.isChecked():
            self.folderEdit_dataanalysis.setEnabled(True)
            self.browseButton_dataanalysis.setEnabled(True)
        else:
            self.folderEdit_dataanalysis.setEnabled(False)
            self.browseButton_dataanalysis.setEnabled(False)

    def UpdateExponentFactorField(self):
        if self.SpatialInterpolationMethodBox.currentText() == "Inversed Distance Weighting":
            self.ExponentFactorBox.setEnabled(True)
            self.label_32.setEnabled(True)
        else:
            self.ExponentFactorBox.setEnabled(False)
            self.label_32.setEnabled(False)

    def UpdateUntilFromBoxes(self):
        if self.AnalyzeAllDataBox.isChecked():
            self.FromBox.setEnabled(False)
            self.UntilBox.setEnabled(False)
            self.CheckButton2.setEnabled(False)
            self.label_30.setEnabled(False)
            self.label_31.setEnabled(False)
            self.groupBox_2.setEnabled(True)
        else:
            self.FromBox.setEnabled(True)
            self.UntilBox.setEnabled(True)
            self.CheckButton2.setEnabled(True)
            self.label_30.setEnabled(True)
            self.label_31.setEnabled(True)
            self.groupBox_2.setEnabled(False)
            self.groupBox_3.setEnabled(False)

    def GriddedDataChecked(self):
        if self.groupBox_7.isChecked():
            self.groupBox.setEnabled(False)
            self.groupBox_2.setEnabled(False)
            self.SaveSpatialInterpolationBox.setEnabled(False)
            self.TimeVieweLayerBox.setEnabled(False)
            self.groupBox_5.setEnabled(True)
            self.folderEdit_dataanalysis.setEnabled(True)
            self.browseButton_dataanalysis.setEnabled(True)
        else:
            self.groupBox.setEnabled(True)
            self.SaveSpatialInterpolationBox.setEnabled(True)
            self.TimeVieweLayerBox.setEnabled(True)
            self.folderEdit_dataanalysis.setEnabled(False)
            self.browseButton_dataanalysis.setEnabled(False)
            self.groupBox_5.setEnabled(False)

    def onBrowseButtonClicked(self):
        currentFolder = self.folderEdit.text()
        folder = QFileDialog.getExistingDirectory(self.iface.mainWindow(), 'Rain Generator', currentFolder)
        if folder != '':
            self.folderEdit.setText(folder)
            self.folderEdit.editingFinished.emit()

    def onBrowseButtonClicked_dataanalysis(self):
        currentFolder = self.folderEdit_dataanalysis.text()
        folder = QFileDialog.getExistingDirectory(self.iface.mainWindow(), 'Rain Generator', currentFolder)
        if folder != '':
            self.folderEdit_dataanalysis.setText(folder)
            self.folderEdit_dataanalysis.editingFinished.emit()

    def onBrowseButtonClicked_griddeddata(self):
        current_filename = self.folderEdit_griddeddata.text()
        file = QFileDialog.getOpenFileName(self.iface.mainWindow(), 'Rain Generator', current_filename)
        if file[0] != "":
            self.folderEdit_griddeddata.setText(file[0])
            self.folderEdit_griddeddata.editingFinished.emit()

    def onBrowseButtonClicked_coordinates(self):
        current_filename = self.folderEdit_coordinates.text()
        file = QFileDialog.getOpenFileName(self.iface.mainWindow(), 'Rain Generator', current_filename)
        if file[0] != "":
            self.folderEdit_coordinates.setText(file[0])
            self.folderEdit_coordinates.editingFinished.emit()


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

        self.dialog.ProcessAreaButton.clicked.connect(self.CreateGenerationArea)
        self.dialog.CheckButton.clicked.connect(self.CheckFiles)
        self.dialog.ProcessButton.clicked.connect(self.PreSpatialInterpolation)
        self.dialog.ProcessButton_GriddedData.clicked.connect(self.PreStormAnalysis_GriddedData)
        self.dialog.CheckButton2.clicked.connect(self.AnalyzeFromUntil)
        self.dialog.GenerateButton.clicked.connect(self.PreGeneration)

        self.dialog.UpdateButton.clicked.connect(self.PreCheckFiles)

    def scheduleAbort(self):
        self.cancel = True

    def quitDialog(self):
        self.StormTraveledDistance = []
        self.StormVolume = []
        self.StormDirection = []
        self.StormDuration = []
        self.StormPeakIntensity = []
        self.StormPeakIntensityTimestep = []
        self.StormPeakIntensityLocation = []
        self.StormSize = []
        self.NoStormDuration = []
        self.CellCoordinates = []
        self.StormLocations = []
        self.StormIDs = []
        self.Storms = []
        self.StormStartingLine = []
        self.StormData = []
        self.act.setEnabled(True)
        self.cancel = False

    ####################################################################################
    ####################################################################################
    ####################################################################################
    ####################################################################################
    ####################################################################################
    ####################################################################################
    ####################################################################################
    # checking files

    data = []
    ngauges = 0
    ntimes = 0
    nrains = 0

    ############################################################
    # updates the time and rain column values
    def PreCheckFiles(self):

        if type(self.dialog.RainGaugeLayer.currentLayer()) == type(None):
            self.dialog.iface.messageBar().pushCritical(
                'Rain Generator',
                'No Layer Selected !'
            )
            return

        files, ok = QgsVectorLayerUtils.getValues(self.dialog.RainGaugeLayer.currentLayer(),
                                                  self.dialog.DataAddressField.expression(), False)
        if not ok:
            return
        for i, locations in enumerate(files):
            address = locations.replace("\\", "/")

        self.dialog.TimeColumnBox.clear()
        self.dialog.RainColumnBox.clear()
        try:
            if self.dialog.DelimiterBox.currentText() == "space":
                df = pd.read_csv(address.strip("\u202a"), delimiter=" ")
            else:
                df = pd.read_csv(address.strip("\u202a"), delimiter=self.dialog.DelimiterBox.currentText())
            for c in df.columns:
                self.dialog.TimeColumnBox.addItem(c)
                self.dialog.RainColumnBox.addItem(c)
        except:
            return

        self.dialog.CheckButton.setEnabled(True)
        self.dialog.FromBox.clear()
        self.dialog.UntilBox.clear()
        self.dialog.groupBox_2.setEnabled(False)
        self.dialog.groupBox_3.setEnabled(False)
        self.dialog.groupBox_5.setEnabled(False)
        self.dialog.ProcessButton.setEnabled(False)
        self.data = []

    def CheckFiles(self):
        self.data = []
        files, ok = QgsVectorLayerUtils.getValues(self.dialog.RainGaugeLayer.currentLayer(),
                                                  self.dialog.DataAddressField.expression(), False)
        if not ok:
            self.iface.messageBar().pushCritical(
                'Rain Generator',
                'Invalid File Locations!'
            )
            return
        numberoftimes = 0
        numberofrains = 0
        for i, locations in enumerate(files):
            address = locations.replace("\\", "/")
            if not os.path.isfile(address.strip("\u202a")):
                self.iface.messageBar().pushCritical(
                    'Rain Generator',
                    'File Does Not Exist!'
                )
                return

            ###################################
            # f = open(address.strip("\u202a"), "r")
            # if self.dialog.HeaderBox.isChecked():
            #    lines = f.readlines()[1:]
            # else:
            #    lines = f.readlines()
            # times = []
            # rains = []
            # for x in lines:
            #    times.append(x.split(' ')[0])
            #    rains.append(x.split(' ')[1])
            # f.close()
            # if len(times) >= numberoftimes:
            #    numberoftimes = len(times)
            # if len(rains) >= numberofrains:
            #    numberofrains = len(rains)
            #######################################
            try:
                if self.dialog.DelimiterBox.currentText() == "space":
                    df = pd.read_csv(address.strip("\u202a"), delimiter=" ")
                else:
                    df = pd.read_csv(address.strip("\u202a"), delimiter=self.dialog.DelimiterBox.currentText())
                times = df[self.dialog.TimeColumnBox.currentText()].tolist()
                rains = df[self.dialog.RainColumnBox.currentText()].tolist()

                if len(times) >= numberoftimes:
                    numberoftimes = len(times)
                if len(rains) >= numberofrains:
                    numberofrains = len(rains)
            except:
                self.iface.messageBar().pushCritical(
                    'Rain Generator',
                    'Could not read Files!'
                )
                return

            #######################################

        # putting data in an array
        self.ngauges = len(files)
        self.ntimes = numberoftimes
        self.nrains = numberofrains

        for x in range(self.ngauges):
            self.data.append([])
            for y in range(2):
                self.data[x].append([])
                # for z in range(nrains):
                # data[x][y].append(0)

        for i, locations in enumerate(files):
            address = locations.replace("\\", "/")
            if self.dialog.DelimiterBox.currentText() == "space":
                df = pd.read_csv(address.strip("\u202a"), delimiter=" ")
            else:
                df = pd.read_csv(address.strip("\u202a"), delimiter=self.dialog.DelimiterBox.currentText())
            times = df[self.dialog.TimeColumnBox.currentText()].tolist()
            rains = df[self.dialog.RainColumnBox.currentText()].tolist()
            for j in range(len(times)):
                self.data[i][0].append(times[j])
                self.data[i][1].append(rains[j])
        # print(self.data)

        # filling the for and until boxes
        self.dialog.FromBox.clear()
        self.dialog.UntilBox.clear()
        lengths = []
        for j in range(len(self.data)):
            lengths.append(len(self.data[j][0]))
        for k in self.data[lengths.index(max(lengths))][0]:  # adds the time values for the shortest time series
            self.dialog.FromBox.addItem(str(k))
            self.dialog.UntilBox.addItem(str(k))
        # self.dialog.FromBox.currentIndex(0)
        # self.dialog.UntilBoxBox.currentIndex(min(lengths)-1)
        if self.dialog.AnalyzeAllDataBox.isChecked():
            self.dialog.groupBox_2.setEnabled(True)

        self.iface.messageBar().pushSuccess(
            'Rain Generator',
            'Files seem ok !'
        )

    ##################################################################################
    def AnalyzeFromUntil(self):
        # checks if the values in the from and until boxes are correct and puts them in self.data
        tempdata = []
        for x in range(len(self.data)):
            tempdata.append([])
            for y in range(2):
                tempdata[x].append([])

        fromindex = 0
        untilindex = 0

        for i in range(len(self.data)):
            if self.dialog.FromBox.currentText() not in str(
                    self.data[i][0]) or self.dialog.UntilBox.currentText() not in str(self.data[i][0]):
                self.iface.messageBar().pushCritical(
                    'Rain Generator',
                    'Entered Values Dont Exist in At least One of the Input Files  !'
                )
                return

            for j in range(len(self.data[i][0])):
                if str(self.data[i][0][j]) == self.dialog.FromBox.currentText():
                    fromindex = j

                if str(self.data[i][0][j]) == self.dialog.UntilBox.currentText():
                    untilindex = j

            if fromindex > untilindex:
                self.iface.messageBar().pushCritical(
                    'Rain Generator',
                    'The Values Entered Are Not Valid  !'
                )
                return

            for k in range(fromindex, untilindex + 1):
                tempdata[i][0].append(self.data[i][0][k])
                tempdata[i][1].append(self.data[i][1][k])

        self.data = tempdata
        self.dialog.groupBox_2.setEnabled(True)
        # print(self.data)

    ####################################################################################
    ####################################################################################
    ####################################################################################
    ####################################################################################
    ####################################################################################
    ####################################################################################
    ####################################################################################

    # spatial interpolation

    ##########################################################################
    # layer2 = spatial interpolation layer
    layer2 = QgsVectorLayer("Polygon", 'Generation_Area', 'memory')
    nx = 0
    ny = 0

    def CreateGenerationArea(self):
        if type(self.dialog.GenerationAreaLayer.currentLayer()) == type(None):
            self.dialog.iface.messageBar().pushCritical(
                'Rain Generator',
                'No Layer Selected !'
            )
            return

        self.layer2 = QgsVectorLayer("Polygon", 'Generation_Area', 'memory')
        layer = self.dialog.GenerationAreaLayer.currentLayer()
        ex = layer.extent()
        xmax = ex.xMaximum()
        ymax = ex.yMaximum()
        xmin = ex.xMinimum()
        ymin = ex.yMinimum()
        prov = self.layer2.dataProvider()

        fields = QgsFields()
        fields.append(QgsField('ID', QVariant.Int, '', 10, 0))
        fields.append(QgsField('XMIN', QVariant.Double, '', 24, 6))
        fields.append(QgsField('XMAX', QVariant.Double, '', 24, 6))
        fields.append(QgsField('YMIN', QVariant.Double, '', 24, 6))
        fields.append(QgsField('YMAX', QVariant.Double, '', 24, 6))
        prov.addAttributes(fields)
        self.layer2.updateExtents()
        self.layer2.updateFields()

        if self.dialog.dxBox.value() <= 0 or self.dialog.dyBox.value() <= 0:
            self.dialog.iface.messageBar().pushCritical(
                'Rain Generator',
                'Invalid Values for dx or dy !'
            )
            return
        else:
            hspacing = self.dialog.dxBox.value()
            vspacing = self.dialog.dyBox.value()

        self.nx = math.ceil((xmax - xmin) / hspacing)
        self.ny = math.ceil((ymax - ymin) / vspacing)

        id = 0
        y = ymax
        while y >= ymin:
            x = xmin
            while x <= xmax:
                point1 = QgsPointXY(x, y)
                point2 = QgsPointXY(x + hspacing, y)
                point3 = QgsPointXY(x + hspacing, y - vspacing)
                point4 = QgsPointXY(x, y - vspacing)
                vertices = [point1, point2, point3, point4]  # Vertices of the polygon for the current id
                inAttr = [id, x, x + hspacing, y - vspacing, y]
                feat = QgsFeature()
                feat.setGeometry(QgsGeometry().fromPolygonXY([vertices]))  # Set geometry for the current id
                feat.setAttributes(inAttr)  # Set attributes for the current id
                prov.addFeatures([feat])
                x = x + hspacing
                id += 1
            y = y - vspacing

        self.layer2.setCrs(
            QgsCoordinateReferenceSystem(self.iface.mapCanvas().mapSettings().destinationCrs().authid()))
        self.layer2.updateExtents()
        QgsProject.instance().addMapLayer(self.layer2)
        self.dialog.groupBox_5.setEnabled(True)
        self.dialog.ProcessButton.setEnabled(True)

    ####################################################################

    def PreSpatialInterpolation(self):
        self.dialog.StatusIndicator.setText("Performing Spatial Interpolation...")
        QTimer.singleShot(50, self.SpatialInterpolation)  # waits half a second for the message to be displayed

    #############################################################################################
    def SpatialInterpolation(self):
        foldername = self.dialog.folderEdit_dataanalysis.text()
        if self.dialog.SaveSpatialInterpolationBox.isChecked() or self.dialog.SaveStormStatisticsBox.isChecked():
            if not foldername:
                self.iface.messageBar().pushCritical(
                    'Rain Generator',
                    'No output folder given!'
                )
                return
        filepath = os.path.join(tempfile.gettempdir(), "RainfallSpatialInterpolation" + '.txt')

        try:  # deletes previous files
            if os.path.isfile(filepath):
                os.remove(filepath)
        except:
            pass

        try:
            file = open(filepath, 'w')
            file.close()
        except:
            pass

        with open(filepath, 'a') as SpatialInterpolation:
            raingaugelocations = []
            generationlocations = []

            # getting the locations of raingauges
            point_layer = self.dialog.RainGaugeLayer.currentLayer()
            features = point_layer.getFeatures()
            for feature in features:
                buff = feature.geometry()
                raingaugelocations.append(buff.asPoint())

            # getting the generation locations
            area_layer = self.layer2
            features = area_layer.getFeatures()
            for feature in features:
                buff = feature.geometry()
                generationlocations.append(buff.centroid().asPoint())

            # calculate generation duration
            rainlengths = []
            for j in range(len(self.data)):
                rainlengths.append(len(self.data[j][0]))

            ###############################################################
            # time viewer layer
            if self.dialog.TimeVieweLayerBox.isChecked():
                layer = self.layer2
                feats = [feat for feat in layer.getFeatures()]

                timeviewerlayer = QgsVectorLayer("Polygon", 'Time_Viewer_Layer', 'memory')

                timeviewerlayer_data = timeviewerlayer.dataProvider()
                attr = layer.dataProvider().fields().toList()
                timeviewerlayer_data.addAttributes(attr)
                timeviewerlayer.dataProvider().addAttributes(
                    [QgsField("Boundary Value", QVariant.Double), QgsField("date_time", QVariant.Double)])
                for i in range(min(rainlengths)):
                    timeviewerlayer_data.addFeatures(feats)

                fieldids = []
                fields = timeviewerlayer.dataProvider().fields()
                # deleting extra fields
                fieldstodelete = ["XMIN", "XMAX", "YMIN", "YMAX"]
                for field in fields:
                    if field.name() in fieldstodelete:
                        fieldids.append(fields.indexFromName(field.name()))

                timeviewerlayer.dataProvider().deleteAttributes(fieldids)
                timeviewerlayer.setCrs(
                    QgsCoordinateReferenceSystem(self.iface.mapCanvas().mapSettings().destinationCrs().authid()))
                timeviewerlayer.updateFields()
            ##################################################################
            #################################################################################################
            # Inversed Distance Weighting
            if self.dialog.SpatialInterpolationMethodBox.currentText() == "Inversed Distance Weighting":
                # writing the file
                for i in range(len(generationlocations)):
                    SpatialInterpolation.write('BEGIN\n')
                    SpatialInterpolation.write(
                        '%s %s             area #Length [m²/s], Area [m/s], waterlevel [m], point [m³/s]\n' % (
                            str(i), str(min(rainlengths))))
                    counter = 0
                    n = self.dialog.ExponentFactorBox.value()  # exponent factor for the invert distance weighting formula
                    while counter + 1 <= min(rainlengths):
                        upperformula = 0
                        lowerformula = 0
                        for j in range(len(self.data)):
                            distance = raingaugelocations[j].distance(generationlocations[i])
                            upperformula = upperformula + ((1 / (distance ** n)) * float(self.data[j][1][counter]))
                            lowerformula = lowerformula + (1 / (distance ** n))
                        rainvalue = round((upperformula / lowerformula), 3)
                        SpatialInterpolation.write(
                            '%s %s   #%s mm/h\n' % (str(counter), str(rainvalue), str(rainvalue)))
                        ###############################################
                        # time viewer layer
                        if self.dialog.TimeVieweLayerBox.isChecked():
                            fields = timeviewerlayer.dataProvider().fields()
                            datetimefieldid = fields.indexFromName("date_time")
                            rainvaluefieldid = fields.indexFromName("Boundary Value")
                            idfieldid = fields.indexFromName("ID")
                            featureids = []
                            for feature in timeviewerlayer.getFeatures():
                                if float(feature.attributes()[idfieldid]) == float(i):
                                    featureids.append(feature.id())
                            try:
                                atts = {
                                    datetimefieldid: float(self.data[rainlengths.index(min(rainlengths))][0][counter]),
                                    rainvaluefieldid: rainvalue}
                            except:
                                atts = {datetimefieldid: self.data[rainlengths.index(min(rainlengths))][0][counter],
                                        rainvaluefieldid: rainvalue}
                            timeviewerlayer.dataProvider().changeAttributeValues({featureids[counter]: atts})
                        ###############################################

                        if counter + 1 == min(rainlengths):
                            SpatialInterpolation.write('!END')
                            SpatialInterpolation.write('\n\n')
                        counter = counter + 1
            ######################################################################################################
            # Trend Surface Analysis (Polynomial 1st Order)
            elif self.dialog.SpatialInterpolationMethodBox.currentText() == "Trend Surface Analysis (Polynomial 1st Order)":

                allrainvalues = []
                for counter in range(min(rainlengths)):
                    xs = []
                    ys = []
                    zs = []
                    # putting all x and y and z values in seperate arrays
                    for r, i in enumerate(raingaugelocations):
                        xs.append(i.x())
                        ys.append(i.y())
                        zs.append(float(self.data[r][1][counter]))

                    data = np.c_[xs, ys, zs]

                    # grid covering the domain of the data
                    # getting the minimum and maximum x and ys of generation area
                    layer = self.dialog.GenerationAreaLayer.currentLayer()
                    ex = layer.extent()
                    xmax = ex.xMaximum()
                    ymax = ex.yMaximum()
                    xmin = ex.xMinimum()
                    ymin = ex.yMinimum()

                    X, Y = np.meshgrid(np.linspace(xmin, xmax, self.dialog.dxBox.value()),
                                       np.linspace(ymin, ymax, self.dialog.dyBox.value()))

                    order = 1  # 1: linear, 2: quadratic
                    if order == 1:
                        # best-fit linear plane
                        A = np.c_[data[:, 0], data[:, 1], np.ones(data.shape[0])]
                        C, _, _, _ = scipy.linalg.lstsq(A, data[:, 2])  # coefficients

                        # formula
                        # Z = C[0] * X + C[1] * Y + C[2]

                    rainvaluesintimestep = []
                    for i in generationlocations:
                        value = (C[0] * i.x()) + (C[1] * i.y()) + C[2]
                        rainvaluesintimestep.append(value)
                    allrainvalues.append(rainvaluesintimestep)

                # writing the file
                for i in range(len(generationlocations)):
                    SpatialInterpolation.write('BEGIN\n')
                    SpatialInterpolation.write(
                        '%s %s             area #Length [m²/s], Area [m/s], waterlevel [m], point [m³/s]\n' % (
                            str(i), str(min(rainlengths))))
                    counter = 0
                    while counter + 1 <= min(rainlengths):
                        rainvalue = float(allrainvalues[counter][i])
                        ###############################################
                        # time viewer layer
                        if self.dialog.TimeVieweLayerBox.isChecked():
                            fields = timeviewerlayer.dataProvider().fields()
                            datetimefieldid = fields.indexFromName("date_time")
                            rainvaluefieldid = fields.indexFromName("Boundary Value")
                            idfieldid = fields.indexFromName("ID")
                            featureids = []
                            for feature in timeviewerlayer.getFeatures():
                                if float(feature.attributes()[idfieldid]) == float(i):
                                    featureids.append(feature.id())
                            try:
                                atts = {
                                    datetimefieldid: float(self.data[rainlengths.index(min(rainlengths))][0][counter]),
                                    rainvaluefieldid: rainvalue}
                            except:
                                atts = {datetimefieldid: self.data[rainlengths.index(min(rainlengths))][0][counter],
                                        rainvaluefieldid: rainvalue}
                            timeviewerlayer.dataProvider().changeAttributeValues({featureids[counter]: atts})
                        ###############################################
                        SpatialInterpolation.write(
                            '%s %s   #%s mm/h\n' % (str(counter), str(rainvalue), str(rainvalue)))
                        if counter + 1 == min(rainlengths):
                            SpatialInterpolation.write('!END')
                            SpatialInterpolation.write('\n\n')
                        counter = counter + 1
            ######################################################################################
            elif self.dialog.SpatialInterpolationMethodBox.currentText() == "Trend Surface Analysis (Polynomial 2nd Order)":

                allrainvalues = []
                for counter in range(min(rainlengths)):
                    xs = []
                    ys = []
                    zs = []
                    # putting all x and y and z values in seperate arrays
                    for r, i in enumerate(raingaugelocations):
                        xs.append(i.x())
                        ys.append(i.y())
                        zs.append(float(self.data[r][1][counter]))

                    data = np.c_[xs, ys, zs]

                    # grid covering the domain of the data
                    # getting the minimum and maximum x and ys of generation area
                    layer = self.dialog.GenerationAreaLayer.currentLayer()
                    ex = layer.extent()
                    xmax = ex.xMaximum()
                    ymax = ex.yMaximum()
                    xmin = ex.xMinimum()
                    ymin = ex.yMinimum()

                    X, Y = np.meshgrid(np.linspace(xmin, xmax, self.dialog.dxBox.value()),
                                       np.linspace(ymin, ymax, self.dialog.dyBox.value()))

                    order = 2  # 2: quadratic
                    if order == 2:
                        # best-fit quadratic curve
                        A = np.c_[np.ones(data.shape[0]), data[:, :2], np.prod(data[:, :2], axis=1), data[:, :2] ** 2]
                        C, _, _, _ = scipy.linalg.lstsq(A, data[:, 2])

                        # formula
                        # Z = C[4]*X**2. + C[5]*Y**2. + C[3]*X*Y + C[1]*X + C[2]*Y + C[0]

                    rainvaluesintimestep = []
                    for i in generationlocations:
                        value = C[4] * i.x() ** 2. + C[5] * i.y() ** 2. + C[3] * i.x() * i.y() + C[1] * i.x() + C[
                            2] * i.y() + C[0]
                        rainvaluesintimestep.append(value)
                    allrainvalues.append(rainvaluesintimestep)

                # writing the file
                for i in range(len(generationlocations)):
                    SpatialInterpolation.write('BEGIN\n')
                    SpatialInterpolation.write(
                        '%s %s             area #Length [m²/s], Area [m/s], waterlevel [m], point [m³/s]\n' % (
                            str(i), str(min(rainlengths))))
                    counter = 0
                    while counter + 1 <= min(rainlengths):
                        rainvalue = float(allrainvalues[counter][i])
                        ###############################################
                        # time viewer layer
                        if self.dialog.TimeVieweLayerBox.isChecked():
                            fields = timeviewerlayer.dataProvider().fields()
                            datetimefieldid = fields.indexFromName("date_time")
                            rainvaluefieldid = fields.indexFromName("Boundary Value")
                            idfieldid = fields.indexFromName("ID")
                            featureids = []
                            for feature in timeviewerlayer.getFeatures():
                                if float(feature.attributes()[idfieldid]) == float(i):
                                    featureids.append(feature.id())
                            try:
                                atts = {
                                    datetimefieldid: float(self.data[rainlengths.index(min(rainlengths))][0][counter]),
                                    rainvaluefieldid: rainvalue}
                            except:
                                atts = {datetimefieldid: self.data[rainlengths.index(min(rainlengths))][0][counter],
                                        rainvaluefieldid: rainvalue}
                            timeviewerlayer.dataProvider().changeAttributeValues({featureids[counter]: atts})
                        ###############################################
                        SpatialInterpolation.write(
                            '%s %s   #%s mm/h\n' % (str(counter), str(rainvalue), str(rainvalue)))
                        if counter + 1 == min(rainlengths):
                            SpatialInterpolation.write('!END')
                            SpatialInterpolation.write('\n\n')
                        counter = counter + 1

        ##########################################################
        # time viewer layer
        if self.dialog.TimeVieweLayerBox.isChecked():
            timeviewerlayer.updateFields()
            QgsProject.instance().addMapLayer(timeviewerlayer)
        ##########################################################
        if self.dialog.SaveSpatialInterpolationBox.isChecked():
            self.dialog.StatusIndicator.setText("Writing Spatial Interpolation Output...")
            QTimer.singleShot(50, self.SpatialInterpolationforPromaides)

        self.dialog.StatusIndicator.setText("Analyzing Storm Statistics...")
        QTimer.singleShot(50, self.StormAnalysis)

    ################################################################################################
    def SpatialInterpolationforPromaides(self):
        filepath = os.path.join(self.dialog.folderEdit_dataanalysis.text(), "RainfallSpatialInterpolation" + '.txt')
        try:  # deletes previous files
            if os.path.isfile(filepath):
                os.remove(filepath)
        except:
            pass

        with open(filepath, 'a') as generateddata:
            generateddata.write('# comment\n')
            generateddata.write('# !BEGIN\n')
            generateddata.write('# number begining from 0 ++ number of points\n')
            generateddata.write('# hour [h] discharge [m³/s]\n')
            generateddata.write('# !END\n\n\n')

            raingaugelocations = []
            generationlocations = []

            # getting the locations of raingauges
            point_layer = self.dialog.RainGaugeLayer.currentLayer()
            features = point_layer.getFeatures()
            for feature in features:
                buff = feature.geometry()
                raingaugelocations.append(buff.asPoint())

            # getting the generation locations
            area_layer = self.layer2
            features = area_layer.getFeatures()
            for feature in features:
                buff = feature.geometry()
                generationlocations.append(buff.centroid().asPoint())

            # calculate generation duration
            rainlengths = []
            for j in range(len(self.data)):
                rainlengths.append(len(self.data[j][0]))

            #################################################################################################
            # Inversed Distance Weighting
            if self.dialog.SpatialInterpolationMethodBox.currentText() == "Inversed Distance Weighting":
                # writing the file
                for i in range(len(generationlocations)):
                    generateddata.write('!BEGIN   #%s\n' % "raingaugename")
                    generateddata.write(
                        '%s %s             area #Length [m²/s], Area [m/s], waterlevel [m], point [m³/s]\n' % (
                            str(i), str(min(rainlengths) * 2)))
                    counter = 0
                    n = self.dialog.ExponentFactorBox.value()  # exponent factor for the invert distance weighting formula
                    while counter + 1 <= min(rainlengths):
                        upperformula = 0
                        lowerformula = 0
                        for j in range(len(self.data)):
                            distance = raingaugelocations[j].distance(generationlocations[i])
                            upperformula = upperformula + ((1 / (distance ** n)) * float(self.data[j][1][counter]))
                            lowerformula = lowerformula + (1 / (distance ** n))
                        rainvalue = round((upperformula / lowerformula), 3)
                        generateddata.write(
                            '%s %s   #%s mm/h\n' % (str(counter), str(rainvalue / 3600000), str(rainvalue)))
                        generateddata.write(
                            '%s.99 %s   #%s mm/h\n' % (str(counter), str(rainvalue / 3600000), str(rainvalue)))
                        if counter + 1 == min(rainlengths):
                            generateddata.write('!END')
                            generateddata.write('\n\n')
                        counter = counter + 1
            ######################################################################################################
            # Trend Surface Analysis (Polynomial 1st Order)
            elif self.dialog.SpatialInterpolationMethodBox.currentText() == "Trend Surface Analysis (Polynomial 1st Order)":

                allrainvalues = []
                for counter in range(min(rainlengths)):
                    xs = []
                    ys = []
                    zs = []
                    # putting all x and y and z values in seperate arrays
                    for r, i in enumerate(raingaugelocations):
                        xs.append(i.x())
                        ys.append(i.y())
                        zs.append(float(self.data[r][1][counter]))

                    data = np.c_[xs, ys, zs]

                    # grid covering the domain of the data
                    # getting the minimum and maximum x and ys of generation area
                    layer = self.dialog.GenerationAreaLayer.currentLayer()
                    ex = layer.extent()
                    xmax = ex.xMaximum()
                    ymax = ex.yMaximum()
                    xmin = ex.xMinimum()
                    ymin = ex.yMinimum()

                    X, Y = np.meshgrid(np.linspace(xmin, xmax, self.dialog.dxBox.value()),
                                       np.linspace(ymin, ymax, self.dialog.dyBox.value()))

                    order = 1  # 1: linear, 2: quadratic
                    if order == 1:
                        # best-fit linear plane
                        A = np.c_[data[:, 0], data[:, 1], np.ones(data.shape[0])]
                        C, _, _, _ = scipy.linalg.lstsq(A, data[:, 2])  # coefficients

                        # formula
                        # Z = C[0] * X + C[1] * Y + C[2]

                    rainvaluesintimestep = []
                    for i in generationlocations:
                        value = (C[0] * i.x()) + (C[1] * i.y()) + C[2]
                        rainvaluesintimestep.append(value)
                    allrainvalues.append(rainvaluesintimestep)

                # writing the file
                for i in range(len(generationlocations)):
                    generateddata.write('!BEGIN   #%s\n' % "raingaugename")
                    generateddata.write(
                        '%s %s             area #Length [m²/s], Area [m/s], waterlevel [m], point [m³/s]\n' % (
                            str(i), str(min(rainlengths) * 2)))
                    counter = 0
                    while counter + 1 <= min(rainlengths):
                        rainvalue = float(allrainvalues[counter][i])
                        generateddata.write(
                            '%s %s   #%s mm/h\n' % (str(counter), str(rainvalue / 3600000), str(rainvalue)))
                        generateddata.write(
                            '%s.99 %s   #%s mm/h\n' % (str(counter), str(rainvalue / 3600000), str(rainvalue)))
                        if counter + 1 == min(rainlengths):
                            generateddata.write('!END')
                            generateddata.write('\n\n')
                        counter = counter + 1
            ######################################################################################
            elif self.dialog.SpatialInterpolationMethodBox.currentText() == "Trend Surface Analysis (Polynomial 2nd Order)":

                allrainvalues = []
                for counter in range(min(rainlengths)):
                    xs = []
                    ys = []
                    zs = []
                    # putting all x and y and z values in seperate arrays
                    for r, i in enumerate(raingaugelocations):
                        xs.append(i.x())
                        ys.append(i.y())
                        zs.append(float(self.data[r][1][counter]))

                    data = np.c_[xs, ys, zs]

                    # grid covering the domain of the data
                    # getting the minimum and maximum x and ys of generation area
                    layer = self.dialog.GenerationAreaLayer.currentLayer()
                    ex = layer.extent()
                    xmax = ex.xMaximum()
                    ymax = ex.yMaximum()
                    xmin = ex.xMinimum()
                    ymin = ex.yMinimum()

                    X, Y = np.meshgrid(np.linspace(xmin, xmax, self.dialog.dxBox.value()),
                                       np.linspace(ymin, ymax, self.dialog.dyBox.value()))

                    order = 2  # 2: quadratic
                    if order == 2:
                        # best-fit quadratic curve
                        A = np.c_[
                            np.ones(data.shape[0]), data[:, :2], np.prod(data[:, :2], axis=1), data[:, :2] ** 2]
                        C, _, _, _ = scipy.linalg.lstsq(A, data[:, 2])

                        # formula
                        # Z = C[4]*X**2. + C[5]*Y**2. + C[3]*X*Y + C[1]*X + C[2]*Y + C[0]

                    rainvaluesintimestep = []
                    for i in generationlocations:
                        value = C[4] * i.x() ** 2. + C[5] * i.y() ** 2. + C[3] * i.x() * i.y() + C[1] * i.x() + C[
                            2] * i.y() + C[0]
                        rainvaluesintimestep.append(value)
                    allrainvalues.append(rainvaluesintimestep)

                # writing the file
                for i in range(len(generationlocations)):
                    generateddata.write('!BEGIN   #%s\n' % "raingaugename")
                    generateddata.write(
                        '%s %s             area #Length [m²/s], Area [m/s], waterlevel [m], point [m³/s]\n' % (
                            str(i), str(min(rainlengths) * 2)))
                    counter = 0
                    while counter + 1 <= min(rainlengths):
                        rainvalue = float(allrainvalues[counter][i])
                        generateddata.write(
                            '%s %s   #%s mm/h\n' % (str(counter), str(rainvalue / 3600000), str(rainvalue)))
                        generateddata.write(
                            '%s.99 %s   #%s mm/h\n' % (str(counter), str(rainvalue / 3600000), str(rainvalue)))
                        if counter + 1 == min(rainlengths):
                            generateddata.write('!END')
                            generateddata.write('\n\n')
                        counter = counter + 1

    ###########################################################################################

    ####################################################################################
    ####################################################################################
    ####################################################################################
    ####################################################################################
    ####################################################################################
    ####################################################################################
    ####################################################################################

    # data analysis

    # shared arrays
    StormTraveledDistance = []
    StormVolume = []
    StormDirection = []
    StormDuration = []
    StormPeakIntensity = []
    StormPeakIntensityTimestep = []
    StormPeakIntensityLocation = []
    StormSize = []
    NoStormDuration = []
    CellCoordinates = []
    StormLocations = []
    StormIDs = []
    Storms = []
    StormStartingLine = []
    StormData = []  # array for the fitting only has volume peak extent in
    StormCount = 0
    MaxNumberofStorms = 500000
    StormStartingTimestep = []
    StormCenters=[]

    def PreStormAnalysis_GriddedData(self):
        filename = self.dialog.folderEdit_griddeddata.text()
        filename2 = self.dialog.folderEdit_coordinates.text()
        if not filename or not filename2:
            self.iface.messageBar().pushCritical(
                'Rain Generator',
                'No output folder given!'
            )
            return

        ###check cooridnate files

        self.dialog.StatusIndicator.setText("Analyzing Storm Statistics...")
        QTimer.singleShot(50, self.StormAnalysis_GriddedData)

    def StormAnalysis_GriddedData(self):

        # calculates angle between two points clockwise
        # east is 0
        # north is 90
        def angle_between(p1, p2):
            ang1 = np.arctan2(*p1[::-1])
            ang2 = np.arctan2(*p2[::-1])
            return np.rad2deg((ang1 - ang2) % (2 * np.pi))

        self.StormCount = 0
        nostormcount = 0

        self.nx = self.dialog.nxBox.value()
        self.ny = self.dialog.nyBox.value()

        # reset
        self.StormTraveledDistance = []
        self.StormVolume = []
        self.StormDirection = []
        self.StormDuration = []
        self.StormPeakIntensity = []
        self.StormSize = []
        self.NoStormDuration = []
        self.StormStartingLine = []
        self.StormData = []
        self.Storms = []
        self.StormStartingTimestep = []
        self.StormCenters = []

        for i in range(self.MaxNumberofStorms):
            self.StormTraveledDistance.append(0)
            self.StormVolume.append(0)
            self.StormDirection.append([])
            self.StormLocations.append([])
            self.StormDuration.append(0)
            self.StormPeakIntensity.append(0)
            self.StormPeakIntensityTimestep.append(0)
            self.StormPeakIntensityLocation.append(0)
            self.StormSize.append(0)
            self.StormStartingTimestep.append(0)
            self.StormData.append(0)
            self.Storms.append([])
            self.StormCenters.append([])

        Storm = []
        StormConnectivity = []
        PreviousStormConnectivity = []

        # reading coordinates
        address = os.path.join(self.dialog.folderEdit_coordinates.text())
        try:
            if self.dialog.DelimiterBox_2.currentText() == "space":
                df2 = pd.read_csv(address.strip("\u202a"), delimiter=" ", header=0)
            else:
                df2 = pd.read_csv(address.strip("\u202a"), delimiter=self.dialog.DelimiterBox_2.currentText(), header=0)

        except:
            self.iface.messageBar().pushCritical(
                'Rain Generator',
                'Could Not Read Given Data file...!'
            )

        for row in df2.iloc:
            self.CellCoordinates.append(row)
        for xy in self.CellCoordinates:
            try:
                xy = [float(i) for i in xy]
            except:
                self.iface.messageBar().pushCritical(
                    'Rain Generator',
                    'Could Not Read Given Data file...! Please Check the Selected Delimiter...'
                )
                return

        # reading data
        address = os.path.join(self.dialog.folderEdit_griddeddata.text())
        # try:
        if self.dialog.DelimiterBox_2.currentText() == "space":
            df = pd.read_csv(address.strip("\u202a"), delimiter=" ", header=0, index_col=0)
        else:
            df = pd.read_csv(address.strip("\u202a"), delimiter=self.dialog.DelimiterBox_2.currentText(), header=0,
                             index_col=0)


        # except:
        #    self.iface.messageBar().pushCritical(
        #        'Rain Generator',
        #        'Could Not Read Given Data file...!'
        #    )

        StormThreshhold = self.dialog.StormThreshholdBox.value()
        numberofcells = self.nx * self.ny

        # start of for loop
        TimestepCounter = 0  # for getting the starting time of storms in data file
        for row in df.iloc:
            for i, rain in enumerate(row):
                Storm.append(float(rain))
                if i + 1 == self.nx * self.ny:
                    break

            # print(Storm, "storm timstep")

            StormConnectivity = [0] * numberofcells
            ###################################################################################
            # storm cluster identification
            for i, value in enumerate(Storm):
                try:
                    if Storm[i - 1] > StormThreshhold and value > StormThreshhold and (i - 1) >= 0:
                        StormConnectivity[i] = StormConnectivity[i - 1]
                        continue
                except:
                    pass

                try:
                    if Storm[i - self.nx] > StormThreshhold and value > StormThreshhold and (i - self.nx) >= 0:
                        StormConnectivity[i] = StormConnectivity[i - self.nx]
                        continue
                except:
                    pass

                try:
                    if Storm[i - self.nx - 1] > StormThreshhold and value > StormThreshhold and (i - self.nx - 1) >= 0:
                        StormConnectivity[i] = StormConnectivity[i - self.nx - 1]
                        continue
                except:
                    pass

                if value > StormThreshhold:
                    self.StormCount = self.StormCount + 1
                    StormConnectivity[i] = self.StormCount
            ####################################################################################
            # find overlapping storms
            for i, value in enumerate(StormConnectivity):
                for j, previousvalue in enumerate(PreviousStormConnectivity):
                    if i == j and value > 0 and previousvalue > 0:
                        for k, value2 in enumerate(StormConnectivity):
                            if value2 == value:
                                StormConnectivity[k] = previousvalue
            ######################################################################################
            # getting storm statistics
            if all(i <= self.dialog.StormThreshholdBox.value() for i in Storm):
                nostormcount = nostormcount + 1
            else:
                self.NoStormDuration.append(nostormcount)
                nostormcount = 0

                # loops over uniqe storm ids
                for stormid in list(set(StormConnectivity)):
                    if stormid == 0:
                        continue
                    # saving the storm id
                    if stormid != 0 and (stormid not in self.StormIDs):
                        self.StormIDs.append(stormid)
                        self.StormStartingTimestep[stormid] = df.index[TimestepCounter]

                    # putting identified storms in an array
                    temparray = []
                    for count, ID in enumerate(StormConnectivity):
                        if ID == stormid and ID != 0:
                            temparray.append(Storm[count])
                        else:
                            temparray.append(0)
                    # print(temparray, "temparray")
                    self.Storms[stormid].append(temparray)

                    # saving storm locations
                    indexes = []
                    for index, element in enumerate(StormConnectivity):
                        if element == stormid:
                            indexes.append(index)
                    self.StormLocations[stormid].append(indexes)

                for value in list(set(StormConnectivity)):
                    if value != 0:
                        # velocity and direction
                        currentstormcoordinates = []
                        for i, id in enumerate(StormConnectivity):
                            if id == value and id != 0:
                                currentstormcoordinates.append(self.CellCoordinates[i])

                        ##################################################
                        #getting storm center x y
                        currentstormcenterx = 0
                        currentstormcentery = 0
                        for xy in currentstormcoordinates:
                            currentstormcenterx = currentstormcenterx + xy[0]
                            currentstormcentery = currentstormcentery + xy[1]
                        if len(currentstormcoordinates) !=0:
                            currentstormcenterx = currentstormcenterx / len(currentstormcoordinates)
                            currentstormcentery = currentstormcentery / len(currentstormcoordinates)
                            self.StormCenters[value].append([currentstormcenterx,currentstormcentery])
                        ########################################################

            PreviousStormConnectivity = StormConnectivity
            Storm = []
            StormConnectivity = []
            TimestepCounter = TimestepCounter + 1

        # print(self.Storms, "final storms")
        # peak, peak location and timestep, volume, duration, area
        for ID, storm in enumerate(self.Storms):
            if len(storm) == 0:
                continue
            stormvolume = 0
            stormpeak = 0
            stormpeaktimestep = 0
            stormpeaklocation = 0
            stormarea = 0
            for timestepnumber, timestep in enumerate(storm):
                stormvolume = stormvolume + sum(timestep)
                stormarea = stormarea + np.count_nonzero(timestep)
                if max(timestep) > stormpeak:
                    stormpeak = max(timestep)
                    stormpeaktimestep = timestepnumber
                    stormpeaklocation = timestep.index(stormpeak)

            self.StormPeakIntensity[ID] = stormpeak
            self.StormPeakIntensityTimestep[ID] = stormpeaktimestep
            self.StormPeakIntensityLocation[ID] = stormpeaklocation
            self.StormDuration[ID] = len(storm)
            self.StormSize[ID] = stormarea
            self.StormVolume[ID] = stormvolume
            self.StormTraveledDistance[ID] = math.sqrt((self.StormCenters[ID][len(self.StormCenters[ID])-1][0] - self.StormCenters[ID][0][0]) ** 2 + (self.StormCenters[ID][len(self.StormCenters[ID])-1][1] - self.StormCenters[ID][0][1]) ** 2)


            angle = angle_between([self.StormCenters[ID][0][0], self.StormCenters[ID][0][1]],
                                  [self.StormCenters[ID][len(self.StormCenters[ID])-1][0], self.StormCenters[ID][len(self.StormCenters[ID])-1][1]])

            if 0 < angle < 22.5 or 337.5 < angle < 360:
                direction = "E"
            elif 22.5 <= angle <= 67.5:
                direction = "NE"
            elif 67.5 <= angle <= 112.5:
                direction = "N"
            elif 112.5 <= angle <= 157.5:
                direction = "NW"
            elif 157.5 <= angle <= 202.5:
                direction = "W"
            elif 202.5 <= angle <= 247.5:
                direction = "SW"
            elif 247.5 <= angle <= 292.5:
                direction = "S"
            elif 292.5 <= angle <= 337.5:
                direction = "W"
            else:
                direction = "Not Available"
            self.StormDirection[ID].append(direction)



        # print(self.StormPeakIntensity[:self.StormCount+1],"peak")
        # print(self.StormSize[:self.StormCount+1],"size")
        # print(self.StormDuration[:self.StormCount+1],"duration")
        # print(self.StormTraveledDistance[:self.StormCount+1],"distance")
        # print(self.StormDirection[:self.StormCount + 1], "direction")
        # print(self.StormLocations, "locations")
        # print(self.StormIDs,"stormids")
        # print(self.StormPeakIntensityTimestep, "timestep")
        # print(self.StormPeakIntensityLocation, "location")
        # print(self.StormCount,"storm count")
        # print(self.StormStartingLine,"starting line")
        #print(self.StormCenters,"centers")

        if self.dialog.SaveStormStatisticsBox.isChecked():
            self.dialog.StatusIndicator.setText("Writing Storm Statistics to File...")
            QTimer.singleShot(50, self.WriteStormStatistics)

        N = 0
        for i in self.StormDuration:
            if i > 0:
                N = N + 1
        # print(N, "N")
        # print(len(self.StormIDs), "len")
        self.dialog.StatusIndicator.setText("Processing Complete, %s Storms Identified" % (N))
        self.iface.messageBar().pushSuccess(

            'Rain Generator',
            'Processing Complete !'
        )

        if N < 2:
            self.iface.messageBar().pushCritical(
                'Rain Generator',
                'Not Enough Storms Identified for Generation!'
            )
            return
        self.dialog.groupBox_3.setEnabled(True)
        self.data = []

    def StormAnalysis(self):

        # getting the center x y of each square cell
        for feature in self.layer2.getFeatures():
            self.CellCoordinates.append(feature.geometry().centroid().asPoint())

        print(self.nx, "nx")
        print(self.ny, "ny")

        # calculates angle between two points clockwise
        # east is 0
        # north is 90
        def angle_between(p1, p2):
            ang1 = np.arctan2(*p1[::-1])
            ang2 = np.arctan2(*p2[::-1])
            return np.rad2deg((ang1 - ang2) % (2 * np.pi))

        self.StormCount = 0
        nostormcount = 0

        # reset
        self.StormTraveledDistance = []
        self.StormVolume = []
        self.StormDirection = []
        self.StormDuration = []
        self.StormPeakIntensity = []
        self.StormSize = []
        self.NoStormDuration = []
        self.StormStartingLine = []
        self.StormData = []
        self.Storms = []

        for i in range(self.MaxNumberofStorms):
            self.StormTraveledDistance.append(0)
            self.StormVolume.append(0)
            self.StormDirection.append([])
            self.StormLocations.append([])
            self.StormDuration.append(0)
            self.StormPeakIntensity.append(0)
            self.StormPeakIntensityTimestep.append(0)
            self.StormPeakIntensityLocation.append(0)
            self.StormSize.append(0)
            self.StormStartingLine.append(0)
            self.StormData.append(0)
            self.StormStartingTimestep.append(0)
            self.Storms.append([])

        Storm = []
        StormConnectivity = []
        PreviousStormConnectivity = []

        # reading file
        filepath = os.path.join(tempfile.gettempdir(), "RainfallSpatialInterpolation" + '.txt')
        f = open(filepath)
        lines = f.readlines()
        StartingLine = 2
        for linecount in range(len(self.data[0][0])):
            for i in range(StartingLine, StartingLine + ((self.nx * self.ny - 1) * (len(self.data[0][0]) + 4)) + 1,
                           len(self.data[0][0]) + 3 + 1):
                Storm.append(lines[i].split(' ')[1])

            # place to put test arrays

            for i in range(len(Storm)):
                StormConnectivity.append(0)
            Storm = [float(i) for i in Storm]
            StartingLine = StartingLine + 1

            ###################################################################################
            # storm cluster identification
            StormThreshhold = self.dialog.StormThreshholdBox.value()
            for i, value in enumerate(Storm):
                try:
                    if Storm[i - 1] > StormThreshhold and value > StormThreshhold and (i - 1) >= 0:
                        StormConnectivity[i] = StormConnectivity[i - 1]
                        continue
                except:
                    pass

                try:
                    if Storm[i - self.nx] > StormThreshhold and value > StormThreshhold and (i - self.nx) >= 0:
                        StormConnectivity[i] = StormConnectivity[i - self.nx]
                        continue
                except:
                    pass

                try:
                    if Storm[i - self.nx - 1] > StormThreshhold and value > StormThreshhold and (i - self.nx - 1) >= 0:
                        StormConnectivity[i] = StormConnectivity[i - self.nx - 1]
                        continue
                except:
                    pass

                if value > StormThreshhold:
                    self.StormCount = self.StormCount + 1
                    StormConnectivity[i] = self.StormCount
            ####################################################################################
            # find overlapping storms
            for i, value in enumerate(StormConnectivity):
                for j, previousvalue in enumerate(PreviousStormConnectivity):
                    if i == j and value > 0 and previousvalue > 0:
                        for k, value2 in enumerate(StormConnectivity):
                            if value2 == value:
                                StormConnectivity[k] = previousvalue
            ######################################################################################
            # getting storm statistics

            if all(i <= self.dialog.StormThreshholdBox.value() for i in Storm):
                nostormcount = nostormcount + 1
            else:
                self.NoStormDuration.append(nostormcount)
                nostormcount = 0

                # saving the storm id
                for stormid in list(set(StormConnectivity)):
                    if stormid != 0 and (stormid not in self.StormIDs):
                        self.StormIDs.append(stormid)
                        self.StormStartingTimestep[stormid]=StartingLine - 1
                        # saving which line each storm starts
                        self.StormStartingLine[stormid] = StartingLine - 1

                # putting identified storms in an array
                for stormid in list(set(StormConnectivity)):
                    if stormid == 0:
                        continue
                    temparray = []
                    for count, ID in enumerate(StormConnectivity):
                        if ID == stormid and ID != 0:
                            temparray.append(Storm[count])
                        else:
                            temparray.append(0)

                    self.Storms[stormid].append(temparray)

                # saving storm locations
                for stormid in list(set(StormConnectivity)):
                    indexes = []
                    if stormid != 0:
                        for index, element in enumerate(StormConnectivity):
                            if element == stormid:
                                indexes.append(index)
                        self.StormLocations[stormid].append(indexes)

                # print(StormConnectivity, "storm connectivity2")
                for value in list(set(StormConnectivity)):
                    if value != 0:
                        # velocity and direction
                        currentstormcoordinates = []
                        for i, id in enumerate(StormConnectivity):
                            if id == value and id != 0:
                                currentstormcoordinates.append(self.CellCoordinates[i])

                        ##################################################
                        # getting storm center x y
                        currentstormcenterx = 0
                        currentstormcentery = 0
                        for xy in currentstormcoordinates:
                            currentstormcenterx = currentstormcenterx + xy[0]
                            currentstormcentery = currentstormcentery + xy[1]
                        if len(currentstormcoordinates) != 0:
                            currentstormcenterx = currentstormcenterx / len(currentstormcoordinates)
                            currentstormcentery = currentstormcentery / len(currentstormcoordinates)
                            self.StormCenters[value].append([currentstormcenterx, currentstormcentery])
                        ########################################################

            PreviousStormConnectivity = StormConnectivity
            Storm = []
            StormConnectivity = []

        # peak, peak location and timestep, volume, duration, area
        for ID, storm in enumerate(self.Storms):
            if len(storm) == 0:
                continue
            stormvolume = 0
            stormpeak = 0
            stormpeaktimestep = 0
            stormpeaklocation = 0
            stormarea = 0
            for timestepnumber, timestep in enumerate(storm):
                stormvolume = stormvolume + sum(timestep)
                stormarea = stormarea + np.count_nonzero(timestep)
                if max(timestep) > stormpeak:
                    stormpeak = max(timestep)
                    stormpeaktimestep = timestepnumber
                    stormpeaklocation = timestep.index(stormpeak)

            self.StormPeakIntensity[ID] = stormpeak
            self.StormPeakIntensityTimestep[ID] = stormpeaktimestep
            self.StormPeakIntensityLocation[ID] = stormpeaklocation
            self.StormDuration[ID] = len(storm)
            self.StormSize[ID] = stormarea
            self.StormVolume[ID] = stormvolume

        # print(self.StormPeakIntensity[:self.StormCount+1],"peak")
        # print(self.StormSize[:self.StormCount+1],"size")
        # print(self.StormDuration[:self.StormCount+1],"duration")
        # print(self.StormTraveledDistance[:self.StormCount+1],"distance")
        # print(self.StormDirection[:self.StormCount + 1], "direction")
        # print(self.StormLocations, "locations")
        # print(self.StormIDs,"stormids")
        # print(self.StormPeakIntensityTimestep, "timestep")
        # print(self.StormPeakIntensityLocation, "location")
        # print(self.StormCount,"storm count")
        # print(self.StormStartingLine,"starting line")

        if self.dialog.SaveStormStatisticsBox.isChecked():
            self.dialog.StatusIndicator.setText("Writing Storm Statistics to File...")
            QTimer.singleShot(50, self.WriteStormStatistics)

        N = 0
        for i in self.StormDuration:
            if i > 0:
                N = N + 1
        self.dialog.StatusIndicator.setText("Processing Complete, %s Storms Identified" % (N))
        self.iface.messageBar().pushSuccess(

            'Rain Generator',
            'Processing Complete !'
        )

        if N < 2:
            self.iface.messageBar().pushCritical(
                'Rain Generator',
                'Not Enough Storms Identified for Generation!'
            )
            return
        self.dialog.groupBox_3.setEnabled(True)
        self.data = []

    # function to write storm statistics to file
    def WriteStormStatistics(self):
        filepath = os.path.join(self.dialog.folderEdit_dataanalysis.text(), "StormStatistics" + '.txt')
        try:  # deletes previous files
            if os.path.isfile(filepath):
                os.remove(filepath)
        except:
            pass

        try:
            file = open(filepath, 'w')
            file.close()
        except:
            pass
        with open(filepath, 'a') as StormStatistics:
            StormStatistics.write(
                'Storm_id Storm_Starting_Timestep Storm_Duration Storm_Volume Storm_PeakIntensity Storm_TotalArea Storm_TraveledDistance StormMainDirection\n')
            for count, i in enumerate(range(1, self.StormCount + 1)):
                if self.StormDuration[i] == 0:
                    continue
                StormStatistics.write('%s %s %s %s %s %s %s %s\n' % (
                    count + 1, self.StormStartingTimestep[i], self.StormDuration[i], self.StormVolume[i], self.StormPeakIntensity[i],
                    (self.StormSize[i]),
                    (self.StormTraveledDistance[i]), (self.StormDirection[i])))

    #############################################################################################
    #############################################################################################
    # generation

    def PreGeneration(self):
        self.iface.messageBar().pushInfo(
            'Rain Generator',
            'Processing, Please Wait...'
        )
        self.dialog.StatusIndicator.setText("Processing, Please Wait...")

        QTimer.singleShot(50, self.Generation)

    StormStatisticsTexttobeWritten = "Storm_ID Storm_StartingTimestep Storm_Duration Storm_Volume Storm_PeakIntensity Storm_TotalArea\n"

    def Generation(self):

        # putting all storm volumes peaks and areas in one array for the copula
        # volume peak area
        for i in range(0, len(self.StormVolume)):
            self.StormData[i] = [self.StormVolume[i], self.StormPeakIntensity[i], self.StormSize[i]]

        StormDataWithoutZeros = []

        # removing the zero values
        for data in self.StormData:
            if data != [0, 0, 0]:
                StormDataWithoutZeros.append(data)
        # print(StormDataWithoutZeros, "storm data")

        cop = Copula(StormDataWithoutZeros)  # giving the data to the copula

        #################################################
        # check output address
        foldername = self.dialog.folderEdit.text()
        if not foldername:
            self.iface.messageBar().pushCritical(
                'Rain Generator',
                'No output folder given!'
            )
            return

        # csv file
        if self.dialog.CSVOutputBox.isChecked():
            filepath3 = os.path.join(self.dialog.folderEdit.text(), "GeneratedRainfall_CSV" + '.txt')
            try:  # deletes previous files
                if os.path.isfile(filepath3):
                    os.remove(filepath3)
            except:
                pass

            try:
                file = open(filepath3, 'w')
                file.close()
            except:
                pass

        #####################################################

        # csv file
        if self.dialog.CSVOutputBox.isChecked():
            TexttobeWritten = "Timestep/CellID "
            for i in range(self.nx * self.ny):
                TexttobeWritten += str(i) + " "
            with open(filepath3, 'a') as CSVGeneratedRainfall:
                CSVGeneratedRainfall.write(TexttobeWritten + "\n")

        #########################################################################################
        # self.NoStormDuration = [i for i in self.NoStormDuration if i != 0]   #removing the zeros
        # alpha for fitting no storm durations to gamma
        fit_alpha = (sum(self.NoStormDuration) / len(self.NoStormDuration)) ** 2 / np.var(self.NoStormDuration)

        ######################################################################################

        RequestedNumberofTimesteps = self.dialog.RequestedGenerationDurationBox.value()

        if self.dialog.InputDataUnitBox.currentText() == "minutely":
            RequestedNumberofTimesteps = RequestedNumberofTimesteps * 365 * 24 * 60
        elif self.dialog.InputDataUnitBox.currentText() == "10-minutely":
            RequestedNumberofTimesteps = RequestedNumberofTimesteps * 365 * 24 * 6
        elif self.dialog.InputDataUnitBox.currentText() == "30-minutely":
            RequestedNumberofTimesteps = RequestedNumberofTimesteps * 365 * 24 * 2
        elif self.dialog.InputDataUnitBox.currentText() == "hourly":
            RequestedNumberofTimesteps = RequestedNumberofTimesteps * 365 * 24
        elif self.dialog.InputDataUnitBox.currentText() == "daily":
            RequestedNumberofTimesteps = RequestedNumberofTimesteps * 365

        timestep = 0
        stormcounter = 0

        StormStatus = "storm"
        StormIDUniqueValues = []
        for i in self.StormIDs:
            StormIDUniqueValues.append(i)

        StormTexttobeWritten = ""
        with open(filepath3, 'a') as CSVGeneratedRainfall:
            while timestep <= RequestedNumberofTimesteps:
                # print(timestep, "timestep")
                # print(StormStatus, "storm status")

                ##########################################################################################
                # storm
                if StormStatus == "storm":
                    stormcounter = stormcounter + 1
                    ###############################################################
                    # generating storm values form copola

                    while (1 < 2):
                        GeneratedValues = cop.gendata(1)  # volume peak area
                        if GeneratedValues[0][1] <= GeneratedValues[0][0]:
                            break

                    print(GeneratedValues, "generated values")
                    ################################################################

                    #################################################################
                    # choose the storm to be written from the observed storms
                    GeneratedStormID = random.choice(StormIDUniqueValues)
                    StormIDUniqueValues.remove(GeneratedStormID)
                    if len(StormIDUniqueValues) == 0:
                        for i in self.StormIDs:
                            StormIDUniqueValues.append(i)
                    ##################################################################

                    #################################################################
                    # generated properties
                    GeneratedStormDuration = self.StormDuration[GeneratedStormID]  # duration
                    GeneratedStormPeakIntensity = GeneratedValues[0][1]  # peak
                    GeneratedVolume = GeneratedValues[0][0]  # volume
                    GeneratedStormArea = GeneratedValues[0][2]  # area
                    # print(GeneratedStormDuration, "generated duration")
                    # print(GeneratedStormArea, "generated storm area")
                    # print(self.StormSize[GeneratedStormID], "data")
                    DifferenceinAreaperTimestep = math.ceil(
                        abs((GeneratedStormArea - self.StormSize[GeneratedStormID]) / GeneratedStormDuration))

                    ###############################################################################

                    stormbeinggenerated = []
                    for i in range(GeneratedStormDuration):
                        stormbeinggenerated.append([])

                    ###################################################################
                    # writing storm statistics
                    if self.dialog.SaveStormStatisticsBox2.isChecked():
                        self.StormStatisticsTexttobeWritten += str(stormcounter) + " " + str(timestep) + " " + str(
                            GeneratedStormDuration) + " " + str(GeneratedVolume) + " " + str(
                            GeneratedStormPeakIntensity) + " " + str(GeneratedStormArea) + "\n"
                    ########################################################################

                    ##########################################################################
                    # loops over the timesteps of the storm for changing the area
                    for step in range(GeneratedStormDuration):
                        # getting the storm values in timestep from original storm

                        StorminTimestep = []
                        for i in range(self.nx * self.ny):
                            StorminTimestep.append(0)
                        for i, value in enumerate(self.Storms[GeneratedStormID][step]):
                            StorminTimestep[i] = float(value)

                        # area
                        if GeneratedStormArea > self.StormSize[GeneratedStormID]:
                            cellstobeadded = DifferenceinAreaperTimestep
                            #################
                            neighboringcellids = []
                            cellsadded = 0
                            cellsaddedtemp = 0
                            currentnumberofneighboringcells = len(neighboringcellids)
                            while cellsadded <= cellstobeadded:

                                if cellsaddedtemp == currentnumberofneighboringcells:  # when all neighboring cells are chosen it updates again
                                    # finding neighboring cells
                                    for index, cell in enumerate(StorminTimestep):
                                        try:  # right
                                            if cell == 0 and StorminTimestep[index - 1] != 0 and (index % self.nx) != 0:
                                                neighboringcellids.append(index)
                                                continue
                                        except:
                                            pass

                                        try:  # left
                                            if cell == 0 and StorminTimestep[index + 1] != 0 and (
                                                    (index + 1) % self.nx) != 0:
                                                neighboringcellids.append(index)
                                                continue

                                        except:
                                            pass

                                        try:  # top
                                            if cell == 0 and StorminTimestep[index + self.nx] != 0:
                                                neighboringcellids.append(index)
                                                continue
                                        except:
                                            pass

                                        try:  # bottom
                                            if cell == 0 and StorminTimestep[index - self.nx] != 0:
                                                neighboringcellids.append(index)
                                                continue
                                        except:
                                            pass
                                    currentnumberofneighboringcells = len(neighboringcellids)
                                    cellsaddedtemp = 0

                                if cellsadded + len(self.StormLocations[GeneratedStormID][step]) >= (self.nx * self.ny):
                                    # print("more cells to be added than domain")
                                    break

                                # print(neighboringcellids, "neighboring cell ids")
                                ChosenCellIndex = random.choice(neighboringcellids)
                                StorminTimestep[ChosenCellIndex] = self.dialog.StormThreshholdBox.value()
                                cellsadded = cellsadded + 1
                                cellsaddedtemp = cellsaddedtemp + 1
                                neighboringcellids.remove(ChosenCellIndex)

                        elif GeneratedStormArea < self.StormSize[GeneratedStormID]:
                            cellstobedeleted = DifferenceinAreaperTimestep
                            # print(cellstobedeleted, "cellstobedeleted")

                            cellsdeleted = 0
                            cellsdeletedtemp = 0
                            boundarycellids = []
                            currentnumberofboundarycells = len(boundarycellids)

                            while cellsdeleted <= cellstobedeleted:
                                if cellsdeleted >= (len(self.StormLocations[GeneratedStormID][step])):
                                    # print("more cells to be deleted than domain")
                                    break
                                if cellsdeletedtemp == currentnumberofboundarycells:
                                    # finding boundary cells
                                    for index, cell in enumerate(StorminTimestep):
                                        try:  # right
                                            if cell != 0 and StorminTimestep[index - 1] == 0:
                                                boundarycellids.append(index)
                                                continue
                                        except:
                                            pass

                                        try:  # left
                                            if cell != 0 and StorminTimestep[index + 1] == 0:
                                                boundarycellids.append(index)
                                                continue

                                        except:
                                            pass

                                        try:  # top
                                            if cell != 0 and StorminTimestep[index + self.nx] == 0:
                                                boundarycellids.append(index)
                                                continue
                                        except:
                                            pass

                                        try:  # bottom
                                            if cell != 0 and StorminTimestep[index - self.nx] == 0:
                                                boundarycellids.append(index)
                                                continue
                                        except:
                                            pass

                                    if len(self.StormLocations[GeneratedStormID][step]) == self.nx * self.ny and len(
                                            boundarycellids) == 0:
                                        for n in range(self.nx):
                                            boundarycellids.append(n)
                                        for n in range(self.nx * (self.ny - 1), self.nx * self.ny):
                                            boundarycellids.append(n)
                                        for n in range(0, self.nx * (self.ny - 1), self.nx):
                                            boundarycellids.append(n)
                                        for n in range(self.nx - 1, (self.nx * self.ny) - 1, self.nx):
                                            boundarycellids.append(n)

                                    currentnumberofboundarycells = len(boundarycellids)
                                    cellsdeletedtemp = 0

                                ChosenCellIndex = random.choice(boundarycellids)
                                StorminTimestep[ChosenCellIndex] = 0
                                cellsdeleted = cellsdeleted + 1
                                cellsdeletedtemp = cellsdeletedtemp + 1
                                boundarycellids.remove(ChosenCellIndex)

                        stormbeinggenerated[step] = StorminTimestep
                    #######################################################################################

                    SumIntensitiesdata = 0

                    for raintimestep in stormbeinggenerated:
                        SumIntensitiesdata = SumIntensitiesdata + sum(raintimestep)
                    SumIntensitiesdata = SumIntensitiesdata - self.StormPeakIntensity[GeneratedStormID]
                    NewVolume = GeneratedVolume - GeneratedStormPeakIntensity

                    # loops over storm timesteps for changing volume and peak
                    for step, stormtimestep in enumerate(stormbeinggenerated):
                        if SumIntensitiesdata != 0:
                            ###volume
                            for j, rain in enumerate(stormtimestep):
                                stormtimestep[j] = (stormtimestep[j] / SumIntensitiesdata) * NewVolume
                        # peak intensity
                        if step == self.StormPeakIntensityTimestep[GeneratedStormID]:
                            stormtimestep[
                                self.StormPeakIntensityLocation[GeneratedStormID]] = GeneratedStormPeakIntensity

                        # write file
                        StormTexttobeWritten += str(timestep) + " "
                        for i in stormtimestep:
                            StormTexttobeWritten += str(abs(i)) + " "
                        StormTexttobeWritten += "\n"

                        timestep = timestep + 1

                        if timestep >= RequestedNumberofTimesteps:
                            # write storm
                            CSVGeneratedRainfall.write(StormTexttobeWritten)
                            StormTexttobeWritten = ""

                            # storm statistics
                            if self.dialog.SaveStormStatisticsBox2.isChecked():
                                self.dialog.StatusIndicator.setText("Writing Storm Statistics...")
                                QTimer.singleShot(50, self.WriteStormStatistics2)
                            QTimer.singleShot(50, self.GenerationFinished)
                            break

                        if timestep % 500000 == 0 and timestep > 0:
                            CSVGeneratedRainfall.write(StormTexttobeWritten)
                            StormTexttobeWritten = ""

                    if timestep >= RequestedNumberofTimesteps:
                        break

                    StormStatus = "nostorm"
                elif StormStatus == "nostorm":
                    GeneratedNoStormDuration = (np.random.gamma(fit_alpha, scale=np.var(self.NoStormDuration) / (
                            sum(self.NoStormDuration) / len(self.NoStormDuration))))
                    GeneratedNoStormDuration = math.ceil(GeneratedNoStormDuration)
                    if GeneratedNoStormDuration < 0:
                        GeneratedNoStormDuration = 0
                    # print(GeneratedNoStormDuration, "generatednostormduration")
                    timestep = timestep + GeneratedNoStormDuration
                    StormStatus = "storm"
                    if timestep >= RequestedNumberofTimesteps:
                        # write storm
                        CSVGeneratedRainfall.write(StormTexttobeWritten)
                        StormTexttobeWritten = ""

                        # storm statistics
                        if self.dialog.SaveStormStatisticsBox2.isChecked():
                            self.dialog.StatusIndicator.setText("Writing Storm Statistics...")
                            QTimer.singleShot(50, self.WriteStormStatistics2)
                        QTimer.singleShot(50, self.GenerationFinished)
                        break
                # print("end of whole while loop")

    def WriteStormStatistics2(self):
        filepath2 = os.path.join(self.dialog.folderEdit.text(),
                                 "GeneratedRainfall_Statistics" + '.txt')
        try:  # deletes previous files
            if os.path.isfile(filepath2):
                os.remove(filepath2)
        except:
            pass

        try:
            file = open(filepath2, 'w')
            file.close()
        except:
            pass

        with open(filepath2, 'a') as GeneratedRainfallStatistics:
            GeneratedRainfallStatistics.write(self.StormStatisticsTexttobeWritten)
        QTimer.singleShot(50, self.ReturnPeriodCalculation)

    def ReturnPeriodCalculation(self):
        filepath2 = os.path.join(self.dialog.folderEdit.text(), "GeneratedRainfall_Statistics" + '.txt')
        df = pd.read_csv(filepath2.strip("\u202a"), delimiter=" ")
        Durations = df["Storm_Duration"].tolist()
        Volumes = df["Storm_Volume"].tolist()
        peaks = df["Storm_PeakIntensity"].tolist()
        areas = df["Storm_TotalArea"].tolist()
        n = self.dialog.RequestedGenerationDurationBox.value()
        Durations_ranks = [len(Durations) - (sorted(Durations).index(x)) for x in Durations]
        Volumes_ranks = [len(Volumes) - (sorted(Volumes).index(x)) for x in Volumes]
        peaks_ranks = [len(peaks) - (sorted(peaks).index(x)) for x in peaks]
        areas_ranks = [len(areas) - (sorted(areas).index(x)) for x in areas]
        Durations_returnperiods = []
        Volumes_returnperiods = []
        peaks_returnperiods = []
        areas_returnperiods = []
        for i in range(len(Durations_ranks)):
            Durations_returnperiods.append((n + 1) / Durations_ranks[i])
            Volumes_returnperiods.append((n + 1) / Volumes_ranks[i])
            peaks_returnperiods.append((n + 1) / peaks_ranks[i])
            areas_returnperiods.append((n + 1) / areas_ranks[i])

        df['Return_Period_Duration'] = Durations_returnperiods
        df['Return_Period_Volume'] = Volumes_returnperiods
        df['Return_Period_Peak'] = peaks_returnperiods
        df['Return_Period_Area'] = areas_returnperiods

        df.to_csv(filepath2.strip("\u202a"), sep=' ', index=False)

    def GenerationFinished(self):
        self.iface.messageBar().pushSuccess(
            'Rain Generator',
            'Generation Successfull !'
        )
        self.dialog.StatusIndicator.setText("Generation Complete")

    def execTool(self):
        print("hello")


#############################################################################################
#############################################################################################
#############################################################################################
#############################################################################################
#############################################################################################
#############################################################################################
# copula class
# https://github.com/ashiq24/Copula
# multivariate Gaussian copulas

class Copula():
    def __init__(self, data):
        self.data = np.array(data)
        if (len(data) < 2):
            raise Exception('input data must have multiple samples')
        if not isinstance(data[0], list):
            raise Exception('input data must be a 2D array')
        self.cov = np.cov(self.data.T)
        if 0 in self.cov:
            raise Exception('Data not suitable for Copula. Covarience of two column is 0')
        self.normal = stats.multivariate_normal([0 for i in range(len(data[0]))], self.cov, allow_singular=True)
        self.norm = stats.norm()
        self.var = []
        self.cdfs = []

    def gendata(self, num):
        self.var = random.multivariate_normal([0 for i in range(len(self.cov[0]))], self.cov, num)

        for i in self.var:
            for j in range(len(i)):
                i[j] = i[j] / math.sqrt(self.cov[j][j])
        self.cdfs = self.norm.cdf(self.var)
        data = [[np.percentile(self.data[:, j], 100 * i[j]) for j in range(len(i))] for i in self.cdfs]
        return data
