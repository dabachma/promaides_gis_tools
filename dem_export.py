from __future__ import unicode_literals
from __future__ import absolute_import

# system modules
import os
import math
from datetime import datetime
import tempfile
import webbrowser

# QGIS modules
from qgis.core import *
from qgis.gui import *
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.PyQt import uic


# promaides modules
from .interpolate import RasterInterpolator
from .raster import RasterWriter
from .environment import get_ui_path
from .version import *
from .utils import *


UI_PATH = get_ui_path('ui_dem_export.ui')

# This plugin exports the 2D-floodplain raster file(s) for the HYD-module of ProMaIdes;
# The polygons are created as temporary layer
# TODO Change to existing polygon shp
class PluginDialog(QDialog):

    rasterAdded = pyqtSignal(int, QgsGeometry)
    rasterUpdated = pyqtSignal(int, QgsGeometry)
    rasterRemoved = pyqtSignal(int)
    ClosingSignal = pyqtSignal()
    RejectSignal = pyqtSignal()

    xllRole = 111
    yllRole = 112
    nrRole = 113
    ncRole = 114
    drRole = 115
    dcRole = 116
    angleRole = 117

    def __init__(self, iface, parent=None, flags=Qt.WindowFlags()):
        QDialog.__init__(self, parent, flags)
        uic.loadUi(UI_PATH, self)
        self.iface = iface

        self.demLayerBox.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.roughnessLayerBox.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.initLayerBox.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.BCLayerBox.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.AreaLayerBox.setFilters(QgsMapLayerProxyModel.PolygonLayer)

        self.interpolationBox.addItem('nearest neighbor (downscaling/upscaling)')
        self.interpolationBox.addItem('bi-linear (downscaling)')
        self.interpolationBox.addItem('bi-cubic (downscaling)')
        self.interpolationBox.addItem('average (upscaling)')
        self.interpolationBox.addItem('max (upscaling)')
        self.interpolationBox.addItem('min (upscaling)')

        self.stationarytype_box.setExpression('true')
        self.boundaryvalue_box.setExpression('0')
        self.boundarytype_box.setExpression("'area'")

        self.picker = QgsMapToolEmitPoint(self.iface.mapCanvas())


        self.addButton.setEnabled(False)
        self.zoomButton.setEnabled(False)
        self.removeButton.setEnabled(False)
        self.ExportButton.setEnabled(False)
        self.bandBox.setEnabled(False)
        self.ilmBox.setEnabled(False)
        self.groupBox.setEnabled(False)
        self.ImportButton.setEnabled(False)
        self.initAbsoluteBox.setEnabled(True)
        self.roughnessLayerBox.setLayer(None)
        self.initLayerBox.setLayer(None)
        self.BCLayerBox.setLayer(None)
        self.AreaLayerBox.setLayer(None)
        self.demLayerBox.setLayer(None)


        self.removeButton.clicked.connect(self.removeRasterItems)
        self.removeButton.setAutoDefault(False)
        self.listWidget.currentRowChanged.connect(self.updateRasterPropertiesGroup)
        self.demLayerBox.layerChanged.connect(self.updateDEMBandBox)
        self.BCLayerBox.layerChanged.connect(self.updatePolygonTabs)
        self.AreaLayerBox.layerChanged.connect(self.UpdateImportButtons)
        self.roughnessLayerBox.layerChanged.connect(self.updateRoughnessBandBox)
        self.initLayerBox.layerChanged.connect(self.updateInitBandBox)
        self.pickButton.clicked.connect(self.enableMapPicker)
        self.HelpButton.clicked.connect(self.Help)
        self.pickButton.setAutoDefault(False)

        self.mGroupBox_4.setSaveCollapsedState(False)
        self.mGroupBox_2.setSaveCollapsedState(False)
        self.mGroupBox.setSaveCollapsedState(False)
        self.mGroupBox_3.setSaveCollapsedState(False)

        self.mGroupBox_4.setCollapsed(True)
        self.mGroupBox_2.setCollapsed(True)
        self.mGroupBox.setCollapsed(True)
        self.mGroupBox_3.setCollapsed(True)
        self.resize(1000, 500)


        self.browseButton.clicked.connect(self.onBrowseButtonClicked)
        self.browseButton.setAutoDefault(False)

    def createIlmFile(self):
        if self.ilmBox.checkState() == Qt.Checked:
            return True
        else:
            return False

    def closeEvent(self, event):
        self.ClosingSignal.emit()

    def reject(self):
        self.RejectSignal.emit()

    def Help(self):
        webbrowser.open("https://promaides.myjetbrains.com/youtrack/articles/PMDP-A-44/2D-Floodplain-Export")


    def UpdateImportButtons(self):
        if self.AreaLayerBox.currentLayer():
            self.ImportButton.setEnabled(True)
        else:
            self.ImportButton.setEnabled(False)



    def enableMapPicker(self, clicked):
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


    def demLayer(self):
        return self.demLayerBox.currentLayer()

    def demBand(self):
        return self.bandBox.value()

    def demInterpolationMode(self):
        return self.interpolationBox.currentText()

    def demNaN(self):
        return self.demNaNBox.value()

    def roughnessLayer(self):
        if self.mGroupBox.isChecked():
            return self.roughnessLayerBox.currentLayer()
        else:
            self.roughnessLayerBox.setLayer(None)

    def roughnessBand(self):
        return self.roughnessBandBox.value()

    def roughnessNaN(self):
        return self.roughnessNaNBox.value()

    def initLayer(self):
        if self.mGroupBox_2.isChecked():
            return self.initLayerBox.currentLayer()
        else:
            self.initLayerBox.setLayer(None)

    def initBand(self):
        return self.initBandBox.value()

    def initNaN(self):
        return self.initNaNBox.value()

    def BCLayer(self):
        return self.BCLayerBox.currentLayer()


    def onBrowseButtonClicked(self):
        currentFolder = self.folderEdit.text()
        folder = QFileDialog.getExistingDirectory(self.iface.mainWindow(), '2D-Floodplain Export', currentFolder)
        if folder != '':
            self.folderEdit.setText(folder)
            self.folderEdit.editingFinished.emit()

    def outFolder(self):
        return self.folderEdit.text()

    def updateDEMBandBox(self, layer):
        if not layer:
            self.bandBox.setEnabled(False)
            self.addButton.setEnabled(False)
            return

        self.bandBox.setEnabled(True)
        self.addButton.setEnabled(True)
        self.groupBox.setEnabled(True)

        ############################################
        # raster settings
        self.xllBox.setEnabled(False)
        self.yllBox.setEnabled(False)
        self.pickButton.setEnabled(False)
        self.drBox.setEnabled(False)
        self.dcBox.setEnabled(False)
        self.nrBox.setEnabled(False)
        self.ncBox.setEnabled(False)
        self.ExportButton.setEnabled(False)
        self.angleBox.setEnabled(False)
        #############################################

        self.bandBox.setMaximum(layer.bandCount())
        self.bandBox.setValue(1)

    def updateRoughnessBandBox(self, layer):
        if not layer:
            self.roughnessBandBox.setEnabled(False)
            return

        self.roughnessBandBox.setEnabled(True)
        self.roughnessBandBox.setMaximum(layer.bandCount())
        self.roughnessBandBox.setValue(1)

    def updateInitBandBox(self, layer):
        if not layer:
            self.initBandBox.setEnabled(False)
            return

        self.initBandBox.setEnabled(True)
        self.initBandBox.setMaximum(layer.bandCount())
        self.initBandBox.setValue(1)

    def updatePolygonTabs(self, layer):
        self.stationarytype_box.setLayer(self.BCLayer())
        self.boundaryvalue_box.setLayer(self.BCLayer())
        self.boundarytype_box.setLayer(self.BCLayer())



    def removeRasterItems(self):
        for item in self.listWidget.selectedItems():
            row = self.listWidget.row(item)
            self.listWidget.takeItem(row)
            self.rasterRemoved.emit(int(row + 1))

        if self.listWidget.count() == 0:
            self.zoomButton.setEnabled(False)
            self.removeButton.setEnabled(False)
            self.ExportButton.setEnabled(False)
            #self.groupBox.setEnabled(False)
            ############################################
            #raster settings
            self.xllBox.setEnabled(False)
            self.yllBox.setEnabled(False)
            self.pickButton.setEnabled(False)
            self.drBox.setEnabled(False)
            self.dcBox.setEnabled(False)
            self.nrBox.setEnabled(False)
            self.ncBox.setEnabled(False)
            self.ExportButton.setEnabled(False)
            self.angleBox.setEnabled(False)
            #############################################
            self.ilmBox.setEnabled(False)

    def updateRasterPropertiesGroup(self, row):
        item = self.listWidget.item(row)
        if item is None:
            return

        self.xllBox.setValue(item.data(PluginDialog.xllRole))
        self.yllBox.setValue(item.data(PluginDialog.yllRole))
        self.nrBox.setValue(item.data(PluginDialog.nrRole))
        self.ncBox.setValue(item.data(PluginDialog.ncRole))
        self.drBox.setValue(item.data(PluginDialog.drRole))
        self.dcBox.setValue(item.data(PluginDialog.dcRole))
        self.angleBox.setValue(item.data(PluginDialog.angleRole))



