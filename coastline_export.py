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


UI_PATH = get_ui_path('ui_coastline_export.ui')

# This plugin exports the coastline file for the HYD-module of ProMaIdes from a line shape file;
# A name field (string) is required within the line layer
class PluginDialog(QDialog):

    def __init__(self, iface, parent=None, flags=Qt.WindowFlags()):
        QDialog.__init__(self, parent, flags=flags)
        uic.loadUi(UI_PATH, self)

        self.iface = iface
        self.input_layer = None
        self.raster_layer = None

        # set default values
        self.base_z_box.setExpression("0.0")
        self.break_box.setExpression("False")
        self.abrupt_break_box.setExpression("False")
        self.abrupt_opening_box.setExpression("25")
        self.resistance_box.setExpression("1.5")
        self.overflow_box.setExpression("True")
        self.poleni_box.setExpression("0.577")

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

        currentFilename = self.filename_edit.text()

        filename, __ = QFileDialog.getSaveFileName(self.iface.mainWindow(), 'Coastline Export', currentFilename)
        if filename != '':
            self.filename_edit.setText(filename)
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

                    # if QgsWkbTypes.isMultiType(layer.wkbType()):
                    #     self.input_layer = None
                    #     self.input_label.setText('<i>Selected layer "{}" is a multi polygon layer.<br>'
                    #                              'Please select a regular polygon layer.</i>'
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
                    self.input_label.setText('<i>Selected layer "{}" is not a polygon layer.<br>'
                                             'Please select a polygon layer.</i>'
                                             .format(layer_name))
            else:
                self.input_layer = None
                self.input_label.setText('<i>Selected layer "{}" is not a vector layer.<br>'
                                         'Please select a polygon layer.</i>'
                                         .format(layer_name))

        self.label_field_box.setLayer(self.input_layer)
        self.base_z_box.setLayer(self.input_layer)
        self.break_box.setLayer(self.input_layer)
        self.abrupt_break_box.setLayer(self.input_layer)
        self.abrupt_opening_box.setLayer(self.input_layer)
        self.resistance_box.setLayer(self.input_layer)
        self.overflow_box.setLayer(self.input_layer)
        self.poleni_box.setLayer(self.input_layer)

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


