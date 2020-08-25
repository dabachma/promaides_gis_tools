from __future__ import unicode_literals
from __future__ import absolute_import

# 3rd party modules
import numpy as np
from datetime import datetime

# QGIS modules
from qgis.core import *
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import *
from qgis.PyQt import uic

# promaides modules
from .interpolate import RasterInterpolator
from .environment import get_ui_path
from .version import *

try:
    from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as Canvas
    from matplotlib.figure import Figure
    from matplotlib.widgets import Cursor
    PREVIEW_ENABLED = True
except ImportError:
    PREVIEW_ENABLED = False
    Canvas, Figure, Cursor = None, None, None

UI_PATH = get_ui_path('ui_river_profile_export.ui')

# This plugin exports the 1D-river file for the HYD-module of ProMaIdes from a line shape file;
# A name field (string) is required within the line layer
class PluginDialog(QDialog):

    def __init__(self, iface, parent=None, flags=Qt.WindowFlags()):
        QDialog.__init__(self, parent, flags)
        uic.loadUi(UI_PATH, self)

        self.iface = iface
        self.input_layer = None
        self.raster_layer = None
        self.roughness_layer = None
        #add channel info
        self.channel_info = None

        # self.name_box.setExpression('')
        # self.station_box.setExpression('')
        self.delta_box.setExpression('0.1')
        self.connection_box.setExpression("'standard'")
        self.type_box.setExpression("'river'")
        self.initial_box.setExpression('0.5')
        self.point_bc_enabled_box.setExpression('False')
        self.point_bc_stationary_box.setExpression('True')
        self.point_bc_value_box.setExpression('0')
        self.lateral_bc_enabled_box.setExpression('False')
        self.lateral_bc_stationary_box.setExpression('True')
        self.lateral_bc_value_box.setExpression('0')
        self.overflow_left_enabled_box.setExpression('True')
        self.overflow_left_poleni_box.setExpression('0.577')
        self.overflow_right_enabled_box.setExpression('True')
        self.overflow_right_poleni_box.setExpression('0.577')

        #set DGM layer
        self.raster_layer_box.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.raster_layer_box.layerChanged.connect(self.setRasterLayer)
        self.raster_band_box.setEnabled(False)

        self.method_box.addItem('nearest neighbor')
        self.method_box.addItem('bi-linear')
        self.method_box.addItem('bi-cubic')

        #set roughness layer
        self.roughness_layer_box.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.roughness_layer_box.layerChanged.connect(self.setRoughnessLayer)
        self.roughness_layer_box.setLayer(None)

        #set channel layer
        self.comboBox_main.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.comboBox_main.layerChanged.connect(self.setChannelLayer)
        self.comboBox_main.setLayer(None)

        self.browse_button.clicked.connect(self.onBrowseButtonClicked)
        self.iface.currentLayerChanged.connect(self.setInputLayer)

        #############################################
        #autostationing button function
        def autoclicked(state):
            if state > 0:
                self.profileid_box.setEnabled(True)
                self.station_box.setEnabled(False)
                self.preview_button.setDisabled(True)
            else:
                self.profileid_box.setEnabled(False)
                self.station_box.setEnabled(True)
                self.preview_button.setDisabled(False)

        self.profileid_box.setEnabled(False)
        self.autostation_box.stateChanged.connect(autoclicked)
        #############################################  
        
        if PREVIEW_ENABLED:
            self.figure = Figure(figsize=(10, 4), dpi=100)
            self.axes = self.figure.add_subplot(111)
            self.axes.set_xlabel('Stationing')
            self.axes.set_ylabel('Elevation [m+NHN]')
            self.figure.tight_layout()
            self.canvas = Canvas(self.figure)
            self.canvas.setParent(self)
            self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.layout().addWidget(self.canvas)
            self.canvas.setVisible(False)
            self.cursor = None
            self.preview_button.toggled.connect(self.canvas.setVisible)
            self.preview_button.toggled.connect(self.update_button.setEnabled)
            self.update_button.clicked.connect(self.updateLongitudinalPreview)
        else:
            self.preview_button.setDisabled(True)
            self.figure = None
            self.axes = None
            self.canvas = None
            self.cursor = None

        self.setInputLayer(self.iface.activeLayer())
        self.setRasterLayer(self.raster_layer_box.currentLayer())


    def __del__(self):
        self.iface.currentLayerChanged.disconnect(self.setInputLayer)

    def onBrowseButtonClicked(self):
        current_filename = self.filename_edit.text()
        new_filename, __ = QFileDialog.getSaveFileName(self.iface.mainWindow(), '1D-River Profile Export', current_filename)
        if new_filename != '':
            self.filename_edit.setText(new_filename)
            self.filename_edit.editingFinished.emit()

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
                    self.input_layer = layer
                    if layer.selectedFeatureCount():
                        self.input_label.setText(u'<i>Input layer is "{}" with {} selected feature(s).</i>'
                                                 .format(layer_name, layer.selectedFeatureCount()))
                    else:
                        self.input_label.setText(u'<i>Input layer is "{}" with {} feature(s).</i>'
                                                 .format(layer_name, layer.featureCount()))

                else:
                    self.input_layer = None
                    self.input_label.setText(u'<i>Selected layer "{}" is not a polyline layer.<br>'
                                             u'Please select a polyline layer.</i>'
                                             .format(layer_name))
            else:
                self.input_layer = None
                self.input_label.setText(u'<i>Selected layer "{}" is not a vector layer.<br>'
                                         u'Please select a polyline layer.</i>'
                                         .format(layer_name))

        self.name_box.setLayer(self.input_layer)
        self.station_box.setLayer(self.input_layer)
        self.delta_box.setLayer(self.input_layer)
        self.connection_box.setLayer(self.input_layer)
        self.type_box.setLayer(self.input_layer)
        self.initial_box.setLayer(self.input_layer)
        self.profileid_box.setLayer(self.input_layer)
        self.point_bc_enabled_box.setLayer(self.input_layer)
        self.point_bc_stationary_box.setLayer(self.input_layer)
        self.point_bc_value_box.setLayer(self.input_layer)
        self.lateral_bc_enabled_box.setLayer(self.input_layer)
        self.lateral_bc_stationary_box.setLayer(self.input_layer)
        self.lateral_bc_value_box.setLayer(self.input_layer)
        self.overflow_left_enabled_box.setLayer(self.input_layer)
        self.overflow_left_poleni_box.setLayer(self.input_layer)
        self.overflow_right_enabled_box.setLayer(self.input_layer)
        self.overflow_right_poleni_box.setLayer(self.input_layer)

        self.updateButtonBox()


    def setRasterLayer(self, layer):
        self.raster_layer = layer
        if layer:
            self.raster_band_box.setEnabled(True)
            self.raster_band_box.setRange(1, layer.bandCount())
        else:
            self.raster_band_box.setEnabled(False)

        self.updateButtonBox()      

    def setRoughnessLayer(self, layer):
        self.roughness_layer = layer
        if layer:
            self.roughness_band_box.setEnabled(True)
            self.roughness_band_box.setRange(1, layer.bandCount())
        else:
            self.roughness_band_box.setEnabled(False)

    def setChannelLayer(self, layer):
            self.channel_info = layer

    def updateButtonBox(self):
        if self.input_layer and self.raster_layer:
            self.button_box.button(QDialogButtonBox.Ok).setEnabled(True)
        else:
            self.button_box.button(QDialogButtonBox.Ok).setEnabled(False)

    def updateLongitudinalPreview(self):
        if not PREVIEW_ENABLED:
            self.iface.messageBar().pushCritical(
                'River Profile Export',
                'Preview is disabled since Python module "matplotlib" is not installed!'
            )
            return
        
        flip_directions = self.flip_directions_box.isChecked()
        addfullriver = self.fullriver_box.isChecked()
        autostation = self.autostation_box.isChecked()
        abs_init = self.abs_init_box.isChecked()
        adjust_elevation = self.adjust_elevation_box.isChecked()
        
        input_layer = self.input_layer
        if not input_layer:
            return

        if input_layer.selectedFeatureCount():
            selected = True
            features = input_layer.selectedFeatures()
        else:
            selected = False
            features = input_layer.getFeatures()

        stations, ok = QgsVectorLayerUtils.getValues(input_layer, self.station_box.expression(), selected)
        if not autostation:
            if not ok:
                self.iface.messageBar().pushCritical(
                    'River Profile Export',
                    'Invalid expression for stations!'
                )
                return

        init_values, ok = QgsVectorLayerUtils.getValues(input_layer, self.initial_box.expression(), selected)
        if not ok:
            self.iface.messageBar().pushCritical(
                'River Profile Export',
                'Invalid expression for initial condition!'
            )
            return


        dem_layer = self.raster_layer
        dem_band = self.raster_band_box.value()
        dem_method = self.method_box.currentText()
        dem_nan = self.nan_box.value()
        dem_interpol = RasterInterpolator(dem_layer, dem_band, dem_method, dem_nan)

        base, left, right, h = [], [], [], []

        # iterate over profiles and extract base elevation,
        # left and right bank elevation, and init value
        for i, f in enumerate(features):

           # line = f.geometry().asPolyline()
            line = []
            buff = f.geometry()
            for p in buff.vertices():
                line.append(p)

            if flip_directions:
                line = list(reversed(line))

            z = [dem_interpol(QgsPointXY(p)) for p in line]

            if adjust_elevation:
                if z[0] <= z[1]:
                    z[0] = z[1] + 0.01
                if z[-1] <= z[-2]:
                    z[-1] = z[-2] + 0.01

            i_min = np.argmin(z)
            # minimum profile elevation
            z_min = z[int(i_min)]

            base.append(z_min)
            left.append(z[0])
            right.append(z[-1])

            init_value = float(init_values[i])
            # init values are absolute values
            if not abs_init:
                init_value += z_min

            h.append(init_value)

        s, base, left, right, h = list(zip(*sorted(zip(stations, base, left, right, h))))

        self.axes.cla()
        self.axes.plot(s, base, 'k', lw=1.5, label='base')
        self.axes.plot(s, left, 'r', lw=1.0, label='left bank')
        self.axes.plot(s, right, 'g', lw=1.0, label='right bank')
        self.axes.plot(s, h, 'b--', lw=0.5, label='init. h')
        self.axes.legend()
        self.axes.set_xticks(s)
        self.axes.set_xticklabels(list(map(str, s)), rotation=90, fontdict=dict(fontsize=9))
        self.axes.set_xlabel('Stationing')
        self.axes.set_ylabel('Elevation [m+NHN]')
        self.figure.tight_layout()
        self.cursor = Cursor(self.axes, useblit=True, color='0.5', linewidth=0.5)
        self.canvas.draw()


