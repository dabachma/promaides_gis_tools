from __future__ import unicode_literals
from __future__ import absolute_import

# QGIS modules
from qgis.core import *
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import *
from qgis.PyQt import uic

# promaides modules
from .interpolate import RasterInterpolator
from .environment import get_ui_path

# system modules
import webbrowser

#general
from datetime import datetime
from .version import *


UI_PATH = get_ui_path('ui_cin_2promaides_polygon.ui')

# This plugin exports the noflow polygon file for the HYD-module of ProMaIdes from a polygon shape file;
# No field is required within the polygon layer
class PluginDialog(QDialog):

    def __init__(self, iface, parent=None, flags=Qt.WindowFlags()):
        QDialog.__init__(self, parent, flags)
        uic.loadUi(UI_PATH, self)

        self.iface = iface
        self.input_layer = None

        self.browse_button.clicked.connect(self.onBrowseButtonClicked)

        self.iface.currentLayerChanged.connect(self.setInputLayer)

        self.setInputLayer(self.iface.activeLayer())
        
        self.HelpButton.clicked.connect(self.Help)

    def __del__(self):
        self.iface.currentLayerChanged.disconnect(self.setInputLayer)

    def onBrowseButtonClicked(self):
        current_filename = self.filename_edit.text()
        new_filename, __ = QFileDialog.getSaveFileName(self.iface.mainWindow(), 'CIN Polygon Export', current_filename)
        if new_filename != '':
            self.filename_edit.setText(new_filename)
            self.filename_edit.editingFinished.emit()
   
    def Help(self):
        webbrowser.open("https://promaides.myjetbrains.com/youtrack/articles/PMDP-A-67/DAM-CIN---Polygon-Export")     
    
    def setInputLayer(self, layer):
        """
        """
        if not layer:
            self.input_layer = None
            self.input_label.setText('<i>No layer selected.<br>'
                                     'Please select a polygon layer.</i>')
        else:
            layer_name = layer.name()

            if layer.type() == QgsMapLayer.VectorLayer:

                if layer.geometryType() == QgsWkbTypes.PolygonGeometry:

                    self.input_layer = layer

                    if layer.selectedFeatureCount():
                        self.input_label.setText('<i>Input layer is "{}" with {} selected feature(s).</i>'
                                                 .format(layer_name, layer.selectedFeatureCount()))
                    else:
                        self.input_label.setText('<i>Input layer is "{}" with {} feature(s).</i>'
                                                 .format(layer_name, layer.featureCount()))

                else:
                    self.input_layer = None
                    self.input_label.setText('<i>Selected layer "{}" is not a polygon layer.<br>'
                                             'Please select a polygon layer.</i>'
                                             .format(layer_name))
            else:
                self.input_layer = None
                self.input_label.setText('<i>Selected layer "{}" is not a vector layer.<br>'
                                         'Please select a polygon layer.</i>'
                                         .format(layer_name))

        self.expression_field_names.setExpression("polygon_name")
        self.expression_field_ids.setExpression("polygon_id")
        self.expression_field_sectors.setExpression("sec_id")
        self.expression_field_endusers.setExpression("end_user")


        self.expression_field_names.setLayer(self.input_layer)
        self.expression_field_ids.setLayer(self.input_layer)
        self.expression_field_sectors.setLayer(self.input_layer)
        self.expression_field_endusers.setLayer(self.input_layer)

        self.updateButtonBox()

    def updateButtonBox(self):
        if self.input_layer: #and self.raster_layer:
            self.button_box.button(QDialogButtonBox.Ok).setEnabled(True)
        else:
            self.button_box.button(QDialogButtonBox.Ok).setEnabled(False)


