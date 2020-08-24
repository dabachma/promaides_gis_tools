from __future__ import unicode_literals
from __future__ import absolute_import

# system modules
import math
import os
import tempfile

# QGIS modules
from qgis.core import *
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import *
from qgis.PyQt import uic

from shapely.geometry import MultiLineString, mapping, shape

# This plugin resamples the vertices of a polyline; use it for a higher point density of a line;
from .environment import get_ui_path


UI_PATH = get_ui_path('ui_densify_linestring.ui')


class PluginDialog(QDialog):

    def __init__(self, iface, parent=None, flags=Qt.WindowFlags()):
        QDialog.__init__(self, parent, flags)
        uic.loadUi(UI_PATH, self)

        self.iface = iface
        self.input_layer = None

        self.iface.currentLayerChanged.connect(self.setInputLayer)
        self.setInputLayer(self.iface.activeLayer())

    def __del__(self):
        self.iface.currentLayerChanged.disconnect(self.setInputLayer)

    def setInputLayer(self, layer):
        """
        """
        if not layer:
            self.input_layer = None
            self.input_label.setText(u'<i>No layer selected.<br>'
                                     u'Please select a polyline layer.</i>')
        else:
            layer_name = layer.name()

            if layer.type() == QgsMapLayer.VectorLayer:

                if layer.geometryType() == QgsWkbTypes.LineGeometry:

                    # if QgsWkbTypes.isMultiType(layer.wkbType()):
                    #     self.input_layer = None
                    #     self.input_label.setText(u'<i>Selected layer "{}" is multi linestring layer.<br>'
                    #                              u'Please select a regular linestring layer.</i>'
                    #                              .format(layer_name))
                    #
                    # else:

                    self.input_layer = layer
                    if layer.selectedFeatureCount():
                        self.input_label.setText(u'<i>Input layer is "{}" with {} selected feature(s).</i>'
                                                 .format(layer_name, layer.selectedFeatureCount()))
                    else:
                        self.input_label.setText(u'<i>Input layer is "{}" with {} feature(s).</i>'
                                                 .format(layer_name, layer.featureCount()))

                else:
                    self.input_layer = None
                    self.input_label.setText(u'<i>Selected layer "{}" is not a linestring layer.<br>'
                                             u'Please select a linestring layer.</i>'
                                             .format(layer_name))
            else:
                self.input_layer = None
                self.input_label.setText(u'<i>Selected layer "{}" is not a vector layer.<br>'
                                         u'Please select a linestring layer.</i>'
                                         .format(layer_name))

        self.value_box.setLayer(self.input_layer)

        self.updateButtonBox()

    def updateButtonBox(self):
        if self.input_layer:
            self.button_box.button(QDialogButtonBox.Ok).setEnabled(True)
        else:
            self.button_box.button(QDialogButtonBox.Ok).setEnabled(False)


class DensifyLinestring(object):

    def __init__(self, iface):
        self.iface = iface
        self.dialog = None
        self.cancel = False
        self.act = QAction('Resample Polyline Vertices', iface.mainWindow())
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
        ###############################################################
        # keeporiginal
        keeporiginal = self.dialog.keeporiginal_box.isChecked()
        if keeporiginal:
            try:
                original = self.dialog.input_layer
                originalpath = os.path.dirname(original.source())
                if not originalpath:
                    originalpath=tempfile.gettempdir()
                originalname = original.name()
                writingpath = originalpath + "/" + originalname + "_resampled.shp"
                _writer = QgsVectorFileWriter.writeAsVectorFormat(original, writingpath, 'utf-8',
                                                              driverName='ESRI Shapefile')
                loadedlayer = QgsVectorLayer(writingpath, originalname + "_resampled", "ogr")
                QgsProject.instance().addMapLayer(loadedlayer)
                line_layer = loadedlayer
                line_layer.startEditing()
            except:
                self.iface.messageBar().pushCritical(
                    'Resample Polyline Vertices',
                    'New layer cannot be created!'
                )
                self.quitDialog()
                return
        else:
            line_layer = self.dialog.input_layer
        #################################################################

        if not line_layer.isEditable():
            self.iface.messageBar().pushCritical(
                'Resample Polyline Vertices',
                'Layer is not editable! Switch on edit mode first.'
            )
            self.quitDialog()
            return

        if line_layer.selectedFeatureCount():
            only_selected = True
            features = line_layer.selectedFeatures()
        else:
            only_selected = False
            features = line_layer.getFeatures()

        values, ok = QgsVectorLayerUtils.getValues(line_layer, self.dialog.value_box.expression(), only_selected)
        if not ok:
            self.iface.messageBar().pushCritical(
                'Resample Polyline Vertices',
                'Invalid expression for values!'
            )
            self.quitDialog()
            return

        line_layer.beginEditCommand('Resample Polyline Vertices')

        # for feature, value in zip(features, values):
        #     print((mapping(feature)))
        #loop over lines
        for feature, value in zip(features, values):

            if not value:
                self.iface.messageBar().pushCritical(
                    'Resample Polyline Vertices',
                    'Empty value found in field "{}"! Aborting ...'
                    .format(self.dialog.label_field_box.expression())
                )
                line_layer.destroyEditCommand()
                self.quitDialog()
                return

            geom = feature.geometry()
            #print((mapping(features)))



            try:
                if self.dialog.number_button.isChecked():
                    num = int(value) - 1  # last point is added below
                    delta = geom.length() / num

                else:
                    delta = float(value)
                    num = int(math.floor(geom.length() / delta)) + 1  # last point is added below
            except ValueError:
                self.iface.messageBar().pushCritical(
                    'Resample Polyline Vertices',
                    'Could not convert value to int/float! Aborting ...'
                )
                line_layer.destroyEditCommand()
                self.quitDialog()
                return

            if delta <= 0.0:
                self.iface.messageBar().pushCritical(
                    'Resample Polyline Vertices',
                    'Invalid value found in field "{}"! Aborting ...'
                    .format(self.dialog.label_field_box.expression())
                )
                line_layer.destroyEditCommand()
                self.quitDialog()
                return

            densified = geom.densifyByDistance(delta)


            densified.removeDuplicateNodes()
            line_layer.changeGeometry(feature.id(), densified)

        line_layer.endEditCommand()

        self.iface.messageBar().pushInfo(
            'Resample Polyline Vertices',
            'Operation finished successfully!'
        )

        self.quitDialog()