class RiverProfileExport(object):

    def __init__(self, iface):
        self.iface = iface
        self.act = None
        self.dialog = None
        self.cancel = False
        self.act = QAction('1D-River Profile Export', iface.mainWindow())
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
        # add a filter to the combo box of the filed selection;
        self.dialog.name_box.setFilters(QgsFieldProxyModel.String)
        self.dialog.type_box.setFilters(QgsFieldProxyModel.String)
        self.dialog.connection_box.setFilters(QgsFieldProxyModel.String)
        self.dialog.point_bc_enabled_box.setFilters(QgsFieldProxyModel.String)
        self.dialog.point_bc_stationary_box.setFilters(QgsFieldProxyModel.String)
        self.dialog.lateral_bc_enabled_box.setFilters(QgsFieldProxyModel.String)
        self.dialog.lateral_bc_stationary_box.setFilters(QgsFieldProxyModel.String)
        self.dialog.overflow_right_enabled_box.setFilters(QgsFieldProxyModel.String)
        self.dialog.overflow_left_enabled_box.setFilters(QgsFieldProxyModel.String)


        self.dialog.station_box.setFilters(QgsFieldProxyModel.Double)
        self.dialog.delta_box.setFilters(QgsFieldProxyModel.Double)
        self.dialog.initial_box.setFilters(QgsFieldProxyModel.Double)
        self.dialog.profileid_box.setFilters(QgsFieldProxyModel.Double)
        self.dialog.point_bc_value_box.setFilters(QgsFieldProxyModel.Double)
        self.dialog.lateral_bc_value_box.setFilters(QgsFieldProxyModel.Double)
        self.dialog.overflow_left_poleni_box.setFilters(QgsFieldProxyModel.Double)
        self.dialog.overflow_right_poleni_box.setFilters(QgsFieldProxyModel.Double)




        self.dialog.show()

    def scheduleAbort(self):
        self.cancel = True

    def quitDialog(self):
        self.dialog = None
        self.act.setEnabled(True)
        self.cancel = False

    def execTool(self):

        abs_init = self.dialog.abs_init_box.isChecked()
        flip_directions = self.dialog.flip_directions_box.isChecked()
        addfullriver = self.dialog.fullriver_box.isChecked()
        autostation = self.dialog.autostation_box.isChecked()
        adjust_elevation = self.dialog.adjust_elevation_box.isChecked()


        filename = self.dialog.filename_edit.text()
        if not filename:
            self.iface.messageBar().pushCritical(
                'River Profile Export',
                'No output filename given!'
            )
            self.quitDialog()
            return

        input_layer = self.dialog.input_layer
        if input_layer.selectedFeatureCount():
            os = True
            features = input_layer.selectedFeatures()
            feature_count = input_layer.selectedFeatureCount()
        else:
            os = False
            features = input_layer.getFeatures()
            feature_count = input_layer.featureCount()

        names, ok = QgsVectorLayerUtils.getValues(input_layer, self.dialog.name_box.expression(), os)
        if not ok:
            self.iface.messageBar().pushCritical(
                'River Profile Export',
                'Invalid expression for names!'
            )
            self.quitDialog()
            return

        stations, ok = QgsVectorLayerUtils.getValues(input_layer, self.dialog.station_box.expression(), os)
        if not autostation:
            ##################################
            #test station values to be numeric
            def isnumeric(obj):
                try:
                    obj + 0
                    return True
                except TypeError:
                    return False
            for i in stations:
                if isnumeric(i)==False:
                    self.iface.messageBar().pushCritical(
                        'River Profile Export',
                        'Invalid values for stations!'
                    )
                    self.quitDialog()
                    return
            ####################################
            if not ok:
                self.iface.messageBar().pushCritical(
                    'River Profile Export',
                    'Invalid expression for stations!'
                )
                self.quitDialog()
                return

        deltas, ok = QgsVectorLayerUtils.getValues(input_layer, self.dialog.delta_box.expression(), os)
        if not ok:
            self.iface.messageBar().pushCritical(
                'River Profile Export',
                'Invalid expression for delta table!'
            )
            self.quitDialog()
            return

        conn_types, ok = QgsVectorLayerUtils.getValues(input_layer, self.dialog.connection_box.expression(), os)
        if not ok:
            self.iface.messageBar().pushCritical(
                'River Profile Export',
                'Invalid expression for connection type!'
            )
            self.quitDialog()
            return

        profile_types, ok = QgsVectorLayerUtils.getValues(input_layer, self.dialog.type_box.expression(), os)
        if not ok:
            self.iface.messageBar().pushCritical(
                'River Profile Export',
                'Invalid expression for profile type!'
            )
            self.quitDialog()
            return

        init_values, ok = QgsVectorLayerUtils.getValues(input_layer, self.dialog.initial_box.expression(), os)
        if not ok:
            self.iface.messageBar().pushCritical(
                'River Profile Export',
                'Invalid expression for initial condition!'
            )
            self.quitDialog()
            return
        
        if autostation:
            profileids, ok = QgsVectorLayerUtils.getValues(input_layer, self.dialog.profileid_box.expression(), os)
            
            #####################################
            #test profile id values to be numeric
            def isnumeric(obj):
                try:
                    obj + 0
                    return True
                except TypeError:
                    return False
            for i in profileids:
                if isnumeric(i)==False:
                    self.iface.messageBar().pushCritical(
                        'River Profile Export',
                        'Invalid values for profile ids!'
                    )
                    self.quitDialog()
                    return
            ####################################
            if not ok:
                self.iface.messageBar().pushCritical(
                    'River Profile Export',
                    'Invalid expression for profile id!'
                )
                self.quitDialog()
                return

        point_bc_flags, ok = QgsVectorLayerUtils.getValues(input_layer, self.dialog.point_bc_enabled_box.expression(), os)
        if not ok:
            self.iface.messageBar().pushCritical(
                'River Profile Export',
                'Invalid expression for point boundary enabled!'
            )
            self.quitDialog()
            return

        point_bc_stationary_flags, ok = QgsVectorLayerUtils.getValues(input_layer, self.dialog.point_bc_stationary_box.expression(), os)
        if not ok:
            self.iface.messageBar().pushCritical(
                'Coastline Export',
                'Invalid expression for point boundary stationary!'
            )
            self.quitDialog()
            return

        point_bc_values, ok = QgsVectorLayerUtils.getValues(input_layer, self.dialog.point_bc_value_box.expression(), os)
        if not ok:
            self.iface.messageBar().pushCritical(
                'River Profile Export',
                'Invalid expression for point boundary value!'
            )
            self.quitDialog()
            return

        lateral_bc_flags, ok = QgsVectorLayerUtils.getValues(input_layer, self.dialog.lateral_bc_enabled_box.expression(), os)
        if not ok:
            self.iface.messageBar().pushCritical(
                'River Profile Export',
                'Invalid expression for lateral boundary enabled!'
            )
            self.quitDialog()
            return

        lateral_bc_stationary_flags, ok = QgsVectorLayerUtils.getValues(input_layer, self.dialog.lateral_bc_stationary_box.expression(), os)
        if not ok:
            self.iface.messageBar().pushCritical(
                'River Profile Export',
                'Invalid expression for lateral boundary stationary!'
            )
            self.quitDialog()
            return

        lateral_bc_values, ok = QgsVectorLayerUtils.getValues(input_layer, self.dialog.lateral_bc_value_box.expression(), os)
        if not ok:
            self.iface.messageBar().pushCritical(
                'River Profile Export',
                'Invalid expression for lateral boundary value!'
            )
            self.quitDialog()
            return

        overflow_left_flags, ok = QgsVectorLayerUtils.getValues(input_layer, self.dialog.overflow_left_enabled_box.expression(), os)
        if not ok:
            self.iface.messageBar().pushCritical(
                'River Profile Export',
                'Invalid expression for overflow left enabled!'
            )
            self.quitDialog()
            return

        poleni_left_values, ok = QgsVectorLayerUtils.getValues(input_layer, self.dialog.overflow_left_poleni_box.expression(), os)
        if not ok:
            self.iface.messageBar().pushCritical(
                'River Profile Export',
                'Invalid expression for left poleni factor!'
            )
            self.quitDialog()
            return

        overflow_right_flags, ok = QgsVectorLayerUtils.getValues(input_layer, self.dialog.overflow_right_enabled_box.expression(), os)
        if not ok:
            self.iface.messageBar().pushCritical(
                'River Profile Export',
                'Invalid expression for overflow right enabled!'
            )
            self.quitDialog()
            return

        poleni_right_values, ok = QgsVectorLayerUtils.getValues(input_layer, self.dialog.overflow_right_poleni_box.expression(), os)
        if not ok:
            self.iface.messageBar().pushCritical(
                'River Profile Export',
                'Invalid expression for right poleni factor!'
            )
            self.quitDialog()
            return

        

        dem_layer = self.dialog.raster_layer
        dem_band = self.dialog.raster_band_box.value()
        dem_name = self.dialog.raster_layer.name()
        dem_method = self.dialog.method_box.currentText()
        dem_nan = self.dialog.nan_box.value()
        dem_interpol = RasterInterpolator(dem_layer, dem_band, dem_method, dem_nan)
        dem_trans: object = QgsCoordinateTransform(input_layer.crs(), dem_layer.crs(), QgsProject.instance()).transform

        roughness_layer = self.dialog.roughness_layer
        roughness_band = self.dialog.roughness_band_box.value()
        roughness_nan = self.dialog.default_roughness_box.value()
        roughness_interpol = RasterInterpolator(roughness_layer, roughness_band, 'nearest neighbor', roughness_nan)
        if roughness_layer:
            roughness_trans = QgsCoordinateTransform(input_layer.crs(), roughness_layer.crs(), QgsProject.instance())\
                .transform
        else:
            roughness_trans = lambda coord: coord

        progress = QProgressDialog('Exporting river profiles ...', 'Abort', 0, 2 * feature_count,
                                   self.iface.mainWindow())
        progress.setWindowTitle('River Profile Export')
        progress.canceled.connect(self.scheduleAbort)
        progress.show()

        text_blocks = {}
