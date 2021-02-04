from __future__ import unicode_literals
from __future__ import absolute_import

# system modules
import math
import os
import tempfile
import collections
import statistics
import random

import numpy as np
from scipy.stats import expon
from scipy.stats import poisson
import scipy.linalg

# QGIS modules
from qgis.core import *
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import *
from qgis.PyQt import uic
from PyQt5.QtCore import *

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

        self.RainGaugeLayer.layerChanged.connect(self.UpdateFields)
        self.AnalyzeAllDataBox.stateChanged.connect(self.UpdateUntilFromBoxes)
        self.SpatialInterpolationOnlyBox.stateChanged.connect(self.UpdateOutputOptions)
        self.SpatialInterpolationMethodBox.activated.connect(self.UpdateExponentFactorField)

        self.RainGaugeLayer.setLayer(None)
        self.GenerationAreaLayer.setLayer(None)

        #self.DataTypeBox.addItem('minutely')
        self.DataTypeBox.addItem('Hourly')
        #self.DataTypeBox.addItem('Daily')

        self.SpatialInterpolationMethodBox.addItem("Inversed Distance Weighting")
        self.SpatialInterpolationMethodBox.addItem("Trend Surface Analysis (Polynomial 1st Order)")
        self.SpatialInterpolationMethodBox.setCurrentIndex(-1)

        self.dxBox.setValue(5000)
        self.dyBox.setValue(5000)

        self.browseButton.clicked.connect(self.onBrowseButtonClicked)
        self.browseButton.setAutoDefault(False)

        self.FromBox.setEnabled(False)
        self.UntilBox.setEnabled(False)
        self.CheckButton2.setEnabled(False)
        self.label_30.setEnabled(False)
        self.label_31.setEnabled(False)

        self.ExponentFactorBox.setEnabled(False)
        self.label_32.setEnabled(False)

        self.groupBox_2.setEnabled(False)
        self.groupBox_3.setEnabled(False)


    def UpdateFields(self, layer):
        self.DataAddressField.setLayer(self.RainGaugeLayer.currentLayer())
        self.RainGaugeNameField.setLayer(self.RainGaugeLayer.currentLayer())
        self.FromBox.clear()
        self.UntilBox.clear()
        self.groupBox_2.setEnabled(False)
        self.groupBox_3.setEnabled(False)

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
        else:
            self.FromBox.setEnabled(True)
            self.UntilBox.setEnabled(True)
            self.CheckButton2.setEnabled(True)
            self.label_30.setEnabled(True)
            self.label_31.setEnabled(True)

    def UpdateOutputOptions(self):
        if self.SpatialInterpolationOnlyBox.isChecked():
            self.label_27.setEnabled(False)
            self.RequestedGenerationDurationBox.setEnabled(False)
            self.SaveRainGaugeValuesBox.setEnabled(False)
        else:
            self.label_27.setEnabled(True)
            self.RequestedGenerationDurationBox.setEnabled(True)
            self.SaveRainGaugeValuesBox.setEnabled(True)


    def onBrowseButtonClicked(self):
        currentFolder = self.folderEdit.text()
        folder = QFileDialog.getExistingDirectory(self.iface.mainWindow(), 'Rain Generator', currentFolder)
        if folder != '':
            self.folderEdit.setText(folder)
            self.folderEdit.editingFinished.emit()



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
        self.dialog.GenerateButton.clicked.connect(self.DataAnalysis)
        self.dialog.CheckButton2.clicked.connect(self.AnalyzeFromUntil)


    def scheduleAbort(self):
        self.cancel = True

    def quitDialog(self):
        self.dialog = None
        self.act.setEnabled(True)
        self.cancel = False

##########################################################################
    layer2 = QgsVectorLayer("Polygon", 'Generation_Area', 'memory')

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

        # feat = QgsFeature()
        # feat.setGeometry(QgsGeometry.fromRect(layer.extent()))
        # prov.addFeatures([feat])
        self.layer2.setCrs(QgsCoordinateReferenceSystem(self.iface.mapCanvas().mapSettings().destinationCrs().authid()))
        self.layer2.updateExtents()
        QgsProject.instance().addMapLayer(self.layer2)
        self.dialog.groupBox_3.setEnabled(True)

####################################################################

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

###########################################################
    rainstorm=[]
    norainduration=[] #rain is based on one dry timestep
    rainduration=[]
    storms=[] #storm is based on calculated dpdmin
    nostormsduration=[] #storm is based on calculated dpdmin