class CINPolygonExport(object):

    def __init__(self, iface):
        self.iface = iface
        self.dialog = None
        self.cancel = False
        self.act = QAction('CIN Polygon Export', iface.mainWindow())
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
        self.dialog.expression_field_ids.setFilters(QgsFieldProxyModel.Int | QgsFieldProxyModel.LongLong | QgsFieldProxyModel.Double | QgsFieldProxyModel.String)
        self.dialog.expression_field_names.setFilters(QgsFieldProxyModel.Int | QgsFieldProxyModel.LongLong | QgsFieldProxyModel.Double | QgsFieldProxyModel.String)
        self.dialog.expression_field_sectors.setFilters(QgsFieldProxyModel.Int | QgsFieldProxyModel.LongLong | QgsFieldProxyModel.Double | QgsFieldProxyModel.String)
        self.dialog.expression_field_endusers.setFilters(QgsFieldProxyModel.Int | QgsFieldProxyModel.LongLong | QgsFieldProxyModel.Double | QgsFieldProxyModel.String)
        self.dialog.show()

    def scheduleAbort(self):
        self.cancel = True

    def quitDialog(self):
        self.dialog = None
        self.act.setEnabled(True)
        self.cancel = False

    def verificationInput(self):
        layer = self.iface.activeLayer()
        field_names = layer.fields().names()
        idx = layer.featureCount()
        ListIDs = []
        ListNames = []
        
        ids_field = self.dialog.expression_field_ids.currentText()       
        names_field = self.dialog.expression_field_names.currentText()
        sectors_field = self.dialog.expression_field_sectors.currentText()
        endusers_field = self.dialog.expression_field_endusers.currentText()
        
        try:
            ids_pos = field_names.index(ids_field)
        except:
            self.iface.messageBar().pushCritical("CIN Point Export","Field ID has no input")
            return False
        
        try:
            name_pos = field_names.index(names_field)                
        except:
            self.iface.messageBar().pushCritical("CIN Point Export","Field Name has no input")
            return False
       
        try:
            sector_pos = field_names.index(sectors_field)
        except:
            self.iface.messageBar().pushCritical("CIN Point Export","Field Sector has no input")
            return False
        
        try:              
            endusers_pos = field_names.index(endusers_field)
        except:
            self.iface.messageBar().pushCritical("CIN Point Export","Field End Users has no input")
            return False
        
        for x in range(0 , idx):
            attrs = layer.getFeature(x)
            ListIDs.append(attrs[ids_pos])
            ListNames.append(attrs[name_pos])

        for i in range(0 , idx):
            attrs = layer.getFeature(i)
            
            #ID controll
            if attrs[ids_pos] == NULL and attrs[name_pos] == NULL:
                self.iface.messageBar().pushCritical(
                    'CIN Point Export',
                    'There is a point without name and id')
                return False
            
            if attrs[ids_pos] == NULL:
                self.iface.messageBar().pushCritical(
                    'CIN Point Export',
                    'ID input of "{}" is NULL'.format(attrs[name_pos]))
                return False

            if not isinstance(attrs[ids_pos], int):
                self.iface.messageBar().pushCritical(
                    'CIN Point Export',
                    'ID input "{}" of "{}" is not a valid input (Required typ: Integer)'.format(attrs[ids_pos],attrs[name_pos]))              
                return False

            if ListIDs.count(attrs[ids_pos]) > 1:
                self.iface.messageBar().pushCritical(
                    'CIN Point Export',
                    'ID "{}" occurs multiple times'.format(attrs[ids_pos]))              
                return False 

            #name controll
            if attrs[name_pos] == NULL:
                self.iface.messageBar().pushCritical(
                    'CIN Point Export',
                    'Name input of ID "{}" is NULL'.format(attrs[ids_pos]))
                return False
            
            if not isinstance(attrs[name_pos], str):
                self.iface.messageBar().pushCritical(
                    'CIN Point Export',
                    'Name input "{}" of ID "{}" is not a valid input (Required typ: String) '.format(attrs[name_pos], attrs[ids_pos]))
                return False

            if ListNames.count(attrs[name_pos]) > 1:
                self.iface.messageBar().pushCritical(
                    'CIN Point Export',
                    'Name "{}" occurs multiple times'.format(attrs[name_pos]))              
                return False 
            
            #sector controll
            if not isinstance(attrs[sector_pos], int):
                self.iface.messageBar().pushCritical(
                    'CIN Point Export',
                    'Sector input "{}" of "{}" is not a valid input (Required typ: Integer)'.format(attrs[sector_pos],attrs[name_pos]))              
                return False
            
            if 1 <= attrs[sector_pos] <= 5 or 10 <= attrs[sector_pos] <= 18:
                pass
            else:
                self.iface.messageBar().pushCritical(
                    'CIN Point Export',
                    'Sector input of "{}" is not a valid sector'.format(attrs[name_pos]))
                return False
            
            #end user controll
            if attrs[endusers_pos] == NULL:
                self.iface.messageBar().pushCritical(
                    'CIN Point Export',
                    'End User input of "{}" is NULL'.format(attrs[name_pos]))
                return False
            
            if not isinstance(attrs[endusers_pos], float):
                self.iface.messageBar().pushCritical(
                    'CIN Point Export',
                    'End User input "{}" of "{}" is not a valid input (Required typ: Double)'.format(attrs[endusers_pos],attrs[name_pos]))              
                return False
        return True

    def execTool(self):
        if not self.verificationInput(): 
            self.quitDialog()
            return

        filename = self.dialog.filename_edit.text()
        if not filename:
            self.iface.messageBar().pushCritical(
                'Polygon Export',
                'No output filename given!'
            )
            self.quitDialog()
            return

        polygon_layer = self.dialog.input_layer
        if polygon_layer.selectedFeatureCount():
            only_selected = True
            features = polygon_layer.selectedFeatures()
            feature_count = polygon_layer.selectedFeatureCount()
        else:
            only_selected = False
            features = polygon_layer.getFeatures()
            feature_count = polygon_layer.featureCount()


        # labeling the input layer attributes to variables
        # the variable name is plural because all names are contained
        names, ok = QgsVectorLayerUtils.getValues(polygon_layer, self.dialog.expression_field_names.expression(),
                                                   only_selected)
        names = [x.replace(" ", "_") for x in names] # replacing empty spaces in name
        ids, ok = QgsVectorLayerUtils.getValues(polygon_layer, self.dialog.expression_field_ids.expression(),
                                                  only_selected)
        sectors, ok = QgsVectorLayerUtils.getValues(polygon_layer, self.dialog.expression_field_sectors.expression(),
                                                   only_selected)
        endusers, ok = QgsVectorLayerUtils.getValues(polygon_layer, self.dialog.expression_field_endusers.expression(),
                                                   only_selected)
        attributes = [names, ids, sectors, endusers]

        attribute = polygon_layer.attributeDisplayName(0)
        labels, ok = QgsVectorLayerUtils.getValues(polygon_layer, attribute, only_selected)

        if not ok:
             self.iface.messageBar().pushCritical(
                 'Polygon Export',
                 'Invalid expression for polygon labels!'
             )
             self.quitDialog()
             return

        progress = QProgressDialog('Exporting Polygon ...', 'Abort', 0, feature_count, self.iface.mainWindow())
        progress.setWindowTitle('Polygon Export')
        progress.canceled.connect(self.scheduleAbort)
        progress.show()

        # iterate over polygon features
        with open(filename, 'w') as polygon_file:

            index = 0
            polygon_file.write('########################################################################\n')
            polygon_file.write('# This file was automatically generated by "Polygon Export for ProMaiDes CIN Module"')
            polygon_file.write('Export-QGIS-Plugin Version {version_1} \n'.format(version_1=VERSION))
            #date and time output
            now = datetime.now()
            dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
            polygon_file.write('# Generated at {dt_string_1} '.format(dt_string_1=dt_string))
            polygon_file.write('from layer {filename_1} \n'.format(filename_1=polygon_layer.sourceName()))
            polygon_file.write('# Comments are marked with #\n')
            polygon_file.write('# There are three CI-elements:\n')
            polygon_file.write('# 1. Points; as in this file)\n')
            polygon_file.write('# 2. Connectors; linking Points with each other, multiple connectors in ''several directions are possible) \n')
            polygon_file.write('# 3. Polygons; mostly final elements\n')
            polygon_file.write('#\n')
            polygon_file.write('# Number of polygons in file: {}  \n'.format(feature_count))
            polygon_file.write('#\n')
            polygon_file.write('# These polygons are part of the critical infrastructure network (CIN); polygons are final elements that are no source for other elements\n')
            polygon_file.write('#\n')
            polygon_file.write('# Explanation of data:\n')
            polygon_file.write('#  Start the CI-polyggons with !BEGIN and end it with !END; in between are:\n')
            polygon_file.write('#  NumberOfPoints\n')
            polygon_file.write('#  id(unique) x-coordinate y-coordinate name(without_whitepace) sector[fixed_strings_abreviations?] level threshold_[m_-9999_nofailure] ''final(true:=final_false:=not_final)\n')
            polygon_file.write('#\n')
            polygon_file.write('# Infos to the sectors:\n')
            polygon_file.write('# - elect 	    := 1 = Electricity (e.g. Power Plants,High Voltage Transmitters, Low Voltage Transmitters)\n')
            polygon_file.write('# - infotec	    := 2 = Information technology (e.g. Radio Station, Landline, Mobile network Station)\n')
            polygon_file.write('# - eme_ser 	:= 3 = (Medical service, Police, Fire Brigade)\n')
            polygon_file.write('# - water_sup 	:= 4 = Water supply (e.g. Water Treatment System, Water Sources)\n')
            polygon_file.write('# - logi	    := 5 = Transport and logistics (Important traffic nodes, Harbors, Airports, Trainstations)\n')
            polygon_file.write('# - health	    := 6 = Health System (Hospitals, Doctors, Carement centers)\n')
            polygon_file.write('# - off_gov	    := 7 = Official and Governmental Institutions (Ministries, Town Halls, Prisons)\n')
            polygon_file.write('# - haz_mat	    := 8 = Hazardous Materials (e.g. Fuel Station, Storage for radioactive or toxic Waster)\n')
            polygon_file.write('# - prod 	    := 9 = Industry and Production sites (e.g. Factories, Mines)\n')
            polygon_file.write('# - culture	    := 0 = Cultural or Religious sites (Temples, Mosques, Churches etc.)\n')
            polygon_file.write('# \n')
            polygon_file.write('########################################################################\n')
            polygon_file.write('#number of polygons\n')
            polygon_file.write('{}\n\n'.format(feature_count))


            for feature, id, name, sector, enduser in zip(features, ids, names,sectors, endusers):
                points = []
                buff = feature.geometry()
                for p in buff.vertices():
                    points.append(p)

                for i in attributes:
                    if not i:
                        self.iface.messageBar().pushCritical(
                            'CIN Polygon Export',
                            'Polygon is missing an entry. Please assign and fill out the attributes:<br>'
                            ' name, id, sector, end users'
                            )
                        self.quitDialog()
                        return
                    if self.cancel:
                        break

                polygon_file.write('!BEGIN\n')
                polygon_file.write('{a} {b} {c} {d} {e}\n'.format
                 (a=str(id), b=len(points)-1, c=str(name), d=str(sector), e=str(enduser)))

                # iterate over points in polygon
                for point in points[:len(points)-1]:

                    polygon_file.write('{x} {y}\n'.format(x=point.x(), y=point.y()))

                polygon_file.write('!END\n\n')

                index += 1
                progress.setValue(index)

                if self.cancel:
                    break

        progress.close()

        #if not self.cancel:
        self.iface.messageBar().pushInfo(
            'Polygon Export',
            'Export finished successfully!'
           )

        self.quitDialog()