################################################################################  
        #autostation
        if autostation:
            # linepre is the previous line
            linepre = []
            stationsum = 0
            autostations = list(range(0, len(profileids)))
            sortedindex=np.argsort(profileids)
            #bug fix
            feature = input_layer.getFeature(0)
            buff = feature.geometry()
            if not buff:
                layerinmemory=True
            else:
                layerinmemory = False
            for i, j in enumerate(sortedindex):
                if layerinmemory==True:
                    feature = input_layer.getFeature(j+1)
                else:
                    feature=input_layer.getFeature(j)
                line = []
                buff = feature.geometry()
                for p in buff.vertices():
                    line.append(p)
                #stationing starts with 0   
                if i == 0:
                    autocalculatedstation = 0
                else:
                    #calculating the lowest hieght in the previous line
                    zpre = [dem_interpol(QgsPointXY(p)) for p in linepre]
                    #the location of the point with the lowest height
                    point_minpre = np.argmin(zpre)
                    znew = [dem_interpol(QgsPointXY(p)) for p in line]
                    point_minnew = np.argmin(znew)
                    difference = linepre[point_minpre].distance(line[point_minnew])
                    stationsum = difference + stationsum
                    autocalculatedstation = -stationsum
                linepre = line
                autostations[j]=autocalculatedstation