###########################################################
    def DataAnalysis(self):

        if self.dialog.SpatialInterpolationOnlyBox.isChecked():
            self.PreSpatialInterpolation()
            return

        filename = self.dialog.folderEdit.text()
        if not filename:
            self.iface.messageBar().pushCritical(
                'Rain Generator',
                'No output folder given!'
            )
            return
        filepath = os.path.join(self.dialog.folderEdit.text(), "GeneratedDataforRainGauges" + '.txt')
        try: #deletes previous files
            if os.path.isfile(filepath):
                os.remove(filepath)
        except:
            pass

        with open(filepath, 'a') as raingaugegenerateddata:
            raingaugegenerateddata.write('# comment\n')
            raingaugegenerateddata.write('# !BEGIN\n')
            raingaugegenerateddata.write('# number begining from 0 ++ number of points\n')
            raingaugegenerateddata.write('# hour [h] discharge [m³/s]\n')
            raingaugegenerateddata.write('# !END\n\n\n')


    ##########################################################
    #calculates if there is rain or no rain periods and their duration
        for x in range(self.ngauges):
            #self.rainstorm.append([])
            self.norainduration.append([])
            #self.rainduration.append([])
            for y in range(1):
                #self.rainstorm[x].append([])
                self.norainduration[x].append([])
                #self.rainduration[x].append([])

        for i in range(len(self.data)):
            raincount = 0
            noraincount = 0
            rain = False
            norain = False
            for k, value in enumerate(self.data[i][1]):
                j=float(value)
                if j>0:
                    raincount = raincount + 1
                    rain=True
                if j==0:
                    noraincount = noraincount + 1
                    norain=True
                if j>0 and norain==True:
                    self.norainduration[i][0].append(noraincount)
                    noraincount=0
                    #self.rainstorm[i][0].append("nostorm")
                    rain=True
                    norain=False
                if j==0 and rain==True:
                    #self.rainduration[i][0].append(raincount)
                    raincount=0
                    #self.rainstorm[i][0].append("storm")
                    rain=False
                    norain=True
                if j>0 and k==len(self.data[i][1])-1:
                    #self.rainduration[i][0].append(raincount)
                    #self.rainstorm[i][0].append("storm")
                    rain=True
                    norain=False
                if j==0 and k==len(self.data[i][1])-1:
                    self.norainduration[i][0].append(noraincount)
                    #self.rainstorm[i][0].append("nostorm")
                    rain=False
                    norain=True


        print(self.rainstorm)
        print(self.norainduration,"noraindurations")

        #######################################################################
        #calculates minimum dry period duration
        for i in range(len(self.norainduration)):
            noraindurations=self.norainduration[i][0]
            noraindurations.sort()
            for j in range(len(noraindurations)-1):
                sdnorain = statistics.stdev(noraindurations) #standard deviation of norain durations
                meannorain = statistics.mean(noraindurations) #mean of norain durations
                cv = sdnorain/meannorain #coefficient of variation
                print(cv, "cv")
                if cv<=1:
                    cv1=cv
                    dpd1= noraindurations[0]  #dpd = dry period duration
                    print(dpd1,"dpd1")
                if cv>=1:   #what if no positive cv happens?
                    cv2=cv
                    dpd2 = noraindurations[0]
                    print(dpd2, "dpd2")
                del noraindurations[0]
                try:
                    cv1
                    try:
                        cv2
                        dpdmin = ((1 - cv1) * ((dpd2 - dpd1) / (cv2 - cv1))) + dpd1 #minimum dry period duration
                        print(dpdmin, "dpdmin") ###### final product!!!!!
                        break
                    except UnboundLocalError:
                        pass
                except UnboundLocalError:
                    pass

            ##########################################################
            # calculates storm and no storm statistics
            for x in range(self.ngauges):
                self.storms.append([])
                self.nostormsduration.append([])
                #for y in range(1):
                    #self.storms[x].append([])
                    #self.nostormsduration[x].append([])

            for i in range(len(self.data)): #loops over raingauges
                raincount = 0
                noraincount = 0
                idpd = 0 #innerstorm dpd
                stormintensity = 0 #strom volume divided by number of timesteps in storm including innerstrom dpd
                stormvolume = 0
                counter = 0

                storm = False
                nostorm = False

                for k, value in enumerate(self.data[i][1]):
                    j=float(value)
                    counter = counter + 1
                    if j > 0:
                        if storm==False:
                            idpd=0
                            stormvolume = 0
                            stormintensity = 0
                        storm=True
                        stormvolume = stormvolume + j
                        raincount = raincount + 1
                        if noraincount>dpdmin:
                            self.nostormsduration[i].append(noraincount)
                            counter=1
                        if k == len(self.data[i][1])-1: #if the last value is positive
                            stormintensity = stormvolume / counter
                            self.storms[i].append([stormvolume, stormintensity, counter, idpd])
                        noraincount=0
                    if j==0:
                        noraincount = noraincount + 1
                        raincount=0
                        if noraincount<dpdmin:
                            storm=True
                        if storm==True and noraincount<dpdmin:
                            idpd=idpd+1
                        elif storm==True and noraincount>=dpdmin:
                            storm=False
                            idpd = idpd - (noraincount - 1)
                            counter=counter-noraincount
                            stormintensity=stormvolume/counter
                            self.storms[i].append([stormvolume,stormintensity,counter,idpd]) #storm volume, storm mean intensity, storm duration, interstorm dpd
                            counter=noraincount
                            stormvolume=0
                            stormintensity=0
                            idpd=0
                        if k == len(self.data[i][1])-1: #if the last value is 0
                            if noraincount<dpdmin:
                                idpd = idpd - (noraincount - 1)
                                counter = counter
                                stormintensity = stormvolume / counter
                                self.storms[i].append([stormvolume, stormintensity, counter, idpd])
                            if noraincount>=dpdmin:
                                self.nostormsduration[i].append(noraincount)



                print(self.nostormsduration, "nostormsduration after loop") #finalproduct!!
                print(self.storms, "storms after loop") #finalproduct!!
                #################################################################
                #making an array for randomly chosing storm or dpd
                stormordpd=[]
                for j in range(len(self.storms[i])):
                    stormordpd.append("storm")
                for j in range(len(self.nostormsduration[i])):
                    stormordpd.append("dpd")
                print(stormordpd)
                #################################################################
                #classifying the storms into 4 catagories based on duration
                allstormdurations = []
                for value in self.storms[i]:
                 allstormdurations.append(value[2])
                classificationtimestep=(max(allstormdurations)-min(allstormdurations))/4

                class1intensities = []
                class2intensities = []
                class3intensities = []
                class4intensities = []

                ###################################################################
                #calculating the means
                sumvolume=0
                sumintensity=0
                sumstormduration=0
                suminterstormdpd=0
                sumdpd=0

                #for storms
                for value in self.storms[i]:
                    sumvolume=sumvolume+value[0]
                    sumintensity=sumintensity+value[1]
                    sumstormduration=sumstormduration+value[2]
                    suminterstormdpd=suminterstormdpd+value[3]
                    #getting the intensities of each storm duration class
                    if min(allstormdurations) <= value[2] < min(allstormdurations) + classificationtimestep:
                        class1intensities.append(value[1])
                    elif min(allstormdurations) + classificationtimestep <= value[2] < min(allstormdurations) + (2 * classificationtimestep):
                        class2intensities.append(value[1])
                    elif min(allstormdurations) + (2 * classificationtimestep) <= value[2] < min(allstormdurations) + (3 * classificationtimestep):
                        class3intensities.append(value[1])
                    elif min(allstormdurations) + (3 * classificationtimestep) <= value[2] <= min(allstormdurations) + (4 * classificationtimestep):
                        class4intensities.append(value[1])

                #storm statistics
                meanvolume=sumvolume/len(self.storms[i])
                meanintensity=sumintensity/len(self.storms[i])
                meanstormduration=sumstormduration/len(self.storms[i])
                meaninterstormdpd=suminterstormdpd/len(self.storms[i])

                #storm class itensities
                class1meanintensity= sum(class1intensities)/len(class1intensities)
                class2meanintensity = sum(class2intensities) / len(class2intensities)
                class3meanintensity = sum(class3intensities) / len(class3intensities)
                class4meanintensity = sum(class4intensities) / len(class4intensities)

                print(class1meanintensity,class2meanintensity,class3meanintensity,class4meanintensity,"storm duration class mean intensities")
                print(meanvolume,meanintensity,meanstormduration,meaninterstormdpd,"storm means")

                #for dry periods
                for value in self.nostormsduration[i]:
                    sumdpd=sumdpd+value
                meandpd=sumdpd/len(self.nostormsduration[i])
                print(meandpd,"meandpd")


                #####################################################################
                raingaugenames, ok = QgsVectorLayerUtils.getValues(self.dialog.RainGaugeLayer.currentLayer(), self.dialog.RainGaugeNameField.expression(), selectedOnly = False)
                if not ok:
                    self.iface.messageBar().pushCritical(
                        'Rain Generator',
                        'Invalid Expression for Names!'
                    )
                    return

                #writing the file
                with open(filepath, 'a') as raingaugegenerateddata:
                    raingaugegenerateddata.write('!BEGIN   #%s\n' % raingaugenames[i])
                    raingaugegenerateddata.write('%s %s             area #Length [m²/s], Area [m/s], waterlevel [m], point [m³/s]\n' % (str(i),str(self.dialog.RequestedGenerationDurationBox.value())))

                    counter=1
                    stormstatus="dpd"
                    while(counter <= self.dialog.RequestedGenerationDurationBox.value()):
                        #randomchoice = random.choice(stormordpd)
                        if stormstatus == "dpd": #dry period
                            roundeddpd = 0
                            while(roundeddpd<dpdmin):  #check for the generated dpd to be bigger than dpdmin
                                dpd = np.random.exponential(meandpd) #chooses the dpd based on an exponentail distribution
                                roundeddpd = round(dpd)
                            for j in range(roundeddpd): #writes the time steps
                                raingaugegenerateddata.write('%s %s\n' % (str(counter), str(0)))
                                counter=counter+1
                                if counter>self.dialog.RequestedGenerationDurationBox.value():
                                    return
                            stormstatus = "storm"


