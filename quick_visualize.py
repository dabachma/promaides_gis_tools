# imports
from __future__ import unicode_literals
from __future__ import absolute_import

import webbrowser
import psycopg2
import threading

from qgis.core import *
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtCore import QObject
from qgis.PyQt.QtCore import QSettings
from qgis.PyQt.QtWidgets import *
from qgis.PyQt.QtGui import QColor
from qgis.PyQt import uic

from .environment import get_ui_path
from .database_list_management import DatabaseListManagement

# Debugging
from datetime import datetime
from pathlib import Path

# Connection to the UI-file (GUI)
UI_PATH = get_ui_path('ui_quick_visualize.ui')


class PluginDialog(QDialog):

    # set-up of the dialog
    def __init__(self, iface, parent=None, flags=Qt.WindowFlags()):
        QDialog.__init__(self, parent, flags)
        # load the UI
        uic.loadUi(UI_PATH, self)

        # Initiation and Globalization of Variables

        self.qsettings = QSettings('QuickVisualize', 'QuickVisualizeSettings')
        # print(self.qsettings.fileName())
        if self.qsettings.contains("advancedcolor1"):
            self.advancedcolor1 = QColor(self.qsettings.value("advancedcolor1"))
        else:
            self.advancedcolor1 = QColor("#fafa24")
        if self.qsettings.contains("advancedcolor2"):
            self.advancedcolor2 = QColor(self.qsettings.value("advancedcolor2"))
        else:
            self.advancedcolor2 = QColor("#e62323")

        if self.qsettings.contains("spinbox_classes_value"):
            self.spinbox_classes.setValue(self.qsettings.value("spinbox_classes_value"))

        if self.qsettings.contains("crs_value"):
            self.CRS_Select.setCrs(QgsCoordinateReferenceSystem(self.qsettings.value("crs_value")))
        else:
            self.CRS_Select.setCrs(QgsCoordinateReferenceSystem("EPSG:25832"))

        if self.qsettings.contains("Add_to_new_group"):
            self.checkbox_addedtonewgroup.setChecked(self.str2bool(self.qsettings.value("Add_to_new_group")))
        else:
            self.checkbox_addedtonewgroup.setChecked(True)

        if self.qsettings.contains("cb_layervisible"):
            self.cb_layervisible.setChecked(self.str2bool(self.qsettings.value("cb_layervisible")))
        else:
            self.cb_layervisible.setChecked(False)


        self.iface = iface
        self.conn = ""


        self.chosen_project = ""
        self.chosen_layer = ""
        self.database_selected_index = 0
        self.firstload = 0
        self.text_of_EditText_Search_Layers = ""
        self.changedbutton=""
        self.unavailablebuttons=[]
        self.senarios=[]
        self.affectedSenarioLayers = []

        self.color_selection_1.setStyleSheet("background-color : " + self.advancedcolor1.name() + "; border: 0px;")
        self.color_selection_2.setStyleSheet("background-color : " + self.advancedcolor2.name() + "; border: 0px;")

        '''
        Due to limitations within QgsCollapsibleGroupBox and QGroupBox a checkbox system had to be implemented.
        The limitation comes from two things.
            1. Checkboxes in these groups are meant to disable or enable the box only and to be used as an option, thus each time the checkbox of a group is pressed, its children must be re-enabled
            2. When checkbox is clicked it does not pass its id within. This can be bypassed by checking which checkbox has changed. In order to do this a checkboxtree variable is introduced to check which button is changed and from which state to which in order to know if user intends to deselect or to select.

        To Update in the future please note that Added/Removed buttons should be Added/Removed to/from the checkboxtree and should reflect its hierarchy! 
        '''
        self.checkboxtree = [self.HYD_Standard_Group, False, [[self.HYD_INPUT, False, [[self.HYD_IN_RV, False, [[self.hyd_in_rv_1, False],[self.hyd_in_rv_2, False]]], [self.HYD_IN_FD, False, [[self.hyd_in_fd_1, False],[self.hyd_in_fd_2, False]]]]], [self.HYD_RESULTS, False, [[self.HYD_RE_RV, False, [[self.hyd_re_rv_1, False],[self.hyd_re_rv_2, False]]],[self.HYD_RE_FD, False, [[self.hyd_re_fd_1, False],[self.hyd_re_fd_2, False]]]]]]], [self.DAM_Standard_Group, False, [[self.DAM_INPUT, False, [[self.cb_dam_ecn_imm, False],[self.cb_dam_in_pop, False],[self.cb_dam_scpoints, False]]],[self.Dam_RESULTS, False , [[self.cb_dam_ecn_total, False],[self.cb_dam_pop_affected, False],[self.cb_dam_pop_endangered, False],[self.cb_dam_sc_points_damages, False]]]]], [self.RISK_Standard_Group, False]

        self.allcheckboxes = []
        self.allGroupCheckboxeswithDepth = []
        self.getAllCheckboxes(self.checkboxtree, 0)
        self.allGroupCheckboxes = self.makeAllGroupCheckboxes(self.allGroupCheckboxeswithDepth)


        self.to_render = [
            [self.hyd_in_rv_1, "hyd_river_profile_prm", "", ["HYD","Input"], "RV cross-section type (line)"],
            [self.hyd_in_rv_2, "hyd_river_profile_points_prm", "distance", ["HYD","Input"], "RV cross-section point height [mNN]"],
            [self.hyd_in_fd_1, "hyd_floodplain_element_prm", "geodetic_height", ["HYD","Input"], "FP geodetic height [mNN]"],
            [self.hyd_in_fd_2, "" "", ["HYD","Input"], "FP 1D-dikeline (line)"],
            [self.hyd_re_rv_1, "hyd_river_profile_max_results_prm", "h_waterlevel", ["HYD","Results"], "RV max result depth [m]"],
            [self.hyd_re_rv_2, "hyd_river_profile_max_results_prm", "discharge", ["HYD","Results"], "RV max result discharge [m³/s]"],
            [self.hyd_re_fd_1, "", "", ["HYD","Results"], ""],
            [self.hyd_re_fd_2, "", "", ["HYD","Results"], ""],
            [self.cb_dam_ecn_imm, "dam_ecn_elements_prm", "immob_id", ["DAM","Input"], "ECN Immob ID"],
            [self.cb_dam_in_pop, "dam_pop_element_prm", "pop_density", ["DAM","Input"], "POP Population Density [P/m2]"],
            [self.cb_dam_scpoints, "dam_sc_point_prm", "cat_id", ["DAM","Input"], "SC points"],
            [self.cb_dam_ecn_total, "dam_ecn_results_prm", "total", ["DAM","Results"], "ECN Total Damages [Monetary]"],
            [self.cb_dam_pop_affected, "dam_pop_result_prm", "pop_affected", ["DAM","Results"], "POP Affected Person [P]"],
            [self.cb_dam_pop_endangered, "dam_pop_result_prm", "pop_endangered", ["DAM","Results"], "POP Endangered Person [P]"],
            [self.cb_dam_sc_points_damages, "dam_sc_point_erg_prm", "affect_score", ["DAM","Results"], "SC Points Damages"]
        ]


        # Hooking buttons | search text is changed
        self.DatabaseListManage_dialog_instance = DatabaseListManagement(self.iface)
        self.HelpButton.clicked.connect(self.Help)
        self.EditText_Search_Projects.textChanged.connect(self.on_text_change_of_EditText_Search_Projects)
        self.EditText_Search_Layers.textChanged.connect(self.on_text_change_of_EditText_Search_Layers)
        self.listView_Projects.currentItemChanged.connect(self.on_currentItemChanged_of_listView_Projects)
        self.listView_Layers.currentItemChanged.connect(self.on_currentItemChanged_of_listView_Layers)
        self.combobox_databaseSelection.currentIndexChanged.connect(self.on_combobox_changed_of_databaseSelection)
        self.database_manage_button.clicked.connect(self.database_manage_tab)
        self.database_connect.clicked.connect(self.connectedPressed)
        self.color_selection_1.clicked.connect(self.getColorClick1)
        self.color_selection_2.clicked.connect(self.getColorClick2)
        self.spinbox_classes.valueChanged.connect(self.on_ValueChanged_of_spinbox_classes)
        self.CRS_Select.crsChanged.connect(self.crs_Select_crsChanged)
        self.checkbox_addedtonewgroup.clicked.connect(self.checkbox_addedtonewgroup_clicked)
        self.cb_layervisible.clicked.connect(self.cb_layervisible_clicked)

        self.signalclass = SignalClass()
        self.signalclass.turnOnOptionsEmittor.connect(self.ResetAllbuttons)
        self.signalclass.turnOffOptionsEmittor.connect(self.disableOptions)
        self.signalclass.turnOnComboBoxEmittor.connect(self.enableCombo)
        self.signalclass.portErrorEmittor.connect(self.portErrorMessage)

        for checkbutton in self.allcheckboxes:
            checkbutton.clicked.connect(self.manageCheckboxSys)

        self.refreshDatabaseData()

    def makeAllGroupCheckboxes(self,theList):
        l = len(theList)
        for i in range(0, l):
            for j in range(0, l-i-1):
                if (theList[j][1] < theList[j + 1][1]):
                    tempo = theList[j]
                    theList[j]= theList[j + 1]
                    theList[j + 1]= tempo
        newlist=[]
        for item in theList:
            if type(item[0]) != QCheckBox:
                newlist.append(item[0])
        return newlist

    def getAllCheckboxes(self, checkboxtreeToGet, depth):
        for part in checkboxtreeToGet:
            self.allcheckboxes.append(part[0])
            self.allGroupCheckboxeswithDepth.append([part[0], depth])
            if len(part) > 2:
                self.getAllCheckboxes(part[2],depth+1)

    def manageCheckboxSys(self):
        self.checkCheckboxTreeChanges(self.checkboxtree, True)
        self.enableDisablechildren(self.changedbutton, self.changedbutton.isChecked())
        self.checkParent()
        self.checkCheckboxTreeChanges(self.checkboxtree, False)
        self.enableAll()

    def checkCheckboxTreeChanges(self, checkboxtreeToCheck, doIset):
        for checkbox in checkboxtreeToCheck:
            if checkbox[0].isChecked() != checkbox[1] and doIset==True:
                self.changedbutton = checkbox[0]
            checkbox[1] = checkbox[0].isChecked()
            if len(checkbox) > 2:
                self.checkCheckboxTreeChanges(checkbox[2], doIset)

    def checkParent(self):
        for group in self.allGroupCheckboxes:
            children = group.findChildren(QCheckBox)
            state=False
            for child in children:
                if child.isChecked():
                    state=True
                    break
            group.setChecked(state)

    def enableDisablechildren(self, qwidget, state):
        if state == False:
            stateno=0
        else:
            stateno=1
        children = qwidget.findChildren(QGroupBox)
        for child in children:
            self.enableDisablechildren(child, stateno)
            child.setChecked(stateno)
        children = qwidget.findChildren(QCheckBox)
        for child in children:
            child.setChecked(stateno)

    def enableAll(self):
        for checkboxtoenable in self.allcheckboxes:
            checkboxtoenable.setEnabled(True)

    def ResetAllbuttons(self):
        for checkboxtoenable in self.allcheckboxes:
            checkboxtoenable.setEnabled(True)
            checkboxtoenable.setStyleSheet("")
            checkboxtoenable.setToolTip("")
        for group in self.allGroupCheckboxes:
            group.setToolTip("")
            group.setStyleSheet("")

    def disableAll(self):
        for checkboxtoenable in self.allcheckboxes:
            checkboxtoenable.setEnabled(False)

    def crs_Select_crsChanged(self):
        self.qsettings.setValue("crs_value", self.CRS_Select.crs().authid())

    def on_ValueChanged_of_spinbox_classes(self, value):
        self.qsettings.setValue("spinbox_classes_value", value)

    def checkbox_addedtonewgroup_clicked(self):
        self.qsettings.setValue("Add_to_new_group", self.checkbox_addedtonewgroup.isChecked())

    def cb_layervisible_clicked(self):
        self.qsettings.setValue("cb_layervisible", self.cb_layervisible.isChecked())

    def getColorClick1(self):
        color = QColorDialog.getColor()
        self.advancedcolor1 = color
        self.qsettings.setValue("advancedcolor1", color.name())
        self.color_selection_1.setStyleSheet("background-color : " + color.name() + "; border: 0px;")

    def getColorClick2(self):
        color = QColorDialog.getColor()
        self.advancedcolor2 = color
        self.qsettings.setValue("advancedcolor2", color.name())
        self.color_selection_2.setStyleSheet("background-color : " + color.name() + "; border: 0px;")

    def refreshDatabaseData(self):
        # Connect based on Default setting
        self.combobox_databaseSelection.clear()
        self.tempDatabaseList = []
        self.database_list = self.readDatabasesList()

        for database_entry in self.database_list:
            if database_entry[5] == "1":
                self.tempDatabaseList.append(database_entry)
                self.combobox_databaseSelection.addItem(database_entry[0] + " " + database_entry[1])
                self.default_database_connect = database_entry

        for database_entry in self.database_list:
            if database_entry[5] != "1":
                self.tempDatabaseList.append(database_entry)
                self.combobox_databaseSelection.addItem(database_entry[0] + " " + database_entry[1])
        self.database_list = self.tempDatabaseList

    def connectedPressed(self):
        self.signalclass.turnOffOptionsEmittor.emit()
        self.listView_Projects.clear()
        self.projects_list = []
        self.cb_scenarios.clear()
        self.listView_Layers.clear()
        self.curlayerlist = []
        self.combobox_feature.clear()
        self.curfeaturelist = []
        self.database_connection_status.setText("Status: Connecting")
        threading.Thread(target=self.tryToConnect, daemon=True).start()

    def disableOptions(self):
        self.disableAll()
        self.combobox_databaseSelection.setEnabled(False)

    def enableCombo(self):
        self.combobox_databaseSelection.setEnabled(True)

    def str2bool(self,v):
        return v.lower() in ("true")

    def tryToConnect(self):

        if self.firstload != 0:
            connectionparameters = self.database_list[self.database_selected_index]
        else:
            connectionparameters = self.default_database_connect
            self.firstload += 1


        host, name, user, pwrd = connectionparameters[0], connectionparameters[2], connectionparameters[3], connectionparameters[4]
        try:
            port = int(connectionparameters[1])
        except:
            self.signalclass.portErrorEmittor.emit()
            port = 1

        try:
            conn_str = "dbname='{}' user='{}' host='{}' port={} password='{}'".format(name, user, host, port, pwrd)
            self.conn = psycopg2.connect(conn_str)

            # Initiate layer selection
            self.uri_chosen_layer = QgsDataSourceUri()
            self.uri_chosen_layer.setConnection(host, str(port), name, user, pwrd)

            # Get all projects in Database
            try:
                cur = self.conn.cursor()
                cur.execute('SELECT nspname, pg_catalog.pg_get_userbyid(nspowner) FROM pg_catalog.pg_namespace')
            except:
                cur = []

            # filter projects that are made by user
            databases = []
            for database in cur:
                owner = database[1]
                if owner != user:
                    continue
                databases.append(database[0])

            # filter ProMaides Projects
            self.projects_list = []
            for database in databases:
                if database.endswith('_prm'):
                    self.projects_list.append(database)

            # Append projects to List-view
            self.listView_Projects.addItems(self.projects_list)
            self.database_connection_status.setText("Status: Connected")
            self.signalclass.turnOnComboBoxEmittor.emit()

        except:
            self.database_connection_status.setText("Status: Connection Refused")
        self.signalclass.turnOnComboBoxEmittor.emit()

    def checkUncalculatedLayers(self):
        self.unavailablebuttons=[]
        for checkbox in self.to_render:
            if checkbox[1] != "" and checkbox[1] in self.curlayerlist:
                curlayer = self.conn.cursor()
                try:
                    curlayer.execute("SELECT COUNT(*) FROM {}".format(self.chosen_project + "." +checkbox[1]))
                    results = curlayer.fetchone()
                    for r in results:
                        num=r
                        break
                    if not num>1:
                        self.checkbuttonNotAva(checkbox[0])
                except:
                    self.checkbuttonNotAva(checkbox[0])
            else:
                self.checkbuttonNotAva(checkbox[0])
        self.checkEntireGroupIsMising()
        self.HYD_Standard_Group.collapseExpandFixes()
        self.DAM_Standard_Group.collapseExpandFixes()
        self.RISK_Standard_Group.collapseExpandFixes()

    def AddedScenarios(self):
        self.senarios=[]
        self.cb_scenarios.clear()
        if "hyd_bound_scenario_prm" in self.curlayerlist:
            curlayer = self.conn.cursor()
            curlayer.execute("SELECT \"boundary_scenario_id\",\"name\" FROM {}.hyd_bound_scenario_prm".format(self.chosen_project))
            for senario in curlayer:
                self.senarios.append([senario[0],senario[1]])
                self.cb_scenarios.addItem(str(senario[0]) + ": " + senario[1])
                self.cb_scenarios.setCheckedItems([str(senario[0]) + ": " + senario[1]])
        curlayer = self.conn.cursor()
        curlayer.execute("SELECT \"table_name\" from information_schema.columns WHERE table_schema = '{}' AND column_name = 'boundary_scenario_id'".format(self.chosen_project))
        self.affectedSenarioLayers = []
        for item in curlayer:
            self.affectedSenarioLayers.append(item[0])

    def checkEntireGroupIsMising(self):
        for group in self.allGroupCheckboxes:
            children = group.findChildren(QCheckBox)
            state = False #all are not calculate
            for child in children:
                if not child in self.unavailablebuttons:
                    state=True #At least one is calculated
            if state == False:
                group.setToolTip("All layers in group are not calculated")
                group.setStyleSheet("QgsCollapsibleGroupBoxBasic::title, QGroupBox::title {color: Red;}")

    def checkbuttonNotAva(self,cbutton):
        self.unavailablebuttons.append(cbutton)
        cbutton.setEnabled(False)
        cbutton.setStyleSheet("QCheckBox { color: red }")
        cbutton.setToolTip("Layer not calculated")

    def on_currentItemChanged_of_listView_Projects(self, now, pre):
        if now is not None:
            self.signalclass.turnOnOptionsEmittor.emit()

            # Set Project variable
            self.chosen_project = now.text()

            # Grab layers that are in selected project
            self.curlayer = self.conn.cursor()
            self.curlayer.execute("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = '{}'".format(now.text()))

            # curlayerlist: To allow for filtering using search
            self.curlayerlist = []
            # Clear Layers lists and add new list
            self.listView_Layers.clear()
            self.combobox_feature.clear()
            for layer in self.curlayer:
                self.curlayerlist.append(str(layer[0]))
                if self.text_of_EditText_Search_Layers in str(layer[0]):
                    self.listView_Layers.addItem(str(layer[0]))
            self.AddedScenarios()
            self.checkUncalculatedLayers()
        else:
            self.signalclass.turnOffOptionsEmittor.emit()

    def on_currentItemChanged_of_listView_Layers(self, now, pre):
        if now is not None:
            # Set Project variable
            self.chosen_layer = now.text()
            # Grab layers that are in selected project
            self.curfeature = self.conn.cursor()

            self.curfeature.execute(
                "SELECT column_name from information_schema.columns WHERE table_schema = '{}' AND table_name='{}'".format(
                    self.chosen_project, self.chosen_layer))

            # curlayerlist: To allow for filtering using search
            self.curfeaturelist = []
            # Clear Layers lists and add new list
            self.combobox_feature.clear()
            for layer in self.curfeature:
                self.curfeaturelist.append(str(layer[0]))
                self.combobox_feature.addItem(str(layer[0]))

    def on_text_change_of_EditText_Search_Projects(self, value):
        # Clear ListView of Projects
        self.listView_Projects.clear()
        self.listView_Layers.clear()
        self.combobox_feature.clear()
        self.curlayerlist = []
        self.curfeaturelist = []
        # Filter projects based on search term
        for project in self.projects_list:
            if value in project:
                self.listView_Projects.addItem(project)

    def on_text_change_of_EditText_Search_Layers(self, value):
        # Clear ListView of Layer
        self.text_of_EditText_Search_Layers = value
        self.listView_Layers.clear()
        self.combobox_feature.clear()
        self.curfeaturelist = []
        # Filter layers based on search term
        for layer in self.curlayerlist:
            if value in layer:
                self.listView_Layers.addItem(layer)

    # Help button press function
    def Help(self):
        webbrowser.open("https://promaides.myjetbrains.com/youtrack/articles/PMDP-A-84/Quick-Visualize")

    # Database Management Tab
    def database_manage_tab(self):
        self.DatabaseListManage_dialog_instance.execDialog(self)

    # Read Databases List:
    def readDatabasesList(self):
        lines = []
        if self.qsettings.contains("promaides_databases_temp"):
            if self.qsettings.value("promaides_databases_temp") == "":
                self.qsettings.setValue("promaides_databases_temp", "localhost,5432,promaides,postgres,,1")
            else:
                lines = self.qsettings.value("promaides_databases_temp")
        else:
            self.qsettings.setValue("promaides_databases_temp", "localhost,5432,promaides,postgres,,1")
        datalines = self.qsettings.value("promaides_databases_temp").split("|")
        lines = [line.split(",") for line in datalines]
        return lines

    def on_combobox_changed_of_databaseSelection(self, index):
        self.database_selected_index = index

    def portErrorMessage(self):
        QMessageBox.information(None, "Message:", "Please check port of your database")



