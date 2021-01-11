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

#general
from datetime import datetime
from .version import *

UI_PATH = get_ui_path('ui_cin_2promaides_point.ui ')

# This plugin exports the observations point file for the HYD-module of ProMaIdes from a point shape file;
# A name field (string) is required within the point layer
class PluginDialog(QDialog):

    def __init__(self, iface, parent=None, flags=Qt.WindowFlags()):
        QDialog.__init__(self, parent, flags)
        uic.loadUi(UI_PATH, self)
        self.iface = iface
        self.input_layer = None
        self.browse_button.clicked.connect(self.onBrowseButtonClicked)
        self.iface.currentLayerChanged.connect(self.setInputLayer)
        self.setInputLayer(self.iface.activeLayer())

    def __del__(self):
        self.iface.currentLayerChanged.disconnect(self.setInputLayer)

    def onBrowseButtonClicked(self):
        current_filename = self.filename_edit.text()
        new_filename, __ = QFileDialog.getSaveFileName(self.iface.mainWindow(), 'CIN Point Export', current_filename)
        if new_filename != '':
            self.filename_edit.setText(new_filename)
            self.filename_edit.editingFinished.emit()

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
        self.expression_field_names.setExpression("name")
        self.expression_field_ids.setExpression("osm_id")
        self.expression_field_sectors.setExpression("sector")
        self.expression_field_levels.setExpression("level")
        self.expression_field_thresholds.setExpression("threshold")
        self.expression_field_finals.setExpression("final")

        self.expression_field_names.setLayer(self.input_layer)
        self.expression_field_ids.setLayer(self.input_layer)
        self.expression_field_sectors.setLayer(self.input_layer)
        self.expression_field_levels.setLayer(self.input_layer)
        self.expression_field_thresholds.setLayer(self.input_layer)
        self.expression_field_finals.setLayer(self.input_layer)

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
        self.dialog.expression_field_ids.setFilters(QgsFieldProxyModel.String)
        self.dialog.expression_field_names.setFilters(QgsFieldProxyModel.String)
        self.dialog.expression_field_sectors.setFilters(QgsFieldProxyModel.String)
        self.dialog.expression_field_levels.setFilters(QgsFieldProxyModel.Int)
        self.dialog.expression_field_thresholds.setFilters(QgsFieldProxyModel.Double)
        self.dialog.expression_field_finals.setFilters(QgsFieldProxyModel.Int) # try to change this to boolean in QT
        self.dialog.show()

    def scheduleAbort(self):
        self.cancel = True

    def quitDialog(self):
        self.dialog = None
        self.act.setEnabled(True)
        self.cancel = False

    def execTool(self):
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
        ids, ok = QgsVectorLayerUtils.getValues(point_layer, self.dialog.expression_field_ids.expression(),
                                                  only_selected)
        sectors, ok = QgsVectorLayerUtils.getValues(point_layer, self.dialog.expression_field_sectors.expression(),
                                                   only_selected)
        levels, ok = QgsVectorLayerUtils.getValues(point_layer, self.dialog.expression_field_levels.expression(),
                                                   only_selected)
        thresholds, ok = QgsVectorLayerUtils.getValues(point_layer, self.dialog.expression_field_thresholds.expression(),
                                                   only_selected)
        finals, ok = QgsVectorLayerUtils.getValues(point_layer, self.dialog.expression_field_finals.expression(),
                                                   only_selected)
        attributes = [names, ids, sectors, levels, thresholds, finals]

        if not ok: #  add loop through all atts
            self.iface.messageBar().pushCritical(
                'CIN Point Export',
                'Invalid expression for pointshape labels!'
            )
            self.quitDialog()
            return

        progress = QProgressDialog('Exporting Observation point ...', 'Abort', 0, feature_count, self.iface.mainWindow())
        progress.setWindowTitle('CIN Point Export')
        progress.canceled.connect(self.scheduleAbort)
        progress.show()

        # iterate over polyline features
        with open(filename, 'w') as observationpoint_file:

            observationpoint_file.write('########################################################################\n')
            observationpoint_file.write('# This file was automatically generated by "Point Export for ProMaiDes CIN module'
                                        'Export-QGIS-Plugin Version {version_1} \n'.format(version_1=VERSION))
            #date and time output
            now = datetime.now()
            dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
            observationpoint_file.write('# Generated at {dt_string_1} '.format(dt_string_1=dt_string))
            observationpoint_file.write('from layer {filename_1} \n'.format(filename_1=point_layer.sourceName()))
            observationpoint_file.write('# Comments are marked with #\n')
            observationpoint_file.write('# There are three CI-elements:\n')
            observationpoint_file.write('# 1. Points; as in this file)\n')
            observationpoint_file.write('# 2. Connectors; linking Points with each other, multiple connectors in '
                                        'several directions are possible) \n')
            observationpoint_file.write('# 3. Polygons; mostly final elements\n')
            observationpoint_file.write('#\n')
            observationpoint_file.write('# Explanation of data:\n')
            observationpoint_file.write('#  Start the CI-points with !BEGIN and end it with !END; in between are:\n')
            observationpoint_file.write('#  NumberOfPoints\n')
            observationpoint_file.write('#  id(unique) x-coordinate y-coordinate name(without_whitepace) sector'
                                        '[fixed_strings_abreviations?] level threshold_[m_-9999_nofailure] '
                                        'final(true:=final_false:=not_final)\n')
            observationpoint_file.write('#\n')
            observationpoint_file.write('# Infos to the sectors:\n')
            observationpoint_file.write('# - elect 	    := 1 = Electricity '
                                        '(e.g. Power Plants,High Voltage Transmitters, Low Voltage Transmitters)\n')
            observationpoint_file.write('# - infotec	:= 2 = Information technology '
                                        '(e.g. Radio Station, Landline, Mobile network Station)\n')
            observationpoint_file.write('# - eme_ser 	:= 3 = (Medical service, Police, Fire Brigade)\n')
            observationpoint_file.write('# - water_sup 	:= 4 = Water supply '
                                        '(e.g. Water Treatment System, Water Sources)\n')
            observationpoint_file.write('# - logi	    := 5 = Transport and logistics '
                                        '(Important traffic nodes, Harbors, Airports, Trainstations)\n')
            observationpoint_file.write('# - health	    := 6 = Health System '
                                        '(Hospitals, Doctors, Carement centers)\n')
            observationpoint_file.write('# - off_gov	:= 7 = Official and Governmental Institutions '
                                        '(Ministries, Town Halls, Prisons)\n')
            observationpoint_file.write('# - haz_mat	:= 8 = Hazardous Materials '
                                        '(e.g. Fuel Station, Storage for radioactive or toxic Waster)\n')
            observationpoint_file.write('# - prod 	    := 9 = Industry and Production sites '
                                        '(e.g. Factories, Mines)\n')
            observationpoint_file.write('# - culture	:= 0 = Cultural or Religious sites '
                                        '(Temples, Mosques, Churches etc.)\n')
            observationpoint_file.write('# \n')
            observationpoint_file.write('########################################################################\n\n')

            observationpoint_file.write('!BEGIN\n')
            observationpoint_file.write('{number} #Number of CI points \n'.format(number=feature_count))
            index = 0

            for feature, id, name, sector, level, threshold, final in zip(features, ids, names, sectors, levels, thresholds, finals):

                points = []
                buff = feature.geometry()

                attributes_single = {id, name, sector, level, threshold, final}
                attributes_str = [name, sector]
                # attributes_int and attributes_bool are still missing
                attributes_single_name = ['id', "name", 'sector', 'level', 'threshold', 'final']
                attributes_single3 = (id, name, sector, level, threshold, final)



                print(attributes_str, "attributes_str")

                points.append(buff.asPoint())
                for i in attributes_str:
                    print(i, "i")
                    i = i.replace(' ', '_')  # loop this through all atts
                    # fuck this this still needs more fixes...
                    # if i:  # loop this through all atts
                    #     self.iface.messageBar().pushCritical(
                    #         'CIN Point Export',
                    #         'Empty \'Name\' or \'Sector\' found! Aborting ...'
                    #         )
                    # observationpoint_file.write('Error during point export\n '
                    #                      'Empty \'Name\' or \'Sector\' found! Aborting...\n')
                    # self.quitDialog()
                    # return

                    # erase whitespace before

                    # label contains whitespaces
                    # if len(i.split(' ')) > 1:
                    #     self.iface.messageBar().pushCritical(
                    #         'CIN Point Export',
                    #         'Labels must not contain whitespaces! Aborting ...'
                    #         )
                    # self.quitDialog()
                    # return

                # iterate over points
                print("did we get here?")
                for dot in points:
                    observationpoint_file.write('{a} {b} {c} {d} {e} {f} {g} {h}\n'.format
                                                (a=str(id), b=dot.x(), c=dot.y(), d=str(name), e=str(sector),
                                                 f=int(level), g=float(threshold), h=int(final)))

                index += 1
                progress.setValue(index)

                if self.cancel:
                    break
            observationpoint_file.write('!END\n\n')
        progress.close()
        #if not self.cancel:
        self.iface.messageBar().pushInfo(
            'CIN Point Export',
            'Export finished successfully!'
           )

        self.quitDialog()