##############################################################################
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
    def PreSpatialInterpolation(self):
        self.iface.messageBar().pushInfo(
            'Rain Generator',
            'Performing Spatial Interpolation, Please Wait !'
        )
        QTimer.singleShot(500, self.SpatialInterpolation) #waits half a second for the message to be displayed
#################################################################################
    def SpatialInterpolation(self):
        filename = self.dialog.folderEdit.text()
        if not filename:
            self.iface.messageBar().pushCritical(
                'Rain Generator',
                'No output folder given!'
            )
            return
        filepath = os.path.join(self.dialog.folderEdit.text(), "GeneratedRainfall" + '.txt')
        try: #deletes previous files
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

            raingaugelocations=[]
            generationlocations=[]

            #getting the locations of raingauges
            point_layer=self.dialog.RainGaugeLayer.currentLayer()
            features = point_layer.getFeatures()
            for feature in features:
                buff = feature.geometry()
                raingaugelocations.append(buff.asPoint())

            #getting the generation locations
            area_layer=self.layer2
            features = area_layer.getFeatures()
            for feature in features:
                buff = feature.geometry()
                generationlocations.append(buff.centroid().asPoint())


            #calculate generation duration
            rainlengths=[]
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

                fieldids=[]
                fields = timeviewerlayer.dataProvider().fields()
                #deleting extra fields
                fieldstodelete=["XMIN","XMAX","YMIN","YMAX"]
                for field in fields:
                    if field.name() in fieldstodelete:
                        fieldids.append(fields.indexFromName(field.name()))

                timeviewerlayer.dataProvider().deleteAttributes(fieldids)
                timeviewerlayer.setCrs(
                    QgsCoordinateReferenceSystem(self.iface.mapCanvas().mapSettings().destinationCrs().authid()))
                timeviewerlayer.updateFields()
            ##################################################################
