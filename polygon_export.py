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


UI_PATH = get_ui_path('ui_polygon_export.ui')

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

    def __del__(self):
        self.iface.currentLayerChanged.disconnect(self.setInputLayer)

    def onBrowseButtonClicked(self):
        current_filename = self.filename_edit.text()
        new_filename, __ = QFileDialog.getSaveFileName(self.iface.mainWindow(), 'Noflow-Polygon Export', current_filename)
        if new_filename != '':
            self.filename_edit.setText(new_filename)
            self.filename_edit.editingFinished.emit()

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

        #self.label_field_box.setLayer(self.input_layer)

        self.updateButtonBox()

    def updateButtonBox(self):
        if self.input_layer: #and self.raster_layer:
            self.button_box.button(QDialogButtonBox.Ok).setEnabled(True)
        else:
            self.button_box.button(QDialogButtonBox.Ok).setEnabled(False)


class PolygonExport(object):

    def __init__(self, iface):
        self.iface = iface
        self.dialog = None
        self.cancel = False
        self.act = QAction('Noflow-Polygon Export', iface.mainWindow())
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

        attribute = polygon_layer.attributeDisplayName(0)
        # labels, ok = QgsVectorLayerUtils.getValues(polygon_layer, self.dialog.label_field_box.expression(), only_selected)
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
            polygon_file.write('# This file was automatically generated by ProMaIDes Noflow-Polygon '
                               'Export-QGIS-Plugin Version {version_1} \n'.format(version_1=VERSION))
            # date and time output
            now = datetime.now()
            dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
            polygon_file.write('# Generated at {dt_string_1} '.format(dt_string_1=dt_string))
            polygon_file.write('from layer {filename_1} \n'.format(filename_1=polygon_layer.sourceName()))
            polygon_file.write('# Comments are marked with #\n')
            polygon_file.write('# Number of polygons in file: {}  \n'.format(feature_count))
            polygon_file.write('#\n')
            polygon_file.write('# Explanation of data:\n')
            polygon_file.write('#  Start the Noflow-polygon with !BEGIN and end it with !END per polygon; '
                               'in between are: \n')
            polygon_file.write('#  Index_(starts by 0) NumberOfPoints\n')
            polygon_file.write('#  x-coordinate y-coordinate\n')
            polygon_file.write('#\n')
            polygon_file.write('# Use in .ilm-file (just copy, delete the leading "#", set file(s)):\n')
            polygon_file.write('# Set per FloodPlain-model between !$BEGINFPMODEL and !$ENDFPMODEL\n')
            polygon_file.write('#  !NOFLOWFILE = <SET>\n')
            polygon_file.write('#    $FILENAME="./PATH2FILE/FILE_NAME.txt"\n')
            polygon_file.write('#    $NO_POLYGONS = 2 #number of polygons in file (see above)\n')
            polygon_file.write('#  </SET>	\n')
            polygon_file.write('########################################################################\n\n')

            for feature, label in zip(features, labels):
                points = []

                buff = feature.geometry()
                for p in buff.vertices():
                    points.append(p)

                if self.cancel:
                    break

                polygon_file.write('!BEGIN\n')
                polygon_file.write('{0:d} {1} {2:d}\n'.format(index, str( ), len(points)-1))

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
