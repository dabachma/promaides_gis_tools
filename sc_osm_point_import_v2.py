from __future__ import unicode_literals
from __future__ import absolute_import

# QGIS modules 
from qgis.core import *
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtWidgets import *
from qgis.PyQt import uic
from qgis.gui import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from PyQt5 import QtWidgets

# promaides modules
from .environment import get_ui_path

# system modules
import webbrowser

#general
import math
import time
import requests
import json
import os
from multiprocessing.pool import ThreadPool as Pool


UI_PATH = get_ui_path('ui_sc_promaides_osm_point_import_v2.ui')



class PluginDialog(QDialog):

    ClosingSignal = pyqtSignal()

    def __init__(self, iface, parent=None, flags=Qt.WindowFlags()):
        QDialog.__init__(self, parent, flags)
        uic.loadUi(UI_PATH, self)
        self.iface = iface

        self.browse_button.clicked.connect(self.onBrowseButtonClicked)
        self.button_searchArea.clicked.connect(self.enableMapPicker)

        self.picker = QgsMapToolEmitPoint(self.iface.mapCanvas())

        project = QgsProject.instance()
        self.crs = project.crs()
        self.HelpButton.clicked.connect(self.Help)

        self.SC1Box.setSaveCollapsedState(False)
        self.SC2Box.setSaveCollapsedState(False)
        self.SC3Box.setSaveCollapsedState(False)
        self.SC4Box.setSaveCollapsedState(False)

        self.SC1Box.setCollapsed(True)
        self.SC2Box.setCollapsed(True)
        self.SC3Box.setCollapsed(True)
        self.SC4Box.setCollapsed(True)

        self.SC1Box.toggled.connect(
            lambda checked: (self.checkBox_fire_station.setChecked(checked),
            self.checkBox_government.setChecked(checked),
            self.checkBox_police.setChecked(checked))
        )
        self.SC2Box.toggled.connect(
            lambda checked: (self.checkBox_chemical.setChecked(checked),
            self.checkBox_wastewater.setChecked(checked),
            self.checkBox_biogas.setChecked(checked))
        )
        self.SC3Box.toggled.connect(
            lambda checked: (self.checkBox_monuments.setChecked(checked),
            self.checkBox_museum.setChecked(checked),
            self.checkBox_worship.setChecked(checked))
        )
        self.SC4Box.toggled.connect(
            lambda checked: (self.checkBox_eldery.setChecked(checked),
            self.checkBox_hospitals.setChecked(checked),
            self.checkBox_kindergarten.setChecked(checked),
            self.checkBox_schools.setChecked(checked))
        )
        self.filename_edit.editingFinished.connect(self.subcategoryFile)

        self.Txt_Button.toggled.connect(
            lambda checked: (self.subcategory_edit.setEnabled(checked),
            self.renameFile(checked),
            self.subcategoryFile())
        )
        self.ChangeBox.toggled.connect(self.defaultValues)
        
        self.Layer_ComboBox.setFilters(QgsMapLayerProxyModel.PolygonLayer)

        self.groupBox_searchArea.toggled.connect(lambda checked: self.groupBox_selectLayer.setChecked(not checked))
        self.groupBox_selectLayer.toggled.connect(lambda checked: self.groupBox_searchArea.setChecked(not checked))

        #self variables 
        self.areaName = "Search Area"
        self.pointValue = 1
        self.boundaryValue = 0.20
        self.searchLayerExisting = len(QgsProject.instance().mapLayersByName(self.areaName)) != 0

    def closeEvent(self, event):
        self.ClosingSignal.emit()
    
    def Help(self):
        webbrowser.open("https://promaides.myjetbrains.com/youtrack/articles/PMDP-A-81/DAM-CIN---OSM-CI-Point-Import")

    def onBrowseButtonClicked(self):
        current_filename = self.filename_edit.text()
        if self.Shp_Button.isChecked():
            new_filename, __ = QFileDialog.getSaveFileName(self.iface.mainWindow(), 'SC OSM Point Import', current_filename, "*.shp *.SHP")
        else:
            new_filename, __ = QFileDialog.getSaveFileName(self.iface.mainWindow(), 'SC OSM Point Import', current_filename, "*.txt *.TXT")
        if new_filename != '':
            self.filename_edit.setText(new_filename)
            self.filename_edit.editingFinished.emit()

    def subcategoryFile(self):
        if self.filename_edit.text() != '':
            if self.Txt_Button.isChecked():
                file_path = os.path.basename(self.filename_edit.text())
                base = os.path.basename(file_path)
                name, ending = base.split(".")
                new_name = name + "_" + "subcatergory" + "." + ending
                old_path = file_path.split("/")
                old_path[-1] = new_name
                subcategory_path = "/".join(old_path)
                self.subcategory_edit.setText(subcategory_path)
            else:
                self.subcategory_edit.setText("")

    def renameFile(self, txtbutton):
        if self.filename_edit.text() != '':
            file_path = self.filename_edit.text()
            name, ending = file_path.split(".")
            if txtbutton:
                ending = ".txt"
            else:
                ending = ".shp"
            new_path = name + ending
            self.filename_edit.setText(new_path)

    def defaultValues(self, checked):
        if checked:
            self.PointBox.setEnabled(True)
            self.boundaryBox.setEnabled(True)

            self.PointBox.setValue(self.pointValue)
            self.boundaryBox.setValue(self.boundaryValue)
        else:
            self.PointBox.setEnabled(False)
            self.boundaryBox.setEnabled(False)
            
            self.pointValue = self.PointBox.value()
            self.boundaryValue = self.boundaryBox.value()
            self.PointBox.setValue(1)
            self.boundaryBox.setValue(0.20)

    def enableMapPicker(self, clicked):
        self.list_of_Points = []
        self.coordinate1 = ()
        self.coordinate2 = ()

        if clicked:
            self.picker.canvasClicked.connect(self.onMapClicked)
            self.iface.mapCanvas().setMapTool(self.picker)
        else:
            self.picker.canvasClicked.disconnect(self.onMapClicked)
            self.iface.mapCanvas().unsetMapTool(self.picker)

    def onMapClicked(self, point, button):
        if self.Poly_Button.isChecked():
            if button == Qt.LeftButton:
                ptnX = point.x()
                ptnY = point.y()
                self.list_of_Points.append(QgsPointXY(ptnX,ptnY))

            if button == Qt.RightButton and len(self.list_of_Points) != 0:
                del self.list_of_Points[-1]

            self.polygon(self.list_of_Points)
        
        if self.Rect_Button.isChecked():
            if button == Qt.LeftButton:
                if self.coordinate1 and self.coordinate2:
                    distA = point.distance(self.coordinate1[0], self.coordinate1[1])    
                    distB = point.distance(self.coordinate2[0], self.coordinate2[1])

                    if distA < distB:
                        self.coordinate1 = point.x(), point.y()
                    else:
                        self.coordinate2 = point.x(), point.y()

                elif self.coordinate1 and not self.coordinate2:
                    self.coordinate2 = point.x(), point.y()
                
                elif not self.coordinate1:
                    self.coordinate1 = point.x(), point.y()

            if self.coordinate1 and self.coordinate2:
                self.rectangle(self.coordinate1, self.coordinate2)

            if button == Qt.RightButton:
                self.button_searchArea.toggle()
                self.enableMapPicker(False)
            
        
    def polygon(self, list_of_Points):
        geom = QgsGeometry().fromPolygonXY([list_of_Points])
        self.drawer(geom)

    def rectangle(self, coordinate1, coordinate2):
        if coordinate1[0] < coordinate2[0]:
            xmin = coordinate1[0]
            xmax = coordinate2[0]
        else:
            xmin = coordinate2[0]
            xmax = coordinate1[0]
        
        if coordinate1[1] < coordinate2[1]:
            ymin = coordinate1[1]
            ymax = coordinate2[1]
        else:
            ymin = coordinate2[1]
            ymax = coordinate1[1]
        
        rect = QgsRectangle(xmin, ymin, xmax, ymax)
        geom = QgsGeometry().fromRect(rect)
        self.drawer(geom)

    def drawer(self, geom):
        self.geom = geom
        self.searchLayerExisting = False
        self.deleteShapefile(self.areaName)
        project = QgsProject().instance()
        layerTree = self.iface.layerTreeCanvasBridge().rootGroup()

        ftr = QgsFeature()
        ftr.setGeometry(self.geom)

        crs = 'crs='+self.crs.authid()

        lyr = QgsVectorLayer('Polygon?{}'.format(crs), self.areaName,'memory')

        symbol = QgsFillSymbol.createSimple({'border_width_map_unit_scale': '3x:0,0,0,0,0,0', 'color': '0,0,0,0', 
        'joinstyle': 'bevel', 'offset': '0,0', 'offset_map_unit_scale': '3x:0,0,0,0,0,0', 'offset_unit': 'MM', 
        'outline_color': '228,26,28,255', 'outline_style': 'solid', 'outline_width': '0.96', 'outline_width_unit': 'MM', 'style': 'solid'})
        
        lyr.renderer().setSymbol(symbol)
        with edit(lyr):
            lyr.addFeature(ftr)
        project.addMapLayer(lyr, False)
        layerTree.insertChildNode(0, QgsLayerTreeLayer(lyr))

    def coordinateTransform(self, x, y, toWGS=bool):
        crsSrc = QgsCoordinateReferenceSystem(self.crs)
        crsDest = QgsCoordinateReferenceSystem("EPSG:4326") #WGS 84: Decimal system
        transformContext = QgsProject.instance().transformContext()
        xform = QgsCoordinateTransform(crsSrc, crsDest, transformContext)

        if toWGS:
            return xform.transform(QgsPointXY(x,y))
        else:
            return xform.transform(QgsPointXY(x,y), QgsCoordinateTransform.ReverseTransform)
    
    def deleteShapefile(self, name):
        layers = self.iface.mapCanvas().layers()
        for layer in layers:
            if layer.name() == name:
                QgsProject.instance().removeMapLayers([layer.id()]) 
                self.iface.mapCanvas().refresh()
 