#################################################################################################
            #Inversed Distance Weighting
            if self.dialog.SpatialInterpolationMethodBox.currentText()=="Inversed Distance Weighting":
                #writing the file
                for i in range(len(generationlocations)):
                    generateddata.write('!BEGIN   #%s\n' % "raingaugename")
                    generateddata.write('%s %s             area #Length [m²/s], Area [m/s], waterlevel [m], point [m³/s]\n' % (str(i), str(min(rainlengths))))
                    counter = 0
                    n = self.dialog.ExponentFactorBox.value() #exponent factor for the invert distance weighting formula
                    while counter+1<=min(rainlengths):
                        upperformula=0
                        lowerformula=0
                        for j in range(len(self.data)):
                            distance=raingaugelocations[j].distance(generationlocations[i])
                            upperformula = upperformula + ((1 / (distance**n)) * float(self.data[j][1][counter]))
                            lowerformula=lowerformula+(1/(distance**n))
                        rainvalue= round((upperformula/lowerformula),3)
                        generateddata.write('%s %s   #%s mm/h\n' % (str(counter), str(rainvalue/3600000) , str(rainvalue)))

                        ###############################################
                        # time viewer layer
                        if self.dialog.TImeVieweLayerBox.isChecked():
                            fields = timeviewerlayer.dataProvider().fields()
                            datetimefieldid=fields.indexFromName("date_time")
                            rainvaluefieldid=fields.indexFromName("Boundary Value")
                            idfieldid=fields.indexFromName("ID")
                            featureids=[]
                            for feature in timeviewerlayer.getFeatures():
                                if float(feature.attributes()[idfieldid]) == float(i):
                                    featureids.append(feature.id())
                            try:
                                atts = {datetimefieldid: float(self.data[rainlengths.index(min(rainlengths))][0][counter]), rainvaluefieldid: rainvalue}
                            except:
                                atts = {datetimefieldid: self.data[rainlengths.index(min(rainlengths))][0][counter], rainvaluefieldid: rainvalue}
                            timeviewerlayer.dataProvider().changeAttributeValues({featureids[counter]: atts})
                        ###############################################

                        if counter+1==min(rainlengths):
                            generateddata.write('!END')
                            generateddata.write('\n\n')
                        counter=counter+1
