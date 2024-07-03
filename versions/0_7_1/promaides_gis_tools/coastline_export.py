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
import webbrowser
from .version import *


UI_PATH = get_ui_path('ui_coastline_export.ui')

# This plugin exports the coastline file for the HYD-module of ProMaIdes from a line shape file;
# A name field (string) is required within the polygon layer
class PluginDialog(QDialog):

    def __init__(self, iface, parent=None, flags=Qt.WindowFlags()):
        QDialog.__init__(self, parent, flags=flags)
        uic.loadUi(UI_PATH, self)

        self.iface = iface
        self.input_layer = None
        self.raster_layer = None

        # set default values
        self.raster_layer_box.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.raster_layer_box.layerChanged.connect(self.setRasterLayer)

        self.raster_band_box.setEnabled(False)

        self.method_box.addItem('nearest neighbor (downscaling/upscaling)')
        self.method_box.addItem('bi-linear (downscaling)')
        self.method_box.addItem('bi-cubic (downscaling)')

        #connect signal and slots
        self.browse_button.clicked.connect(self.onBrowseButtonClicked)
        self.breakbox.stateChanged.connect(self.change_break)
        self.overflow.stateChanged.connect(self.change_overflow)
        self.abrupt_break.stateChanged.connect(self.change_abrupt)
        self.interpolation_group.clicked.connect(self.change_interpolation)
        self.HelpButton.clicked.connect(self.Help)
        self.iface.currentLayerChanged.connect(self.setInputLayer)

        self.setInputLayer(self.iface.activeLayer())
        self.setRasterLayer(self.raster_layer_box.currentLayer())

    def __del__(self):
        self.iface.currentLayerChanged.disconnect(self.setInputLayer)

    def Help(self):
        webbrowser.open("https://promaides.myjetbrains.com/youtrack/articles/PMDP-A-49/Coastline-Export")

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

    # change if the check box of break is changed
    def change_break(self):
        if self.breakbox.checkState() == 0:
            self.abrupt_break.setEnabled(False)
            self.abrupt_opening_width.setEnabled(False)
            self.resistance.setEnabled(False)

        else:
            self.abrupt_break.setEnabled(False)
            if self.abrupt_break.isChecked() == 0:
                self.abrupt_opening_width.setEnabled(False)
                self.resistance.setEnabled(True)
            else:
                self.abrupt_opening_width.setEnabled(True)
                self.resistance.setEnabled(False)

    # change if the check box of overflow is changed
    def change_overflow(self):
        if self.overflow.checkState() == 0:
            self.poleni.setEnabled(False)
        else:
            self.poleni.setEnabled(True)




    # change if the interpolation box is changed
    def change_interpolation(self):
        if self.interpolation_group.isChecked() == 0:
            self.z_box.setEnabled(True)
        else:
            self.z_box.setEnabled(False)

    # change if the abrupt box is changed
    def change_abrupt(self):
        if self.abrupt_break.isChecked() == 0:

            self.abrupt_opening_width.setEnabled(False)
            self.resistance.setEnabled(True)
        else:
            self.abrupt_opening_width.setEnabled(True)
            self.resistance.setEnabled(False)



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

        base_elevations = self.dialog.base_elevation.value()
        break_flags = self.dialog.breakbox.isChecked()
        abrupt_break_flags = self.dialog.abrupt_break.isChecked()
        abrupt_openings = self.dialog.abrupt_opening_width.value()
        resistances = self.dialog.resistance.value()
        overflow_flags = self.dialog.overflow.isChecked()
        poleni_factors = self.dialog.poleni.value()

        if interpolate_z:
            raster_layer = self.dialog.raster_layer
            raster_band = self.dialog.raster_band_box.value()
            method = self.dialog.method_box.currentText()
            nan = self.dialog.nan_box.value()
            interpolator = RasterInterpolator(raster_layer, raster_band, 10, 10, method, nan)
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
            coastline_file.write('########################################################################\n')
            coastline_file.write('# This file was automatically generated by ProMaiDes Coastline '
                               'Export-QGIS-Plugin Version {version_1} \n'.format(version_1=VERSION))
            # date and time output
            now = datetime.now()
            dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
            coastline_file.write('# Generated at {dt_string_1} '.format(dt_string_1=dt_string))
            coastline_file.write('from layer {filename_1} \n'.format(filename_1=input_layer.sourceName()))
            if interpolate_z:
                coastline_file.write('#  based on height raster (DEM) {}  \n'.format(raster_layer.name()))
            coastline_file.write('# Comments are marked with #\n')
            coastline_file.write('#\n')
            coastline_file.write('# Explanation of data:\n')
            coastline_file.write('#  Start the coastline with !BEGIN and end it with !END; '
                                 'just one polygon is allowed; in between are: \n')
            coastline_file.write('#  Index_(starts by 0) Name NumberOfPoints\n')
            coastline_file.write('#  x-coordinate y-coordinate z-coordinate base_elevation break_flag abrupt_break_flag '
                                 'Abrupt_opening_with/Resistance Overflow_flag Poleni_Factor \n')
            coastline_file.write('#\n')
            coastline_file.write('# Use in .ilm-file (just copy, delete the leading "#", set file(s)):\n')
            coastline_file.write('# Set a coastal model between !$BEGINDESCRIPTION and !$ENDDESCRIPTION\n')
            coastline_file.write('#  !$BEGINCOASTMODEL = "NAME" \n')
            coastline_file.write('#   !COASTLINEFILE = <SET>	\n')
            coastline_file.write('#       $FILENAME= "./PATH2_THIS_FILE/FILE_NAME.txt" #to this generated file\n')
            coastline_file.write('#    </SET>	\n')
            coastline_file.write('#   !INSTATBOUNDFILE = <SET>	\n')
            coastline_file.write('#       $FILENAME="./PATH2FILE/FILE_NAME.txt" #Instationary boundary file of coast\n')
            coastline_file.write('#    </SET>	\n')
            coastline_file.write('#  !$ENDCOASTMODEL  \n')
            coastline_file.write('########################################################################\n\n')

            for f, label in zip(features, labels):

                be = base_elevations
                bf = break_flags
                abf = abrupt_break_flags
                ao = abrupt_openings
                res = resistances
                of = overflow_flags
                pf = poleni_factors



                if input_layer.selectedFeatureCount():
                    only_selected = True
                    features = input_layer.selectedFeatures()
                    feature_count = input_layer.selectedFeatureCount()
                else:
                    only_selected = False
                    features = input_layer.getFeatures()
                    feature_count = input_layer.featureCount()


                # polygon has more than one ring
                if feature_count != 1:
                    self.iface.messageBar().pushCritical(
                        'Error during coastline export',
                        'More than one polygon available in layer! Please just select one! Aborting...')
                    coastline_file.write('Error during coastline export\n '
                                         'More than one polygon available in '
                                         'layer! Please just select one! Aborting...\n')

                    self.quitDialog()
                    return

                # label is None or empty
                if not label:
                    self.iface.messageBar().pushCritical(
                        'Error during coastline export',
                        'Invalid coastline label found in field "{}"! Aborting...'
                        .format(self.dialog.label_field_box.expression())
                    )
                    self.quitDialog()
                    return

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
                    self.quitDialog()
                    return

                if self.cancel:
                    break

                coastline_file.write('!BEGIN\n')
                points = []
                for feature, label1 in zip(features, labels):
                    buff = feature.geometry()

                for p in buff.vertices():
                    points.append(p)

                coastline_file.write('{0:d} {1} {2:d}\n'.format(index, label, len(points)-1))

                # iterate over points in polygon in CCW direction
                # if signed_distance < 0, polygon is CW
                # points = polygon[0][1:] if signed_area(polygon[0]) > 0 else reversed(polygon[0][1:])
                # don't include the first point which is identical to the last

                for i in range(len(points)-1):

                    if interpolate_z:
                        z = interpolator(QgsPointXY(points[i]))
                    else:
                        z = z_values[index]
                    print(z)
                    print(nan)
                    if z is nan:
                        bf_buff = 'False'
                        abf_buff = 'False'
                        of_buff = 'False'
                    else:
                        bf_buff = bf
                        abf_buff = abf
                        of_buff = of


                    if abf:
                        coastline_file.write('{x} {y} {z} {zb} {bf} {ab} {op} {ov} {po}\n'
                                             .format(x=points[i].x(), y=points[i].y(), z=z, zb=be,
                                                     bf=str(bf_buff).lower(), ab=str(abf_buff).lower(),
                                                     op=ao, ov=str(of_buff).lower(), po=pf))
                    else:
                        coastline_file.write('{x} {y} {z} {zb} {bf} {ab} {res} {ov} {po}\n'
                                             .format(x=points[i].x(), y=points[i].y(), z=z, zb=be,
                                                     bf=str(bf_buff).lower(), ab=str(abf_buff).lower(),
                                                     res=res, ov=str(of_buff).lower(), po=pf))

                coastline_file.write('!END\n\n')

                index += 1
                progress.setValue(index)

                if self.cancel:
                    break

        progress.close()

        #if not self.cancel:
        self.iface.messageBar().pushInfo('Coastline Export', 'Export finished successfully!')

        self.quitDialog()
