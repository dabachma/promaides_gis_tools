from __future__ import unicode_literals
from __future__ import absolute_import

# system modules
import math
import os
import tempfile

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

        self.RainGaugeLayer.setLayer(None)
        self.GenerationAreaLayer.setLayer(None)

        self.SpatialInterpolationMethodBox.addItem("Inversed Distance Weighting")
        self.SpatialInterpolationMethodBox.addItem("Trend Surface Analysis (Polynomial 1st Order)")
        self.SpatialInterpolationMethodBox.addItem("Trend Surface Analysis (Polynomial 2nd Order)")
        #self.SpatialInterpolationMethodBox.setCurrentIndex(-1)

        self.dxBox.setValue(5000)
        self.dyBox.setValue(5000)

        self.browseButton.clicked.connect(self.onBrowseButtonClicked)
        self.browseButton_dataanalysis.clicked.connect(self.onBrowseButtonClicked_dataanalysis)
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
        if self.SpatialInterpolationMethodBox.currentText()=="Inversed Distance Weighting":
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
        self.dialog.CheckButton2.clicked.connect(self.AnalyzeFromUntil)


    def scheduleAbort(self):
        self.cancel = True

    def quitDialog(self):
        self.dialog = None
        self.act.setEnabled(True)
        self.cancel = False

####################################################################################
####################################################################################
####################################################################################
####################################################################################
####################################################################################
####################################################################################
####################################################################################
    #checking files

    data = []
    ngauges = 0
    ntimes = 0
    nrains = 0
############################################################
    def CheckFiles(self):
        self.data=[]
        files, ok = QgsVectorLayerUtils.getValues(self.dialog.RainGaugeLayer.currentLayer(), self.dialog.DataAddressField.expression(), False)
        if not ok:
            self.iface.messageBar().pushCritical(
                'Rain Generator',
                'Invalid File Locations!'
            )
            return
        numberoftimes = 0
        numberofrains = 0
        for i, locations in enumerate(files):
            address=locations.replace("\\","/")
            if not os.path.isfile(address.strip("\u202a")):
                self.iface.messageBar().pushCritical(
                    'Rain Generator',
                    'File Does Not Exist!'
                )
                return

            ###################################
            f = open(address.strip("\u202a"), "r")
            if self.dialog.HeaderBox.isChecked():
                lines = f.readlines()[1:]
            else:
                lines = f.readlines()
            times = []
            rains = []
            for x in lines:
                times.append(x.split(' ')[0])
                rains.append(x.split(' ')[1])
            f.close()
            if len(times) >= numberoftimes:
                numberoftimes = len(times)
            if len(rains) >= numberofrains:
                numberofrains = len(rains)
            #######################################
            #df = pandas.read_csv(address.strip("\u202a"),delimiter=',')
            #times=df["Time"].tolist()
            #rains=df["Value"]
            #for c in df.columns:
            #    print(c)

            #######################################

        #puttin data in an array
        self.ngauges = len(files)
        self.ntimes = numberoftimes
        self.nrains = numberofrains


        for x in range(self.ngauges):
            self.data.append([])
            for y in range(2):
                self.data[x].append([])
                #for z in range(nrains):
                    #data[x][y].append(0)

        for i, locations in enumerate(files):
            address = locations.replace("\\", "/")
            f = open(address.strip("\u202a"), "r")
            if self.dialog.HeaderBox.isChecked():
                lines = f.readlines()[1:]
            else:
                lines = f.readlines()
            for x in lines:
                x=x.replace('\n','')
                self.data[i][0].append((x.split(' ')[0]).strip("\\n"))
                self.data[i][1].append((x.split(' ')[1]).strip("\\n"))
            f.close()
        print(self.data)

        #filling the for and until boxes
        lengths=[]
        for j in range(len(self.data)):
            lengths.append(len(self.data[j][0]))
        for k in self.data[lengths.index(max(lengths))][0]: #adds the time values for the shortest time series
            self.dialog.FromBox.addItem(k)
            self.dialog.UntilBox.addItem(k)
        #self.dialog.FromBox.currentIndex(0)
        #self.dialog.UntilBoxBox.currentIndex(min(lengths)-1)
        if self.dialog.AnalyzeAllDataBox.isChecked():
            self.dialog.groupBox_2.setEnabled(True)

        self.iface.messageBar().pushSuccess(
            'Rain Generator',
            'Files seem ok !'
        )


