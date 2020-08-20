from __future__ import unicode_literals
from __future__ import absolute_import

# system modules
import math

# QGIS modules 
from qgis.core import *
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import *
from qgis.PyQt import uic

from shapely.geometry import MultiLineString, mapping, shape

# promaides modules
from .environment import get_ui_path

#Connection to the UI-file (GUI); Edit the ui-file  via QTCreator
UI_PATH = get_ui_path('ui_hello_world.ui')

# This plugin serves as learning and test plugin
class PluginDialog(QDialog):

    #set-up of the dialog
    def __init__(self, iface, parent=None, flags=Qt.WindowFlags()):
        QDialog.__init__(self, parent, flags)
        #load the ui
        uic.loadUi(UI_PATH, self)

        self.iface = iface






class HelloWorld(object):

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

    #Execution of the tool by "ok" button
    def execTool(self):

        #Print text of the lineEdit to the QGIs python console
        print(self.dialog.lineEdit_1.text())

        self.quitDialog()
