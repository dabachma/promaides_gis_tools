from __future__ import unicode_literals
from __future__ import absolute_import

# system modules
import os
import math
from datetime import datetime
import tempfile

# QGIS modules
from qgis.core import *
from qgis.gui import *
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.PyQt import uic


# promaides modules
from .interpolate import RasterInterpolator
from .raster import SimpleRasterWriter
from .environment import get_ui_path
from .version import *
from .utils import *


UI_PATH = get_ui_path('ui_raster_export.ui')

# This plugin exports the 2D-floodplain raster file(s) for the HYD-module of ProMaIdes;
# The polygons are created as temporary layer
# TODO Change to existing polygon shp
class PluginDialog(QDialog):

    rasterAdded = pyqtSignal(int, QgsGeometry)
    rasterUpdated = pyqtSignal(int, QgsGeometry)
    rasterRemoved = pyqtSignal(int)
    ClosingSignal = pyqtSignal()

    xllRole = 111  # Those numbers only describe an ID but not the actual values
    yllRole = 112
    nrRole = 113
    ncRole = 114
    drcRole = 115

    def __init__(self, iface, parent=None, flags=Qt.WindowFlags()):
        QDialog.__init__(self, parent, flags)
        uic.loadUi(UI_PATH, self)
        self.iface = iface

        self.ecnLayerBox.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.popLayerBox.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.AreaLayerBox.setFilters(QgsMapLayerProxyModel.PolygonLayer)

        # The module consists of two input options ecn/ pop. The lines below set the default that none of them are chosen in the beginning.
        # The user has to choose one of them. The two bottom functions will make sure that only one of the options can be chosen.
        self.mGroupBox_ecn.setChecked(False)
        self.mGroupBox_pop.setChecked(False)
        self.mGroupBox_ecn.clicked.connect(self.check_mGroupBox_ecn)
        self.mGroupBox_pop.clicked.connect(self.check_mGroupBox_pop)

        self.picker = QgsMapToolEmitPoint(self.iface.mapCanvas())

        self.addButton.setEnabled(False)
        self.zoomButton.setEnabled(False)
        self.removeButton.setEnabled(False)
        self.ExportButton.setEnabled(False)
        self.groupBox.setEnabled(False)
        self.ImportButton.setEnabled(False)
        self.AreaLayerBox.setLayer(None)
        self.ecnLayerBox.setLayer(None)
        self.popLayerBox.setLayer(None)

        self.removeButton.clicked.connect(self.removeRasterItems)
        self.removeButton.setAutoDefault(False)
        self.listWidget.currentRowChanged.connect(self.updateRasterPropertiesGroup)
        self.ecnLayerBox.layerChanged.connect(self.updateECNBox)
        self.popLayerBox.layerChanged.connect(self.updatePOPBox)
        self.AreaLayerBox.layerChanged.connect(self.UpdateImportButtons)
        self.pickButton.clicked.connect(self.enableMapPicker)
        self.pickButton.setAutoDefault(False)
        self.browseButton.clicked.connect(self.onBrowseButtonClicked)
        self.browseButton.setAutoDefault(False)

    def closeEvent(self, event):
        self.ClosingSignal.emit()

    def UpdateImportButtons(self):
        if self.AreaLayerBox.currentLayer():
            self.ImportButton.setEnabled(True)
        else:
            self.ImportButton.setEnabled(False)

    def check_mGroupBox_ecn(self):
        self.mGroupBox_pop.setChecked(False)
        self.ecnNaNBox.setEnabled(True)
        self.ecndeltaBox.setEnabled(True)

    def check_mGroupBox_pop(self):

        self.mGroupBox_ecn.setChecked(False)
        self.popNaNBox.setEnabled(True)
        self.popTypeBox.setEnabled(True)

    def enableMapPicker(self, clicked):
        #  Triggered after 'pick coordinates from Map ...' and will link to QG functino to read coordinates from a map click.
        if clicked:
            self.picker.canvasClicked.connect(self.onMapClicked)
            self.iface.mapCanvas().setMapTool(self.picker)
        else:
            self.picker.canvasClicked.disconnect(self.onMapClicked)
            self.iface.mapCanvas().unsetMapTool(self.picker)

    def onMapClicked(self, point, button):
        if button == Qt.LeftButton:
            self.xllBox.setValue(point.x())
            self.yllBox.setValue(point.y())
            self.xllBox.editingFinished.emit()

    def ecnLayer(self):
        #  RS: This command will make the currently chosen layer in qgis the layer now defined as lucLayer
        return self.ecnLayerBox.currentLayer()

    def ecnNaN(self):
        # This will define the number in the nanBox in theQGIS GUI as ecnNaN
        return self.ecnNaNBox.value()

    def ecnDelta(self):
        # This defines the number in the deltaMobImmobBox as the difference between values for mobile and immobile
        return self.ecndeltaBox.value()

    def popLayer(self):
        #  RS: This command will make the currently chosen layer in qgis the layer now defined as lucLayer
        return self.popLayerBox.currentLayer()

    def popNaN(self):
        # This will define the number in the nanBox in theQGIS GUI as popnNaN (*) maybe useless, question asked to root
        return self.popNaNBox.value()

    def popType(self):
        # This will define the number in the nanBox in theQGIS GUI as popnNaN (*) maybe useless, question asked to root
        return self.popTypeBox.value()

    def onBrowseButtonClicked(self):
        #  Definition of the directory you will be lead to when choosing the output folder.
        #  Naming the heading of the window opening
        #  Covering the case of no file/folder chosen
        currentFolder = self.folderEdit.text()
        folder = QFileDialog.getExistingDirectory(self.iface.mainWindow(), 'DAM Exposure Raster Export', currentFolder)
        if folder != '':
            self.folderEdit.setText(folder)
            self.folderEdit.editingFinished.emit()

    def outFolder(self):
        return self.folderEdit.text()

    def updateECNBox(self, layer):
        #  Enables the option for user to change the layer which is basis for raster input
        if not layer:
            self.addButton.setEnabled(False)
            return

        self.addButton.setEnabled(True)
        self.groupBox.setEnabled(True)

        ############################################
        # raster settings
        self.xllBox.setEnabled(False)
        self.yllBox.setEnabled(False)
        self.pickButton.setEnabled(False)
        self.nrBox.setEnabled(False)
        self.ncBox.setEnabled(False)
        self.drcBox.setEnabled(False)
        self.ExportButton.setEnabled(False)
        # ecn specific settings
        self.ecnNaNBox.setEnabled(False)
        self.ecndeltaBox.setEnabled(False)
        #############################################

    def updatePOPBox(self, layer):
        #  Enables the option for user to change the layer which is basis for raster input
        if not layer:
            self.addButton.setEnabled(False)
            return

        self.addButton.setEnabled(True)
        self.groupBox.setEnabled(True)

        ############################################
        # raster settings
        self.xllBox.setEnabled(False)
        self.yllBox.setEnabled(False)
        self.pickButton.setEnabled(False)
        self.nrBox.setEnabled(False)
        self.ncBox.setEnabled(False)
        self.drcBox.setEnabled(False)
        self.ExportButton.setEnabled(False)
        # ecn specific settings
        self.popNaNBox.setEnabled(False)
        self.popTypeBox.setEnabled(False)
        #############################################


    def removeRasterItems(self):
        #  removes raster item from listWidget and the corresponding values from groupBox
        #  if no more rasters in the widget list raster settings will be disabled
        for item in self.listWidget.selectedItems():
            row = self.listWidget.row(item)
            self.listWidget.takeItem(row)
            self.rasterRemoved.emit(int(row + 1))

        if self.listWidget.count() == 0:
            self.zoomButton.setEnabled(False)
            self.removeButton.setEnabled(False)
            self.ExportButton.setEnabled(False)
            self.groupBox.setEnabled(False)
            ############################################
            #raster settings
            self.xllBox.setEnabled(False)
            self.yllBox.setEnabled(False)
            self.pickButton.setEnabled(False)
            self.nrBox.setEnabled(False)
            self.ncBox.setEnabled(False)
            self.drcBox.setEnabled(False)
            self.ExportButton.setEnabled(False)
            #############################################

    def updateRasterPropertiesGroup(self, row):
        #  used when new properties are added to raster settings to automatically update bounding box
        item = self.listWidget.item(row)
        if item is None:
            return

        self.xllBox.setValue(item.data(PluginDialog.xllRole))
        self.yllBox.setValue(item.data(PluginDialog.yllRole))
        self.nrBox.setValue(item.data(PluginDialog.nrRole))
        self.ncBox.setValue(item.data(PluginDialog.ncRole))
        self.drcBox.setValue(item.data(PluginDialog.drcRole))