##################################################################################
    def AnalyzeFromUntil(self):
        #checks if the values in the from and until boxes are correct and puts them in self.data
        tempdata=[]
        for x in range(len(self.data)):
            tempdata.append([])
            for y in range(2):
                tempdata[x].append([])

        for i in range(len(self.data)):
            if self.dialog.FromBox.currentText() not in self.data[i][0] or self.dialog.UntilBox.currentText() not in self.data[i][0]:
                self.iface.messageBar().pushCritical(
                    'Rain Generator',
                    'Entered Values Dont Exist in Atleast One of the Input Files  !'
                )
                return

            fromindex=self.data[i][0].index(self.dialog.FromBox.currentText())
            untilindex = self.data[i][0].index(self.dialog.UntilBox.currentText())

            if fromindex >= untilindex:
                self.iface.messageBar().pushCritical(
                    'Rain Generator',
                    'The Values Entered Are Not Valid  !'
                )
                return

        for i in range(len(self.data)):
            for j in range(self.data[i][0].index(self.dialog.FromBox.currentText()),self.data[i][0].index(self.dialog.UntilBox.currentText())+1):
                tempdata[i][0].append(self.data[i][0][j])
                tempdata[i][1].append(self.data[i][1][j])

        self.data=tempdata
        self.dialog.groupBox_2.setEnabled(True)



####################################################################################
####################################################################################
####################################################################################
####################################################################################
####################################################################################
####################################################################################
####################################################################################

    #spatial interpolation

