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

        self.iface = iface
        self.conn = ""
        self.chosen_project = ""
        self.chosen_layer = ""
        self.database_selected_index = 0
        self.firstload = 0
        self.text_of_EditText_Search_Layers = ""

        self.color_selection_1.setStyleSheet("background-color : " + self.advancedcolor1.name() + "; border: 0px;")
        self.color_selection_2.setStyleSheet("background-color : " + self.advancedcolor2.name() + "; border: 0px;")

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

        self.signalclass = SignalClass()
        self.signalclass.turnOnOptionsEmittor.connect(self.enableOptions)
        self.signalclass.turnOffOptionsEmittor.connect(self.disableOptions)
        self.signalclass.turnOnComboBoxEmittor.connect(self.enableCombo)

        self.refreshDatabaseData()

    def on_ValueChanged_of_spinbox_classes(self, value):
        self.qsettings.setValue("spinbox_classes_value", value)

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
        self.listView_Layers.clear()
        self.curlayerlist = []
        self.combobox_feature.clear()
        self.curfeaturelist = []
        self.database_connection_status.setText("Status: Connecting")
        threading.Thread(target=self.tryToConnect, daemon=True).start()

    def enableOptions(self):
        self.group_river.setEnabled(True)
        self.group_floodplain.setEnabled(True)

    def disableOptions(self):
        self.group_river.setEnabled(False)
        self.combobox_databaseSelection.setEnabled(False)
        self.group_floodplain.setEnabled(False)

    def enableCombo(self):
        self.combobox_databaseSelection.setEnabled(True)

    def tryToConnect(self):

        if self.firstload != 0:
            connectionparameters = self.database_list[self.database_selected_index]
        else:
            connectionparameters = self.default_database_connect
            self.firstload += 1

        host, port, name, user, pwrd = connectionparameters[0], int(connectionparameters[1]), connectionparameters[2], \
                                       connectionparameters[3], connectionparameters[4]
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
            # self.signalclass.turnOnComboBoxEmittor.emit()
            # self.signalclass.turnOnOptionsEmittor.emit()

        except:
            self.database_connection_status.setText("Status: Connection Refused")
        self.signalclass.turnOnComboBoxEmittor.emit()

    def on_currentItemChanged_of_listView_Projects(self, now, pre):
        if now is not None:
            self.signalclass.turnOnOptionsEmittor.emit()
            # Set Project variable
            self.chosen_project = now.text()
            # Grab layers that are in selected project
            self.curlayer = self.conn.cursor()
            self.curlayer.execute(
                "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = '{}'".format(now.text()))
            # curlayerlist: To allow for filtering using search
            self.curlayerlist = []
            # Clear Layers lists and add new list
            self.listView_Layers.clear()
            self.combobox_feature.clear()
            for layer in self.curlayer:
                self.curlayerlist.append(str(layer[0]))
                if self.text_of_EditText_Search_Layers in str(layer[0]):
                    self.listView_Layers.addItem(str(layer[0]))
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
        webbrowser.open("https://promaides.myjetbrains.com/youtrack/articles/PMDP-A-52/Hello-World")

    # Database Management Tab
    def database_manage_tab(self):
        self.DatabaseListManage_dialog_instance.execDialog(self)

    # Read Databases List:
    def readDatabasesList(self):
        lines = []
        try:
            with open("promaides_databases.txt") as file:
                lines = file.readlines()
                lines = [line.rstrip().split(",") for line in lines]
                if lines == []:
                    lines = ["localhost,5432,promaides,postgres,,1".split(",")]
                    file = open("promaides_databases.txt", "w")
                    file.write("localhost,5432,promaides,postgres,,1")
                    file.close()
        except:
            print(
                "Tried to read Database failed. By default the database list in Documents Folder. Please Check that it exist otherwise please contact developers for support!")
            file = open("promaides_databases.txt", "w")
            file.write("localhost,5432,promaides,postgres,,1")
            file.close()
            lines = ["localhost,5432,promaides,postgres,,1".split(",")]
        return lines

    def on_combobox_changed_of_databaseSelection(self, index):
        self.database_selected_index = index


