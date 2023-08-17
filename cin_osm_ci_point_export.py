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
from .environment import get_json_path

# system modules
import webbrowser

#general
import time
import requests
import json
import os
import itertools

UI_PATH = get_ui_path('ui_cin_2promaides_osm_point_export.ui')
JSON_PATH = get_json_path("CIN_sectors.json")

OVERPASS_URL = "https://lz4.overpass-api.de/api/interpreter"

#Load all sectors with corosponding OSM Key, Value as Dict
with open(JSON_PATH, 'r') as f:
        CIN_SECTORS: dict = json.load(f)

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
        self.searchLayerExisting = len(QgsProject.instance().mapLayersByName(self.areaName)) != 0

        self.Layer_ComboBox.setFilters(QgsMapLayerProxyModel.PolygonLayer)

        self.groupBox_searchArea.toggled.connect(lambda checked: self.groupBox_selectLayer.setChecked(not checked))
        self.groupBox_selectLayer.toggled.connect(lambda checked: self.groupBox_searchArea.setChecked(not checked))

    def closeEvent(self, event):
        self.ClosingSignal.emit()
    
    def Help(self):
        webbrowser.open("https://promaides.myjetbrains.com/youtrack/articles/PMDP-A-81/DAM-CIN---OSM-CI-Point-Export")

    def onBrowseButtonClicked(self):
        current_filename = self.filename_edit.text()
        new_filename, __ = QFileDialog.getSaveFileName(self.iface.mainWindow(), 'OSM CI Point Export', current_filename, "*.shp *.SHP")
        if new_filename != '':
            self.filename_edit.setText(new_filename)
            self.filename_edit.editingFinished.emit()
    
    def searchWidget(self):
        self.sectorList = ['Electricity', 'Information technology', 'Water supply', 'Water treatment', 'Emergency service', 'Health and Care System', 'Transport and logistics goods', 
        'Transport and logistics person', 'Official and Governmental Institutions', 'Hazardous Materials', 'Industry and Production sites', 'Cultural or Religious sites', 'Education']
        #Get the name of the sectors -> names are the keys of the dict
        self.sectorList = list(CIN_SECTORS.keys())
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

