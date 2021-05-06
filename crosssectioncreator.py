from __future__ import unicode_literals
from __future__ import absolute_import

# system modules
import os
from qgis import processing
import tempfile
import webbrowser

# QGIS modules
from qgis.core import *
from qgis.PyQt.QtWidgets import *
from qgis.PyQt import uic
from qgis.utils import iface
from qgis.gui import *
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.PyQt import uic

from .environment import get_ui_path


UI_PATH = get_ui_path('ui_crosssectioncreator.ui')


class PluginDialog(QDialog):

    def __init__(self, iface, parent=None, flags=Qt.WindowFlags()):
        QDialog.__init__(self, parent, flags)
        uic.loadUi(UI_PATH, self)

        self.iface = iface

        self.PolygonLayerBox.setEnabled(False)
        self.label_26.setEnabled(False)

        self.RiverShapeBox.setFilters(QgsMapLayerProxyModel.LineLayer)
        self.ElevationBox.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.PolygonLayerBox.setFilters(QgsMapLayerProxyModel.PolygonLayer)

        self.browseButton.clicked.connect(self.onBrowseButtonClicked)
        self.HelpButton.clicked.connect(self.Help)
        self.PolygonBox.stateChanged.connect(self.RiverPolygonClicked)



    def onBrowseButtonClicked(self):
        currentFolder = self.filename_edit.text()
        folder = QFileDialog.getExistingDirectory(self.iface.mainWindow(), 'Cross Section Creator', currentFolder)
        if folder != '':
            self.filename_edit.setText(folder)


    def Help(self):
        webbrowser.open("https://promaides.myjetbrains.com/youtrack/articles/PMDP-A-62/Cross-Section-Creator")


    def RiverPolygonClicked(self):
        if self.PolygonBox.isChecked():
            self.PolygonLayerBox.setEnabled(True)
            self.label_26.setEnabled(True)
            self.LengthBox.setEnabled(False)

        else:
            self.PolygonLayerBox.setEnabled(False)
            self.label_26.setEnabled(False)
            self.LengthBox.setEnabled(True)



