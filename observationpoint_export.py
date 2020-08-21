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

UI_PATH = get_ui_path('ui_observationpoint_export.ui')

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
        new_filename, __ = QFileDialog.getSaveFileName(self.iface.mainWindow(), 'Observation Point Export', current_filename)
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

        self.label_field_box.setLayer(self.input_layer)

        self.updateButtonBox()

    def updateButtonBox(self):
        if self.input_layer: #and self.raster_layer:
            self.button_box.button(QDialogButtonBox.Ok).setEnabled(True)
        else:
            self.button_box.button(QDialogButtonBox.Ok).setEnabled(False)


class ObservationPointExport(object):

    def __init__(self, iface):
        self.iface = iface
        self.dialog = None
        self.cancel = False
        self.act = QAction('Observation Point Export', iface.mainWindow())
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
                'Observation Point Export',
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


        labels, ok = QgsVectorLayerUtils.getValues(point_layer, self.dialog.label_field_box.expression(), only_selected)
        if not ok:
            self.iface.messageBar().pushCritical(
                'Observation Point Export',
                'Invalid expression for pointshape labels!'
            )
            self.quitDialog()
            return

        progress = QProgressDialog('Exporting Observation point ...', 'Abort', 0, feature_count, self.iface.mainWindow())
        progress.setWindowTitle('Observation Point Export')
        progress.canceled.connect(self.scheduleAbort)
        progress.show()

        # iterate over polyline features
        with open(filename, 'w') as observationpoint_file:

            observationpoint_file.write('# This file was automatically generated by ProMaiDes Observation Point '
                                        'Export-QGIS-Plugin Version {version_1} \n'.format(version_1=VERSION))
            #date and time output
            now = datetime.now()
            dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
            observationpoint_file.write('# Generated at {dt_string_1} '.format(dt_string_1=dt_string))
            observationpoint_file.write('from layer {filename_1} \n'.format(filename_1=point_layer.sourceName()))
            observationpoint_file.write('# Comments are marked with #\n')
            observationpoint_file.write('# Explanation of data:\n')
            observationpoint_file.write('#  Start the observation points with !BEGIN and end it with !END; '
                                        'in between are: \n')
            observationpoint_file.write('#  NumberOfPoints \n# x-coordinate y-coordinate name(without_whitepace)\n\n')

            observationpoint_file.write('!BEGIN\n')
            observationpoint_file.write('{number} #Number of points \n'.format(number=feature_count))
            index = 0
            for feature, label in zip(features, labels):



                points = []
                buff = feature.geometry()

                points.append(buff.asPoint())



                if not label:
                    self.iface.messageBar().pushCritical(
                        'Observation Point Export',
                        'Empty label found! Aborting ...'
                    )
                    observationpoint_file.write('Error during point export\n '
                                         'Empty label found! Aborting...\n')
                    self.scheduleAbort()
                # erase whitespace before
                label = label.replace(' ', '_')
                # label contains whitespaces
                if len(label.split(' ')) > 1:
                    self.iface.messageBar().pushCritical(
                        'Observation Point Export',
                        'Labels must not contain whitespaces fgfdshsh! Aborting ...'
                    )
                    self.scheduleAbort()

                # iterate over points
                for dot in points:
                    observationpoint_file.write('{x} {y} {z}\n'.format(x=dot.x(), y=dot.y(), z=str(label)))


                index += 1
                progress.setValue(index)

                if self.cancel:
                    break
            observationpoint_file.write('!END\n\n')
        progress.close()
        #if not self.cancel:
        self.iface.messageBar().pushInfo(
            'Observation Point Export',
            'Export finished successfully!'
           )

        self.quitDialog()