##########################################################################
    # layer2 = spatial interpolation layer
    layer2 = QgsVectorLayer("Polygon", 'Generation_Area', 'memory')
    nx=0
    ny=0

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

        self.nx = math.ceil((xmax-xmin)/hspacing)
        self.ny = math.ceil((ymax-ymin)/vspacing)

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
        self.dialog.groupBox_3.setEnabled(True)
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
            file=open(filepath, 'w')
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
            if self.dialog.TImeVieweLayerBox.isChecked():
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
                        if self.dialog.TImeVieweLayerBox.isChecked():
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
                        if self.dialog.TImeVieweLayerBox.isChecked():
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
                        if self.dialog.TImeVieweLayerBox.isChecked():
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
        if self.dialog.TImeVieweLayerBox.isChecked():
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

    #data analysis

    #shared arrays
    StormTraveledDistance=[]
    StormVolume=[]
    StormDirection=[]
    StormDuration=[]
    StormPeakIntensity=[]
    StormSize=[]
    NoStormDuration=[]
    CellCoordinates=[]
    StormCount=0


    def StormAnalysis(self):

        #getting the center x y of each square cell
        for feature in self.layer2.getFeatures():
            self.CellCoordinates.append(feature.geometry().centroid().asPoint())

        print(self.nx,"nx")
        print(self.ny,"ny")

        #calculates angle between two points clockwise
        #east is 0
        #north is 90
        def angle_between(p1, p2):
            ang1 = np.arctan2(*p1[::-1])
            ang2 = np.arctan2(*p2[::-1])
            return np.rad2deg((ang1 - ang2) % (2 * np.pi))

        self.StormCount=0
        nostormcount=0

        #reset
        self.StormTraveledDistance = []
        self.StormVolume = []
        self.StormDirection = []
        self.StormDuration = []
        self.StormPeakIntensity = []
        self.StormSize = []
        self.NoStormDuration = []

        for i in range(100000):
            self.StormTraveledDistance.append(0)
            self.StormVolume.append(0)
            self.StormDirection.append(0)
            self.StormDuration.append(0)
            self.StormPeakIntensity.append(0)
            self.StormSize.append(0)

        Storm=[]
        StormConnectivity=[]
        PreviousStormConnectivity=[]

        #reading file
        filepath = os.path.join(tempfile.gettempdir(), "RainfallSpatialInterpolation" + '.txt')
        f = open(filepath)
        lines = f.readlines()
        StartingLine = 2
        for linecount in range(len(self.data[0][0])):
            print(StartingLine,"startingline")
            for i in range(StartingLine,StartingLine+((self.nx*self.ny-1)*(len(self.data[0][0])+4))+1,len(self.data[0][0])+3+1):
                Storm.append(lines[i].split(' ')[1])

            #place to put test arrays

            for i in range(len(Storm)):
                StormConnectivity.append(0)
            Storm = [float(i) for i in Storm]
            StartingLine=StartingLine+1

            ###################################################################################
            #storm cluster identification
            StormThreshhold = self.dialog.StormThreshholdBox.value()
            for i, value in enumerate(Storm):
                try:
                    if Storm[i-1]>StormThreshhold and value>StormThreshhold and (i-1)>=0:
                        StormConnectivity[i]=StormConnectivity[i-1]
                        continue
                except:
                    pass

                try:
                    if Storm[i - self.nx] > StormThreshhold and value > StormThreshhold and (i - self.nx)>=0:
                        StormConnectivity[i] = StormConnectivity[i - self.nx]
                        continue
                except:
                    pass

                try:
                    if Storm[i - self.nx-1] > StormThreshhold and value > StormThreshhold and (i - self.nx-1)>=0:
                        StormConnectivity[i] = StormConnectivity[i - self.nx-1]
                        continue
                except:
                    pass

                if value > StormThreshhold:
                    self.StormCount = self.StormCount + 1
                    StormConnectivity[i] = self.StormCount
            ####################################################################################
            print(PreviousStormConnectivity,"previous connectivity1")
            print(StormConnectivity, "storm connectivity1")
            print(Storm, "storm")
            #find overlapping storms
            for i, value in enumerate(StormConnectivity):
                for j, previousvalue in enumerate(PreviousStormConnectivity):
                    if i==j and value>0 and previousvalue>0:
                        for k, value2 in enumerate(StormConnectivity):
                            if value2==value:
                                StormConnectivity[k]=previousvalue
           ######################################################################################

            #getting storm statistics

            if all(i <= self.dialog.StormThreshholdBox.value() for i in Storm):
                nostormcount=nostormcount+1
            else:
                self.NoStormDuration.append(nostormcount)
                nostormcount=0

               #storm volume
                for i, value in enumerate(StormConnectivity):
                    if value>0:
                        self.StormVolume[value]=self.StormVolume[value]+Storm[i]
                #storm duration
                print(StormConnectivity, "storm connectivity2")
                for value in list(set(StormConnectivity)):
                    if value!=0:
                        self.StormDuration[value]=self.StormDuration[value]+1
                        #peak intensity and storm area and velocity and direction
                        rainintensities=[]
                        currentstormcoordinates=[]
                        previousstormcoordinates=[]
                        stormarea=0
                        for i, id in enumerate(StormConnectivity):
                            if id==value and id!=0:
                                rainintensities.append(Storm[i])
                                currentstormcoordinates.append(self.CellCoordinates[i])
                                stormarea=stormarea+1

                        for i, id in enumerate(PreviousStormConnectivity):
                            if id==value and id!=0:
                                previousstormcoordinates.append(self.CellCoordinates[i])

                        if value != 0:
                            self.StormPeakIntensity[value]=max(rainintensities)
                            self.StormSize[value]=self.StormSize[value]+stormarea

                        #traveled distance and direction
                        if value != 0 and (value in PreviousStormConnectivity):
                            currentstormcenterx=0
                            currentstormcentery=0
                            for xy in currentstormcoordinates:
                                currentstormcenterx=currentstormcenterx+xy.x()
                                currentstormcentery = currentstormcentery + xy.y()
                            currentstormcenterx = currentstormcenterx/len(currentstormcoordinates)
                            currentstormcentery = currentstormcentery/len(currentstormcoordinates)

                            previousstormcenterx = 0
                            previousstormcentery = 0
                            for xy in previousstormcoordinates:
                                previousstormcenterx = previousstormcenterx + xy.x()
                                previousstormcentery = previousstormcentery + xy.y()

                            if value !=1:
                                previousstormcenterx = previousstormcenterx / len(previousstormcoordinates)
                                previousstormcentery = previousstormcentery / len(previousstormcoordinates)

                            #both need averaging out
                            self.StormTraveledDistance[value] = self.StormTraveledDistance[value] + math.sqrt((currentstormcenterx - previousstormcenterx)**2 + (currentstormcentery - previousstormcentery)**2)
                            self.StormDirection[value] = self.StormDirection[value] + angle_between([previousstormcenterx,previousstormcentery], [currentstormcenterx,currentstormcentery])

            PreviousStormConnectivity=StormConnectivity
            Storm = []
            StormConnectivity = []


        #print(self.StormPeakIntensity[:self.StormCount+1],"peak")
        #print(self.StormSize[:self.StormCount+1],"size")
        #print(self.StormDuration[:self.StormCount+1],"duration")
        #print(self.StormTraveledDistance[:self.StormCount+1],"distance")
        #print(self.StormDirection[:self.StormCount+1], "direction")


        if self.dialog.SaveStormStatisticsBox.isChecked():
            self.dialog.StatusIndicator.setText("Writing Storm Statistics to File...")
            QTimer.singleShot(50, self.WriteStormStatistics)



    #function to write storm statistics to file
    def WriteStormStatistics(self):
        filepath = os.path.join(self.dialog.folderEdit_dataanalysis.text(), "StormStatistics" + '.txt')
        try:  # deletes previous files
            if os.path.isfile(filepath):
                os.remove(filepath)
        except:
            pass

        try:
            file=open(filepath, 'w')
            file.close()
        except:
            pass
        with open(filepath, 'a') as StormStatistics:
            StormStatistics.write('Storm_id Storm_Duration Storm_Volume Storm_PeakIntensity Storm_TotalArea Storm_TraveledDistance StormTotalAngle\n')
            for i in range(1,self.StormCount+1):
                StormStatistics.write('%s %s %s %s %s %s %s\n' % (i, self.StormDuration[i],self.StormVolume[i],self.StormPeakIntensity[i], (self.StormSize[i]),(self.StormTraveledDistance[i]),(self.StormDirection[i])))




    
    def execTool(self):
        print("hello")