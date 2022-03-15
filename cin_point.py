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

import operator

UI_PATH = get_ui_path('ui_cin_2promaides_point.ui')

# This plugin exports the CIs point element file for the DAM-CI-module of ProMaIdes from a point shape file;
# A name field (string) is required within the point layer
class PluginDialog(QDialog):

    def __init__(self, iface, parent=None, flags=Qt.WindowFlags()):
        QDialog.__init__(self, parent, flags)
        uic.loadUi(UI_PATH, self)
        self.iface = iface
        self.input_layer = None
        self.browse_button.clicked.connect(self.onBrowseButtonClicked)
        self.HelpButton.clicked.connect(self.Help)
        self.iface.currentLayerChanged.connect(self.setInputLayer)
        self.setInputLayer(self.iface.activeLayer())

    def __del__(self):
        self.iface.currentLayerChanged.disconnect(self.setInputLayer)

    def onBrowseButtonClicked(self):
        current_filename = self.filename_edit.text()
        new_filename, __ = QFileDialog.getSaveFileName(self.iface.mainWindow(), 'CIN Points Export', current_filename)
        if new_filename != '':
            self.filename_edit.setText(new_filename)
            self.filename_edit.editingFinished.emit()
            
    def Help(self):
        webbrowser.open("https://promaides.myjetbrains.com/youtrack/articles/PMDP-A-63/DAM-CI---Point-Export")

    def setInputLayer(self, layer):
        """
        """
        if not layer:
            self.input_layer = None
            self.input_label.setText('<i>No layer selected.<br>'
                                     'Please select a polypoint layer.</i>')
        else:
            layer_name = layer.name()

            if layer.type() == QgsMapLayer.VectorLayer:

                if layer.geometryType() == QgsWkbTypes.PointGeometry:

                    self.input_layer = layer

                    if layer.selectedFeatureCount():
                        self.input_label.setText('<i>Input layer is "{}" with {} selected feature(s).</i>'
                                                 .format(layer_name, layer.selectedFeatureCount()))
                    else:
                        self.input_label.setText('<i>Input layer is "{}" with {} feature(s).</i>'
                                                 .format(layer_name, layer.featureCount()))

                else:
                    self.input_layer = None
                    self.input_label.setText('<i>Selected layer "{}" is not a point layer.<br>'
                                             'Please select a polypoint layer.</i>'
                                             .format(layer_name))
            else:
                self.input_layer = None
                self.input_label.setText('<i>Selected layer "{}" is not a vector layer.<br>'
                                         'Please select a polypoint layer.</i>'
                                         .format(layer_name))

        self.expression_field_ids.setExpression("point_id")
        self.expression_field_names.setExpression("point_name")
        self.expression_field_sectors.setExpression("sec_id")
        self.expression_field_levels.setExpression("sec_level")
        self.expression_field_thresholds.setExpression("threshold")
        self.expression_field_regulars.setExpression("regular")
        self.expression_field_recoverys.setExpression("recovery")
        self.expression_field_actives.setExpression("activation")

        self.expression_field_names.setLayer(self.input_layer)
        self.expression_field_ids.setLayer(self.input_layer)
        self.expression_field_sectors.setLayer(self.input_layer)
        self.expression_field_levels.setLayer(self.input_layer)
        self.expression_field_thresholds.setLayer(self.input_layer)
        self.expression_field_regulars.setLayer(self.input_layer)
        self.expression_field_recoverys.setLayer(self.input_layer)
        self.expression_field_actives.setLayer(self.input_layer)

        self.updateButtonBox()

    def updateButtonBox(self):
        if self.input_layer: #and self.raster_layer:
            self.button_box.button(QDialogButtonBox.Ok).setEnabled(True)
        else:
            self.button_box.button(QDialogButtonBox.Ok).setEnabled(False)