######################################################################################################
            #Trend Surface Analysis (Polynomial 1st Order)
            elif self.dialog.SpatialInterpolationMethodBox.currentText()=="Trend Surface Analysis (Polynomial 1st Order)":

                allrainvalues=[]
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
                        #Z = C[0] * X + C[1] * Y + C[2]

                    rainvaluesintimestep=[]
                    for i in generationlocations:
                        value=(C[0] * i.x()) + (C[1] * i.y()) + C[2]
                        rainvaluesintimestep.append(value)
                    allrainvalues.append(rainvaluesintimestep)

                #writing the file
                for i in range(len(generationlocations)):
                    generateddata.write('!BEGIN   #%s\n' % "raingaugename")
                    generateddata.write('%s %s             area #Length [m²/s], Area [m/s], waterlevel [m], point [m³/s]\n' % (str(i), str(min(rainlengths))))
                    counter = 0
                    while counter+1<=min(rainlengths):
                        rainvalue= float(allrainvalues[counter][i])
                        ###############################################
                        # time viewer layer
                        if self.dialog.TImeVieweLayerBox.isChecked():
                            fields = timeviewerlayer.dataProvider().fields()
                            datetimefieldid=fields.indexFromName("date_time")
                            rainvaluefieldid=fields.indexFromName("Boundary Value")
                            idfieldid=fields.indexFromName("ID")
                            featureids=[]
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
                        generateddata.write('%s %s   #%s mm/h\n' % (str(counter), str(rainvalue/3600000) , str(rainvalue)))
                        if counter+1==min(rainlengths):
                            generateddata.write('!END')
                            generateddata.write('\n\n')
                        counter=counter+1
 ######################################################################################
            elif self.dialog.SpatialInterpolationMethodBox.currentText() == "Trend Surface Analysis (Polynomial 2nd Order)":

                #elif order == 2:
                    # best-fit quadratic curve
                    A = np.c_[np.ones(data.shape[0]), data[:, :2], np.prod(data[:, :2], axis=1), data[:, :2] ** 2]
                    C, _, _, _ = scipy.linalg.lstsq(A, data[:, 2])

                    # evaluate it on a grid
                    Z = np.dot(np.c_[np.ones(XX.shape), XX, YY, XX * YY, XX ** 2, YY ** 2], C).reshape(X.shape)



            self.iface.messageBar().pushSuccess(
                'Rain Generator',
                'Generation Successful !'
            )
        ##########################################################
        #time viewer layer
        if self.dialog.TImeVieweLayerBox.isChecked():
            timeviewerlayer.updateFields()
            QgsProject.instance().addMapLayer(timeviewerlayer)
        ##########################################################



    #use poisson.pmf(k,lambd) from the library scipy.stats
    #k=np.arange(0,1000)
    #distribution = np.zeros(k_axis.shape[0])
    #for i in range(k_axis.shape[0]):
        #distribution[i] = poisson.pmf(i, lambd)
    #plt.bar(k_axis, distribution)
    
    #numpy.random.choice(numpy.arange(1, 7), p=[0.1, 0.05, 0.05, 0.2, 0.4, 0.2])
    
    
    def poisson_distribution(k, lambd):
        return (lambd ** k * np.exp(-lambd)) / np.math.factorial(k)

    ###################################################################
        #not needed
        #print(len(self.norainduration),"len")
        #for i in range(len(self.norainduration)):
            #print(i,"i")
            #print(self.norainduration[i][0],"array")
            #countofnoraindurations = collections.Counter(self.norainduration[i][0])
            #print(countofnoraindurations.keys()) #dpd values
            #print(countofnoraindurations.values()) #dpd frequencies
            #sortedcountofnoraindurations=sorted(countofnoraindurations.items(), key=lambda i: i[1]) #sort in ascending order based on frequency
            #print(sortedcountofnoraindurations,"sorted")
####################################################################

#####################################################################

    
    def execTool(self):
        print("hello")