##################################################################################

        # iterate over profiles and extract attributes and points
        for i, f in enumerate(features):
            line = []
            buff = f.geometry()

            for p in buff.vertices():
                line.append(p) 
                
            if flip_directions:
                line = list(reversed(line))
                
            if autostation:
                stations=autostations

            # TODO check if true or false write a own functions
            name = str(names[i])
            station = float(stations[i])
            delta_x = float(deltas[i])
            conn_type = str(conn_types[i])
            profile_type = str(profile_types[i])
            init_value = float(init_values[i])
            point_bc = bool(point_bc_flags[i])
            point_bc_stat = bool(point_bc_stationary_flags[i])
            point_bc_v = point_bc_values[i]
            lat_bc = bool(lateral_bc_flags[i])
            lat_bc_stat = bool(lateral_bc_stationary_flags[i])
            lat_bc_v = lateral_bc_values[i]
            overflow_left = str(overflow_left_flags[i])
            poleni_left = float(poleni_left_values[i])
            overflow_right = str(overflow_right_flags[i])
            poleni_right = float(poleni_right_values[i])

            # label is None or empty
            if not name:
                self.iface.messageBar().pushCritical(
                    'Error during river profile export',
                    'Invalid coastline label found in field "{}"! Aborting ...'
                    .format(self.dialog.label_field_box.expression())
                )
                self.scheduleAbort()

            # implicitly convert label to string
            name = str(name)
            # erase whitespace before
            name = name.replace(' ', '_')
            # label contains whitespaces
            if len(name.split(' ')) > 1:
                self.iface.messageBar().pushCritical(
                    'Error during river profile export',
                    'Labels must not contain whitespaces! Aborting ...'
                    .format(self.dialog.label_field_box.expression())
                )
                self.scheduleAbort()

            if self.cancel:
                break

            # collect point data
            #print(line)
            first = line[0]
            last = line[-1]

            x = [p.x() for p in line]
            y = [p.y() for p in line]
            z = [dem_interpol(QgsPointXY(p)) for p in line]
            mat = [int(roughness_interpol(roughness_trans(QgsPointXY(p)))) for p in line]


            if adjust_elevation:
                if z[0] <= z[1]:
                    z[0] = z[1] + 0.01
                if z[-1] <= z[-2]:
                    z[-1] = z[-2] + 0.01
            
            dist, ident = [], []
            # set channel type
            flag = False
            sumd=0

            #Main channel is used

            if self.dialog.channel_info == None:
                mainchannel_flag = False
            else:
                mainchannel_flag = True

                if self.dialog.channel_info.featureCount() != 1:
                    self.iface.messageBar().pushWarning('1-D River Profile Export',
                                                    'More than one polygon in main'
                                                    ' channel file; just the first one is used')

            for j, point in enumerate(line):
                if j==0:
                    d = 0
                else:
                    d = line[j-1].distance(point)
                sumd=d+sumd
                dist.append(sumd)


                if point == first:
                    ident.append(1)
                else:
                    # get main channel polygons
                    if mainchannel_flag == False:
                        ident.append(2)

                    else:
                        features_main = self.dialog.channel_info.getFeatures()
                        counter_p = 0
                        for poly in features_main:
                            counter_p = counter_p+1
                            if counter_p == 1:
                                geom_pol = poly.geometry()
                                if geom_pol.contains(QgsPointXY(point)) == True:
                                    ident.append(2)
                                    flag = True
                                elif flag == True:
                                    ident.append(3)
                                elif flag == False:
                                    ident.append(1)



                # elif point == last:
                #     ident.append(3)
                # else:
                #     ident.append(2)
                
            i_min = np.argmin(z)
            # minimum profile elevation
            z_min = z[int(i_min)]
            # init values are absolute values
            if abs_init:
                init_value -= z_min
            # write profile attributes
            block = ""
            block += 'ZONE T="{}" I={:d}\n'.format(name, len(line))
            block += 'AUXDATA ProfLDist="{:.2f}"\n'.format(station)
            block += 'AUXDATA DeltaXtable="{}"\n'.format(delta_x)
            if addfullriver:
                if stations[i]==max(stations):
                    block += 'AUXDATA ConnectionType="inflow"\n'
                elif stations[i]==min(stations):
                    block += 'AUXDATA ConnectionType="outflow"\n'
                else:
                    block += 'AUXDATA ConnectionType="{}"\n'.format(conn_type)
            else:
                block += 'AUXDATA ConnectionType="{}"\n'.format(conn_type)
            block += 'AUXDATA ProfType="{}"\n'.format(profile_type)
            block += 'AUXDATA InitCondition="{:.2f}"\n'.format(init_value)
            if addfullriver:
                if stations[i]==max(stations):
                    block += 'AUXDATA BoundaryPointCondition="true"\n'
                else:
                    block += 'AUXDATA BoundaryPointCondition="{}"\n'.format(str(point_bc).lower())
            else:
                block += 'AUXDATA BoundaryPointCondition="{}"\n'.format(str(point_bc).lower())
            block += 'AUXDATA BoundaryPointStationary="{}"\n'.format(str(point_bc_stat).lower())
            if addfullriver:
                if stations[i]==max(stations):
                    block += 'AUXDATA BoundaryPointValue="0.5"\n'
                else:
                    block += 'AUXDATA BoundaryPointValue="{}"\n'.format(point_bc_v)
            else:
                block += 'AUXDATA BoundaryPointValue="{}"\n'.format(point_bc_v)
            block += 'AUXDATA BoundaryLateralCondition="{}"\n'.format(str(lat_bc).lower())
            block += 'AUXDATA BoundaryLateralStationary="{}"\n'.format(str(lat_bc_stat).lower())
            block += 'AUXDATA BoundaryLateralValue="{}"\n'.format(lat_bc_v)
            if addfullriver:
                sortstations=np.sort(stations)
                if stations[i]==min(stations) or stations[i]==sortstations[1]:
                    block += 'AUXDATA OverflowCouplingLeft="false"\n'
                else:
                    block += 'AUXDATA OverflowCouplingLeft="{}"\n'.format(str(overflow_left).lower())
            else:
                block += 'AUXDATA OverflowCouplingLeft="{}"\n'.format(str(overflow_left).lower())
            block += 'AUXDATA PoleniFacLeft="{}"\n'.format(poleni_left)
            if addfullriver:
                sortstations = np.sort(stations)
                if stations[i]==min(stations) or stations[i]==sortstations[1]:
                    block += 'AUXDATA OverflowCouplingRight="false"\n'
                else:
                    block += 'AUXDATA OverflowCouplingRight="{}"\n'.format(str(overflow_right).lower())
            else:
                block += 'AUXDATA OverflowCouplingRight="{}"\n'.format(str(overflow_right).lower())
            block += 'AUXDATA PoleniFacRight="{}"\n\n'.format(poleni_right)

            # write profile points
            for xj, yj, zj, matj, distj, identj in zip(x, y, z, mat, dist, ident):
                block += '{x:.2f} {y:.2f} {z:.2f} {mat} {dist:.2f} {ident}\n'.format(x=xj, y=yj, z=zj, mat=matj,
                                                                                     dist=distj, ident=identj)

            block += '\n'

            if station in text_blocks:
                self.iface.messageBar().pushWarning(
                    'River Profile Export',
                    'Duplicate profile station "{}"! Overwriting previous profile definition.'.format(station)
                )

            text_blocks[station] = block
            progress.setValue(i + 1)

            if self.cancel:
                break

        if self.cancel:
            progress.close()
            self.quitDialog()
            return

        # write (station-wise sorted) profiles and profile points to file
        with open(filename, 'w') as profile_file:
            profile_file.write('########################################################################\n')
            profile_file.write('# This file was automatically generated by ProMaiDes 1D-River Profile Export '
                                 '-QGIS-Plugin Version {version_1} \n'.format(version_1=VERSION))
            # date and time output
            now = datetime.now()
            dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
            profile_file.write('# Generated at {dt_string_1} '.format(dt_string_1=dt_string))
            profile_file.write('from layer {filename_1} \n'.format(filename_1=input_layer.sourceName()))
            profile_file.write('#  based on height raster (DEM) {}  \n'.format(dem_name))
            if self.dialog.channel_info is not None:
                profile_file.write('#  based on main channel polygon {}  \n'.
                                   format(self.dialog.channel_info.sourceName()))
            if roughness_layer:
                profile_file.write('#  based on roughness raster {}  \n'.
                                   format(roughness_layer.name()))

            profile_file.write('# Comments are marked with #\n')
            profile_file.write('# Explanation of data:\n')
            profile_file.write('#  The river profile-file is optimized for Tecplot; '
                                 ' each profile is one Zone with Name (T=..) NumberOfPoints (I=..) \n')
            profile_file.write('#  Several additional information to the profile follows; these '
                                 'attributes are valid to the distance to the next downstream profile \n')
            profile_file.write('#   The station value is from upstream to downstream decreasing\n')
            profile_file.write(
                '#  Finally the point data is given (always from left to right in flow direction): '
                'x-coordinate y-coordinate z-coordinate material_id local_distance Lbank(1)_Main(2)_Rbank(3)\n'
                '#  Further remarks: \n#    material_id and Lbank(1)_Main(2)_Rbank(3) are valid to '
                'the distance before the point\n#    First point has always Lbank(1) \n#    '
                'First point must be higher than point after; last point must be higher than point before\n#    '
                'If you want to have a higher point density, please use plugin Resample Polyline Vertices'
                ' \n')
            profile_file.write('########################################################################\n\n')


            profile_file.write('TITLE = "{}"\n'.format(input_layer.name()))
            profile_file.write('VARIABLES = "X", "Y", "Z", "MathType", "Distance", "Ident"\n')
            profile_file.write('DATASETAUXDATA NumOfProf = "{:d}"\n\n'.format(len(text_blocks)))

            # write profiles in reverse sorted order, i.e. decreasing station values
            for i, station in enumerate(reversed(sorted(text_blocks.keys()))):
                profile_file.write(text_blocks[station])
                progress.setValue(feature_count + i + 1)

        progress.close()

        #if not self.cancel:
        self.iface.messageBar().pushInfo('1D-River Profile Export', 'Export finished successfully!')

        self.quitDialog()