class SignalClass(QObject):
    turnOnOptionsEmittor = pyqtSignal()
    turnOffOptionsEmittor = pyqtSignal()
    turnOnComboBoxEmittor = pyqtSignal()


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

        to_render = [
            [self.dialog.bt_river_max_1, "hyd_river_profile_max_results_prm", "velocity"],
            [self.dialog.bt_river_max_2, "hyd_river_profile_max_results_prm", "discharge"],
            [self.dialog.bt_river_instat_1, "hyd_river_profile_instat_results_prm", "velocity"],
            [self.dialog.bt_river_instat_2, "hyd_river_profile_instat_results_prm", "discharge"],
            [self.dialog.bt_floodplain_max_x, "hyd_floodplain_elem_max_result_prm", "x_velocity"],
            [self.dialog.bt_floodplain_max_y, "hyd_floodplain_elem_max_result_prm", "y_velocity"],
            [self.dialog.bt_floodplain_instat_x, "hyd_floodplain_elem_instat_result_prm", "x_velocity"],
            [self.dialog.bt_floodplain_instat_y, "hyd_floodplain_elem_instat_result_prm", "y_velocity"],
            [self.dialog.bt_floodplain_goedetic, "hyd_floodplain_element_prm", "geodetic_height"]
        ]

        for layer in to_render:
            if layer[0].isChecked():

                project_name = self.dialog.chosen_project
                layer_name = layer[1]
                value_field = layer[2]

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
                    vlayer = QgsVectorLayer(self.dialog.uri_chosen_layer.uri(False), layer_name + "_" + value_field,
                                            "postgres")

                    # Styling of layer based on its type
                    if layer_name == "hyd_river_profile_max_results_prm" or layer_name == "hyd_river_profile_instat_results_prm" or "hyd_floodplain_elem_max_result_prm" or layer_name == "hyd_floodplain_elem_instat_result_prm" or layer_name == "hyd_floodplain_element_prm":
                        if (value_field == "velocity"):
                            rampcolor2 = QColor(255, 0, 0)
                            num_classes = 10
                        elif (value_field == "discharge"):
                            rampcolor2 = QColor(255, 145, 0)
                            num_classes = 10
                        elif (value_field == "x_velocity"):
                            rampcolor2 = QColor(230, 35, 0)
                            num_classes = 5
                        elif (value_field == "y_velocity"):
                            rampcolor2 = QColor(230, 35, 0)
                            num_classes = 5
                        elif (value_field == "geodetic_height"):
                            rampcolor2 = QColor(230, 35, 0)
                            num_classes = 5

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
                        color_ramp.setColor1(QColor(250, 250, 36))
                        color_ramp.setColor2(rampcolor2)

                        renderer.setClassAttribute(value_field)
                        renderer.setClassificationMethod(classification_method)
                        renderer.setLabelFormat(format)
                        renderer.updateClasses(vlayer, num_classes)
                        renderer.updateColorRamp(color_ramp)

                        symbol = QgsFillSymbol.createSimple({'color': '200,200,43,255', 'outline_width': '0'})
                        symbol.symbolLayers()[0].setDataDefinedProperty(QgsSymbolLayer.PropertyStrokeColor,
                                                                        QgsProperty.fromExpression("@symbol_color",
                                                                                                   True))
                        renderer.updateSymbols(symbol)

                    elif layer_name == "hyd_floodplain_elem_max_result_prm" or layer_name == "hyd_floodplain_elem_instat_result_prm" or layer_name == "hyd_floodplain_element_prm":
                        print("Debug 13FHD2")
                    else:
                        print(
                            "Please contact developer! Error in naming of layers. (Maybe there is a change in layer naming, please try using an older version of ProMaides!)")

                    vlayer.setRenderer(renderer)
                    vlayer.renderer().setSourceSymbol(symbol.clone())
                    vlayer.triggerRepaint()

                    # Add layer to current QGIS Instance
                    QgsProject.instance().addMapLayer(vlayer)
                    vlayer.triggerRepaint()

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
                vlayer = QgsVectorLayer(self.dialog.uri_chosen_layer.uri(False), layer_name + "_" + value_field,
                                        "postgres")

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
                vlayer.renderer().setSourceSymbol(symbol.clone())
                vlayer.triggerRepaint()

                # Add layer to current QGIS Instance
                QgsProject.instance().addMapLayer(vlayer)
                vlayer.triggerRepaint()
            else:
                QMessageBox.information(None, "DEBUG:",
                                        "You selected an invalid layer<br><br>Possible Reasons: Layer was not calculated by ProMaides<br><br>Please try to select another layer")
        self.quitDialog()