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

# loflodes modules
from .environment import get_ui_path

#Connection to the UI-file (GUI); Edit the ui-file  via QTCreator
UI_PATH = get_ui_path('ui_weather_transfer.ui')

# This plugin serves as learning and test plugin
class PluginDialog(QDialog):

    #set-up of the dialog
    def __init__(self, iface, parent=None, flags=Qt.WindowFlags()):
        QDialog.__init__(self, parent, flags)
        #load the ui
        uic.loadUi(UI_PATH, self)
        self.iface = iface

        self.browse_button.clicked.connect(self.onBrowseButtonClicked)
        self.browse_button_import.clicked.connect(self.onBrowseButtonImportClicked)
        self.HelpButton.clicked.connect(self.Help)

    def printDatetime(self):
        value = self.start_date.dateTime()
        start_value = value.toString("yyyy-MM-dd HH:mm:ss")


    def onBrowseButtonImportClicked(self):
        current_filename_import = self.import_filename.text()
        new_filename_import, __ = QFileDialog.getOpenFileName(self.iface.mainWindow(), 'Weather transfer Import',current_filename_import, "*.txt")
        if new_filename_import != '':
            self.import_filename.setText(new_filename_import)
            self.import_filename.editingFinished.emit()


    #defines what happens when the browse button is clicked
    def onBrowseButtonClicked(self):
        current_filename = self.filename_edit.text()
        new_filename, __ = QFileDialog.getSaveFileName(self.iface.mainWindow(), 'Weather transfer Export', current_filename, "*.txt")
        if new_filename != '':
            self.filename_edit.setText(new_filename)
            self.filename_edit.editingFinished.emit()


    def Help(self):
        webbrowser.open("https://promaides.myjetbrains.com/youtrack/articles/LFDH-A-7/Weathertransfer")


class WeatherTransfer(object):

    def __init__(self, iface):
        self.iface = iface
        self.dialog = None
        self.cancel = False
        self.act = QAction('Weather transfer', iface.mainWindow())
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

    #function for
    def transfer(self, import_path, resolution,type , starttime, endtime, outputpath):
        if type == 'humidity':
            df_name = pd.read_csv(import_path, sep=';', header=0, index_col=1, na_values='-99.9')
        elif type == 'radiation':
            df_name = pd.read_csv(import_path, sep=';', header=0, index_col=1, na_values=['-999', '-999.0', '-999.00', '  -999', '-999  '], on_bad_lines='skip')
            if 'eor' in df_name.columns:  # this serves to filter the column of 'eor' which are in the global radtion files after 2000
                df_name = df_name.drop('eor', axis=1)
        else:
            df_name = pd.read_csv(import_path,sep=';', header=0, index_col=1,  na_values='  -999')
        if resolution == 'hourly':
            df_name.index = pd.to_datetime(df_name.index, format='%Y%m%d%H')
            start = df_name.index[0].date()
            end = df_name.index[len(df_name) - 1].date()
            new_dates = pd.date_range(start=start, end=end, freq='H')
            df_name = df_name.reindex(new_dates)
            df_name = df_name.rename_axis('MESS_DATUM')
            factor = 1
        elif resolution == 'daily':
            df_name.index = pd.to_datetime(df_name.index, format='%Y%m%d')
            start = df_name.index[0].date()
            end = df_name.index[len(df_name) - 1].date()
            new_dates = pd.date_range(start=start, end=end, freq='d')
            df_name = df_name.reindex(new_dates)
            df_name = df_name.rename_axis('MESS_DATUM')
            factor = 1/24
        elif resolution == 'min':
            df_name.index = pd.to_datetime(df_name.index, format='%Y%m%d%H%M')
            start = df_name.index[0].date()
            end = df_name.index[len(df_name) - 1].date()
            new_dates = pd.date_range(start=start, end=end, freq='10min')
            df_name = df_name.groupby(
            df_name.index).first()  # Remove duplicates by aggregating to the first value in each group
            df_name = df_name.reindex(new_dates)
            df_name = df_name.rename_axis('MESS_DATUM')
            df_name = df_name.resample('H').mean()
            factor = 6
        df_name = df_name.loc[starttime: endtime]
        df_name = df_name.reset_index()
        if type == 'wind':
            df_output = df_name['   F']
        elif type == 'radiation':
            df_output = df_name['GS_10'] * (2.78 * factor)
        elif type == 'air temperature':
            df_output = df_name['TT_STD'] +273.15
        elif type == 'humidity':
            df_output = df_name['RF_STD'] /100
        df_output = df_output.interpolate()
        df_output.to_csv(outputpath, sep=' ')

    #Execution of the tool by "ok" button
    def execTool(self):
        #define the input data
        importpath = self.dialog.import_filename.text()
        outputpath = self.dialog.filename_edit.text()
        if self.dialog.daily_box.isChecked():
            resolution = 'daily'
        elif self.dialog.hourly_box.isChecked():
            resolution = 'hourly'
        elif self.dialog.min_box.isChecked():
            resolution = 'min'
        if self.dialog.wind_box.isChecked():
            type = 'wind'
        elif self.dialog.radiation_box.isChecked():
            type = 'radiation'
        elif self.dialog.airtemperature_box.isChecked():
            type = 'air temperature'
        elif self.dialog.humidity_box.isChecked():
            type = 'humidity'
        value = self.dialog.start_date.dateTime()
        start_value = value.toString("yyyy-MM-dd HH:mm:ss")
        value = self.dialog.end_date.dateTime()
        end_value = value.toString("yyyy-MM-dd HH:mm:ss")

        self.transfer(importpath, resolution,type,start_value,end_value, outputpath)

        self.quitDialog()
