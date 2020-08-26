from __future__ import unicode_literals
from __future__ import absolute_import

# system modules
import os
import math
from datetime import datetime

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


UI_PATH = get_ui_path('ui_dem_export.ui')

# This plugin exports the 2D-floodplain raster file(s) for the HYD-module of ProMaIdes;
# The polygons are created as temporary layer
# TODO Change to existing polygon shp
class PluginDialog(QDialog):

    rasterAdded = pyqtSignal(int, QgsGeometry)
    rasterUpdated = pyqtSignal(int, QgsGeometry)
    rasterRemoved = pyqtSignal(int)

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

        self.interpolationBox.addItem('nearest neighbor')
        self.interpolationBox.addItem('bi-linear')
        self.interpolationBox.addItem('bi-cubic')

        self.picker = QgsMapToolEmitPoint(self.iface.mapCanvas())

        self.addButton.clicked.connect(self.addNewRasterItem)
        self.addButton.setAutoDefault(False)
        self.removeButton.clicked.connect(self.removeRasterItems)
        self.removeButton.setAutoDefault(False)
        self.listWidget.currentRowChanged.connect(self.updateRasterPropertiesGroup)
        self.demLayerBox.layerChanged.connect(self.updateDEMBandBox)
        self.roughnessLayerBox.layerChanged.connect(self.updateRoughnessBandBox)
        self.initLayerBox.layerChanged.connect(self.updateInitBandBox)
        self.pickButton.clicked.connect(self.enableMapPicker)
        self.pickButton.setAutoDefault(False)
        self.zoomButton.clicked.connect(self.zoomToRaster)
        self.zoomButton.setAutoDefault(False)


        self.xllBox.editingFinished.connect(self.saveRasterProperties)
        self.yllBox.editingFinished.connect(self.saveRasterProperties)
        self.drBox.editingFinished.connect(self.saveRasterProperties)
        self.dcBox.editingFinished.connect(self.saveRasterProperties)
        self.nrBox.editingFinished.connect(self.saveRasterProperties)
        self.ncBox.editingFinished.connect(self.saveRasterProperties)
        self.angleBox.editingFinished.connect(self.saveRasterProperties)

        self.browseButton.clicked.connect(self.onBrowseButtonClicked)
        self.browseButton.setAutoDefault(False)

        self.addButton.setEnabled(False)
        self.zoomButton.setEnabled(False)
        self.removeButton.setEnabled(False)
        self.bandBox.setEnabled(False)
        self.ilmBox.setEnabled(False)
        self.groupBox.setEnabled(False)
        self.roughnessLayerBox.setLayer(None)
        self.initLayerBox.setLayer(None)
        self.demLayerBox.setLayer(self.demLayerBox.currentLayer())

    def createIlmFile(self):
        if self.ilmBox.checkState() == Qt.Checked:
            return True
        else:
            return False

    def zoomToRaster(self):

        item = self.listWidget.currentItem()

        xll = item.data(PluginDialog.xllRole)
        yll = item.data(PluginDialog.yllRole)
        nr = item.data(PluginDialog.nrRole)
        nc = item.data(PluginDialog.ncRole)
        dr = item.data(PluginDialog.drRole)
        dc = item.data(PluginDialog.dcRole)
        angle = item.data(PluginDialog.angleRole)

        bb = self.polygon(xll, yll, nc * dc, nr * dr, angle / 180.0 * math.pi).boundingBox()
        self.iface.mapCanvas().setExtent(bb)
        self.iface.mapCanvas().refresh()

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
        return self.roughnessLayerBox.currentLayer()

    def roughnessBand(self):
        return self.roughnessBandBox.value()

    def roughnessNaN(self):
        return self.roughnessNaNBox.value()

    def initLayer(self):
        return self.initLayerBox.currentLayer()

    def initBand(self):
        return self.initBandBox.value()

    def initNaN(self):
        return self.initNaNBox.value()

    def rasters(self):

        result = []
        for row in range(self.listWidget.count()):
            item = self.listWidget.item(row)

            xll = item.data(PluginDialog.xllRole)
            yll = item.data(PluginDialog.yllRole)
            nr = item.data(PluginDialog.nrRole)
            nc = item.data(PluginDialog.ncRole)
            dr = item.data(PluginDialog.drRole)
            dc = item.data(PluginDialog.dcRole)
            angle = item.data(PluginDialog.angleRole)

            nodata = {
                'elev': self.demNaNBox.value(),
                'roughn': self.roughnessNaNBox.value(),
                'init': self.initNaNBox.value()
            }

            raster = RasterWriter(xll, yll, dc, dr, nc, nr, angle / 180.0 * math.pi, nodata)
            filename = os.path.join(self.folderEdit.text(), item.text() + '.txt')
            result.append((raster, filename))

        return result

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

    def addNewRasterItem(self):
        num = self.listWidget.count() + 1
        item = QListWidgetItem('raster_{:d}'.format(num))
        item.setData(PluginDialog.xllRole, 0.0)
        item.setData(PluginDialog.yllRole, 0.0)
        item.setData(PluginDialog.nrRole, 100)
        item.setData(PluginDialog.ncRole, 100)
        item.setData(PluginDialog.drRole, 1.0)
        item.setData(PluginDialog.dcRole, 1.0)
        item.setData(PluginDialog.angleRole, 0.0)

        item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled)

        self.removeButton.setEnabled(True)
        self.zoomButton.setEnabled(True)
        self.groupBox.setEnabled(True)
        self.ilmBox.setEnabled(True)

        polygon = self.polygon(0.0, 0.0, 100.0, 100.0, 0.0)
        self.rasterAdded.emit(int(self.listWidget.count() + 1), polygon)

        self.listWidget.addItem(item)
        self.listWidget.setCurrentItem(item)

    def polygon(self, xll, yll, dx, dy, angle):
        poly = [QgsPointXY(xll, yll), QgsPointXY(xll + dx * math.cos(angle), yll + dx * math.sin(angle)),
                QgsPointXY(xll + (dx * math.cos(angle) - dy * math.sin(angle)),
                           yll + (dy * math.cos(angle) + dx * math.sin(angle))),
                QgsPointXY(xll - dy * math.sin(angle), yll + dy * math.cos(angle))]
        return QgsGeometry.fromPolygonXY([poly])

    def removeRasterItems(self):
        for item in self.listWidget.selectedItems():
            row = self.listWidget.row(item)
            self.listWidget.takeItem(row)
            self.rasterRemoved.emit(int(row + 1))

        if self.listWidget.count() == 0:
            self.zoomButton.setEnabled(False)
            self.removeButton.setEnabled(False)
            self.groupBox.setEnabled(False)
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

    def saveRasterPropertiesNoRedraw(self):
        self.saveRasterProperties(False)

    def saveRasterProperties(self, redraw=True):

        item = self.listWidget.currentItem()

        if not item:
            return

        xll = self.xllBox.value()
        yll = self.yllBox.value()
        dx = self.ncBox.value() * self.dcBox.value()
        dy = self.nrBox.value() * self.drBox.value()
        angle = self.angleBox.value()

        item.setData(PluginDialog.xllRole, xll)
        item.setData(PluginDialog.yllRole, yll)
        item.setData(PluginDialog.nrRole, self.nrBox.value())
        item.setData(PluginDialog.ncRole, self.ncBox.value())
        item.setData(PluginDialog.drRole, self.drBox.value())
        item.setData(PluginDialog.dcRole, self.dcBox.value())
        item.setData(PluginDialog.angleRole, angle)

        if redraw:
            self.rasterUpdated.emit(int(self.listWidget.row(item) + 1),
                                    self.polygon(xll, yll, dx, dy, angle / 180.0 * math.pi))


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

        self.previewLayer = QgsVectorLayer('Polygon', 'ProMaIDes DEM Raster', 'memory')
        # set layer properties
        my_symbol = QgsFillSymbol.createSimple({'color': 'black', 'outline_color': 'red', 'outline_width': '0.8',
                                                'style':'no'})

        self.previewLayer.renderer().setSymbol(my_symbol)
        QgsProject.instance().addMapLayer(self.previewLayer)



        self.act.setEnabled(False)
        self.dialog.show()

    def scheduleAbort(self):
        self.cancel = True

    def quitDialog(self):
        #self.dialog = None

        QgsProject.instance().removeMapLayer(self.previewLayer.id())
        self.previewLayer = None
        self.act.setEnabled(True)
        self.cancel = False
        self.dialog.reject()


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
                'interpol_mode': 'nearest neighbor',
                'nan': self.dialog.roughnessNaN()
            },
            'init': {
                'layer': self.dialog.initLayer(),
                'band': self.dialog.initBand(),
                'interpol_mode': 'nearest neighbor',
                'nan': self.dialog.initNaN()
            }
        }

        rasters = self.dialog.rasters()  # list of tuples (raster, filename)
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
            interpol[data_name] = RasterInterpolator(items['layer'], items['band'], items['interpol_mode'], items['nan']).interpolate

        out_raster.open(filename, input_layers)
        # write cell values
        for i in range(out_raster.num_cells()):
            point = out_raster.cell_center(i)
            values = {data_name: interpol[data_name](trans[data_name](point)) for data_name in list(input_layers.keys())}
            out_raster.write_cell(values)
            if progress:
                progress.setValue(progress.value() + 1)
        out_raster.close()

    def addRasterBounds(self, id, polygon):
        dp = self.previewLayer.dataProvider()
        newPoly = QgsFeature(id)
        newPoly.setGeometry(polygon)
        dp.addFeatures([newPoly])

        self.previewLayer.updateExtents()
        self.previewLayer.triggerRepaint()

    def updateRasterBounds(self, id, polygon):
        self.previewLayer.dataProvider().changeGeometryValues({id: polygon})
        self.previewLayer.updateExtents()
        self.previewLayer.triggerRepaint()

    def removeRasterBounds(self, id):
        self.previewLayer.dataProvider().deleteFeatures([id])
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

                ilm.write('!2DOUTPUT = "./results"\n')
                ilm.write('!FLOODPLAINFILE = "%s"\n' % filename)

                ilm.write('!LIMITS = <SET>  # numerical limits for 2D simulation\n')
                ilm.write('  $RTOL = 1e-9  # relative tolerances   [optional, standard value = 1e-9]\n')
                ilm.write('  $ATOL = 1e-5   # absolute tolerances   [optional, standard value = 1e-5]\n')
                ilm.write('  $WET  = 0.01   # wet and dry parameter [optional, standard value = 1e-2]\n')
                ilm.write('</SET>\n')
                ilm.write('!$ENDFPMODEL\n\n')

                counter += 1

            ilm.write('!$ENDDESCRIPTION\n')