class CINPointExport(object):

    def __init__(self, iface):
        self.iface = iface
        self.dialog = None
        self.cancel = False
        self.act = QAction('CIN Point Export', iface.mainWindow())
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

    def execDialog(self): #  add tooltips
        """
        """
        self.dialog = PluginDialog(self.iface, self.iface.mainWindow())
        self.dialog.accepted.connect(self.execTool)
        self.dialog.rejected.connect(self.quitDialog)
        self.dialog.setModal(False)
        self.act.setEnabled(False)
        # add a filter to the combo box of the filed selection; for "Name" just a string filed make sense
        self.dialog.expression_field_ids.setFilters(QgsFieldProxyModel.Int | QgsFieldProxyModel.LongLong | QgsFieldProxyModel.Double | QgsFieldProxyModel.String)
        self.dialog.expression_field_names.setFilters(QgsFieldProxyModel.Int | QgsFieldProxyModel.LongLong | QgsFieldProxyModel.Double | QgsFieldProxyModel.String)
        self.dialog.expression_field_sectors.setFilters(QgsFieldProxyModel.Int | QgsFieldProxyModel.LongLong | QgsFieldProxyModel.Double | QgsFieldProxyModel.String)
        self.dialog.expression_field_levels.setFilters(QgsFieldProxyModel.Int | QgsFieldProxyModel.LongLong | QgsFieldProxyModel.Double | QgsFieldProxyModel.String)
        self.dialog.expression_field_thresholds.setFilters(QgsFieldProxyModel.Int | QgsFieldProxyModel.LongLong | QgsFieldProxyModel.Double | QgsFieldProxyModel.String)
        self.dialog.expression_field_regulars.setFilters(QgsFieldProxyModel.Int | QgsFieldProxyModel.LongLong | QgsFieldProxyModel.Double | QgsFieldProxyModel.String) # try to change this to boolean in QT
        self.dialog.expression_field_recoverys.setFilters(QgsFieldProxyModel.Int | QgsFieldProxyModel.LongLong | QgsFieldProxyModel.Double | QgsFieldProxyModel.String)
        self.dialog.expression_field_actives.setFilters(QgsFieldProxyModel.Int | QgsFieldProxyModel.LongLong | QgsFieldProxyModel.Double | QgsFieldProxyModel.String)
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
        
        ids_field = self.dialog.expression_field_ids.currentText()       
        names_field = self.dialog.expression_field_names.currentText()
        sectors_field = self.dialog.expression_field_sectors.currentText()
        levels_field = self.dialog.expression_field_levels.currentText()
        thresholds_field = self.dialog.expression_field_thresholds.currentText()
        regular_field = self.dialog.expression_field_regulars.currentText()
        recoverys_field = self.dialog.expression_field_recoverys.currentText()
        actives_field = self.dialog.expression_field_actives.currentText()

        try:
            ids_pos = field_names.index(ids_field)
        except:
            self.iface.messageBar().pushCritical("CIN Point Export","Field ID has no input")
            self.quitDialog()
            return False
        
        try:
            name_pos = field_names.index(names_field)                
        except:
            self.iface.messageBar().pushCritical("CIN Point Export","Field Name has no input")
            self.quitDialog()
            return False
       
        try:
            sector_pos = field_names.index(sectors_field)
        except:
            self.iface.messageBar().pushCritical("CIN Point Export","Field Sector has no input")
            self.quitDialog()
            return False
        
        try:              
            levels_pos = field_names.index(levels_field)
        except:
            self.iface.messageBar().pushCritical("CIN Point Export","Field Level has no input")
            self.quitDialog()
            return False
        
        try:    
            thresholds_pos = field_names.index(thresholds_field)
        except:
            self.iface.messageBar().pushCritical("CIN Point Export","Field Threshold has no input")
            self.quitDialog()
            return False
        
        try:
            regular_pos =field_names.index(regular_field)
        except:
            self.iface.messageBar().pushCritical("CIN Point Export","Field Regular has no input")
            self.quitDialog()
            return False    
        
        try:
            recoverys_pos = field_names.index(recoverys_field)
        except:
            self.iface.messageBar().pushCritical("CIN Point Export","Field Recovery Time has no input")
            self.quitDialog()
            return False   
        
        try:
            actives_pos = field_names.index(actives_field)
        except:
            self.iface.messageBar().pushCritical("CIN Point Export","Field Activation Time has no input")
            self.quitDialog()
            return False

        for i in range(0 , idx):
            attrs = layer.getFeature(i)

            if attrs[ids_pos] == NULL:
                self.iface.messageBar().pushCritical(
                    'CIN Point Export',
                    'ID input of "{}" is NULL'.format(attrs[name_pos]))
                self.quitDialog()
                return False

            if attrs[name_pos] == NULL:
                self.iface.messageBar().pushCritical(
                    'CIN Point Export',
                    'Name input of ID "{}" is NULL'.format(attrs[ids_pos]))
                self.quitDialog()
                return False

            if not isinstance(attrs[sector_pos], int):
                self.iface.messageBar().pushCritical(
                    'CIN Point Export',
                    'Sector input of "{}" is not an integer'.format(attrs[name_pos]))              
                self.quitDialog()
                return False
            
            if 1 <= attrs[sector_pos] <= 4 or 10 <= attrs[sector_pos] <= 19:
                pass
            else:
                self.iface.messageBar().pushCritical(
                    'CIN Point Export',
                    'Sector input of "{}" is not a valid sector'.format(attrs[name_pos]))
                self.quitDialog()
                return False
            
            if attrs[levels_pos] == NULL:
                self.iface.messageBar().pushCritical(
                    'CIN Point Export',
                    'Level input of "{}" is NULL'.format(attrs[name_pos]))
                self.quitDialog()
                return False
            
            if attrs[thresholds_pos] == NULL:
                self.iface.messageBar().pushCritical(
                    'CIN Point Export',
                    'Threshold input of "{}" is NULL'.format(attrs[name_pos]))
                self.quitDialog()
                return False

            if attrs[regular_pos] == NULL:
                self.iface.messageBar().pushCritical(
                    'CIN Point Export',
                    'Regular input of "{}" is NULL'.format(attrs[name_pos]))
                self.quitDialog()
                return False          

            if str(attrs[regular_pos]).lower() == "true" or str(attrs[regular_pos]).lower() == "false":
                pass
            else:
                self.iface.messageBar().pushCritical(
                    'CIN Point Export',
                    'Regular input of "{}" must be true or false'.format(attrs[name_pos]))
                self.quitDialog()
                return False

            if attrs[recoverys_pos] == NULL:
                self.iface.messageBar().pushCritical(
                    'CIN Point Export',
                    'Recovery Time input of "{}" is NULL'.format(attrs[name_pos]))
                self.quitDialog()
                return False

            if attrs[actives_pos] == NULL:
                self.iface.messageBar().pushCritical(
                    'CIN Point Export',
                    'Activation Time input of "{}" is NULL'.format(attrs[name_pos]))
                self.quitDialog()
                return False
        return True

     def execTool(self):
        if not self.verificationInput(): 
            self.quitDialog()
            return
        
        filename = self.dialog.filename_edit.text()
        if not filename:
            self.iface.messageBar().pushCritical(
                'CIN Point Export',
                'No output filename given!'
            )
            self.quitDialog()
            return
        point_layer = self.dialog.input_layer

        if point_layer.selectedFeatureCount():
            only_selected = True
            features = point_layer.selectedFeatures()
            feature_count = point_layer.selectedFeatureCount()

        else:
            only_selected = False
            features = point_layer.getFeatures()
            feature_count = point_layer.featureCount()

        # labeling the input layer attributes to variables
        # the variable name is plural because all names are contained
        names, ok = QgsVectorLayerUtils.getValues(point_layer, self.dialog.expression_field_names.expression(),
                                                   only_selected)
        names = [x.replace(" ", "_") for x in names]  # replacing empty spaces in name
        ids, ok = QgsVectorLayerUtils.getValues(point_layer, self.dialog.expression_field_ids.expression(),
                                                  only_selected)
        sectors, ok = QgsVectorLayerUtils.getValues(point_layer, self.dialog.expression_field_sectors.expression(),
                                                   only_selected)
        levels, ok = QgsVectorLayerUtils.getValues(point_layer, self.dialog.expression_field_levels.expression(),
                                                   only_selected)
        thresholds, ok = QgsVectorLayerUtils.getValues(point_layer, self.dialog.expression_field_thresholds.expression(),
                                                   only_selected)
        regulars, ok = QgsVectorLayerUtils.getValues(point_layer, self.dialog.expression_field_regulars.expression(),
                                                   only_selected)
        recoverys, ok = QgsVectorLayerUtils.getValues(point_layer, self.dialog.expression_field_recoverys.expression(),
                                                   only_selected)
        actives, ok = QgsVectorLayerUtils.getValues(point_layer, self.dialog.expression_field_actives.expression(),
                                                   only_selected)

        if not ok: #  add loop through all atts
            self.iface.messageBar().pushCritical(
                'CIN Point Export',
                'Invalid expression for pointshape labels!'
            )
            self.quitDialog()
            return

        progress = QProgressDialog('Exporting CIN point ...', 'Abort', 0, feature_count, self.iface.mainWindow())
        progress.setWindowTitle('CIN Point Export')
        progress.canceled.connect(self.scheduleAbort)
        progress.show()

        # iterate over polyline features
        with open(filename, 'w') as cin_point_file:

            cin_point_file.write('########################################################################\n')
            cin_point_file.write('# This file was automatically generated by "Point Export for ProMaiDes CIN Module"')
            cin_point_file.write('Export-QGIS-Plugin Version {version_1} \n'.format(version_1=VERSION))
            #date and time output
            now = datetime.now()
            dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
            cin_point_file.write('# Generated at {dt_string_1} '.format(dt_string_1=dt_string))
            cin_point_file.write('from layer {filename_1} \n'.format(filename_1=point_layer.sourceName()))
            cin_point_file.write('# Comments are marked with #\n')
            cin_point_file.write('# There are three CI-elements:\n')
            cin_point_file.write('# 1. Points; as in this file)\n')
            cin_point_file.write('# 2. Connectors; linking Points with each other, multiple connectors in '
                                        'several directions are possible) \n')
            cin_point_file.write('# 3. Polygons; mostly final elements\n')
            cin_point_file.write('#\n')
            cin_point_file.write('# Explanation of data:\n')
            cin_point_file.write('#  Start the CI-points with !BEGIN and end it with !END; in between are:\n')
            cin_point_file.write('#  NumberOfPoints\n')
            cin_point_file.write('#  id(unique) x-coordinate y-coordinate name(without_whitepace) sector_id level threshold_[m_-9999_nofailure] recovery_time_[d] regular_flag_[-] activation_time_[d]\n')
            cin_point_file.write('#\n')
            cin_point_file.write('# Infos to the id: this id is connected within the connections data#\n')
            cin_point_file.write('# Infos to the sectors:\n')
            cin_point_file.write('# 1-4 are sectors for network points supplying other points and sectors!\n')
            cin_point_file.write('# - 1 = Electricity (e.g. Power Plants,High Voltage Transmitters, Low Voltage Transmitters)\n')
            cin_point_file.write('# - 2 = Information technology (e.g. Radio Station, Landline, Mobile network Station)\n')
            cin_point_file.write('# - 3 = Water supply (e.g.Water Sources)\n')
            cin_point_file.write('# - 4 = Water treatment(e.g. Water Treatment System)\n')
            cin_point_file.write('# 10 - 19 are sectors endpoints!\n')
            cin_point_file.write('# - 10 = Emergency service (e.g Medical service, Police, Fire Brigade)\n')
            cin_point_file.write('# - 11 = Health and Care System (Hospitals, Doctors, Carement centers, home for elderly people)\n')
            cin_point_file.write('# - 12 = Transport and logistics goods (Important traffic nodes, Harbors, Airports, Trainstations)\n')
            cin_point_file.write('# - 13 = Transport and logistics person (Important traffic nodes, Harbors, Airports, Trainstations)\n')
            cin_point_file.write('# - 14 = Official and Governmental Institutions (Ministries, Town Halls, Prisons)\n')
            cin_point_file.write('# - 15 = Hazardous Materials (e.g. Fuel Station, Storage for radioactive or toxic Waster)\n')
            cin_point_file.write('# - 16 = Industry and Production sites (e.g. Factories, Mines)\n')
            cin_point_file.write('# - 17 = Cultural or Religious sites (Temples, Mosques, Churches etc.)\n')
            cin_point_file.write('# - 18 = Education (School, University, kindergarten etc.)\n')
            cin_point_file.write('\n')
            cin_point_file.write('# Infos to the level: it shows the importance of the infrastructure (level with high value:=high importance e.g. 20; level with low value:=low importance e.g. 1);\n')
            cin_point_file.write('# Infos to threshold [m]: it is a water level; if this water level is reached the structure will fail to 100%; -9999 no direct failure through water is possible\n')
            cin_point_file.write('# Infos to recovery_time [d]: it is the number of days needed until the structure is to 100% recovered after it failed by a direct water impact\n')
            cin_point_file.write('# Infos to regular_flag [-]: If the structure is regular (true) or a emergency structure (false) (e.g. emergency generator); an emergency structure must be direct coupled to an enduser; it has no incomings\n')
            cin_point_file.write('# Infos to activation_time [d]: This number is used in case on an emergency structure; it is the time until the structure is active\n')
            cin_point_file.write('# \n')
            cin_point_file.write('########################################################################\n\n')

            cin_point_file.write('!BEGIN\n')
            cin_point_file.write('{number} #Number of CI points \n'.format(number=feature_count))
            index = 0

            zipped_list = zip(ids, names, sectors, levels, thresholds, regulars, actives, recoverys, features)
            sort_zip = sorted(zipped_list, key = lambda t: t[0]) #  sorts the list based on the ids

            for id, name, sector, level, threshold, regular, active, recovery, feature in sort_zip:

                points_x = []
                points_y = []
                attributes_str = [name]

                try:
                    points_x.append(feature.geometry().asPoint().x())
                    points_y.append(feature.geometry().asPoint().y())

                except ValueError:
                    self.iface.messageBar().pushCritical(
                        'CIN Point Export',
                        'Point is not correctly defined. '
                        'Check whether an x and y coordinate is present for every point.'
                    )
                    self.quitDialog()
                    return

                for i in attributes_str:
                    if not i:
                        self.iface.messageBar().pushCritical(
                            'CIN Point Export',
                            'Point is missing an entry. Please make sure that all points have the attributes:<br>'
                            ' name, id, sector, level, threshold, regular, active, recovery'
                        )
                        self.quitDialog()
                        return
                    i.replace(' ', '_')  # loop this through all atts

                cin_point_file.write('{a} {b} {c} {d} {e} {f} {g} {h} {i} {j}\n'.format
                                              (a=str(id), b=points_x[0], c=points_y[0], d=str(name), e=int(sector),
                                               f=int(level), g=float(threshold), h=float(recovery),
                                               i=str(regular), j=float(active)))

                index += 1
                progress.setValue(index)

                if self.cancel:

                    break

            cin_point_file.write('!END\n\n')
        progress.close()
        #if not self.cancel:
        self.iface.messageBar().pushInfo(
            'CIN Point Export',
            'Export finished successfully!'
           )

        self.quitDialog()