class DAMRasterExport(object):

    def __init__(self, iface):
        self.iface = iface
        self.dialog = None
        self.cancel = False
        self.previewLayer = None
        self.act = QAction('Land-Use-Category Raster Export', iface.mainWindow())
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
        #  the function execDialog builds the backbone for the possible options to click in the plugin GUI
        #  for every button pressed it connects to a specific other function.
        """
        """
        self.dialog = PluginDialog(self.iface, self.iface.mainWindow())
        self.dialog.pushButton_ok.clicked.connect(self.execTool)
        self.dialog.pushButton_ok.setAutoDefault(False)
        self.dialog.pushButton_cancel.clicked.connect(self.quitDialog)
        self.dialog.pushButton_cancel.setAutoDefault(False)
        self.dialog.rasterAdded.connect(self.addRasterBounds)
        self.dialog.rasterUpdated.connect(self.updateRasterBounds)
        self.dialog.rasterRemoved.connect(self.removeRasterBounds)
        self.dialog.setModal(False)
        self.dialog.ExportButton.clicked.connect(self.SaveasPolygon)
        self.dialog.addButton.clicked.connect(self.addNewRasterItem)
        self.dialog.addButton.setAutoDefault(False)
        self.dialog.ImportButton.clicked.connect(self.ImportAreaFromPolygon)
        self.dialog.zoomButton.clicked.connect(self.zoomToRaster)
        self.dialog.zoomButton.setAutoDefault(False)

        self.dialog.ClosingSignal.connect(self.quitDialog)

        self.dialog.xllBox.editingFinished.connect(self.saveRasterProperties)
        self.dialog.yllBox.editingFinished.connect(self.saveRasterProperties)
        self.dialog.drcBox.editingFinished.connect(self.saveRasterProperties)
        self.dialog.nrBox.editingFinished.connect(self.saveRasterProperties)
        self.dialog.ncBox.editingFinished.connect(self.saveRasterProperties)

        self.previewLayer = QgsVectorLayer('Polygon', 'ProMaIDes LUC Raster', 'memory')
        self.previewLayer.setCrs(QgsCoordinateReferenceSystem(self.iface.mapCanvas().mapSettings().destinationCrs().authid()))
        self.previewLayer.dataProvider().addAttributes([QgsField("xll", QVariant.Double),
                                                        QgsField("yll", QVariant.Double),
                                                        QgsField("dy", QVariant.Double),
                                                        QgsField("dx", QVariant.Double),
                                                        QgsField("nr", QVariant.Double),
                                                        QgsField("nc", QVariant.Double)])
        self.previewLayer.updateFields()


        # set layer properties
        my_symbol = QgsFillSymbol.createSimple({'color': 'black', 'outline_color': 'blue', 'outline_width': '0.8',
                                                'style':'no'})

        self.previewLayer.renderer().setSymbol(my_symbol)
        QgsProject.instance().addMapLayer(self.previewLayer)

        self.act.setEnabled(False)
        self.dialog.show()

    def scheduleAbort(self):
        self.cancel = True
    ImportFromPolygon = False

    def ImportAreaFromPolygon(self):
        self.ImportFromPolygon = True
        self.addNewRasterItem()

    def zoomToRaster(self):
        #  RS: Reacts when zoomButton is pressed and changes bounding box to the raster settings entered in raster settings.
        #  item = self.listWidget.currentItem()
        item = self.dialog.listWidget.currentItem()

        xll = item.data(PluginDialog.xllRole)  # RS only rectangular grids
        yll = item.data(PluginDialog.yllRole)
        nr = item.data(PluginDialog.nrRole)  # RS raster number of cells per row and column
        nc = item.data(PluginDialog.ncRole)  # RS raster number of cells per row and column
        drc = item.data(PluginDialog.drcRole)  # RS delta row and column cell

        bb = self.polygon(xll, yll, (nr * drc), (nc * drc)).boundingBox()

        self.dialog.iface.mapCanvas().setExtent(bb)
        self.dialog.iface.mapCanvas().refresh()

    def addNewRasterItem(self):
        #  activated once a new raster is added. default values defined below are filled in

        if self.ImportFromPolygon == True:
            try:
                layer = self.dialog.AreaLayerBox.currentLayer()
                features = layer.getFeatures()

                for i, f in enumerate(features):
                    num = self.dialog.listWidget.count() + 1
                    item = QListWidgetItem('raster_{:d}'.format(num))
                    item.setData(PluginDialog.xllRole, f.attribute("xll"))
                    item.setData(PluginDialog.yllRole, f.attribute("yll"))
                    item.setData(PluginDialog.nrRole, f.attribute("nr"))
                    item.setData(PluginDialog.ncRole, f.attribute("nc"))
                    item.setData(PluginDialog.drcRole, f.attribute("dy"))

                    item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled)

                    self.dialog.removeButton.setEnabled(True)
                    self.dialog.ExportButton.setEnabled(True)
                    self.dialog.zoomButton.setEnabled(True)
                    self.dialog.groupBox.setEnabled(True)
                    ############################################
                    # raster settings
                    self.dialog.xllBox.setEnabled(True)
                    self.dialog.yllBox.setEnabled(True)
                    self.dialog.pickButton.setEnabled(True)
                    self.dialog.drcBox.setEnabled(True)
                    self.dialog.nrBox.setEnabled(True)
                    self.dialog.ncBox.setEnabled(True)
                    self.dialog.ExportButton.setEnabled(True)
                    #############################################
                    polygon = self.polygon(0.0, 0.0, 100.0, 100.0)
                    self.dialog.rasterAdded.emit(int(self.dialog.listWidget.count() + 1), polygon)

                    self.dialog.listWidget.addItem(item)
                    self.dialog.listWidget.setCurrentItem(item)
                    self.saveRasterProperties()
                    if i == layer.featureCount() - 1:
                        self.ImportFromPolygon = False
                        return
            except:
                self.iface.messageBar().pushCritical(
                    '2D-Floodplain Export',
                    'Area Cannot be Imported from Polygon !'
                )
                self.ImportFromPolygon = False
                return

        num = self.dialog.listWidget.count() + 1
        item = QListWidgetItem('raster_{:d}'.format(num))
        item.setData(PluginDialog.xllRole, -157230)  # The first argument refers back to an id, the second one to the actual value
        item.setData(PluginDialog.yllRole, 1066410)
        item.setData(PluginDialog.drcRole, 310.0)  # 25
        item.setData(PluginDialog.nrRole, 3)  # 100
        item.setData(PluginDialog.ncRole, 2)  # 120

        item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled)

        self.dialog.removeButton.setEnabled(True)
        self.dialog.ExportButton.setEnabled(True)
        self.dialog.zoomButton.setEnabled(True)
        self.dialog.groupBox.setEnabled(True)
        ############################################
        # raster settings
        self.dialog.xllBox.setEnabled(True)
        self.dialog.yllBox.setEnabled(True)
        self.dialog.pickButton.setEnabled(True)
        self.dialog.drcBox.setEnabled(True)
        self.dialog.nrBox.setEnabled(True)
        self.dialog.ncBox.setEnabled(True)
        self.dialog.ExportButton.setEnabled(True)
        #############################################


        polygon = self.polygon(0.0, 0.0, 100.0, 100.0)
        self.dialog.rasterAdded.emit(int(self.dialog.listWidget.count() + 1), polygon)

        self.dialog.listWidget.addItem(item)
        self.dialog.listWidget.setCurrentItem(item)

        self.saveRasterProperties()

    def polygon(self, xll, yll, dx, dy):
        #  Function for polygon in format that QG can pick up
        poly = [QgsPointXY(xll, yll),
                QgsPointXY(xll + dx, yll),
                QgsPointXY(xll + dx, yll + dy),
                QgsPointXY(xll, yll + dy)]
        return QgsGeometry.fromPolygonXY([poly])

    def SaveasPolygon(self):
        try:
            original = self.previewLayer
            currentFolder = QgsProject.instance().homePath()
            originalpath = QFileDialog.getExistingDirectory(self.iface.mainWindow(), '2D-Floodplain Export TestyMcTest', currentFolder)
            if originalpath == '':
                self.iface.messageBar().pushCritical(
                    '2D-Floodplain Export',
                    'New layer cannot be created!'
                )
                return
            originalname = original.name()
            writingpath = originalpath + "/" + originalname + "_exported.shp"
            _writer = QgsVectorFileWriter.writeAsVectorFormat(original, writingpath, 'utf-8',
                                                              driverName='ESRI Shapefile')
            loadedlayer = QgsVectorLayer(writingpath, originalname + "_exported", "ogr")
            QgsProject.instance().addMapLayer(loadedlayer)
            self.dialog.iface.layerTreeView().setCurrentLayer(original)

        except:
            self.iface.messageBar().pushCritical(
                '2D-Floodplain Export',
                'New layer cannot be created!'
            )
            self.quitDialog()
            return

    def rasters(self):

        result = []
        for row in range(self.dialog.listWidget.count()):
            item = self.dialog.listWidget.item(row)

            xll = item.data(PluginDialog.xllRole)
            yll = item.data(PluginDialog.yllRole)
            nr = item.data(PluginDialog.nrRole)
            nc = item.data(PluginDialog.ncRole)
            drc = item.data(PluginDialog.drcRole)

            nodata = {
                'ecn': self.dialog.ecnNaNBox.value(),
                'pop': self.dialog.popNaNBox.value(),
            }
            filename = os.path.join(self.dialog.folderEdit.text(), item.text())
            raster = SimpleRasterWriter(xll, yll, nr, nc, drc, item, nodata)

            result.append((raster, filename))

        return result

    def saveRasterPropertiesNoRedraw(self):
        self.saveRasterProperties(False)

    def saveRasterProperties(self, redraw=True):

        item = self.dialog.listWidget.currentItem()

        if not item:
            return

        if type(self.previewLayer) != type(None):
            xll = self.dialog.xllBox.value()
            yll = self.dialog.yllBox.value()
            dx = self.dialog.ncBox.value() * self.dialog.drcBox.value()
            dy = self.dialog.nrBox.value() * self.dialog.drcBox.value()
            nr = self.dialog.nrBox.value()
            nc = self.dialog.ncBox.value()

            layer=self.previewLayer
            prov = layer.dataProvider()
            # lookup index of fields using their names
            xll_idx = layer.fields().lookupField('xll')
            yll_idx = layer.fields().lookupField('yll')
            dx_idx = layer.fields().lookupField('dx')
            dy_idx = layer.fields().lookupField('dy')
            nr_idx = layer.fields().lookupField('nr')
            nc_idx = layer.fields().lookupField('nc')

            # create a dictionary with field index as key and the attribute you want as value
            atts = {xll_idx: xll, yll_idx: yll, dx_idx: dx/nc, dy_idx: dy/nr, nr_idx: nr, nc_idx: nc}

            # store reference to feature you want to update
            feat = layer.getFeature(self.dialog.listWidget.row(item)+1)
            # call changeAttributeValues(), pass feature id and attribute dictionary
            prov.changeAttributeValues({feat.id(): atts})

            item.setData(PluginDialog.xllRole, xll)
            item.setData(PluginDialog.yllRole, yll)
            item.setData(PluginDialog.nrRole, self.dialog.nrBox.value())
            item.setData(PluginDialog.ncRole, self.dialog.ncBox.value())
            item.setData(PluginDialog.drcRole, self.dialog.drcBox.value())

            if True:
                self.dialog.rasterUpdated.emit(int(self.dialog.listWidget.row(item) + 1), self.polygon(xll, yll, dx, dy))

    def quitDialog(self):
        if type(self.previewLayer) != type(None):
            QgsProject.instance().removeMapLayer(self.previewLayer)
        self.previewLayer = None
        self.act.setEnabled(True)
        self.cancel = False
        self.dialog.reject()

    def execTool(self):
        """Performs the Land Use Category export."""
        input_layers = {
            'ecn': {
                'layer': self.dialog.ecnLayer(),
                'interpol_mode': "nearest neighbor",  #  Previously dialog box lucInterpolationMode
                'nan': self.dialog.ecnNaN(),
                'deltaecn': self.dialog.ecnDelta()
                },
            'pop': {
                'layer': self.dialog.popLayer(),
                'interpol_mode': "nearest neighbor",  # Previously dialog box lucInterpolationMode
                'nan': self.dialog.popNaN(),
                'pop_type': self.dialog.popType()
                }
        }

        rasters = self.rasters()  # list of tuples (raster, filename)
        num_cells = sum([r.num_cells() for r, f in rasters])

        if num_cells == 0:
            self.quitDialog()
            return

        if len(rasters) > 1:
            text = 'Interpolating and exporting %d rasters ...' % len(rasters)
        else:
            text = 'Interpolating and exporting raster ...'

        progress = QProgressDialog(text, 'Abort', 0, num_cells, self.iface.mainWindow())
        progress.setWindowTitle('DAM Exposure Raster Export')
        progress.canceled.connect(self.scheduleAbort)
        progress.show()

        for raster, filename in rasters:
            try:
                self.export_raster(input_layers, raster, filename, progress)
            except IOError:
                QMessageBox.critical(self.iface.mainWindow(), 'I/O Error', 'An I/O error occured during\nraster export to file\n\n%s' % filename)
                progress.close()
                self.quitDialog()
                return

            if self.cancel:
                progress.close()
                self.quitDialog()
                return

        progress.close()
        self.quitDialog()
        return

    def export_raster(self, input_layers, out_raster, filename, progress=None):
        trans, interpol, mob_values, pop_type_values = dict(), dict(), dict(), dict()
        for data_name, items in list(input_layers.items()):
            if items['layer']:
                trans[data_name] = QgsCoordinateTransform(self.previewLayer.crs(), items['layer'].crs(), QgsProject.instance()).transform
            else:
                trans[data_name] = lambda p: p
            interpol[data_name] = RasterInterpolator(items['layer'], 1, items['interpol_mode'],
                                                     items['nan']).interpolate
            # if the dataayer is named ecn and the tick box in the user interface is checked the ecn export will be done.
            if data_name == 'ecn' and self.dialog.mGroupBox_ecn.isChecked():
                rastertype_0 = 'ecn'
                rastertype_1 = 'ecn_immob'
                rastertype_2 = 'ecn_mob'
                # Writing the standard raster file for economic immobile damages
                out_raster.open(filename, input_layers, rastertype_1)
                for i in range(int(out_raster.num_cells())):
                    point = out_raster.cell_center(i)

                    values = {data_name: interpol[data_name](trans[data_name](QgsPointXY(point)))}
                    out_raster.write_cell(values, rastertype_0)
                    if progress:
                        progress.setValue(progress.value() + 1)
                out_raster.close()

                # writing a raster file as input for the mobile economic impacts.
                # for that a user-chosen number is added to the land use id - by default this is 1000
                out_raster.open(filename, input_layers, rastertype_2)
                for i in range(int(out_raster.num_cells())):
                    point = out_raster.cell_center(i)

                    values = {data_name: interpol[data_name](trans[data_name](QgsPointXY(point)))}
                    mob_values[rastertype_0] = values[rastertype_0]+input_layers[rastertype_0]['deltaecn']  # adding the user chosen value to initial immob value

                    out_raster.write_cell(mob_values, rastertype_0)
                    if progress:
                        progress.setValue(progress.value() + 1)
                out_raster.close()

            elif data_name == 'pop' and self.dialog.mGroupBox_pop.isChecked():
                rastertype_0 = 'pop'
                rastertype_1 = 'pop_dens'
                rastertype_2 = 'pop_type'
                # Writing the standard raster file for economic immobile damages
                out_raster.open(filename, input_layers, rastertype_1)
                for i in range(int(out_raster.num_cells())):
                    point = out_raster.cell_center(i)
                    values = {data_name: interpol[data_name](trans[data_name](QgsPointXY(point)))}
                    out_raster.write_cell(values, rastertype_0)
                    if progress:
                        progress.setValue(progress.value() + 1)
                out_raster.close()

                # writing a raster file as input for the mobile economic impacts.
                # for that a user-chosen number is added to the land use id - by default this is 1000
                out_raster.open(filename, input_layers, rastertype_2)
                for i in range(int(out_raster.num_cells())):
                    point = out_raster.cell_center(i)
                    values = {data_name: interpol[data_name](trans[data_name](QgsPointXY(point)))}

                    if values[rastertype_0] == 0:
                        pop_type_values[rastertype_0] = 0
                    else:
                        pop_type_values[rastertype_0] = input_layers[rastertype_0][rastertype_2]

                    out_raster.write_cell(pop_type_values, rastertype_0)
                    if progress:
                        progress.setValue(progress.value() + 1)
                out_raster.close()
            else:
                continue

        #######################################################################

    def addRasterBounds(self, id, polygon):
        if type(self.previewLayer) != type(None):
            dp = self.previewLayer.dataProvider()
            newPoly = QgsFeature()
            newPoly.setGeometry(polygon)
            dp.addFeatures([newPoly])


        self.previewLayer.updateExtents()
        self.previewLayer.triggerRepaint()

    def updateRasterBounds(self, id, polygon):
        if type(self.previewLayer) != type(None):
            feat=self.previewLayer.getFeatures()
            idlist=[]
            for f in feat:
                i=f.id()
                idlist.append(i)
                idlist.sort()
            idtemp=idlist[id-1]
            self.previewLayer.dataProvider().changeGeometryValues({idtemp: polygon})
            self.previewLayer.updateExtents()
            self.previewLayer.triggerRepaint()

    def removeRasterBounds(self, id):
        if type(self.previewLayer) != type(None):
            layer = self.previewLayer
            prov = layer.dataProvider()
            feat=self.previewLayer.getFeatures()
            idlist=[]
            for f in feat:
                i=f.id()
                idlist.append(i)
                idlist.sort()
            idtemp=idlist[id-1]

            f = layer.getFeature(idtemp)
            xll_idx = layer.fields().lookupField('xll')
            yll_idx = layer.fields().lookupField('yll')
            dx_idx = layer.fields().lookupField('dx')
            dy_idx = layer.fields().lookupField('dy')
            nr_idx = layer.fields().lookupField('nr')
            nc_idx = layer.fields().lookupField('nc')
            atts = {xll_idx: 0, yll_idx: 0, dx_idx: 0, dy_idx: 0,nc_idx: 0, nr_idx: 0}
            prov.changeAttributeValues({f.id(): atts})
            layer.updateFields()
            self.previewLayer.dataProvider().deleteFeatures([idtemp])
            self.previewLayer.updateExtents()
            self.previewLayer.triggerRepaint()