class CrossSectionCreator(object):

    def __init__(self, iface):
        self.iface = iface
        self.dialog = None
        self.cancel = False
        self.act = QAction('Cross Section Creator', iface.mainWindow())
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
        #self.dialog.accepted.connect(self.execTool)
        self.dialog.rejected.connect(self.quitDialog)
        self.dialog.setModal(False)
        self.act.setEnabled(False)
        self.dialog.show()

        self.dialog.RunButton.clicked.connect(self.WritePleaseWait)

    def scheduleAbort(self):
        self.cancel = True

    def quitDialog(self):
        self.dialog.hide()
        self.dialog = None
        self.act.setEnabled(True)
        self.cancel = False


    def WritePleaseWait(self):
        if type(self.dialog.RiverShapeBox.currentLayer()) == type(None):
            self.iface.messageBar().pushCritical(
                'Cross Section Creator',
                'No River Shape Layer Selected !'
            )
            return

        if type(self.dialog.ElevationBox.currentLayer()) == type(None):
            self.iface.messageBar().pushCritical(
                'Cross Section Creator',
                'No Elevation Layer Selected !'
            )
            return

        if type(self.dialog.PolygonLayerBox.currentLayer()) == type(None) and self.PolygonBox.isChecked():
            self.iface.messageBar().pushCritical(
                'Cross Section Creator',
                'No River Shape Polygon Selected !'
            )
            return

        if self.dialog.filename_edit.text() == "":
            self.iface.messageBar().pushCritical(
                'Cross Section Creator',
                'No Output Location Selected !'
            )
            return

        self.iface.messageBar().pushInfo(
            'Cross Section Creator',
            'Processing, Please Wait !'
        )
        QTimer.singleShot(100, self.Run)

    def Run(self):

        if self.dialog.PolygonBox.isChecked():
            ProfileLengths=500
        else:
            ProfileLengths = self.dialog.LengthBox.value()

        if self.dialog.PolygonBox.isChecked():
            outputlocation = tempfile.gettempdir()+ "/crosssections.shp"
        else:
            outputlocation = self.dialog.filename_edit.text() + "/crosssections.shp"

        params = {'DEM': self.dialog.ElevationBox.currentLayer().dataProvider().dataSourceUri(), 'DIST_LINE': self.dialog.DistanceBox.value(), 'DIST_PROFILE': ProfileLengths,
         'LINES': self.dialog.RiverShapeBox.currentLayer().dataProvider().dataSourceUri(),
         'NUM_PROFILE': 3, 'PROFILES': outputlocation}
        result =processing.run('saga:crossprofiles', params)

        try:
            resultlayer = QgsVectorLayer(outputlocation, "Cross Sections", "ogr")
        except:
            self.iface.messageBar().pushCritical(
                'Cross Section Creator',
                'Operation Failed ! '
            )
            return

        resultlayer.setName('Cross Sections')
        resultlayer.dataProvider().addAttributes(
            [QgsField("Stations", QVariant.Double), QgsField("Names", QVariant.String), QgsField("Type", QVariant.String)])
        resultlayer.updateFields()

        prov = resultlayer.dataProvider()
        # lookup index of fields using their names
        ID = resultlayer.fields().lookupField('ID')
        Stations = resultlayer.fields().lookupField('Stations')
        Names = resultlayer.fields().lookupField('Names')
        ProfileType = resultlayer.fields().lookupField('Type')


        Part=resultlayer.fields().lookupField('PART')
        X000 = resultlayer.fields().lookupField('X000')
        X001 = resultlayer.fields().lookupField('X001')
        X002 = resultlayer.fields().lookupField('X002')

        field_ids=[Part,X000,X001,X002]
        resultlayer.dataProvider().deleteAttributes(field_ids)
        resultlayer.updateFields()

        resultlayer.startEditing()
        for feat in resultlayer.getFeatures():
            FeutureID=feat.attributes()[ID]
            atts = {Stations: self.dialog.DistanceBox.value()*FeutureID, Names: self.dialog.NameBox.text()+"_"+str(FeutureID), ProfileType: "river"}
            # call changeAttributeValues(), pass feature id and attribute dictionary
            prov.changeAttributeValues({feat.id(): atts})
            feat['Stations'] = self.dialog.DistanceBox.value() * (-FeutureID)
            feat['Names'] = self.dialog.NameBox.text() + "_" + str(FeutureID)
            feat['Type'] = "river"
            resultlayer.updateFeature(feat)

        resultlayer.commitChanges()
        resultlayer.updateFields()

        if self.dialog.PolygonBox.isChecked():
            outputlocation2 = self.dialog.filename_edit.text() + "/crosssections.shp"
            params = { 'INPUT' : resultlayer.dataProvider().dataSourceUri(), 'INPUT_FIELDS' : [], 'OUTPUT' : outputlocation2, 'OVERLAY' : self.dialog.PolygonLayerBox.currentLayer().dataProvider().dataSourceUri(), 'OVERLAY_FIELDS' : [], 'OVERLAY_FIELDS_PREFIX' : '' }
            result = processing.run('qgis:intersection', params)
            resultlayer = QgsVectorLayer(outputlocation2, "Cross Sections", "ogr")
            resultlayer.setName('Cross Sections')
            QgsProject.instance().addMapLayer(resultlayer)
        else:
            QgsProject.instance().addMapLayer(resultlayer)

        try:
            resultlayer.renderer().symbol().setWidth(0.7)
            resultlayer.triggerRepaint()
        except:
            pass


        self.iface.messageBar().pushSuccess(
            'Cross Section Creator',
            'Operation finished successfully!'
        )
        self.quitDialog()

    #def execTool(self):
        #print("hello")



