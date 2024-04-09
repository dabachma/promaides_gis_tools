from __future__ import unicode_literals
from __future__ import absolute_import
import datetime

# system modules
import math
import webbrowser

# QGIS modules 
import PyQt5
from dataclasses import dataclass
from qgis.core import *
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import *
from qgis.PyQt.QtWidgets import QDialog, QApplication, QWidget, QInputDialog, QLineEdit, QFileDialog, QAction
from qgis.PyQt import uic


import pathlib

from shapely.geometry import MultiLineString, mapping, shape

# promaides modules
from .BoundaryConditionEinleiter import generate_boundary_conditions, HEADERS_pretty

#Connection to the UI-file (GUI); Edit the ui-file  via QTCreator
p = pathlib.Path(__file__).with_name('ui_bc_regular_industry_actors.ui')
print(p)
UI_PATH = p.resolve().absolute().as_posix()


@dataclass
class InputValues:
    fp_import_industry : str
    fp_import_inflows: str
    date_begin : datetime.datetime
    date_end : datetime.datetime
    fp_output_bc : str  

class PluginDialog(QDialog):

    #set-up of the dialog
    def __init__(self, iface, parent=None, flags=Qt.WindowFlags()):
        QDialog.__init__(self, parent, flags)
        #load the ui
        uic.loadUi(UI_PATH, self)
        self.iface = iface

        self.button_help.clicked.connect(self.Help)
        self.input_browse_industry.clicked.connect(self.onBrowseInputButtonClicked_Industry)	
        self.input_browse_inflows.clicked.connect(self.onBrowseInputButtonClicked_Inflows)	
        self.export_browse.clicked.connect(self.onBrowseOutputButtonClicked)
        
        self.label_import_industry_columns.setText("; ".join([h.name for h in HEADERS_pretty]))

    def Help(self):
        webbrowser.open("https://promaides.myjetbrains.com/youtrack/articles/LFDH-A-9/Regular-Industry-Actors")

    def __del__(self):
        pass

    def onBrowseInputButtonClicked_Industry(self):
        current_filename = self.import_filename_industry.text()
        new_filename, __ = QFileDialog.getOpenFileName(self.iface.mainWindow(), 'Choose CSV for the Industry actors', current_filename, filter = "*.csv", initialFilter = "*.csv")
        if new_filename != '':
            self.import_filename_industry.setText(new_filename)

    def onBrowseInputButtonClicked_Inflows(self):
        current_filename = self.import_filename_inflows.text()
        new_filename, __ = QFileDialog.getOpenFileName(self.iface.mainWindow(), 'Choose boundary condition file for river inflows', current_filename, filter = "*.txt", initialFilter = "*.txt")
        if new_filename != '':
            self.import_filename_inflows.setText(new_filename)

    def onBrowseOutputButtonClicked(self):
        current_filename = self.export_filename.text()
        new_filename, __ = QFileDialog.getSaveFileName(self.iface.mainWindow(), 'Choose where to save the boundary condition file', current_filename, initialFilter = "*.txt")
        if new_filename != '':
            self.export_filename.setText(new_filename)


class RegularIndustryActors(object):

    def __init__(self, iface):
        self.iface = iface
        self.dialog = None
        self.cancel = False
        self.act = QAction('Boundary conditions industry', iface.mainWindow())
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


    def button_ok_clicked(self):
        self.execTool()


    def button_cancel_clicked(self):
        self.quitDialog()

    def execDialog(self):
        """
        """
        self.dialog = PluginDialog(self.iface, self.iface.mainWindow())
        self.dialog.button_ok.clicked.connect(self.button_ok_clicked)
        self.dialog.button_cancel.clicked.connect(self.button_cancel_clicked)
        self.dialog.show()

    def scheduleAbort(self):
        self.cancel = True

  
    def quitDialog(self):
        self.act.setEnabled(True)
        self.cancel = False
        self.dialog.close()
        self.dialog = None

    def execTool(self):
        date_format = '%d/%m/%Y %H:%M'
        iv = input_vals = InputValues(
            fp_import_industry = self.dialog.import_filename_industry.text().strip(),
            fp_import_inflows = self.dialog.import_filename_inflows.text().strip(),
            date_begin = self.dialog.datebegin.dateTime().toPyDateTime(),
            date_end = self.dialog.dateend.dateTime().toPyDateTime(),
            fp_output_bc = self.dialog.export_filename.text().strip()
        )
        #Check
        result, errors = generate_boundary_conditions(path_einleiter_data = iv.fp_import_industry,
                                                        path_zuflusse_Ls = iv.fp_import_inflows,
                                                        date_begin = iv.date_begin,
                                                        date_end = iv.date_end,
                                                        path_save_to = iv.fp_output_bc)
        
        if not result: self.iface.messageBar().pushCritical('Errors in the input', "".join(errors)  )            
        else:
            self.dialog.button_ok.setText("Completed")
            self.dialog.button_ok.setEnabled(False)
            self.dialog.button_cancel.setText("Exit")
        
