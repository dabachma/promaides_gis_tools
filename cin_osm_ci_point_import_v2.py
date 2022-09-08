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

UI_PATH = get_ui_path('ui_cin_2promaides_osm_point_import_v2.ui')

class PluginDialog(QDialog):

    ClosingSignal = pyqtSignal()

    def __init__(self, iface, parent=None, flags=Qt.WindowFlags()):
        QDialog.__init__(self, parent, flags)
        uic.loadUi(UI_PATH, self)
        self.iface = iface

        self.browse_button.clicked.connect(self.onBrowseButtonClicked)
        self.add_button.clicked.connect(self.addOne)
        self.addAll_button.clicked.connect(self.addAll)
        self.clear_button.clicked.connect(self.clear)
        self.clearAll_button.clicked.connect(self.clearAll)
        self.button_searchArea.clicked.connect(self.enableMapPicker)
        self.listWidget_sectors.itemDoubleClicked.connect(self.addOne)
        self.listWidget_search.itemDoubleClicked.connect(self.clear)

        self.picker = QgsMapToolEmitPoint(self.iface.mapCanvas())

        project = QgsProject.instance()
        self.crs = project.crs()
        self.HelpButton.clicked.connect(self.Help)

        self.searchWidget()

        #self variables 
        self.areaName = "Search Area"

        self.Layer_ComboBox.setFilters(QgsMapLayerProxyModel.PolygonLayer)

        self.groupBox_searchArea.toggled.connect(lambda checked: self.groupBox_selectLayer.setChecked(not checked))
        self.groupBox_selectLayer.toggled.connect(lambda checked: self.groupBox_searchArea.setChecked(not checked))

    def closeEvent(self, event):
        self.ClosingSignal.emit()
    
    def Help(self):
        webbrowser.open("https://promaides.myjetbrains.com/youtrack/articles/PMDP-A-81/DAM-CIN---OSM-CI-Point-Import")

    def onBrowseButtonClicked(self):
        current_filename = self.filename_edit.text()
        new_filename, __ = QFileDialog.getSaveFileName(self.iface.mainWindow(), 'OSM CI Point Import', current_filename, "*.shp *.SHP")
        if new_filename != '':
            self.filename_edit.setText(new_filename)
            self.filename_edit.editingFinished.emit()
    
    def searchWidget(self):
        self.sectorList = ['Electricity', 'Information technology', 'Water supply', 'Water treatment', 'Emergency service', 'Health and Care System', 'Transport and logistics goods', 
        'Transport and logistics person', 'Official and Governmental Institutions', 'Hazardous Materials', 'Industry and Production sites', 'Cultural or Religious sites', 'Education']

        self.listWidget_sectors.addItems(self.sectorList)
    
    def addOne(self):
        for item in self.listWidget_sectors.selectedItems():
            if not self.listWidget_search.findItems(item.text(), Qt.MatchExactly | Qt.MatchRecursive):
                self.listWidget_search.addItem(item.text())
    
    def addAll(self):
        self.listWidget_search.clear()
        self.listWidget_search.addItems(self.sectorList)

    def clear(self):
        for item in self.listWidget_search.selectedItems():
            row = self.listWidget_search.row(item)
            self.listWidget_search.takeItem(row)

    def clearAll(self):
        self.listWidget_search.clear()                 

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

