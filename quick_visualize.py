#imports
from __future__ import unicode_literals
from __future__ import absolute_import

import webbrowser
import psycopg2
from qgis.core import *
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import *
from qgis.PyQt import uic
from .environment import get_ui_path

#Connection to the UI-file (GUI)
UI_PATH = get_ui_path('ui_quick_visualize.ui')


class PluginDialog(QDialog):

    #set-up of the dialog
    def __init__(self, iface, parent=None, flags=Qt.WindowFlags()):
        QDialog.__init__(self, parent, flags)
        #load the UI
        uic.loadUi(UI_PATH, self)

        #Initiation and Globalization of Variables 
        self.iface = iface
        self.conn = ""
        self.chosen_project=""
        self.chosen_layer=""

        #Hooking buttons | search text is changed | combo box selection change
        self.HelpButton.clicked.connect(self.Help)
        self.EditText_Search_Projects.textChanged.connect(self.on_text_change_of_EditText_Search_Projects)
        self.EditText_Search_Layers.textChanged.connect(self.on_text_change_of_EditText_Search_Layers)
        self.listView_Projects.currentItemChanged.connect(self.on_currentItemChanged_of_listView_Projects)
        self.project_combo.currentTextChanged.connect(self.on_combobox_changed_of_project_combo)

        # Connect based on Default setting
        host,port,name,user,pwrd = "localhost",5432,"promaides","postgres", ""
        try:
            conn_str = "dbname='{}' user='{}' host='{}' port={} password='{}'".format(name, user, host, port, pwrd)
            self.conn = psycopg2.connect(conn_str)
        except:
            #May have to add functionality to allow user to change default setting, and add default settings to an external file to import setting on plugin startup
            print("An error occurred connecting with default parameters")

        #Setting coordinate system is default recommended 25832
        #May have to add functionality to allow user to change this
        crs_id = 25832
        crs = QgsCoordinateReferenceSystem(crs_id, QgsCoordinateReferenceSystem.EpsgCrsId)

        #Initiate layer selection
        self.uri_chosen_layer = QgsDataSourceUri()
        self.uri_chosen_layer.setConnection(host, str(port), name, user, pwrd)

        # Get all projects in Database
        cur = self.conn.cursor()
        cur.execute('SELECT nspname, pg_catalog.pg_get_userbyid(nspowner) FROM pg_catalog.pg_namespace')

        #filter projects that are made by user
        databases = []
        for database in cur:
            owner = database[1]
            if owner != user:
                continue
            databases.append(database[0])

        #filter ProMaides Projects
        self.projects_list = []
        for database in databases:
            if database.endswith('_prm'):
                self.projects_list.append(database)

        #Append projects to Combo-box and List-view
        for project in self.projects_list:
            self.project_combo.addItem(project)
        self.listView_Projects.addItems(self.projects_list)

    #On selection of new project from Combo Box
    def on_combobox_changed_of_project_combo(self, value):
        #Set Project variable
        self.chosen_project=value
        #Grab layers that are in selected project
        self.curlayer = self.conn.cursor()
        self.curlayer.execute("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = '{}'".format(value))
        #curlayerlist: To allow for filtering using search
        self.curlayerlist=[]
        #Clear Layers lists and add new list
        self.layer_combo.clear()
        self.listView_Layers.clear()
        for layer in self.curlayer:
            self.curlayerlist.append(str(layer[0]))
            self.layer_combo.addItem(str(layer[0]))
            self.listView_Layers.addItem(str(layer[0]))

    def on_currentItemChanged_of_listView_Projects(self,now,pre):
        if now is not None:
            #Set Project variable
            self.chosen_project=now.text()
            #Grab layers that are in selected project
            self.curlayer = self.conn.cursor()
            self.curlayer.execute("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = '{}'".format(now.text()))
            #curlayerlist: To allow for filtering using search
            self.curlayerlist = []
            #Clear Layers lists and add new list
            self.layer_combo.clear()
            self.listView_Layers.clear()
            self.listView_Layers.clear()
            for layer in self.curlayer:
                self.curlayerlist.append(str(layer[0]))
                self.layer_combo.addItem(str(layer[0]))
                self.listView_Layers.addItem(str(layer[0]))

    def on_text_change_of_EditText_Search_Projects(self, value):
        #Clear combo and ListView of Project
        self.project_combo.clear()
        self.listView_Projects.clear()
        #Filter projects based on search term
        for project in self.projects_list:
            if value in project:
                self.project_combo.addItem(project)
                self.listView_Projects.addItem(project)

    def on_text_change_of_EditText_Search_Layers(self, value):
        #Clear combo and ListView of Layer
        self.layer_combo.clear()
        self.listView_Layers.clear()
        #Filter layers based on search term
        for layer in self.curlayerlist:
            if value in layer:
                self.layer_combo.addItem(layer)
                self.listView_Layers.addItem(layer)

    #Help button press function
    def Help(self):
        webbrowser.open("https://promaides.myjetbrains.com/youtrack/articles/PMDP-A-52/Hello-World")


class QuickVisualize(object):

    def __init__(self, iface):
        self.iface = iface
        self.dialog = None
        self.cancel = False
        self.act = QAction('Quick Visualize', iface.mainWindow())
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

    #Execution of the tool by "OK" button
    def execTool(self):

        #Check that a layer is selected
        if self.dialog.listView_Layers.currentItem() is not None:
            project_name=self.dialog.chosen_project
            layer_name=self.dialog.listView_Layers.currentItem().text()

            #Get type of selected layer from database
            curColumnType = self.dialog.conn.cursor()
            curColumnType.execute("SELECT column_name from information_schema.columns WHERE table_schema = '{}' AND table_name='{}' AND data_type = 'USER-DEFINED'".format(project_name,layer_name))
            
            ColumnType = curColumnType.fetchone()

            #Check that layer has a valid type
            if ColumnType is not None:
                layer_type=ColumnType[0]

                print("Chose: " + layer_name + "  |  " + project_name + "  |  " + layer_type)

                #Create QGIS layer from source
                self.dialog.uri_chosen_layer.setDataSource(project_name,layer_name, layer_type)
                vlayer = QgsVectorLayer(self.dialog.uri_chosen_layer.uri(False), layer_name , "postgres")

                #Styling of layer based on its type
                if layer_type == "geo_point":
                    renderer = vlayer.renderer()
                    symbol = QgsMarkerSymbol.createSimple({'name': 'circle', 'color': 'blue'})
                    vlayer.renderer().setSymbol(symbol)
                    vlayer.triggerRepaint()
                elif layer_type == "other_type":
                    #do styling here
                    style=1

                #Add layer to current QGIS Instance
                QgsProject.instance().addMapLayer(vlayer)
            else:
                QMessageBox.information(None, "DEBUG:", "You selected an invalid layer<br><br>Possible Reasons: Layer was not calculated by ProMaides<br><br>Please try to select another layer") 


        self.quitDialog()