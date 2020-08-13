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

        self.method_box.addItem('nearest neighbor')
        self.method_box.addItem('bi-linear')
        self.method_box.addItem('bi-cubic')

        self.browse_button.clicked.connect(self.onBrowseButtonClicked)

        self.iface.currentLayerChanged.connect(self.setInputLayer)

        self.setInputLayer(self.iface.activeLayer())
        self.setRasterLayer(self.raster_layer_box.currentLayer())
		

    def __del__(self):
        self.iface.currentLayerChanged.disconnect(self.setInputLayer)

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
            interpolator = RasterInterpolator(raster_layer, raster_band, method, nan)
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
            for feature, label in zip(features, labels):

                #line = feature.geometry().asPolyline()

                line = []
                buff = feature.geometry()
                for p in buff.vertices():
                    line.append(p)


                if not label:
                    self.iface.messageBar().pushCritical(
                        'Dikeline Export',
                        'Empty label found! Aborting ...'
                    )
                    self.scheduleAbort()

                # label contains whitespaces
                if len(label.split(' ')) > 1:
                    self.iface.messageBar().pushCritical(
                        'Dikeline Export',
                        'Labels must not contain whitespaces! Aborting ...'
                    )
                    self.scheduleAbort()

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
