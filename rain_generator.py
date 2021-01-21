from __future__ import unicode_literals
from __future__ import absolute_import

# system modules
import math
import os
import tempfile
import collections
import statistics

import numpy as np

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

        self.RainGaugeLayer.layerChanged.connect(self.UpdateDataAddressField)

        self.RainGaugeLayer.setLayer(None)
        self.GenerationAreaLayer.setLayer(None)

        self.DataTypeBox.addItem('minutely')
        self.DataTypeBox.addItem('Hourly')
        self.DataTypeBox.addItem('Daily')

        self.dxBox.setValue(10)
        self.dyBox.setValue(10)

        self.browseButton.clicked.connect(self.onBrowseButtonClicked)
        self.browseButton.setAutoDefault(False)


    def UpdateDataAddressField(self, layer):
        self.DataAddressField.setLayer(self.RainGaugeLayer.currentLayer())

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

##########################################################################
    def CreateGenerationArea(self):
        if type(self.dialog.GenerationAreaLayer.currentLayer()) == type(None):
            self.dialog.iface.messageBar().pushCritical(
                'Rain Generator',
                'No Layer Selected !'
            )
            return

        layer = self.dialog.GenerationAreaLayer.currentLayer()
        ex = layer.extent()
        xmax = ex.xMaximum()
        ymax = ex.yMaximum()
        xmin = ex.xMinimum()
        ymin = ex.yMinimum()
        layer2 = QgsVectorLayer("Polygon", 'Generation Area', 'memory')
        prov = layer2.dataProvider()

        fields = QgsFields()
        fields.append(QgsField('ID', QVariant.Int, '', 10, 0))
        fields.append(QgsField('XMIN', QVariant.Double, '', 24, 6))
        fields.append(QgsField('XMAX', QVariant.Double, '', 24, 6))
        fields.append(QgsField('YMIN', QVariant.Double, '', 24, 6))
        fields.append(QgsField('YMAX', QVariant.Double, '', 24, 6))
        prov.addAttributes(fields)
        layer2.updateExtents()
        layer2.updateFields()

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

        #feat = QgsFeature()
        #feat.setGeometry(QgsGeometry.fromRect(layer.extent()))
        #prov.addFeatures([feat])
        layer2.setCrs(QgsCoordinateReferenceSystem(self.iface.mapCanvas().mapSettings().destinationCrs().authid()))
        layer2.updateExtents()
        QgsProject.instance().addMapLayer(layer2)
####################################################################

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
        self.dialog.TestButton.clicked.connect(self.DataAnalysis)

    def scheduleAbort(self):
        self.cancel = True

    def quitDialog(self):
        self.dialog = None
        self.act.setEnabled(True)
        self.cancel = False

    data = []
    ngauges = 0
    ntimes = 0
    nrains = 0
############################################################
    def CheckFiles(self):
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
            lines = f.readlines()
            for x in lines:
                x=x.replace('\n','')
                self.data[i][0].append((x.split(' ')[0]).strip("\\n"))
                self.data[i][1].append((x.split(' ')[1]).strip("\\n"))
            f.close()
###########################################################
    rainstorm=[]
    norainduration=[] #rain is based on one dry timestep
    rainduration=[]
    storms=[] #storm is based on calculated dpdmin
    nostormsduration=[] #storm is based on calculated dpdmin

###########################################################
    def DataAnalysis(self):

    ##########################################################
    #calculates if there is a storm or not and their duration
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
                j=int(value)
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
        print(self.norainduration,"norain")
        print(self.rainduration,"rain")

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
                    j=int(value)
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
                            self.storms[i].append([stormvolume,stormintensity,counter,idpd]) #storm volume, storm intensity, storm duration, interstorm dpd
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



                print(self.nostormsduration, "nostormsduration after loop")
                print(self.storms, "storms after loop")






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