class CoastlineExport(object):

    def __init__(self, iface):
        self.iface = iface
        self.dialog = None
        self.cancel = False
        self.act = QAction('Coastline Export', iface.mainWindow())
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
                'Coastline Export',
                'No output filename given!'
            )
            self.quitDialog()
            return

        input_layer = self.dialog.input_layer
        if input_layer.selectedFeatureCount():
            only_selected = True
            features = input_layer.selectedFeatures()
            feature_count = input_layer.selectedFeatureCount()
        else:
            only_selected = False
            features = input_layer.getFeatures()
            feature_count = input_layer.featureCount()

        interpolate_z = self.dialog.interpolation_group.isChecked()

        labels, ok = QgsVectorLayerUtils.getValues(input_layer, self.dialog.label_field_box.expression(), only_selected)
        if not ok:
            self.iface.messageBar().pushCritical(
                'Coastline Export',
                'Invalid expression for labels!'
            )
            self.quitDialog()
            return

        base_elevations, ok = QgsVectorLayerUtils.getValues(input_layer, self.dialog.base_z_box.expression(), only_selected)
        if not ok:
            self.iface.messageBar().pushCritical(
                'Coastline Export',
                'Invalid expression for base elevation!'
            )
            self.quitDialog()
            return

        break_flags, ok = QgsVectorLayerUtils.getValues(input_layer, self.dialog.break_box.expression(), only_selected)
        if not ok:
            self.iface.messageBar().pushCritical(
                'Coastline Export',
                'Invalid expression for break flags!'
            )
            self.quitDialog()
            return

        abrupt_break_flags, ok = QgsVectorLayerUtils.getValues(input_layer, self.dialog.abrupt_break_box.expression(), only_selected)
        if not ok:
            self.iface.messageBar().pushCritical(
                'Coastline Export',
                'Invalid expression for abrupt break flags!'
            )
            self.quitDialog()
            return

        abrupt_openings, ok = QgsVectorLayerUtils.getValues(input_layer, self.dialog.abrupt_opening_box.expression(), only_selected)
        if not ok:
            self.iface.messageBar().pushCritical(
                'Coastline Export',
                'Invalid expression for abrupt opening!'
            )
            self.quitDialog()
            return

        resistances, ok = QgsVectorLayerUtils.getValues(input_layer, self.dialog.resistance_box.expression(), only_selected)
        if not ok:
            self.iface.messageBar().pushCritical(
                'Coastline Export',
                'Invalid expression for resistance!'
            )
            self.quitDialog()
            return

        overflow_flags, ok = QgsVectorLayerUtils.getValues(input_layer, self.dialog.overflow_box.expression(), only_selected)
        if not ok:
            self.iface.messageBar().pushCritical(
                'Coastline Export',
                'Invalid expression for overflow!'
            )
            self.quitDialog()
            return

        poleni_factors, ok = QgsVectorLayerUtils.getValues(input_layer, self.dialog.poleni_box.expression(), only_selected)
        if not ok:
            self.iface.messageBar().pushCritical(
                'Coastline Export',
                'Invalid expression for poleni factor!'
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
            z_values, ok = QgsVectorLayerUtils.getValues(input_layer, self.dialog.z_box.expression(), only_selected)
            if not ok:
                self.iface.messageBar().pushCritical(
                    'Coastline Export',
                    'Invalid expression for elevation!'
                )
                self.quitDialog()
                return

        progress = QProgressDialog('Exporting coastline ...', 'Abort', 0, feature_count, self.iface.mainWindow())
        progress.setWindowTitle('Coastline Export')
        progress.canceled.connect(self.scheduleAbort)
        progress.show()

        def signed_area(ring):
            """Returns the signed area of a polygon ring."""
            area = 0
            for i, p in enumerate(ring):
                x1 = p.x()
                y1 = p.y()
                if p is ring[-1]:
                    x2 = ring[0].x()
                    y2 = ring[0].y()
                else:
                    x2 = ring[i + 1].x()
                    y2 = ring[i + 1].y()
                area += (x1 * y2 - x2 * y1)
            return area / 2

        # iterate over polyline features
        with open(filename, 'w') as coastline_file:

            index = 0
            for f, label, be, bf, abf, ao, res, of, pf in zip(features, labels, base_elevations, break_flags,
                                                              abrupt_break_flags, abrupt_openings, resistances,
                                                              overflow_flags, poleni_factors):

                polygon = f.geometry().asPolygon()

                # polygon has more than one ring
                if len(polygon) != 1:
                    self.iface.messageBar().pushCritical(
                        'Error during coastline export',
                        'Polygon contains more than one ring! Aborting ...'
                    )
                    self.scheduleAbort()

                # label is None or empty
                if not label:
                    self.iface.messageBar().pushCritical(
                        'Error during coastline export',
                        'Invalid coastline label found in field "{}"! Aborting ...'
                        .format(self.dialog.label_field_box.expression())
                    )
                    self.scheduleAbort()

                # implicitly convert label to string
                label = str(label)

                # erase whitespace before
                label = label.replace(' ', '_')
                # label contains whitespaces
                if len(label.split(' ')) > 1:
                    self.iface.messageBar().pushCritical(
                        'Error during coastline export',
                        'Labels must not contain whitespaces! Aborting ...'
                        .format(self.dialog.label_field_box.expression())
                    )
                    self.scheduleAbort()

                if self.cancel:
                    break

                coastline_file.write('!BEGIN\n')
                coastline_file.write('{0:d} {1} {2:d}\n'.format(index, label, len(polygon[0]) - 1))

                # iterate over points in polygon in CCW direction
                # if signed_distance < 0, polygon is CW
                points = polygon[0][1:] if signed_area(polygon[0]) > 0 else reversed(polygon[0][1:])
                # don't include the first point which is identical to the last
                for point in points:

                    if interpolate_z:
                        z = interpolator(point)
                    else:
                        z = z_values[index]

                    if abf:
                        coastline_file.write('{x} {y} {z} {zb} {bf} {ab} {res} {op} {ov} {po}\n'
                                             .format(x=point.x(), y=point.y(), z=z, zb=be,
                                                     bf=str(bf).lower(), ab=str(abf).lower(),
                                                     res=res, op=ao, ov=str(of).lower(), po=pf))
                    else:
                        coastline_file.write('{x} {y} {z} {zb} {bf} {ab} {res} {ov} {po}\n'
                                             .format(x=point.x(), y=point.y(), z=z, zb=be,
                                                     bf=str(bf).lower(), ab=str(abf).lower(),
                                                     res=res, ov=str(of).lower(), po=pf))

                coastline_file.write('!END\n\n')

                index += 1
                progress.setValue(index)

                if self.cancel:
                    break

        progress.close()

        #if not self.cancel:
        self.iface.messageBar().pushInfo('Coastline Export', 'Export finished successfully!')

        self.quitDialog()