class DEMExport(object):

    ILM_TMPL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ilm_template.txt')

    def __init__(self, iface):
        self.iface = iface
        self.dialog = None
        self.cancel = False
        self.previewLayer = None
        self.act = QAction('2D-Floodplain Export', iface.mainWindow())
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
        self.dialog.RejectSignal.connect(self.quitDialog)


        self.dialog.xllBox.editingFinished.connect(self.saveRasterProperties)
        self.dialog.yllBox.editingFinished.connect(self.saveRasterProperties)
        self.dialog.drBox.editingFinished.connect(self.saveRasterProperties)
        self.dialog.dcBox.editingFinished.connect(self.saveRasterProperties)
        self.dialog.nrBox.editingFinished.connect(self.saveRasterProperties)
        self.dialog.ncBox.editingFinished.connect(self.saveRasterProperties)
        self.dialog.angleBox.editingFinished.connect(self.saveRasterProperties)

        #filters for boundary fields
        self.dialog.stationarytype_box.setFilters(QgsFieldProxyModel.String)
        self.dialog.boundaryvalue_box.setFilters(QgsFieldProxyModel.Numeric)
        self.dialog.boundarytype_box.setFilters(QgsFieldProxyModel.String)

        self.previewLayer = QgsVectorLayer('Polygon', 'ProMaIDes_HYD_Raster', 'memory')
        self.previewLayer.setCrs(QgsCoordinateReferenceSystem(self.iface.mapCanvas().mapSettings().destinationCrs().authid()))
        self.previewLayer.dataProvider().addAttributes([QgsField("xll", QVariant.Double), QgsField("yll", QVariant.Double), QgsField("dy", QVariant.Double),QgsField("dx", QVariant.Double),QgsField("nr", QVariant.Double),QgsField("nc", QVariant.Double), QgsField("angle", QVariant.Double)])
        self.previewLayer.updateFields()


        # set layer properties
        my_symbol = QgsFillSymbol.createSimple({'color': 'black', 'outline_color': 'red', 'outline_width': '0.8',
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

        item = self.dialog.listWidget.currentItem()

        xll = item.data(PluginDialog.xllRole)
        yll = item.data(PluginDialog.yllRole)
        nr = item.data(PluginDialog.nrRole)
        nc = item.data(PluginDialog.ncRole)
        dr = item.data(PluginDialog.drRole)
        dc = item.data(PluginDialog.dcRole)
        angle = item.data(PluginDialog.angleRole)

        bb = self.polygon(xll, yll, nc * dc, nr * dr, angle / 180.0 * math.pi).boundingBox()
        self.dialog.iface.mapCanvas().setExtent(bb)
        self.dialog.iface.mapCanvas().refresh()


    def addNewRasterItem(self):

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
                    item.setData(PluginDialog.drRole, f.attribute("dy"))
                    item.setData(PluginDialog.dcRole, f.attribute("dx"))
                    item.setData(PluginDialog.angleRole, f.attribute("angle"))

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
                    self.dialog.drBox.setEnabled(True)
                    self.dialog.dcBox.setEnabled(True)
                    self.dialog.nrBox.setEnabled(True)
                    self.dialog.ncBox.setEnabled(True)
                    self.dialog.ExportButton.setEnabled(True)
                    self.dialog.angleBox.setEnabled(True)
                    #############################################
                    self.dialog.ilmBox.setEnabled(True)

                    polygon = self.polygon(0.0, 0.0, 100.0, 100.0, 0.0)
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
        item.setData(PluginDialog.xllRole, 0.0)
        item.setData(PluginDialog.yllRole, 0.0)
        item.setData(PluginDialog.nrRole, 100)
        item.setData(PluginDialog.ncRole, 100)
        item.setData(PluginDialog.drRole, 10.0)
        item.setData(PluginDialog.dcRole, 20.0)
        item.setData(PluginDialog.angleRole, 0.0)


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
        self.dialog.drBox.setEnabled(True)
        self.dialog.dcBox.setEnabled(True)
        self.dialog.nrBox.setEnabled(True)
        self.dialog.ncBox.setEnabled(True)
        self.dialog.ExportButton.setEnabled(True)
        self.dialog.angleBox.setEnabled(True)
        #############################################
        self.dialog.ilmBox.setEnabled(True)

        polygon = self.polygon(0.0, 0.0, 100.0, 100.0, 0.0)
        self.dialog.rasterAdded.emit(int(self.dialog.listWidget.count() + 1), polygon)

        self.dialog.listWidget.addItem(item)
        self.dialog.listWidget.setCurrentItem(item)

        self.saveRasterProperties()


    def polygon(self, xll, yll, dx, dy, angle):
        poly = [QgsPointXY(xll, yll), QgsPointXY(xll + dx * math.cos(angle), yll + dx * math.sin(angle)),
                QgsPointXY(xll + (dx * math.cos(angle) - dy * math.sin(angle)),
                           yll + (dy * math.cos(angle) + dx * math.sin(angle))),
                QgsPointXY(xll - dy * math.sin(angle), yll + dy * math.cos(angle))]
        return QgsGeometry.fromPolygonXY([poly])

    def SaveasPolygon(self):
        try:
            original = self.previewLayer
            currentFolder = QgsProject.instance().homePath()
            originalpath = QFileDialog.getExistingDirectory(self.iface.mainWindow(), '2D-Floodplain Export', currentFolder)
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
            dr = item.data(PluginDialog.drRole)
            dc = item.data(PluginDialog.dcRole)
            angle = item.data(PluginDialog.angleRole)

            nodata = {
                'elev': self.dialog.demNaNBox.value(),
                'roughn': self.dialog.roughnessNaNBox.value(),
                'init': self.dialog.initNaNBox.value()
            }

            raster = RasterWriter(xll, yll, dc, dr, nc, nr, angle / 180.0 * math.pi, nodata)
            filename = os.path.join(self.dialog.folderEdit.text(), item.text() + '.txt')
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
            dx = self.dialog.ncBox.value() * self.dialog.dcBox.value()
            dy = self.dialog.nrBox.value() * self.dialog.drBox.value()
            nc = self.dialog.ncBox.value()
            nr = self.dialog.nrBox.value()
            angle = self.dialog.angleBox.value()

            layer=self.previewLayer
            prov = layer.dataProvider()
            # lookup index of fields using their names
            xll_idx = layer.fields().lookupField('xll')
            yll_idx = layer.fields().lookupField('yll')
            dx_idx = layer.fields().lookupField('dx')
            dy_idx = layer.fields().lookupField('dy')
            nc_idx = layer.fields().lookupField('nc')
            nr_idx = layer.fields().lookupField('nr')
            angle_idx = layer.fields().lookupField('angle')

            # create a dictionary with field index as key and the attribute you want as value
            atts = {xll_idx: xll, yll_idx: yll, dx_idx: dx/nc, dy_idx: dy/nr,nc_idx: nc, nr_idx: nr, angle_idx: angle}

            # store reference to feature you want to update
            feat = layer.getFeature(self.dialog.listWidget.row(item)+1)
            # call changeAttributeValues(), pass feature id and attribute dictionary
            prov.changeAttributeValues({feat.id(): atts})

            item.setData(PluginDialog.xllRole, xll)
            item.setData(PluginDialog.yllRole, yll)
            item.setData(PluginDialog.nrRole, self.dialog.nrBox.value())
            item.setData(PluginDialog.ncRole, self.dialog.ncBox.value())
            item.setData(PluginDialog.drRole, self.dialog.drBox.value())
            item.setData(PluginDialog.dcRole, self.dialog.dcBox.value())
            item.setData(PluginDialog.angleRole, angle)

            if True:
                self.dialog.rasterUpdated.emit(int(self.dialog.listWidget.row(item) + 1),
                                    self.polygon(xll, yll, dx, dy, angle / 180.0 * math.pi))

    def quitDialog(self):
        #self.dialog = None
        if type(self.previewLayer) != type(None):
            QgsProject.instance().removeMapLayer(self.previewLayer)
        self.previewLayer = None
        self.act.setEnabled(True)
        self.cancel = False
        self.dialog.close()

    def execTool(self):
        """Performs actual DEM export."""
        input_layers = {
            'elev': {
                'layer': self.dialog.demLayer(),
                'band': self.dialog.demBand(),
                'interpol_mode': self.dialog.demInterpolationMode(),
                'nan': self.dialog.demNaN()
            },
            'roughn': {
                'layer': self.dialog.roughnessLayer(),
                'band': self.dialog.roughnessBand(),
                'interpol_mode': 'nearest neighbor (downscaling/upscaling)',
                'nan': self.dialog.roughnessNaN()
            },
            'init': {
                'layer': self.dialog.initLayer(),
                'band': self.dialog.initBand(),
                'interpol_mode': 'nearest neighbor (downscaling/upscaling)',
                'nan': self.dialog.initNaN()
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
        progress.setWindowTitle('2D-Floodplain Export')
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

        if self.dialog.createIlmFile():
            path = os.path.join(self.dialog.outFolder(), 'project.ilm')
            self.writeIlmFile(path, rasters, self.dialog.demNaN())

        progress.close()
        self.quitDialog()
        return

    def export_raster(self, input_layers, out_raster, filename, progress=None):
        trans, interpol = dict(), dict()
        for data_name, items in list(input_layers.items()):
            if items['layer']:
                trans[data_name] = QgsCoordinateTransform(self.previewLayer.crs(), items['layer'].crs(), QgsProject.instance()).transform
            else:
                trans[data_name] = lambda p: p
            interpol[data_name] = RasterInterpolator(items['layer'], items['band'], self.dialog.dcBox.value(), self.dialog.drBox.value(), items['interpol_mode'], items['nan']).interpolate

        out_raster.open(filename, input_layers)

        ########################################################################
        #reading boundary polygon data
        if self.dialog.mGroupBox_4.isChecked():
            polygonlayer = self.dialog.BCLayerBox.currentLayer()
            if polygonlayer:
                boundarystationary, ok = QgsVectorLayerUtils.getValues(polygonlayer, self.dialog.stationarytype_box.expression(), False)
                if not ok:
                    self.iface.messageBar().pushCritical(
                        '2D-Floodplain Export',
                        'Invalid expression for stationary boundary condition !'
                    )
                    return
                ##################################################################
                #getting the id of each attribute field
                fields = polygonlayer.dataProvider().fields()
                for f in fields:
                    if str(f.name())==self.dialog.boundaryvalue_box.currentText():
                        boundaryvaluefieldid=fields.indexFromName(f.name())
                    if str(f.name())==self.dialog.stationarytype_box.currentText():
                        stationarytypefieldid=fields.indexFromName(f.name())
                    if str(f.name())==self.dialog.boundarytype_box.currentText():
                        boundarytypefieldid=fields.indexFromName(f.name())
                #################################################################

                boundaryvalue, ok = QgsVectorLayerUtils.getValues(polygonlayer, self.dialog.boundaryvalue_box.expression(), False)
                if not ok:
                    self.iface.messageBar().pushCritical(
                        '2D-Floodplain Export',
                        'Invalid expression for boundary condition value !'
                    )
                    return
                boundarytype, ok = QgsVectorLayerUtils.getValues(polygonlayer, self.dialog.boundarytype_box.expression(), False)
                if not ok:
                    self.iface.messageBar().pushCritical(
                        '2D-Floodplain Export',
                        'Invalid expression for boundary type !'
                    )
                    return
        #######################################################################
        defaultcellproperties=["false", "false", "0", "point"]


        # write cell values
        for i in range(int(out_raster.num_cells())):
            point = out_raster.cell_center(i)
            if self.dialog.mGroupBox_4.isChecked():
                if polygonlayer:
                    features_main = polygonlayer.getFeatures()
                    for poly in features_main:
                        geom_pol = poly.geometry()
                        if geom_pol.contains(QgsPointXY(point)) == True:

                            ##########################################################################
                            #value check
                            try:
                                boundarystationarystatus = str(boundarystationary[poly.id()]).lower()
                            except:
                                boundarystationarystatus = str(boundarystationary[poly.id()-1]).lower()
                            if check_true_false(boundarystationarystatus) == 0:
                                self.iface.messageBar().pushCritical(
                                    '2D-Floodplain Export',
                                    'Invalid expression for stationary boundary condition !'
                                )
                                self.quitDialog()
                                return

                            try:
                                cellboundarytypestatus=str(boundarytype[poly.id()])
                            except:
                                cellboundarytypestatus = str(boundarytype[poly.id()-1])
                            if check_cell_boundary_type(cellboundarytypestatus) == 0:
                                self.iface.messageBar().pushCritical(
                                    '2D-Floodplain Export',
                                    'Invalid expression for boundary type !'
                                )
                                self.quitDialog()
                                return
                            ##############################################################################

                            boundaryenabledforcell="true"
                            #############################################################################
                            #boundary stationary
                            if fields.indexFromName(self.dialog.stationarytype_box.currentText())==-1:
                                try:
                                    cellstationary=str(boundarystationary[poly.id()])
                                except:
                                    cellstationary = str(boundarystationary[poly.id()-1])
                            else:
                                cellstationary=poly.attributes()[stationarytypefieldid]
                            #############################################################################
                            #boundary value
                            if fields.indexFromName(self.dialog.boundaryvalue_box.currentText())==-1:
                                try:
                                    cellboundaryvalue=str(boundaryvalue[poly.id()])
                                except:
                                    cellboundaryvalue = str(boundaryvalue[poly.id()-1])
                            else:
                                cellboundaryvalue=poly.attributes()[boundaryvaluefieldid]
                            ###########################################################################
                            #boundary type
                            if fields.indexFromName(self.dialog.boundarytype_box.currentText())==-1:
                                try:
                                    cellboundarytype=str(boundarytype[poly.id()])
                                except:
                                    cellboundarytype = str(boundarytype[poly.id()-1])
                            else:
                                cellboundarytype=poly.attributes()[boundarytypefieldid]
                            ###########################################################################
                            cellproperties=[boundaryenabledforcell,cellstationary,cellboundaryvalue,cellboundarytype]
                            break
                        else:
                            cellproperties = defaultcellproperties
                else:
                    boundaryenabledforcell = "true"
                    cellstationary = self.dialog.stationarytype_box.currentText().strip('\'')
                    if check_true_false(cellstationary) == 0:
                        self.iface.messageBar().pushCritical(
                            '2D-Floodplain Export',
                            'Invalid expression for stationary boundary condition !'
                        )
                        self.quitDialog()
                        return
                    cellboundaryvalue = self.dialog.boundaryvalue_box.currentText().strip('\'')
                    cellboundarytype = self.dialog.boundarytype_box.currentText().strip('\'')
                    if check_cell_boundary_type(cellboundarytype) == 0:
                        self.iface.messageBar().pushCritical(
                            '2D-Floodplain Export',
                            'Invalid expression for boundary type !'
                        )
                        self.quitDialog()
                        return
                    cellproperties = [boundaryenabledforcell, cellstationary, cellboundaryvalue, cellboundarytype]
            else:
                cellproperties = defaultcellproperties

            values = {data_name: interpol[data_name](trans[data_name](point)) for data_name in list(input_layers.keys())}
            out_raster.write_cell(values,cellproperties,self.dialog.initAbsoluteBox.isChecked())
            if progress:
                progress.setValue(progress.value() + 1)
        out_raster.close()

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
            nc_idx = layer.fields().lookupField('nc')
            nr_idx = layer.fields().lookupField('nr')
            angle_idx = layer.fields().lookupField('angle')

            atts = {xll_idx: 0, yll_idx: 0, dx_idx: 0, dy_idx: 0,nc_idx: 0, nr_idx: 0, angle_idx: 0}
            prov.changeAttributeValues({f.id(): atts})
            layer.updateFields()
            self.previewLayer.dataProvider().deleteFeatures([idtemp])
            self.previewLayer.updateExtents()
            self.previewLayer.triggerRepaint()

    def writeIlmFile(self, filename, rasters, nan):
        ilm_tmpl_file = open(self.ILM_TMPL_FILE, 'r')
        ilm_tmpl = ilm_tmpl_file.read()
        ilm_tmpl_file.close()

        with open(filename, 'w+') as ilm:
            # write general settings to ilm file
            ilm.write(ilm_tmpl.format(len(rasters)))

            counter = 0
            for raster, filename in rasters:
                # CAUTION! The positive rotation direction is defined opposite in ProMaIDEs
                angle = -raster.angle / math.pi * 180.0

                ilm.write('!$BEGINFPMODEL = %d "raster-%d"\n' % (counter, counter + 1))
                ilm.write('!GENERAL= <SET> \n')
                ilm.write('  $NX          = %d\n' % raster.nc)
                ilm.write('  $NY          = %d\n' % raster.nr)
                ilm.write('  $LOWLEFTX    = %f\n' % raster.xll)
                ilm.write('  $LOWLEFTY    = %f\n' % raster.yll)
                ilm.write('  $ELEMWIDTH_X = %f\n' % raster.dc)
                ilm.write('  $ELEMWIDTH_Y = %f\n' % raster.dr)
                ilm.write('  $NOINFOVALUE = %f\n' % nan)
                ilm.write('  $ANGLE       = %f\n' % angle)
                ilm.write('</SET> \n')

                ilm.write('!FLOODPLAINFILE = "./%s"\n' % os.path.basename(filename))

                ilm.write('#!INSTATBOUNDFILE = <SET>\n')
                ilm.write('      #$FILENAME= "./Your_FIle_Address.txt" \n')
                ilm.write('      #$NUMBER_CURVE= 1 \n')
                ilm.write('      # </SET> \n')

                ilm.write('#!NOFLOWFILE = <SET>\n')
                ilm.write('      #$FILENAME= "./Your_FIle_Address.txt" \n')
                ilm.write('      #$NO_POLYGONS= 1 \n')
                ilm.write('      # </SET> \n')

                ilm.write('#!DIKELINEFILE = <SET>\n')
                ilm.write('      #$FILENAME= "./Your_FIle_Address.txt" \n')
                ilm.write('      #$NO_POLYLINES= 2 \n')
                ilm.write('      # </SET> \n')

                ilm.write('!LIMITS = <SET>  # numerical limits for 2D simulation\n')
                ilm.write('  $RTOL = 1e-9   # Relative tolerances [optional, standard value = 1e-6] '
                          '(recommendation 1e-9)\n')
                ilm.write('  $ATOL = 1e-5   # Absolute tolerances   [optional, standard value = 1e-5]\n')
                ilm.write('  $WET  = 0.01   # Water depth [m], when the element is defined as wet [optional,' 
                          'standard value = 1e-3]\n')
                ilm.write('</SET>\n')
                ilm.write('!$ENDFPMODEL\n\n')

                counter += 1

            ilm.write('!$ENDDESCRIPTION\n')
