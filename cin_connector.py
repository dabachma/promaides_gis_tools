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

UI_PATH = get_ui_path('ui_cin_2promaides_connector.ui ')

list_of_input = []
list_of_pairs = []  # multi-dimensional List for the source sink pairs

# This plugin exports the observations point file for the HYD-module of ProMaIdes from a point shape file;
# A name field (string) is required within the point layer
class PluginDialog(QDialog):

    def __init__(self, iface, parent=None, flags=Qt.WindowFlags()):
        QDialog.__init__(self, parent, flags)
        uic.loadUi(UI_PATH, self)
        self.iface = iface
        self.input_layer = None
        self.iface.currentLayerChanged.connect(self.setInputLayer)
        self.setInputLayer(self.iface.activeLayer())

        #  self.listWidget.currentRowChanged.connect(self.updateRasterPropertiesGroup)
        self.addButton_2source.clicked.connect(self.add2sourcelist)
        self.addButton_2sink.clicked.connect(self.add2sinklist)
        self.addButton_2source_sink_pair.clicked.connect(self.merge2pair)
        self.removeButton.clicked.connect(self.remove_pair)

        self.browseButton.clicked.connect(self.onBrowseButtonClicked)
        self.browseButton.setAutoDefault(False)

        self.comboBox_conTypes.addItem('physical')
        self.comboBox_conTypes.addItem('cyber')
        self.comboBox_conTypes.addItem('geographic')
        self.comboBox_conTypes.addItem('logical')

    def __del__(self):
        self.iface.currentLayerChanged.disconnect(self.setInputLayer)

    def onBrowseButtonClicked(self):
        currentFolder = self.folderEdit.text()
        folder = QFileDialog.getExistingDirectory(self.iface.mainWindow(), 'CIN_Connector_Export', currentFolder)
        if folder != '':
            self.folderEdit.setText(folder)
            self.folderEdit.editingFinished.emit()

    def add2sourcelist(self):
        for item in self.listWidget_input.selectedItems():
            self.comboBox_source.addItem(item.text())

    def add2sinklist(self):
        for item in self.listWidget_input.selectedItems():
            self.comboBox_sink.addItem(item.text())

    def merge2pair(self):

        pair_index = self.listWidget_pairs.count()
        str_source = self.comboBox_source.currentText()
        str_sink = self.comboBox_sink.currentText()
        str_con_type = self.comboBox_conTypes.currentText()

        list_of_pairs.append([str_source, str_sink, pair_index, str_con_type])
        self.listWidget_pairs.addItem("Source: "+ self.comboBox_source.currentText() + "; Sink: " + self.comboBox_sink.currentText() + ";")

    def remove_pair(self):
        del list_of_pairs[self.listWidget_pairs.currentRow()]
        self.listWidget_pairs.takeItem(self.listWidget_pairs.currentRow())

    def setInputLayer(self, layer):
        if not layer:
            self.input_layer = None
            self.input_label.setText('<i>No layer selected.<br>'
                                     'Please select a merged CI point layer.</i>')
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
        #  Critical Infrastructure Objects in Input Layers
        #  self.listWidget_input.currentRowChanged.connect(self.updateRasterPropertiesGroup) #  listWidget_input
        self.addButton_2source.setEnabled(True)#  addButton_2source
        self.addButton_2sink.setEnabled(True)  # addButton_2sink
        self.addButton_2source_sink_pair.setEnabled(True)

        #  CI coupled Pairs
        # listWidget_pairs
        lay = self.input_layer
        for feature in lay.getFeatures():
            self.listWidget_input.addItem(feature["name"])
            list_of_input.append([feature["name"], feature["osm_id"], feature["level"], feature["sector"], feature["final"], feature["threshold"]])

class CINConnectorExport(object):

    def __init__(self, iface):
        self.iface = iface
        self.dialog = None
        self.cancel = False
        self.act = QAction('CIN Connector Export', iface.mainWindow())
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
        self.dialog = PluginDialog(self.iface, self.iface.mainWindow())
        self.dialog.pushButton_ok.clicked.connect(self.execTool)
        self.dialog.pushButton_ok.setAutoDefault(False)
        self.dialog.pushButton_cancel.clicked.connect(self.quitDialog)
        self.dialog.pushButton_cancel.setAutoDefault(False)
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
        filename = (self.dialog.folderEdit.text() + "/CIN_Connector_Export.prmds")
        print(filename, "filename")

        if not filename:
            self.iface.messageBar().pushCritical(
                'CIN Connector Export',
                'No output filename given!'
            )
            self.quitDialog()

        progress = QProgressDialog('Exporting connectors ...', 'Abort', 0, len(list_of_pairs), self.iface.mainWindow())
        progress.setWindowTitle('CIN Connector Export')
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
            connector_file.write('from layer {filename_1} \n'.format(filename_1=self.dialog.input_layer.sourceName()))
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
            connector_file.write('########################################################################\n\n')

            connector_file.write('!BEGIN\n')
            connector_file.write('{number} #Number of CI Connectors \n'.format(number=len(list_of_pairs)))
            index = 0

            for x1 in range(len(list_of_pairs)):
                print (range(len(list_of_pairs)),"range(len(list_of_pairs)")
                pair_index = x1
                for x2 in range(len(list_of_input)):
                    if list_of_pairs[x1][0] == list_of_input[x2][0]:
                        source_name_write = list_of_input [x1][0]
                        source_id_write = list_of_input[x1][1]
                    if list_of_pairs[x1][1] == list_of_input[x2][0]:
                        sink_name_write = list_of_input [x2][0]
                        sink_id_write = list_of_input[x2][1]
                connector_file.write('  {a} {b} point {c} point # Source: {d}; Sink: {e}\n'.format
                                     (a=pair_index, b=source_id_write, c=sink_id_write, d=str(source_name_write), e=str(sink_name_write),))

            connector_file.write('!END\n\n')
        progress.close()
        #if not self.cancel:
        self.iface.messageBar().pushInfo(
            'CIN Connector Export',
            'Export finished successfully!'
           )

        self.quitDialog()