class SignalClass(QObject):
    turnOnOptionsEmittor = pyqtSignal()
    turnOffOptionsEmittor = pyqtSignal()
    turnOnComboBoxEmittor = pyqtSignal()
    portErrorEmittor = pyqtSignal()


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

    # connect here the buttons to functions, e.g. "OK"-button to execTool
    def execDialog(self):
        self.dialog = PluginDialog(self.iface, self.iface.mainWindow())
        self.dialog.accepted.connect(self.execTool)
        self.dialog.rejected.connect(self.quitDialog)
        self.dialog.show()
        self.dialog.do = 0
        threading.Thread(target=self.dialog.connectedPressed, daemon=True).start()
        # QgsApplication.taskManager().addTask(self.dialog.tryToConnect())

    def scheduleAbort(self):
        self.cancel = True

    # Quit the dialog; in general make nothing
    def quitDialog(self):
        self.dialog = None
        self.act.setEnabled(True)
        self.cancel = False

    # Execution of the tool by "OK" button
    def execTool(self):

        to_render=self.dialog.to_render


        for layer in to_render:
            if layer[0].isChecked() and layer[1] != "":

                project_name = self.dialog.chosen_project
                layer_name = layer[1]
                value_field = layer[2]
                layer_displayname=layer[4]

                # Get type of selected layer from database
                curColumnType = self.dialog.conn.cursor()
                curColumnType.execute("SELECT column_name from information_schema.columns WHERE table_schema = '{}' AND table_name='{}' AND data_type = 'USER-DEFINED'".format(project_name, layer_name))
                ColumnType = curColumnType.fetchone()

                # Check that layer has a valid type
                if ColumnType is not None:
                    layer_type = ColumnType[0]
                    if layer_displayname == "":
                        layer_toBeNamed = layer_name + "_" + value_field
                    else:
                        layer_toBeNamed= layer_displayname

                    if layer_name == "hyd_river_profile_prm":
                        vlayer = self.vlayerMakeradvanced("single", QColor(250, 250, 36), QColor(250, 250, 36), 5, project_name, layer_name, ColumnType[0], value_field, layer_toBeNamed)
                    elif layer_name == "hyd_river_profile_points_prm":
                        vlayer = self.vlayerMakeradvanced("marker", QColor(230, 35, 35), QColor(250, 250, 36), 5, project_name, layer_name, ColumnType[0], value_field, layer_toBeNamed)
                    elif layer_name == "hyd_floodplain_element_prm":
                        vlayer = self.vlayerMakeradvanced("graduated", QColor(230, 35, 35), QColor(250, 250, 36), 5, project_name, layer_name, ColumnType[0], value_field, layer_toBeNamed)
                    elif layer_name == "hyd_river_profile_max_results_prm":
                        vlayer = self.vlayerMakeradvanced("graduated", QColor(230, 35, 35), QColor(250, 250, 36), 5, project_name, layer_name, ColumnType[0], value_field, layer_toBeNamed)
                    elif layer_name == "dam_ecn_elements_prm":
                        vlayer = self.vlayerMakeradvanced("categorized", QColor(230, 35, 35), QColor(250, 250, 36), 5, project_name, layer_name, ColumnType[0], value_field, layer_toBeNamed)
                    elif layer_name == "dam_pop_element_prm":
                        vlayer = self.vlayerMakeradvanced("graduated", QColor(17, 208, 29), QColor(255, 0, 0), 5, project_name, layer_name, ColumnType[0], value_field, layer_toBeNamed)
                    elif layer_name == "dam_sc_point_prm":
                        vlayer = self.vlayerMakeradvanced("labeled", QColor(17, 208, 29), QColor(255, 0, 0), 5, project_name, layer_name, ColumnType[0], value_field, layer_toBeNamed)
                    elif layer_name == "dam_ecn_results_prm":
                        vlayer = self.vlayerMakeradvanced("graduated", QColor(250, 250, 36), QColor(255, 0, 0), 5, project_name, layer_name, ColumnType[0], value_field, layer_toBeNamed)
                    elif layer_name == "dam_pop_result_prm":
                        vlayer = self.vlayerMakeradvanced("dense", QColor(17, 255, 29), QColor(255, 0, 0), 5, project_name, layer_name, ColumnType[0], value_field, layer_toBeNamed)
                    elif layer_name == "dam_sc_point_erg_prm":
                        vlayer = self.vlayerMakeradvanced("labeledwithcolor", QColor(17, 255, 29), QColor(255, 0, 0), 5, project_name, layer_name, ColumnType[0], value_field, layer_toBeNamed)
                    else:
                        vlayer = self.vlayerMakeradvanced("", QColor(250, 250, 36), QColor(250, 250, 36), 5, project_name, layer_name, ColumnType[0], value_field, layer_toBeNamed)

                    selected_scenario_ids_list = [item.split(":") for item in self.dialog.cb_scenarios.checkedItems()]
                    if layer_name in self.dialog.affectedSenarioLayers:
                        selectedSenarios = self.dialog.cb_scenarios.checkedItems()
                        for selected_id in selected_scenario_ids_list:
                            v2layer=vlayer.clone()
                            v2layer.setName(layer_toBeNamed+ "_SC:"+selected_id[1].strip())
                            v2layer.setSubsetString('"boundary_scenario_id" = ' + selected_id[0] +' ')

                            if(self.dialog.checkbox_addedtonewgroup.isChecked()):
                                QgsProject.instance().addMapLayer(v2layer, False)
                                root = QgsProject.instance().layerTreeRoot()
                                layerroot = root
                                for x in range(2): #len(layer[3])
                                    if(layerroot.findGroup(layer[3][x]) is None):
                                        layerroot.addGroup(layer[3][x])
                                        layerroot = layerroot.findGroup(layer[3][x])
                                    else:
                                        layerroot = layerroot.findGroup(layer[3][x])
                                layerroot.addLayer(v2layer)
                            else:
                                QgsProject.instance().addMapLayer(v2layer)

                            if(not self.dialog.cb_layervisible.isChecked()):
                                layerlocation = QgsProject.instance().layerTreeRoot().findLayer(v2layer.id())
                                layerlocation.setItemVisibilityChecked(False)
                    else:
                        if(self.dialog.checkbox_addedtonewgroup.isChecked()):
                            QgsProject.instance().addMapLayer(vlayer, False)
                            root = QgsProject.instance().layerTreeRoot()
                            layerroot = root
                            for x in range(2): #len(layer[3])
                                if(layerroot.findGroup(layer[3][x]) is None):
                                    layerroot.addGroup(layer[3][x])
                                    layerroot = layerroot.findGroup(layer[3][x])
                                else:
                                    layerroot = layerroot.findGroup(layer[3][x])
                            layerroot.addLayer(vlayer)
                        else:
                            QgsProject.instance().addMapLayer(vlayer)

                        if(not self.dialog.cb_layervisible.isChecked()):
                            layerlocation = QgsProject.instance().layerTreeRoot().findLayer(vlayer.id())
                            layerlocation.setItemVisibilityChecked(False)

        # Check that a layer is selected
        if self.dialog.listView_Layers.currentItem() is not None and self.dialog.combobox_feature.currentText() is not None:
            project_name = self.dialog.chosen_project
            layer_name = self.dialog.chosen_layer
            value_field = self.dialog.combobox_feature.currentText()

            # Get type of selected layer from database
            curColumnType = self.dialog.conn.cursor()
            curColumnType.execute(
                "SELECT column_name from information_schema.columns WHERE table_schema = '{}' AND table_name='{}' AND data_type = 'USER-DEFINED'".format(
                    project_name, layer_name))

            ColumnType = curColumnType.fetchone()

            # Check that layer has a valid type
            if ColumnType is not None:
                layer_type = ColumnType[0]

                # Create QGIS layer from source
                self.dialog.uri_chosen_layer.setDataSource(project_name, layer_name, layer_type)
                layer_toBeNamed = layer_name + "_" + value_field

                vlayer = QgsVectorLayer(self.dialog.uri_chosen_layer.uri(False), layer_toBeNamed, "postgres")

                rampcolor1 = self.dialog.advancedcolor1
                rampcolor2 = self.dialog.advancedcolor2
                num_classes = self.dialog.spinbox_classes.value()

                renderer = QgsGraduatedSymbolRenderer()
                ramp_name = 'Greys'
                # classification_method = QgsClassificationEqualInterval()
                classification_method = QgsClassificationQuantile()
                format = QgsRendererRangeLabelFormat()
                format.setFormat("%1 - %2")
                format.setPrecision(2)
                format.setTrimTrailingZeroes(True)

                default_style = QgsStyle().defaultStyle()
                color_ramp = default_style.colorRamp(ramp_name)
                color_ramp.setColor1(rampcolor1)
                color_ramp.setColor2(rampcolor2)

                renderer.setClassAttribute(value_field)
                renderer.setClassificationMethod(classification_method)
                renderer.setLabelFormat(format)
                renderer.updateClasses(vlayer, num_classes)
                renderer.updateColorRamp(color_ramp)

                symbol = QgsFillSymbol.createSimple({'color': '200,200,43,255', 'outline_width': '0'})
                symbol.symbolLayers()[0].setDataDefinedProperty(QgsSymbolLayer.PropertyStrokeColor,
                                                                QgsProperty.fromExpression("@symbol_color", True))
                renderer.updateSymbols(symbol)

                vlayer.setRenderer(renderer)
                vlayer.setCrs(self.dialog.CRS_Select.crs())
                vlayer.setVisible(False)
                vlayer.triggerRepaint()

                # Add layer to current QGIS Instance
                QgsProject.instance().addMapLayer(vlayer)

                if(self.dialog.checkbox_addedtonewgroup.isChecked()):
                    root = QgsProject.instance().layerTreeRoot()
                    layer = root.findLayer(vlayer.id())

                    #Create Group if not existing
                    if(root.findGroup("QuickViz") is None):
                        root.addGroup("QuickViz")
                        group = root.findGroup("QuickViz")
                    else:
                        group = root.findGroup("QuickViz")
                    clone = layer.clone()
                    group.insertChildNode(0, clone)
                    parent = layer.parent()
                    parent.removeChildNode(layer)
            else:
                QMessageBox.information(None, "DEBUG:",
                                        "You selected an invalid layer<br><br>Possible Reasons: Layer was not calculated by ProMaides<br><br>Please try to select another layer")
        self.quitDialog()

    def vlayerMakeradvanced(self, typeRender, color1, color2, num_classes, project_name, layer_name, layer_type, value_field, layer_toBeNamed, line_width=0.4):
        self.dialog.uri_chosen_layer.setDataSource(project_name, layer_name, layer_type)
        vlayer = QgsVectorLayer(self.dialog.uri_chosen_layer.uri(False), layer_toBeNamed, "postgres")

        if typeRender == "single":
            symbol=QgsLineSymbol.createSimple({'color': '200,200,43,255', 'outline_width': line_width})
            renderer = QgsSingleSymbolRenderer(symbol)
        elif typeRender == "graduated" or typeRender == "marker" or typeRender == "dense" or typeRender == "labeledwithcolor":
            renderer = QgsGraduatedSymbolRenderer()
            # classification_method = QgsClassificationEqualInterval()
            classification_method = QgsClassificationQuantile()
            format = QgsRendererRangeLabelFormat()
            format.setFormat("%1 - %2")
            format.setPrecision(2)
            format.setTrimTrailingZeroes(True)

            default_style = QgsStyle().defaultStyle()
            color_ramp = default_style.colorRamp('Greys')
            color_ramp.setColor1(color1)
            color_ramp.setColor2(color2)

            renderer.setClassAttribute(value_field)
            renderer.setClassificationMethod(classification_method)
            renderer.setLabelFormat(format)
            renderer.updateClasses(vlayer, num_classes)
            renderer.updateColorRamp(color_ramp)

            if typeRender == "marker":
                symbol = QgsMarkerSymbol.createSimple({'color': '200,200,43,255', 'size' : '1', 'outline_style' : 'no'})
            elif typeRender == "labeledwithcolor":
                renderer.setGraduatedMethod(QgsGraduatedSymbolRenderer.GraduatedSize)
                renderer.updateClasses(vlayer, num_classes)
                renderer.setSymbolSizes(2, 8)
                symbol = QgsMarkerSymbol.createSimple({'outline_style' : 'no'})
                symbol.symbolLayers()[0].setDataDefinedProperty(QgsSymbolLayer.PropertyFillColor,QgsProperty.fromExpression("if(\"cat_id\" = 1,  color_rgb( 244,22,34),  if(\"cat_id\" = 2, color_rgb(63, 183, 180),  if(\"cat_id\" = 3, color_rgb(215,91,255),  if(\"cat_id\" = 4, color_rgb(221,167,91),  color_rgb( 244,222,34)))))", True))
                renderer.updateSymbols(symbol)
                settings  = QgsPalLayerSettings()
                settings.isExpression = True
                settings.fieldName = " if(\"cat_id\" = 1, 'Public Building',  if(\"cat_id\" = 2, 'Hazardous Substances Entity',  if(\"cat_id\" = 3, 'Cultural Heritage',  if(\"cat_id\" = 4, 'Buildings with Endangered People',  '?'))))"
                settings.enabled = True

                root = QgsRuleBasedLabeling.Rule(QgsPalLayerSettings())
                rule = QgsRuleBasedLabeling.Rule(settings)
                root.appendChild(rule)

                vlayer.setLabelsEnabled(True)
                qgsRuleBasedLabeling = QgsRuleBasedLabeling(root)
                vlayer.setLabeling(qgsRuleBasedLabeling)
            elif typeRender == "dense":
                styleUse = 'dense1' if value_field == 'pop_affected' else 'dense2'
                symbol = QgsFillSymbol.createSimple({'color': '200,200,43,255', 'outline_width': '0', 'style' : styleUse})
            else:
                symbol = QgsFillSymbol.createSimple({'color': '200,200,43,255', 'outline_width': '0'})
                symbol.symbolLayers()[0].setDataDefinedProperty(QgsSymbolLayer.PropertyStrokeColor,QgsProperty.fromExpression("@symbol_color",True))
            renderer.updateSymbols(symbol)
        elif typeRender == "categorized" or typeRender == "labeled":
            unique_values = vlayer.uniqueValues(vlayer.fields().indexFromName(value_field))
            category_list = []
            for value in unique_values:
                symbol = QgsSymbol.defaultSymbol(vlayer.geometryType())
                category = QgsRendererCategory(value, symbol, str(value))
                category_list.append(category)
            renderer = QgsCategorizedSymbolRenderer(value_field, category_list)
            renderer.updateColorRamp(QgsRandomColorRamp())

            if typeRender == "labeled":
                settings  = QgsPalLayerSettings()
                settings.isExpression = True
                settings.fieldName = " if(\"cat_id\" = 1, 'Public Building',  if(\"cat_id\" = 2, 'Hazardous Substances Entity',  if(\"cat_id\" = 3, 'Cultural Heritage',  if(\"cat_id\" = 4, 'Buildings with Endangered People',  '?'))))"
                settings.enabled = True

                root = QgsRuleBasedLabeling.Rule(QgsPalLayerSettings())
                rule = QgsRuleBasedLabeling.Rule(settings)
                root.appendChild(rule)

                vlayer.setLabelsEnabled(True)
                qgsRuleBasedLabeling = QgsRuleBasedLabeling(root)
                vlayer.setLabeling(qgsRuleBasedLabeling)

        vlayer.setRenderer(renderer)
        vlayer.setCrs(self.dialog.CRS_Select.crs())
        return vlayer