class CINPointImport(object):

    def __init__(self, iface):
        self.iface = iface
        self.dialog = None
        self.cancel = False
        self.act = QAction('CIN OSM CI Point Import', iface.mainWindow())
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
        self.dialog.deleteShapefile(self.dialog.areaName)
        self.iface.mapCanvas().unsetMapTool(self.dialog.picker)
        self.act.setEnabled(True)
        self.cancel = False
        self.dialog.close()
    
    def verification(self):
        if not self.dialog.filename_edit.text():
            self.iface.messageBar().pushCritical(
                'OSM CI Point Import',
                'No output filename given!'
            )
            self.quitDialog()
        elif self.dialog.listWidget_search.count() == 0:
            self.iface.messageBar().pushCritical(
                'OSM CI Point Import',
                'No Sector chosen!'
            )
            self.quitDialog()

        elif not QgsProject.instance().mapLayersByName("Search Area") and self.dialog.groupBox_searchArea.isChecked():
            self.iface.messageBar().pushCritical(
                'OSM CI Point Import',
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
        searchList = []
        rows = self.dialog.listWidget_search.count()
        for row in range(rows):
            item = self.dialog.listWidget_search.item(row)
            searchList.append(item.text())

        fn = self.dialog.filename_edit.text()

        layerFields = QgsFields()
        layerFields.append(QgsField('point_id', QVariant.Int))            
        layerFields.append(QgsField('point_name', QVariant.String))       
        layerFields.append(QgsField('sec_id', QVariant.Int))        
        layerFields.append(QgsField('value_name', QVariant.String))   
        layerFields.append(QgsField('sec_level', QVariant.Int))     
        layerFields.append(QgsField('boundary_v', QVariant.Double))    
        layerFields.append(QgsField('regular_fl', QVariant.String))    
        layerFields.append(QgsField('recovery_t', QVariant.Double)) 
        layerFields.append(QgsField('activation_t', QVariant.Double))     
        layerFields.append(QgsField('osm_id', QVariant.String))     
        
        writer = QgsVectorFileWriter(fn, 'UTF-8', layerFields, QgsWkbTypes.Point, QgsCoordinateReferenceSystem(self.dialog.crs), 'ESRI Shapefile')
        feat = QgsFeature()
        
        inputValues = {"name":[], "sec_id":[], "valueList":[], "lon":[], "lat":[], "osm_id":[]}
        
        #Multiprocessing 
        with Pool(10) as p:
            all_sectors = p.map(self.query, searchList)

        max_lenght = 0
        for sector in all_sectors:
            sector_result, sec_id, valueList = sector
            sector_lenght = 0
            for result in sector_result:   #goes through all results of a sector
                sector_lenght += len(result['elements'])

                for element in result['elements']:    #goes through all elements in the value
                    value_name = valueList.pop(0)
                    
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
                    
                    typ = str(element['type'])
                    id = str(element['id'])
                    osm_id = typ +"/"+ id

                    pt = self.dialog.coordinateTransform(lon,lat,False)

                    if self.geometry().contains(pt):
                        inputValues['name'].append(name)
                        inputValues['sec_id'].append(sec_id)
                        inputValues['valueList'].append(value_name)
                        inputValues['lon'].append(lon)
                        inputValues['lat'].append(lat)
                        inputValues['osm_id'].append(osm_id)
            if sector_lenght >= max_lenght:
                max_lenght = sector_lenght
        
        num = 1
        new_tag_name = ""
        old_sec_id = ""
        outputValues = self.checkValues(inputValues)
        multiplier = len(str(max_lenght))
        feature_count = 0
        for name, sec_id ,value, lon, lat, osm_id in zip(outputValues['name'], 
                                                        outputValues['sec_id'], 
                                                        outputValues['valueList'], 
                                                        outputValues['lon'], 
                                                        outputValues['lat'],
                                                        outputValues['osm_id']):   
            if sec_id != old_sec_id:
                old_sec_id = sec_id
                idx = 1
            idx_sec = sec_id * (10**multiplier)
            idx_num = idx_sec + idx
            idx += 1
            
            if value != new_tag_name:
                new_tag_name = value
                num = 1
            if name == new_tag_name:
                name = f"{name}_{num}"
                num += 1    

            pt = self.dialog.coordinateTransform(lon,lat,False)
            feat.setGeometry(QgsGeometry.fromPointXY(pt))
            feat.setAttributes([idx_num, name, sec_id, value, 5, 0.2, "true", 14, 0, osm_id]) 
            writer.addFeature(feat)
            feature_count += 1
        layer = self.iface.addVectorLayer(fn, '', 'ogr')

        del(writer)
        end_time = time.time()
        length = round(end_time-start_time,2)

        self.iface.messageBar().pushInfo(
            'OSM CI Point Import',
            f'Inport finished successfully! {feature_count} Points in {length} sec. found.')
           
        self.quitDialog()
   
    def query(self, search):
        north, east, south, west = self.direction()
        overpass_url = "https://lz4.overpass-api.de/api/interpreter"
        osm_dict = {'key':[], 'value':[]}
        dataList = []
        valueList = []     

        if search == 'Electricity':
            osm_dict['key'].append('power')
            osm_dict['value'].append('plant')

            osm_dict['key'].append('power')
            osm_dict['value'].append('substation')

            osm_dict['key'].append('power')
            osm_dict['value'].append('transformer')
            
            sec_id = 1
        if search == 'Information technology':
            osm_dict['key'].append('man_made')
            osm_dict['value'].append('antenna')

            osm_dict['key'].append('tower:type')
            osm_dict['value'].append('communication')

            osm_dict['key'].append('amenity')
            osm_dict['value'].append('telephone')

            osm_dict['key'].append('studio')
            osm_dict['value'].append('radio')

            osm_dict['key'].append('studio')
            osm_dict['value'].append('televison')
            
            sec_id = 2
        if search == 'Water supply':
            osm_dict['key'].append('man_made')
            osm_dict['value'].append('water_works')

            osm_dict['key'].append('man_made')
            osm_dict['value'].append('water_tower')

            osm_dict['key'].append('man_made')
            osm_dict['value'].append('water_well')

            osm_dict['key'].append('man_made')
            osm_dict['value'].append('reservoir_covered')
            
            sec_id = 3  
        if search == 'Water treatment':
            osm_dict['key'].append('man_made')
            osm_dict['value'].append('wastewater_plant')
            
            sec_id = 4
            
        if search == 'Emergency service':
            osm_dict['key'].append('amenity')
            osm_dict['value'].append('police')

            osm_dict['key'].append('amenity')
            osm_dict['value'].append('fire_station')

            osm_dict['key'].append('emergency')
            osm_dict['value'].append('ambulance_station')

            #different approches for disaster response 
            osm_dict['key'].append('emergency_service')
            osm_dict['value'].append('technical')

            osm_dict['key'].append('amenity')
            osm_dict['value'].append('emergency_service')

            osm_dict['key'].append('emergency')
            osm_dict['value'].append('disaster_response')

            sec_id = 10
        if search == 'Health and Care System':
            osm_dict['key'].append('amenity')
            osm_dict['value'].append('hospital')

            osm_dict['key'].append('amenity')
            osm_dict['value'].append('clinic')

            osm_dict['key'].append('amenity')
            osm_dict['value'].append('pharmacy')

            osm_dict['key'].append('amenity')
            osm_dict['value'].append('doctors')

            osm_dict['key'].append('social_facility')
            osm_dict['value'].append('nursing_home')

            sec_id = 11
        if search == 'Transport and logistics goods':
            osm_dict['key'].append('industrial')
            osm_dict['value'].append('port')

            sec_id = 12
        if search == 'Transport and logistics person':
            osm_dict['key'].append('amenity')
            osm_dict['value'].append('bus_station')

            osm_dict['key'].append('railway')
            osm_dict['value'].append('station')
            
            osm_dict['key'].append('aeroway')
            osm_dict['value'].append('aerodrome')
            
            osm_dict['key'].append('aeroway')
            osm_dict['value'].append('helipad')

            osm_dict['key'].append('leisure')
            osm_dict['value'].append('marina')
            
            osm_dict['key'].append('amenity')
            osm_dict['value'].append('ferry_terminal')
            
            sec_id = 13
        if search == 'Official and Governmental Institutions':
            osm_dict['key'].append('amenity')
            osm_dict['value'].append('prison')

            osm_dict['key'].append('amenity')
            osm_dict['value'].append('courthouse')
            
            osm_dict['key'].append('government') 
            osm_dict['value'].append('ministry')

            osm_dict['key'].append('office')
            osm_dict['value'].append('government')

            osm_dict['key'].append('amenity')
            osm_dict['value'].append('townhall')
            
            sec_id = 14          
        if search == 'Hazardous Materials':
            osm_dict['key'].append('amenity')
            osm_dict['value'].append('fuel')
            
            sec_id = 15
        if search == 'Industry and Production sites':
            osm_dict['key'].append('industrial')
            osm_dict['value'].append('oil')
            
            osm_dict['key'].append('industrial')
            osm_dict['value'].append('factory')

            osm_dict['key'].append('industrial')
            osm_dict['value'].append('warehouse')

            osm_dict['key'].append('industrial')
            osm_dict['value'].append('mine')

            osm_dict['key'].append('landuse')
            osm_dict['value'].append('quarry')

            sec_id = 16
        if search == 'Cultural or Religious sites':
            osm_dict['key'].append('amenity')
            osm_dict['value'].append('place_of_worship')
            
            sec_id = 17
        if search == 'Education':
            osm_dict['key'].append('amenity')
            osm_dict['value'].append('school')

            osm_dict['key'].append('amenity')
            osm_dict['value'].append('kindergarten')

            osm_dict['key'].append('amenity')
            osm_dict['value'].append('college')

            osm_dict['key'].append('amenity')
            osm_dict['value'].append('university')

            sec_id = 18
        
        for key, value in zip(osm_dict['key'], osm_dict['value']):
            n = 0
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
                    dataList.append(data)
                    break
                except:
                    n += 1
                    if n == 100:
                        print("abort")
        
        return dataList, sec_id, valueList
            
    def checkValues(self, inputValues):
        for osm_id in inputValues["osm_id"]:
            location = [i for i,x in enumerate(inputValues["osm_id"]) if x==osm_id]
            while len(location) > 1:
                del inputValues["name"][location[1]]
                del inputValues["sec_id"][location[1]]
                del inputValues['valueList'][location[1]]
                del inputValues['lon'][location[1]]
                del inputValues['lat'][location[1]]
                del inputValues['osm_id'][location[1]]
                location = [i for i,x in enumerate(inputValues["osm_id"]) if x==osm_id]
        outputValues = inputValues
        return outputValues
