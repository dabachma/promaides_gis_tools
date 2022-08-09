import os

# QGIS modules
from qgis.core import *
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import *
from qgis.PyQt import uic
from PyQt5 import QtWidgets
from qgis.PyQt.QtGui import *
from PyQt5.QtCore import *
from PyQt5 import QtCore

from .ui import resources

# promaides modules
from .environment import get_ui_path

UI_PATH = get_ui_path('ui_database_list_management.ui')


class DatabaseListManagementDialog(QDialog):
    trigger = pyqtSignal()

    def __init__(self, iface, parent=None, flags=Qt.WindowFlags()):
        QDialog.__init__(self, parent, flags)
        uic.loadUi(UI_PATH, self)
        self.iface = iface

        # trigger.connect(self.tempo)
        # trigger.emit()

        self.databases_list = self.readDatabasesList(0)

        self.groupPriority = QButtonGroup(self.databases_view)
        self.groupRemove = QButtonGroup(self.databases_view)
        self.groupPriority.idClicked.connect(self.itclicked)
        self.groupRemove.idClicked.connect(self.removeClicked)

        self.b_ok.clicked.connect(self.b_ok_clicked)

        self.b_add.clicked.connect(self.b_add_clicked)
        self.b_cancel.clicked.connect(self.b_cancel_clicked)

        header = self.databases_view.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QtWidgets.QHeaderView.ResizeToContents)
        self.databases_view.itemChanged.connect(self.databases_view_itemChanged)

        self.refreshDatabase()

    def refreshDatabase(self):
        self.databases_view.setRowCount(0)
        for x in range(len(self.databases_list)):
            self.databases_view.insertRow(x)
            for y in range(7):
                if y == 5:
                    button = QRadioButton()
                    if self.databases_list[x][y] == "1":
                        button.setChecked(True)
                    self.groupPriority.addButton(button, x)
                    w = QWidget()
                    l = QHBoxLayout()
                    l.addWidget(button)
                    l.setAlignment(Qt.AlignHCenter)
                    l.setContentsMargins(0, 0, 0, 0)
                    w.setLayout(l)
                    self.databases_view.setCellWidget(x, y, w)
                elif y == 6:
                    button = QPushButton()
                    button.setIcon(QIcon(':/remove_icon'))
                    button.setIconSize(QSize(15, 15))
                    button.setFlat(True)
                    self.groupRemove.addButton(button, x)
                    w = QWidget()
                    l = QHBoxLayout()
                    l.addWidget(button)
                    l.setAlignment(Qt.AlignHCenter)
                    l.setContentsMargins(0, 0, 0, 0)
                    w.setLayout(l)
                    self.databases_view.setCellWidget(x, y, w)
                else:
                    item = QtWidgets.QTableWidgetItem(str(self.databases_list[x][y]))
                    item.setTextAlignment(Qt.AlignHCenter)
                    item.setTextAlignment(Qt.AlignVCenter)
                    self.databases_view.setItem(x, y, item)

    def removeClicked(self, theid):
        for x in range(len(self.databases_list)):
            if x == theid:
                del self.databases_list[x]
                self.refreshDatabase()
                break

    def itclicked(self, theid):
        for x in range(len(self.databases_list)):
            if x == theid:
                self.databases_list[x][5] = "1"
            else:
                self.databases_list[x][5] = ""

    def b_add_clicked(self):
        self.databases_list.append(["", "", "", "", "", ""])
        self.refreshDatabase()

    def databases_view_itemChanged(self, item):
        if int(item.row()) == len(self.databases_list):
            self.databases_list.append(["", "", "", "", "", ""])
        self.databases_list[item.row()][item.column()] = item.text()

    def writelist(self, thelist):
        file = open("promaides_databases.txt", "w")
        for x in range(len(thelist)):
            lineout = thelist[x][0]
            for y in range(1, len(thelist[x])):
                lineout = lineout + "," + str(thelist[x][y])
            file.write(lineout + "\n")
        file.close()

    def checkCorrectDataRow(self, one):
        dataexists = False
        empties = False
        for x in range(len(one)):
            if one[x] == "":
                if not (x == 4 or x == 5):
                    empties = True
            else:
                dataexists = True
        return [empties, dataexists]

    def b_ok_clicked(self):
        fillerror = False
        towrite = []
        for row in self.databases_list:
            state = self.checkCorrectDataRow(row)
            if state[0] == True and state[1] == True:
                QMessageBox.information(None, "Message:", "Please fill all required fields")
                fillerror = True
            elif state[0] == True and state[1] == False:
                # no data
                print("no data")
            elif state[0] == False and state[1] == True:
                towrite.append(row)
        if fillerror == False:
            self.writelist(towrite)
            self.trigger.emit()
            self.close()

    def b_cancel_clicked(self):
        self.close()

    def readDatabasesList(self, tries):
        lines = []
        try:
            with open("promaides_databases.txt") as file:
                lines = file.readlines()
                lines = [line.rstrip().split(",") for line in lines]
        except:
            if tries > 3:
                print(
                    "Tried to read Database 3 times and failed. By default the database list in Documents Folder. Please Check that it exist otherwise please contact developers for support!")
                return []
            else:
                tries += 1
            file = open("promaides_databases.txt", "a")
            file.write("localhost,5432,promaides,postgres,,1")
            file.close()
            self.readDatabasesList(tries)
        return lines


class DatabaseListManagement(object):

    def __init__(self, iface):
        self.iface = iface
        self.dialog = None
        self.cancel = False
        self.act = QAction('Hello world', iface.mainWindow())
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
    def execDialog(self, pluginSelf):
        self.pluginSelf = pluginSelf
        self.dialog = DatabaseListManagementDialog(self.iface, self.iface.mainWindow())
        self.dialog.trigger.connect(self.refreshMainPlugin)
        self.dialog.show()

    def scheduleAbort(self):
        self.cancel = True

    def refreshMainPlugin(self):
        self.pluginSelf.refreshDatabaseData()

