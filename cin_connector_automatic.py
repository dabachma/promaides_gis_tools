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

UI_PATH = get_ui_path('ui_cin_2promaides_connector_auto.ui')

# This plugin exports the observations point file for the HYD-module of ProMaIdes from a point shape file;
# A name field (string) is required within the point layer
class PluginDialog(QDialog):
    list_of_input = []
    list_of_inputnames = ["name", "full_id", "level", "sector", "final", "threshold"]
    list_of_pairs = []  # multi-dimensional List for the source sink pairs
    emptyattributes = []

    def __init__(self, iface, parent=None, flags=Qt.WindowFlags()):
        QDialog.__init__(self, parent, flags)
        uic.loadUi(UI_PATH, self)
        self.iface = iface
        self.input_layer = None

        self.PolygonLayerBox.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.PointLayerBox.setFilters(QgsMapLayerProxyModel.PointLayer)

        self.PolygonLayerBox.setLayer(None)
        self.PointLayerBox.setLayer(None)

        self.browse_button.clicked.connect(self.onBrowseButtonClicked)
        self.button_box.rejected.connect(self.reject)
        
        self.HelpButton.clicked.connect(self.Help)

    def __del__(self):
        print("__del__")

    def PolygonLayer(self):
        return self.PolygonLayerBox.currentLayer()

    def PointLayer(self):
        return self.PointLayerBox.currentLayer()

    def ConnectorNumberingBox(self):
        return self.ConnectorNumberingBox.value()

    def onBrowseButtonClicked(self):
        current_filename = self.filename_edit.text()
        new_filename, __ = QFileDialog.getSaveFileName(self.iface.mainWindow(), 'CIN Connector Export - Automatic', current_filename)
        if new_filename != '':
            self.filename_edit.setText(new_filename)
            self.filename_edit.editingFinished.emit()

    def Help(self):
        webbrowser.open("https://promaides.myjetbrains.com/youtrack/articles/PMDP-A-66/DAM-CIN---Connector-Export---Automatic")

class CINConnectorExportAuto(object):

    def __init__(self, iface):
        self.iface = iface
        self.dialog = None
        self.cancel = False
        self.act = QAction('CIN Connector Export - Automatic', iface.mainWindow())
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
        self.dialog.button_box.accepted.connect(self.execTool)
        self.dialog.accepted.connect(self.execTool)
        self.dialog.rejected.connect(self.quitDialog)
        self.dialog.setModal(False)
        self.act.setEnabled(False)
        self.dialog.show()

    def scheduleAbort(self):
        self.cancel = True

    def quitDialog(self):
        # self.dialog = None
        # self.act.setEnabled(True)
        # self.cancel = True

        self.act.setEnabled(True)
        self.cancel = False
        self.dialog.close()

    def execTool(self):
        filename = self.dialog.filename_edit.text()

        #  1. get polygon layer

        #  2. loop through polygon layer

        #  3. check for every polygon whether point is in there

        #  4. if yes -> connect Source: Polygon id to point id
        #       Be aware the polygons are used to define which POINT source is relevant
        #       At the end we are connecting a point source with a point sink
        #  need to create: (a=pair_index, b=source_id_write, c=sink_id_write, d=str(source_name_write), e=str(sink_name_write),))

        polygonlayer = self.dialog.PolygonLayerBox.currentLayer()
        pointlayer = self.dialog.PointLayerBox.currentLayer()
        pair_index = self.dialog.ConnectorNumberingBox.value()
        print(pair_index, "pair_index")
        source_id_write = []
        sink_id_write = []
        source_name_write = []
        sink_name_write = []
        connector_id = []

        if polygonlayer:

            for pol_feature in polygonlayer.getFeatures():
                if pointlayer:
                    for point_feature in pointlayer.getFeatures():
                        if pol_feature.geometry().contains(point_feature.geometry()):
                            connector_id.append(str(pair_index))
                            source_id_write.append(str(pol_feature["polygon_id"]))
                            source_name_write.append(str(pol_feature["polygon_na"]))
                            sink_id_write.append(str(point_feature["point_id"]))
                            sink_name_write.append(str(point_feature["point_name"]))

                            print(str(source_id_write[pair_index]) + " " + str(source_name_write[pair_index]))

                            pair_index = pair_index + 1

            print(pair_index, "pair_index_end")

        else:
            self.iface.messageBar().pushCritical(
                'CIN Connector Export - Automatic',
                'Not a polygon layer!'
            )

        if not filename:
            self.iface.messageBar().pushCritical(
                'CIN Connector Export - Automatic',
                'No output filename given!'
            )
            self.quitDialog()
            return

        progress = QProgressDialog('Exporting connectors ...', 'Abort', 0, len(connector_id), self.iface.mainWindow())
        progress.setWindowTitle('CIN Connector Export - Automatic')
        progress.canceled.connect(self.scheduleAbort)
        progress.show()

        # iterate over polyline features
        with open(filename, 'w+') as connector_file:

            connector_file.write('########################################################################\n')
            connector_file.write('# This file was automatically generated by "Connector Export for ProMaiDes CIN module'
                                        'Export-QGIS-Plugin Version {version_1} \n'.format(version_1=VERSION))
            #date and time output
            now = datetime.now()
            dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
            connector_file.write('# Generated at {dt_string_1} '.format(dt_string_1=dt_string))
            connector_file.write('from polygon layer {filename_1} \n'.format(filename_1=polygonlayer.sourceName()))
            connector_file.write('# and from point layer {filename_2} \n'.format(filename_2=pointlayer.sourceName()))
            connector_file.write('# Comments are marked with #\n')
            connector_file.write('# There are three CI-elements:\n')
            connector_file.write('# 1. Points; as in this file)\n')
            connector_file.write('# 2. Connectors; linking Points with each other, multiple connectors in '
                                        'several directions are possible) \n')
            connector_file.write('# 3. Polygons; mostly final elements\n')
            connector_file.write('#\n')
            connector_file.write('# Explanation of data:\n')
            connector_file.write('#  Start the CI-connectors with !BEGIN and end it with !END; in between are:\n')
            connector_file.write('#  NumberOfPoints\n')
            connector_file.write('#  id(unique) id_from_CI_element type(point_polygon)  id_to_CI_element type(point_polygon)')
            connector_file.write('#\n')
            connector_file.write('########################################################################\n')
            connector_file.write('!BEGIN\n')
            connector_file.write('{number} #Number of CI Connectors \n'.format(number=len(connector_id)))

            for x in range(1, pair_index):
                connector_file.write('  {a} {b} point {c} point # Source: {d}; Sink: {e}\n'.format
                                     (a=connector_id[x], b=source_id_write[x], c=sink_id_write[x], d=str(source_name_write[x]), e=str(sink_name_write[x]),))
                if self.cancel:
                    break
            connector_file.write('!END\n\n')
            connector_file.close()

        #if not self.cancel:
        self.iface.messageBar().pushInfo(
            'CIN Connector Export',
            'Export finished successfully!'
           )

        progress.close()
        self.quitDialog()
        return