class SCPointImport(object):

    def __init__(self, iface):
        self.iface = iface
        self.dialog = None
        self.cancel = False
        self.act = QAction('SC OSM Point Import', iface.mainWindow())
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
        self.dialog = PluginDialog(self.iface, self.iface.mainWindow())
        self.dialog.button_box.accepted.connect(self.verification)
        self.dialog.button_box.rejected.connect(self.quitDialog)
        self.dialog.setModal(False)
        self.act.setEnabled(False)
        self.dialog.show()
        self.dialog.ClosingSignal.connect(self.quitDialog)

    def scheduleAbort(self):
        self.cancel = True
        
    def quitDialog(self):
        if not self.dialog.checkBox_safeArea.isChecked() and not self.dialog.searchLayerExisting:
            self.dialog.deleteShapefile(self.dialog.areaName)
        self.iface.mapCanvas().unsetMapTool(self.dialog.picker)
        self.act.setEnabled(True)
        self.cancel = False
        self.dialog.close()

    def verification(self):
        if not self.dialog.filename_edit.text():
            self.iface.messageBar().pushCritical(
                'SC OSM Point Import',
                'No output filename given!'
            )
            self.execDialog()
        elif not self.dialog.SC1Box.isChecked() and not self.dialog.SC2Box.isChecked() and not self.dialog.SC3Box.isChecked() and not self.dialog.SC4Box.isChecked():
            self.iface.messageBar().pushCritical(
                'SC OSM Point Import',
                'No SC chosen!'
            )
            self.execDialog()
        elif not QgsProject.instance().mapLayersByName("Search Area") and self.dialog.groupBox_searchArea.isChecked():
            self.iface.messageBar().pushCritical(
                'SC OSM Point Import',
                'No Search Area selected!'
            )
            self.quitDialog()
        else:
            self.execTool()

    def geometry(self):
        if self.dialog.groupBox_searchArea.isChecked():
            return self.dialog.geom
        
        if self.dialog.groupBox_selectLayer.isChecked():
            layer = self.dialog.Layer_ComboBox.currentLayer()
            feature = layer.getFeature(0)
            geom = feature.geometry()
            return geom
    
    def direction(self):
        boundingBox = self.geometry().boundingBox()

        pt = self.dialog.coordinateTransform(boundingBox.xMinimum(), boundingBox.yMinimum(), True)
        west = pt.x()
        south = pt.y()
        
        pt = self.dialog.coordinateTransform(boundingBox.xMaximum(), boundingBox.yMaximum(), True)
        east = pt.x()
        north = pt.y()
        
        return north, east, south, west

    def execTool(self):
        start_time = time.time()

        inputValues = {"name":[], "id":[], "valueList":[], "lon":[], "lat":[], "osm_id":[], 'id_sub': []}

        sector_result, valueList, idList, id_subList = self.query()

        for result in sector_result:   #goes through all results of a sector
            for element in result['elements']:    #goes through all elements in the value
                value_name = valueList.pop(0)
                id = idList.pop(0)
                id_sub = id_subList.pop(0)

                if 'center' in element:
                    lon = element['center']['lon']
                    lat = element['center']['lat']
                else:
                    lon = element['lon']
                    lat = element['lat']

                if 'tags' in element:
                    if 'name' in element['tags']:
                        name = element['tags']['name'] 
                        name = name.replace(" ", "_")      
                    else:
                        name = value_name
                osm_id = str(element['type']) +"/"+ str(element['id'])

                pt = self.dialog.coordinateTransform(lon,lat,False)

                if self.geometry().contains(pt):
                    inputValues['name'].append(name)
                    inputValues['id'].append(id)
                    inputValues['valueList'].append(value_name)
                    inputValues['lon'].append(lon)
                    inputValues['lat'].append(lat)
                    inputValues['osm_id'].append(osm_id)
                    inputValues['id_sub'].append(id_sub)

        outputValues = self.checkValues(inputValues)
        filename = self.dialog.filename_edit.text()
        head, tail = os.path.split(filename)
        tail = self.dialog.subcategory_edit.text()
        subcategory = head + "/" + tail


        if self.dialog.Shp_Button.isChecked():
            feature_count = self.createShapefile(outputValues, filename)
        else:
            feature_count = self.creatTextFile(outputValues, filename, subcategory)
        

        end_time = time.time()
        length = round(end_time-start_time,2)

        self.iface.messageBar().pushInfo(
            'SC OSM Point Import',
            f'Inport finished successfully! {feature_count} Points in {length} sec. found.')

        self.quitDialog()

    def createShapefile(self, outputValues, filename):
        layerFields = QgsFields()
        layerFields.append(QgsField('x', QVariant.Double))            
        layerFields.append(QgsField('y', QVariant.Double))         
        layerFields.append(QgsField('id', QVariant.Int))
        layerFields.append(QgsField('name', QVariant.String))   
        layerFields.append(QgsField('value', QVariant.Int))  
        layerFields.append(QgsField('boundary', QVariant.Double))  
        layerFields.append(QgsField('id_subcat', QVariant.Int))     
        
        writer = QgsVectorFileWriter(filename, 'UTF-8', layerFields, QgsWkbTypes.Point, QgsCoordinateReferenceSystem(self.dialog.crs), 'ESRI Shapefile')
        feat = QgsFeature()
        
        num = 1
        new_tag_name = ""
        point_value = self.dialog.PointBox.value()
        water_boundary = self.dialog.boundaryBox.value()
        feature_count = 0
        for name, id ,valueList, lon, lat, id_sub in zip(outputValues['name'], 
                                                outputValues['id'], 
                                                outputValues['valueList'], 
                                                outputValues['lon'], 
                                                outputValues['lat'],
                                                outputValues['id_sub']):   
            if valueList != new_tag_name:
                new_tag_name = valueList
                num = 1
            if name == new_tag_name:
                name = f"{name}_{num}"
                num += 1    

            pt = self.dialog.coordinateTransform(lon,lat,False)
            feat.setGeometry(QgsGeometry.fromPointXY(pt))
            feat.setAttributes([pt.x(), pt.y(), id, name, point_value, water_boundary, id_sub]) 
            writer.addFeature(feat)
            feature_count += 1
        layer = self.iface.addVectorLayer(filename, '', 'ogr')
        del(writer)
        return feature_count
 
    def creatTextFile(self, outputValues, filename, subcategory):
        sub_output = {"id": [], "name": []}

        with open(filename, 'w') as f:
            f.write("#########################################\n")
            f.write("# SC - Special Risk Object point set for the damage module of ProMaIDes\n")
            f.write("# Each point (location defined by x- y- coordinates) gets a category and a score value.\n") 
            f.write("# If the point is affected by a flood the score value is counted.\n") 
            f.write("# Moreover, the name and the sub-category ID can be specified. The number of points in\n")
            f.write("# the file must be defined at the beginning of the point list.\n") 
            f.write("#\n") 
            f.write("# Explanation of point data:\n") 
            f.write("#	- Data block starts with !BEGIN\n")
            f.write("#   - Total number of points in file\n") 
            f.write("#	- Per line the point data:\n") 	
            f.write("#		- x-coordinate of the point [m]\n") 	
            f.write("#		- y-coordinate of the point [m]\n")
            f.write("#		- Category ID of the point [-]\n")	
            f.write("#		- Score value (importance) per point [-]\n")
            f.write("#		- Water level boundary for failure per point [m]\n")
            f.write("#		- Name\n")  	
            f.write("#		- Subcategory ID of the point [-, optional]; specify the subcategories in an separated file (only used for visualization purpose)\n")
            f.write("#	- dData blocks ends with !END\n")
            f.write("#\n")	
            f.write("# Available implemented categories of points:\n")
            f.write("# ID specification score (select site-specific score)\n")
            f.write("#	1	 Public buildings\n")						
            f.write("#	2	 Ecologic hazardous sites or buildings\n")			
            f.write("#	3	 Cultural heritage\n")								
            f.write("#  4  	 Buildings with highly vulnerable people\n")			
            f.write("#\n")
            f.write("# Syntax:		- Comments are marked with: #\n")
            f.write("#				- Keywords for the type are case-sensitive\n")
            f.write("#				- Delimiter between values are whitespace(s) or tab(s)\n")
            f.write("#				- Each function have to end with the keyword !END\n")
            f.write("#				- Name can not include any whitespaces or tabs or any special characters\n")
            f.write("#########################################\n\n")
            f.write("!BEGIN\n")
            f.write("#total number of points in file\n")

            f.write(f"{len(outputValues['name'])}\n")
            f.write("#x[m] y[m] Category_Id Score-value Boundary-value [water_depth m] Name Subcategory_Id (file subcategories)\n")

            num = 1
            new_tag_name = ""
            point_value = self.dialog.PointBox.value()
            water_boundary = self.dialog.boundaryBox.value()
            feature_count = 0
            for name, id ,value, lon, lat, id_sub in zip(outputValues['name'], 
                                                    outputValues['id'], 
                                                    outputValues['valueList'], 
                                                    outputValues['lon'], 
                                                    outputValues['lat'],
                                                    outputValues['id_sub']):   
                if value != new_tag_name:
                    new_tag_name = value
                    num = 1
                if name == new_tag_name:
                    name = f"{name}_{num}"
                    num += 1  

                if not id_sub in sub_output['id']:
                    sub_output['id'].append(id_sub)
                    sub_output['name'].append(value)

                pt = self.dialog.coordinateTransform(lon,lat,False)

                f.write(f"{pt.x()} {pt.y()} {id} {point_value} {water_boundary} {name} {id_sub} \n")
                feature_count += 1
            f.write("!END")

        with open(subcategory, 'w') as f:
            f.write("########################################\n")
            f.write("# SC - Special Risk Object subcategory set for the damage module of ProMaIDes\n")
            f.write("# Here the subcategories for the Special Risk Object Points are defined by the user.\n") 
            f.write("# They are connected and used for visualization purpose only.\n")
            f.write("#\n")
            f.write("# Explanation of subcategory data:\n")
            f.write("#	- Data block starts with !BEGIN\n")
            f.write("#   - Total number of subcategories in file\n") 
            f.write("#	- Per line the subcategory data:\n")
            f.write("#		- ID of the subcategory (no duplicates are allowed)\n")
            f.write("#		- Name of the subcategory \n")
            f.write("#\n") 
            f.write("# Please chose/add your required sub-catebories.\n")
            f.write("#\n")
            f.write("# Syntax:		- Comments are marked with: #\n")
            f.write("#				- Keywords for the type are case-sensitive\n")
            f.write("#				- Delimiter between values are whitespace(s) or tab(s)\n")
            f.write("#				- Each function has to end with the keyword !END\n")
            f.write("#				- Name can not include any whitespaces or tabs or any special characters\n")
            f.write("#\n")
            f.write("########################################\n")
            f.write("!BEGIN\n")
            f.write("#total number of points in file\n")
            
            f.write(f"{len(sub_output['id'])}\n")
            f.write("#id name\n")

            for id, name in zip(sub_output['id'], sub_output['name']):
                f.write(f"{id} {name} \n")

            f.write("END!")

        return feature_count

    def creatSearchList(self):
        osm_dict = {'key':[], 'value':[], 'id': [], 'id_sub': []}
        if self.dialog.checkBox_fire_station.isChecked():
            osm_dict['key'].append('amenity')
            osm_dict['value'].append('fire_station')
            osm_dict['id'].append(1)
            osm_dict['id_sub'].append(1)

        if self.dialog.checkBox_government.isChecked():
            osm_dict['key'].append('office')
            osm_dict['value'].append('government')
            osm_dict['id'].append(1)
            osm_dict['id_sub'].append(2)

            osm_dict['key'].append('amenity')
            osm_dict['value'].append('townhall')
            osm_dict['id'].append(1)
            osm_dict['id_sub'].append(3)

        if self.dialog.checkBox_police.isChecked():
            osm_dict['key'].append('amenity')
            osm_dict['value'].append('police')
            osm_dict['id'].append(1)
            osm_dict['id_sub'].append(4)

        if self.dialog.checkBox_wastewater.isChecked():
            osm_dict['key'].append('man_made')
            osm_dict['value'].append('wastewater_plant')
            osm_dict['id'].append(2)
            osm_dict['id_sub'].append(5)

        if self.dialog.checkBox_chemical.isChecked():
            osm_dict['key'].append('industrial')
            osm_dict['value'].append('chemical')
            osm_dict['id'].append(2)
            osm_dict['id_sub'].append(6)

        if self.dialog.checkBox_biogas.isChecked():
            osm_dict['key'].append('plant:source')
            osm_dict['value'].append('biomass')
            osm_dict['id'].append(2)
            osm_dict['id_sub'].append(7)

        if self.dialog.checkBox_monuments.isChecked():
            osm_dict['key'].append('historic')
            osm_dict['value'].append('memorial')
            osm_dict['id'].append(3)
            osm_dict['id_sub'].append(8)

            osm_dict['key'].append('historic')
            osm_dict['value'].append('monument')
            osm_dict['id'].append(3)
            osm_dict['id_sub'].append(9)

        if self.dialog.checkBox_museum.isChecked():
            osm_dict['key'].append('tourism')
            osm_dict['value'].append('museum')
            osm_dict['id'].append(3)
            osm_dict['id_sub'].append(10)

        if self.dialog.checkBox_worship.isChecked():
            osm_dict['key'].append('amenity')
            osm_dict['value'].append('place_of_worship')
            osm_dict['id'].append(3)
            osm_dict['id_sub'].append(11)

        if self.dialog.checkBox_eldery.isChecked():
            osm_dict['key'].append('social_facility')
            osm_dict['value'].append('nursing_home')
            osm_dict['id'].append(4)
            osm_dict['id_sub'].append(12)

        if self.dialog.checkBox_hospitals.isChecked():
            osm_dict['key'].append('amenity')
            osm_dict['value'].append('hospital')
            osm_dict['id'].append(4)
            osm_dict['id_sub'].append(12)

            osm_dict['key'].append('amenity')
            osm_dict['value'].append('clinic')
            osm_dict['id'].append(4)
            osm_dict['id_sub'].append(13)

        if self.dialog.checkBox_kindergarten.isChecked():
            osm_dict['key'].append('amenity')
            osm_dict['value'].append('kindergarten')
            osm_dict['id'].append(4)
            osm_dict['id_sub'].append(14)

        if self.dialog.checkBox_schools.isChecked():
            osm_dict['key'].append('amenity')
            osm_dict['value'].append('school')
            osm_dict['id'].append(4)
            osm_dict['id_sub'].append(15)
        return osm_dict
   
    def query(self):
        osm_dict = self.creatSearchList()
        north, east, south, west = self.direction()
        overpass_url = "https://lz4.overpass-api.de/api/interpreter"
        dataList = []
        valueList = []  
        idList = []   
        id_subList = []
        keys, values, ids, is_subs = osm_dict.values()
        n = 0
        for key, value, id, id_sub in zip(keys, values, ids, is_subs):
            while n <= 100:
                overpass_query = """
                [out:json];
                (
                node["{key}"="{value}"]({south},{west},{north},{east});
                way["{key}"="{value}"]({south},{west},{north},{east});
                relation["{key}"="{value}"]({south},{west},{north},{east});
                );
                out center;
                """.format(key=key, value=value, south=south, west=west, north=north, east=east)

                try:
                    response = requests.get(overpass_url, params={'data': overpass_query})
                    data = response.json()
                    for _ in range(len(data['elements'])):
                        valueList.append(value)
                        idList.append(id)
                        id_subList.append(id_sub)
                    dataList.append(data)
                    break
                except:
                    n += 1
                    if n == 100:
                        print("abort")
    
        return dataList, valueList, idList, id_subList
            
    def checkValues(self, inputValues):
        for osm_id in inputValues["osm_id"]:
            location = [i for i,x in enumerate(inputValues["osm_id"]) if x==osm_id]
            while len(location) > 1:
                del inputValues["name"][location[1]]
                del inputValues["id"][location[1]]
                del inputValues['valueList'][location[1]]
                del inputValues['lon'][location[1]]
                del inputValues['lat'][location[1]]
                del inputValues['osm_id'][location[1]]
                del inputValues['id_sub'][location[1]]
                location = [i for i,x in enumerate(inputValues["osm_id"]) if x==osm_id]
        outputValues = inputValues
        return outputValues