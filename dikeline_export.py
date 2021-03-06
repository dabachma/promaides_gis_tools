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

UI_PATH = get_ui_path('ui_dikeline_export.ui')

#general
from datetime import datetime
import webbrowser
from .version import *

# This plugin exports the dikelinie file for the HYD-module of ProMaIdes from a line shape file;
# A name field (string) is required within the line layer
class PluginDialog(QDialog):

    def __init__(self, iface, parent=None, flags=Qt.WindowFlags()):
        QDialog.__init__(self, parent, flags)
        uic.loadUi(UI_PATH, self)

        self.iface = iface
        self.input_layer = None
        self.raster_layer = None

        self.raster_layer_box.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.raster_layer_box.layerChanged.connect(self.setRasterLayer)

        self.raster_band_box.setEnabled(False)


        self.method_box.addItem('nearest neighbor (downscaling/upscaling)')
        self.method_box.addItem('bi-linear (downscaling)')
        self.method_box.addItem('bi-cubic (downscaling)')

        #connect by signal and slot
        self.browse_button.clicked.connect(self.onBrowseButtonClicked)
        self.interpolation_group.clicked.connect(self.change_interpolation)
        self.HelpButton.clicked.connect(self.Help)

        self.iface.currentLayerChanged.connect(self.setInputLayer)

        self.setInputLayer(self.iface.activeLayer())
        self.setRasterLayer(self.raster_layer_box.currentLayer())

    def __del__(self):
        self.iface.currentLayerChanged.disconnect(self.setInputLayer)

    def Help(self):
        webbrowser.open("https://promaides.myjetbrains.com/youtrack/articles/PMDP-A-43/Dikeline-Export")

    def onBrowseButtonClicked(self):
        current_filename = self.filename_edit.text()
        new_filename, __ = QFileDialog.getSaveFileName(self.iface.mainWindow(), 'Dikeline Export', current_filename)
        if new_filename != '':
            self.filename_edit.setText(new_filename)
            self.filename_edit.editingFinished.emit()

    def setInputLayer(self, layer):
        """
        """
        if not layer:
            self.input_layer = None
            self.input_label.setText('<i>No layer selected.<br>'
                                     'Please select a polyline layer.</i>')
        else:
            layer_name = layer.name()

            if layer.type() == QgsMapLayer.VectorLayer:

                if layer.geometryType() == QgsWkbTypes.LineGeometry:

                    # if QgsWkbTypes.isMultiType(layer.wkbType()):
                    #     self.input_layer = None
                    #     self.input_label.setText('<i>Selected layer "{}" is a multi linestring layer.<br>'
                    #                              'Please select a regular linestring layer.</i>'
                    #                              .format(layer_name))
                    #
                    # else:
                    self.input_layer = layer

                    if layer.selectedFeatureCount():
                        self.input_label.setText('<i>Input layer is "{}" with {} selected feature(s).</i>'
                                                 .format(layer_name, layer.selectedFeatureCount()))
                    else:
                        self.input_label.setText('<i>Input layer is "{}" with {} feature(s).</i>'
                                                 .format(layer_name, layer.featureCount()))

                else:
                    self.input_layer = None
                    self.input_label.setText('<i>Selected layer "{}" is not a linestring layer.<br>'
                                             'Please select a polyline layer.</i>'
                                             .format(layer_name))
            else:
                self.input_layer = None
                self.input_label.setText('<i>Selected layer "{}" is not a vector layer.<br>'
                                         'Please select a polyline layer.</i>'
                                         .format(layer_name))

        self.label_field_box.setLayer(self.input_layer)

        self.updateButtonBox()

    def setRasterLayer(self, layer):
        self.raster_layer = layer
        if layer:
            self.raster_band_box.setEnabled(True)
            self.raster_band_box.setRange(1, layer.bandCount())
        else:
            self.raster_band_box.setEnabled(False)

        self.updateButtonBox()

    def updateButtonBox(self):
        if self.input_layer and self.raster_layer:
            self.button_box.button(QDialogButtonBox.Ok).setEnabled(True)
        else:
            self.button_box.button(QDialogButtonBox.Ok).setEnabled(False)

    # change if the interpolation box is changed
    def change_interpolation(self):
        if self.interpolation_group.isChecked() == 0:
            self.z_box.setEnabled(True)
        else:
            self.z_box.setEnabled(False)


