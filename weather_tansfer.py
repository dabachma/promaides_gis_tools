from __future__ import unicode_literals
from __future__ import absolute_import

# system modules
import math
import webbrowser
import pandas as pd
from datetime import datetime, timedelta

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
    def transfer_dwd(self, import_path, resolution, type, starttime, endtime, outputpath):
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
        df_output = df_name
        if type == 'wind':
            df_output = df_name['   F']
        elif type == 'radiation':
            df_output = df_name['GS_10'] * (2.78 * factor)
        elif type == 'air temperature':
            prim_col = 'TT_STD'
            alt_col = 'TT_TU'
            oth_col = ' TMK'
            if prim_col in df_name.columns:
                df_output = df_name['TT_STD'] +273.15
            elif alt_col in df_name.columns:
                df_output = df_name['TT_TU'] + 273.15
            elif oth_col in df_name.columns:
                df_output = df_name[' TMK'] + 273.15
        elif type == 'humidity':
            df_output = df_name['RF_STD'] /100

        df_output = df_output.interpolate()
        df_output.to_csv(outputpath, sep=' ')

    def transfer_wg(self, importpath, resolution, type, outputpath):
        df_name = pd.read_csv(importpath, sep=',', header=0) #index_col=0)
        if resolution == 'hourly':
            df_name['date'] = df_name['date'].astype(str)
            df_name['date'] = df_name['date'].apply(lambda x: datetime.strptime(x, '%Y%m%d'))
            #this is the reference date which must be editable by the user in published version
            ref_date = datetime(5000, 1, 1, 0, 0, 0)
            def hours_since_date(t):
                return (t - ref_date).total_seconds() // 3600
            df_name['hour'] = df_name['date'].apply(hours_since_date)
            #this list contains the values for calculation hourly radiation (should be editable by the user)
            perc_list_radiation = [0, 0, 0, 0, 0, 0, 0, 0.02, 0.03, 0.06, 0.08, 0.12, 0.15, 0.14, 0.12, 0.11, 0.08, 0.06, 0.02, 0.01, 0, 0, 0, 0]
            perc_list_airtemp =  [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
            def spread_hourly(sub_series: pd.Series) -> pd.DataFrame:
                hour: int = sub_series["hour"]
                hours = [hour + index for index in range(24)]
                if type == 'radiation':
                    value = sub_series["GLOST"]
                    values = [value * p for p in perc_list_radiation]
                elif type == 'air temperature':
                    value = sub_series["TEMP"]
                    values = [value * p for p in perc_list_airtemp]
                sub_df = pd.DataFrame({"hours": hours, "sub_value": values})
                return sub_df

            dfs = []
            df_result =pd.DataFrame()
            for r, row in df_name.iterrows():
                sub_df = spread_hourly(row)
                dfs.append(sub_df)
            df_name = pd.concat(dfs)
            if type == 'air temperature' and resolution == 'hourly':
                perc_temp = pd.read_csv('C:/Users/uhalbrit/DryRivers/07_Code/promaides_gis_tools/perc_air_temp.csv',
                                        sep=',', index_col=0)

                # Berechne die Anzahl der vollständigen Blöcke, die auf die Länge des DataFrames passen
                iterations = len(df_name) // len(perc_temp)

                # Iteriere über jeden Block und multipliziere mit den Prozentwerten
                df_result_blocks = []
                for i in range(iterations):
                    start_idx = i * len(perc_temp)
                    end_idx = start_idx + len(perc_temp)
                    df_name_block = df_name.iloc[start_idx:end_idx]
                    df_result_block = df_name_block.mul(perc_temp.values, axis=0)
                    df_result_blocks.append(df_result_block)

                # Verarbeite den Rest, falls die Länge von df_name nicht genau durch perc_temp teilbar ist
                if len(df_name) % len(perc_temp) != 0:
                    start_idx = iterations * len(perc_temp)
                    df_name_block = df_name.iloc[start_idx:]
                    df_perc_block = perc_temp.iloc[:len(df_name_block)]
                    df_result_block = df_name_block.mul(df_perc_block.values, axis=0)
                    df_result_blocks.append(df_result_block)

                # Füge alle Blöcke zusammen
                df_result = pd.concat(df_result_blocks).reset_index(drop=True)

                # Temperaturumrechnung und Begrenzung
                df_result = df_result + 273.15 #ueberfaellig da ab WG V4 Kelvij-Werte ausgegeben werden
                df_result = df_result.clip(upper=313)
                df_result = df_result.clip(lower=243)

                df_name = df_result
            df_output = df_name['sub_value'].reset_index(drop=True)

        elif resolution == 'daily':
            df_output = df_name.index * 24
            if type == 'wind':
                df_output = df_name['WIND']
            elif type == 'radiation':
                df_output = df_name['GLOST'] * (2.78)
            elif type == 'air temperature':
                df_output = df_name['TEMP']+273.15
            elif type == 'humidity':
                df_output = df_name['LUFEU']
        df_output.index = df_output.index
        df_output.to_csv(outputpath, sep=' ')
        return df_output
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
        if self.dialog.dwd_box.isChecked():
            self.transfer_dwd(importpath, resolution, type, start_value, end_value, outputpath)
        elif self.dialog.wg_box.isChecked():
            self.transfer_wg(importpath,resolution,type,outputpath)
        self.quitDialog()