class CINPointExport(object):

    def __init__(self, iface):
        self.iface = iface
        self.dialog = None
        self.cancel = False
        self.act = QAction('CIN OSM CI Point Export', iface.mainWindow())
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
        return
    
    def verification(self):
        if not self.dialog.filename_edit.text():
            self.iface.messageBar().pushCritical(
                'OSM CI Point Export',
                'No output filename given!'
            )
            self.quitDialog()
        elif self.dialog.listWidget_search.count() == 0:
            self.iface.messageBar().pushCritical(
                'OSM CI Point Export',
                'No Sector chosen!'
            )
            self.quitDialog()
        elif not hasattr(self.dialog, "geom") and not self.dialog.groupBox_selectLayer.isChecked():
            self.iface.messageBar().pushCritical(
                'OSM CI Point Export',
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
            features = layer.getFeatures()
            for feature in features:
                if feature.geometry():
                    return feature.geometry()


    def execTool(self):
        start_time = time.time()
        search = []
        rows = self.dialog.listWidget_search.count()
        for row in range(rows):
            item = self.dialog.listWidget_search.item(row)
            search.append(item.text())
        
        data = self.query(self.geometry(), search)

        #if data is a nDim list n > 1 merge data to a single list 
        if isinstance(data[0], list):
            data = itertools.chain(*data)

        points = dict()

        for element in data:
            point = OSMPoint(element, search)

            # add Point to coresponding sec id in dict (unsorted)
            if point.secId in points:
                points[point.secId].append(point)
            else:
                points[point.secId] = [point]

        #Sort Points Dict after Sec Id -> 1:[],2:[],3:[]...
        dictKeys = list(points.keys())
        dictKeys.sort()
        sortedPoints = {i: points[i] for i in dictKeys}
        
        #Sort the elements in the list for every sector after the name
        for idx, value in sortedPoints.items():
            sortedElemnts = sorted(value, key=lambda x: x.name, reverse=True)
            sortedPoints[idx] = sortedElemnts

        # get the len of the results of every sector. get the longest result of a sector
        maxLength = max(map(len, sortedPoints.values()))

        # e.g. zeropoins 2 -> sec 1: 101 ... 199, sec 10: 1001 ... 1099 
        # zeropoints 3 -> sec 1: 1001 ... 1999, sec 11: 11001 ... 11999
        zeropoint = len(str(maxLength))


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

        feature_count = 0
        for secId, points in sortedPoints.items():
            lookupDoubleName = set()
            lookupCounter = dict()
            lookupCounterPos = 0

            for count, point in enumerate(points, start=1):
                idx = secId * (10**zeropoint) + count
                pt = self.dialog.coordinateTransform(point.lon,point.lat,False)
                if self.geometry().contains(pt):
                    #create unique name of points with a value name
                    if not point.unique:
                        if point.name not in lookupDoubleName:
                            lookupCounterPos += 1
                            lookupCounter[lookupCounterPos] = 1
                            lookupDoubleName.add(point.name)
                        replace = f"{point.name}_{lookupCounter[lookupCounterPos]}"
                        lookupCounter[lookupCounterPos] += 1
                        point.name = replace

                    feat = QgsFeature()
                    feat.setGeometry(QgsGeometry.fromPointXY(pt))
                    attr = [idx, point.name, secId, point.value, 5, 0.2, "true", 14, 0, point.osmId]
                    feat.setAttributes(attr)
                    writer.addFeature(feat)
                    feature_count += 1

        layer = self.iface.addVectorLayer(fn, '', 'ogr')
        del(writer)
        end_time = time.time()
        length = round(end_time-start_time,2)
        self.iface.messageBar().pushInfo(
            'OSM CI Point Export',
            f'Export finished successfully! {feature_count} Points in {length} sec. found.')
           
        self.quitDialog()
         
    def query(self, geom, search: list, recursion = 0):
        north, east, south, west = self.direction(geom)
        nodes = ""
        ways = ""
        realations = ""
        for sector in search:
            keys, values = CIN_SECTORS[sector]["key"], CIN_SECTORS[sector]["value"]
        
            for key, value in zip(keys, values):
                nodes += f"""node["{key}"="{value}"]({south},{west},{north},{east});\n"""
                ways += f""" way["{key}"="{value}"]({south},{west},{north},{east});\n"""
                realations += f"""relation["{key}"="{value}"]({south},{west},{north},{east});\n"""
        overpass_query = f"""
                    [out:json];
                    (
                    {nodes}
                    {ways}
                    {realations}
                    );
                    out center;
                    """
        trys = 0
        while trys < 100:
            response = requests.post(OVERPASS_URL, data={"data": overpass_query})
            if response.status_code == 200:
                result = response.json()
               
                #'remark': runtime error
                if "remark" not in result:
                    return list(result["elements"])
                else:
                    print(f"Begin Recoursion {recursion}")
                    """
                    If the area of the request is to large there is no return 
                    """
                    #begin reqursion
                    #QgsGeometry(geom) creat a copy of geom object
                    data = [
                        self.query(self.split(QgsGeometry(geom), left=True), search, recursion+1),
                        self.query(self.split(QgsGeometry(geom), left=False), search, recursion+1)
                    ]
                    return data
            else:
                trys += 1
    
    def direction(self, geom):
        boundingBox = geom.boundingBox()

        pt = self.dialog.coordinateTransform(boundingBox.xMinimum(), boundingBox.yMinimum(), True)
        west = pt.x()
        south = pt.y()
        
        pt = self.dialog.coordinateTransform(boundingBox.xMaximum(), boundingBox.yMaximum(), True)
        east = pt.x()
        north = pt.y()
        
        return north, east, south, west 
    
    #split the geometry in half (vertical)
    def split(self, geom, left):
        # from QgsGeometry -> QgsRectangle
        rect = geom.boundingBox()
        #get corners
        xmin, xmax = rect.xMinimum(), rect.xMaximum()
        ymin, ymax = rect.yMinimum(), rect.yMaximum()
        #create corner points
        lt = QgsPointXY(xmin, ymax)
        ld = QgsPointXY(xmin, ymin)
        rt = QgsPointXY(xmax, ymax)
        rd = QgsPointXY(xmax, ymin)

        #get center of top end bottom line
        bottomLine = QgsGeometry.fromPolylineXY([ld, rd])
        length = bottomLine.length()
        bottomPoint = bottomLine.interpolate(length/2.0).asPoint()

        topLine = QgsGeometry.fromPolylineXY([lt, rt])
        length = topLine.length()
        topPoint = topLine.interpolate(length/2.0).asPoint()

        """
        if left -> down to up
        else up to down
        """
        if left:
            #split to left
            splitLine = [bottomPoint, topPoint]
        else:
            #split to right
            splitLine = [topPoint, bottomPoint]

        #-> Tuple[QgsGeometry.OperationResult, List[QgsGeometry] = 1Dim, List[QgsPointXY]] = empty
        res, geom, topolist = geom.splitGeometry(splitLine, False)
        return geom[0]

class OSMPoint:
    def __init__(self, data, searchFor):       
        self.get_infos(data, searchFor)
        self.set_coord(data)
        self.set_name(data)

    def get_infos(self, data, searchFor):
        self.key = ""
        self.value = ""
        self.secId = ""
        self.osmId = ""

        if 'tags' not in data:
            return None
        
        for itemKey, itemValue in data["tags"].items():
            for sector in searchFor:
                values = CIN_SECTORS[sector]["value"]
                if itemValue in values:
                    self.key = itemKey
                    self.value = itemValue
                    self.secId = CIN_SECTORS[sector]["sec_id"]
        
        typ = str(data['type'])
        id = str(data['id'])
        self.osmId = typ +"/"+ id
    
    def set_coord(self, data):
        if 'center' in data:
            self.lon = data['center']['lon']
            self.lat = data['center']['lat']
        else:
            self.lon = data['lon']
            self.lat = data['lat']
    
    def set_name(self, data):
        self.unique = True
        if 'tags' in data:
            if 'name' in data['tags']:
                self.name = data['tags']['name'] 
                self.name = self.name.replace("\n","_").replace(" ", "_")      
            else:
                self.name = self.value
                self.unique = False