class DikelineExport(object):

    def __init__(self, iface):
        self.iface = iface
        self.dialog = None
        self.cancel = False
        self.act = QAction('Dikeline Export', iface.mainWindow())
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
        # add a filter to the combo box of the filed selection; for "Name" just a string filed make sense
        self.dialog.label_field_box.setFilters(QgsFieldProxyModel.String)
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
                'Dikeline Export',
                'No output filename given!'
            )
            self.quitDialog()
            return

        line_layer = self.dialog.input_layer
        if line_layer.selectedFeatureCount():
            only_selected = True
            features = line_layer.selectedFeatures()
            feature_count = line_layer.selectedFeatureCount()
        else:
            only_selected = False
            features = line_layer.getFeatures()
            feature_count = line_layer.featureCount()

        interpolate_z = self.dialog.interpolation_group.isChecked()

        labels, ok = QgsVectorLayerUtils.getValues(line_layer, self.dialog.label_field_box.expression(), only_selected)
        if not ok:
            self.iface.messageBar().pushCritical(
                'Dikeline Export',
                'Invalid expression for dikeline labels!'
            )
            self.quitDialog()
            return

        if interpolate_z:
            raster_layer = self.dialog.raster_layer
            raster_band = self.dialog.raster_band_box.value()
            method = self.dialog.method_box.currentText()
            nan = self.dialog.nan_box.value()
            interpolator = RasterInterpolator(raster_layer, raster_band, 10, 10,  method, nan)
            z_values = None
        else:
            interpolator = None
            z_values, ok = QgsVectorLayerUtils.getValues(line_layer, self.dialog.z_box.expression(), only_selected)
            if not ok:
                self.iface.messageBar().pushCritical(
                    'Dikeline Export',
                    'Invalid expression for dikeline crest levels!'
                )
                self.quitDialog()
                return

        progress = QProgressDialog('Exporting dikeline ...', 'Abort', 0, feature_count, self.iface.mainWindow())
        progress.setWindowTitle('Dikeline Export')
        progress.canceled.connect(self.scheduleAbort)
        progress.show()

        # iterate over polyline features
        with open(filename, 'w') as dikeline_file:

            index = 0
            dikeline_file.write('########################################################################\n')
            dikeline_file.write('# This file was automatically generated by ProMaiDes Dikeline '
                               'Export-QGIS-Plugin Version {version_1} \n'.format(version_1=VERSION))
            # date and time output
            now = datetime.now()
            dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
            dikeline_file.write('# Generated at {dt_string_1} '.format(dt_string_1=dt_string))
            dikeline_file.write('from layer {filename_1} \n'.format(filename_1=line_layer.sourceName()))
            if interpolate_z:
                dikeline_file.write('#  based on height raster (DEM) {}  \n'.format(raster_layer.name()))
            dikeline_file.write('# Comments are marked with #\n')
            dikeline_file.write('# Number of lines in file: {}  \n'.format(feature_count))
            dikeline_file.write('#\n')
            dikeline_file.write('# Explanation of data:\n')
            dikeline_file.write('#  Start the dikeline with !BEGIN and end it with !END per line; in between are: \n')
            dikeline_file.write('#  Index_(starts by 0) Name NumberOfPoints\n')
            dikeline_file.write('#  x-coordinate y-coordinate z-coordinate\n')
            dikeline_file.write('#\n')
            dikeline_file.write('# Use in .ilm-file (just copy, delete the leading "#", set file(s)):\n')
            dikeline_file.write('# Set per FloodPlain-model between !$BEGINFPMODEL and !$ENDFPMODEL\n')
            dikeline_file.write('#  !DIKELINEFILE = <SET>\n')
            dikeline_file.write('#    $FILENAME="./PATH2FILE/FILE_NAME.txt"\n')
            dikeline_file.write('#    $NO_POLYLINES = 2 #number of lines in file (see above)\n')
            dikeline_file.write('#  </SET>	\n')
            dikeline_file.write('########################################################################\n\n')
            for feature, label in zip(features, labels):

                line = []
                buff = feature.geometry()
                for p in buff.vertices():
                    line.append(p)


                if not label:
                    self.iface.messageBar().pushCritical(
                        'Dikeline Export',
                        'Empty label found! Aborting ...')
                    dikeline_file.write('Error during dikeline export\n '
                                         'Empty label found! Aborting...\n')

                    self.quitDialog()
                    return

                # erase whitespace before
                label = label.replace(' ', '_')
                # label contains whitespaces
                if len(label.split(' ')) > 1:
                    self.iface.messageBar().pushCritical(
                        'Dikeline Export',
                        'Labels must not contain whitespaces! Aborting ...'
                    )
                    self.quitDialog()
                    return

                if self.cancel:
                    break

                dikeline_file.write('!BEGIN\n')
                dikeline_file.write('{0:d} {1} {2:d}\n'.format(index, str(label), len(line)))

                # iterate over points in polyline
                for point in line:

                    if interpolate_z:
                        z = interpolator.interpolate(QgsPointXY(point))
                    else:
                        z = z_values[index]

                    dikeline_file.write('{x} {y} {z}\n'.format(x=point.x(), y=point.y(), z=z))

                dikeline_file.write('!END\n\n')

                index += 1
                progress.setValue(index)

                if self.cancel:
                    break

        progress.close()

        #if not self.cancel:
        self.iface.messageBar().pushInfo(
            'Dikeline Export',
            'Export finished successfully!'
           )

        self.quitDialog()
