from __future__ import unicode_literals
from __future__ import absolute_import

# system modules
import math
import webbrowser
import pandas as pd

# QGIS modules 
from qgis.core import *
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import *
from qgis.PyQt import uic

from shapely.geometry import MultiLineString, mapping, shape

# promaides modules
from .environment import get_ui_path

#Connection to the UI-file (GUI); Edit the ui-file  via QTCreator
UI_PATH = get_ui_path('ui_navigation_analyzer.ui')

# This plugin serves as learning and test plugin
class PluginDialog(QDialog):

    #set-up of the dialog
    def __init__(self, iface, parent=None, flags=Qt.WindowFlags()):
        QDialog.__init__(self, parent, flags)
        #load the ui
        uic.loadUi(UI_PATH, self)
        self.iface = iface
        self.browse_button_glob2wl_import.clicked.connect(self.onBrowseButtonImportGlob2WLClicked)
        self.HelpButton.clicked.connect(self.Help)


    def onBrowseButtonImportGlob2WLClicked(self):
        current_filename_import = self.glob2wl_import.text()
        new_filename_import, __ = QFileDialog.getOpenFileName(self.iface.mainWindow(), 'Navigation Analyzer Import',current_filename_import, "*.txt")
        if new_filename_import != '':
            self.import_filename.setText(new_filename_import)
            self.import_filename.editingFinished.emit()



    def Help(self):
        webbrowser.open("https://promaides.myjetbrains.com/youtrack/articles/LFDH-A-14/Navigationanalyzer")


class Navigation_Analyzer(object):

    def __init__(self, iface):
        self.iface = iface
        self.dialog = None
        self.cancel = False
        self.act = QAction('Navigation Analyzer', iface.mainWindow())
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

    #connect here the buttons to functions, e.g. "OK"-button to execTool
    def execDialog(self):
        """
        """

        self.dialog = PluginDialog(self.iface, self.iface.mainWindow())
        self.dialog.accepted.connect(self.execTool)
        self.dialog.rejected.connect(self.quitDialog)
        self.dialog.show()




    def scheduleAbort(self):
        self.cancel = True

    #Quit the dialog; in general make nothing
    def quitDialog(self):
        self.dialog = None
        self.act.setEnabled(True)
        self.cancel = False

    def df_from_vlayer(input: QgsVectorLayer) -> pd.DataFrame:
        return pd.DataFrame([feat.attributes() for feat in input.getFeatures()],
                                columns=[field.name() for field in input.fields()])
    #here is the import function for glob_id to water_level
    def glob_id2wl(import_path_glob_id, data_layer : QgsMapLayer):
        df_glob_id = pd.read_csv(import_path_glob_id, sep=',', header=0)
        hyd_results = df_from_vlayer(data_layer)
        merged_df = pd.merge(df_glob_id, hyd_results, on='glob_id', how='inner')
        print(merged_df)



    #Execution of the tool by "ok" button
    def execTool(self):
        importpath = self.dialog.import_filename.text()
        data_layer = self.mMapLayerComboBox_hyd_result.currentLayer()
        self.glob_id2wl(import_path_glob_id=importpath,data_layer=data_layer)

        self.quitDialog()
