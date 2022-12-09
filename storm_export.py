from __future__ import unicode_literals
from __future__ import absolute_import

# system modules
import math
import webbrowser
import pandas as pd
import time
import threading


# QGIS modules 
from qgis.core import *
from qgis.PyQt.QtCore import Qt, QAbstractTableModel, QModelIndex, pyqtSignal, QObject
from qgis.PyQt.QtWidgets import *
from qgis.PyQt import uic
from PyQt5 import QtWidgets
from PyQt5 import QtCore

from shapely.geometry import MultiLineString, mapping, shape

# promaides modules
from .environment import get_ui_path

#Connection to the UI-file (GUI); Edit the ui-file  via QTCreator
UI_PATH = get_ui_path('ui_storm_export.ui')

# This plugin serves as learning and test plugin
class PluginDialog(QDialog):

    #set-up of the dialog
    def __init__(self, iface, parent=None, flags=Qt.WindowFlags()):
        QDialog.__init__(self, parent, flags)
        uic.loadUi(UI_PATH, self)
        self.iface = iface
        self.HelpButton.clicked.connect(self.Help)

        #initialize:
        self.filter_1_valueStyle = self.filter_1_value.styleSheet()
        self.button_box_ok.setEnabled(False)
        self.results_display_currentItem = None
        self.results_display_currentItemIndex = -1


        self.fixSizePolicy(self.button_clear)
        self.fixSizePolicy(self.clear_table_button)
        self.fixSizePolicy(self.loading_icon)
        self.fixSizePolicy(self.filter_stats)

        self.button_clear.setVisible(False)
        self.clear_table_button.setVisible(False)
        self.loading_icon.setVisible(False)
        self.filter_stats.setVisible(False)

        self.grs_browse.setAutoDefault(False)
        self.grc_browse.setAutoDefault(False)
        self.output_browse.setAutoDefault(False)
        self.button_clear.setAutoDefault(False)
        self.button_filter.setAutoDefault(False)
        self.button_filter_further.setAutoDefault(False)
        self.button_box_ok.setAutoDefault(False)
        self.button_box_cancel.setAutoDefault(False)
        self.clear_table_button.setAutoDefault(False)
        self.HelpButton.setAutoDefault(False)

        #Connect Signals
        self.signalclass = SignalClass()
        self.button_box_ok_emittor = self.signalclass.button_box_ok_emittor
        self.button_box_cancel_emittor = self.signalclass.button_box_cancel_emittor
        self.signalclass.plugin_loading_state_emittor.connect(self.plugin_loading_state)
        self.signalclass.plugin_finished_loading_state_emittor.connect(self.plugin_finished_loading_state)

        #Connect Buttons
        self.button_box_ok.clicked.connect(self.button_box_ok_clicked)
        self.button_box_cancel.clicked.connect(self.button_box_cancel_clicked)
        self.grs_browse.clicked.connect(self.grs_browse_clicked)
        self.grc_browse.clicked.connect(self.grc_browse_clicked)
        self.output_browse.clicked.connect(self.output_browse_clicked)
        self.grs_edit_path.textChanged.connect(self.grs_text_edited)
        self.grc_edit_path.textChanged.connect(self.grc_text_edited)
        self.output_edit_path.textChanged.connect(self.output_text_edited)


        self.grs_edit_path.returnPressed.connect(self.grs_browse_clicked)
        self.grc_edit_path.returnPressed.connect(self.grc_browse_clicked)
        self.output_edit_path.returnPressed.connect(self.output_browse_clicked)
        self.filter_1_value.returnPressed.connect(self.button_filter_further_clicked)

        self.button_filter.clicked.connect(self.button_filter_clicked)
        self.button_filter_further.clicked.connect(self.button_filter_further_clicked)
        self.button_clear.clicked.connect(self.button_clear_clicked)
        self.clear_table_button.clicked.connect(self.clear_table_button_clicked)
        self.results_display.currentItemChanged.connect(self.results_display_currentItemChanged)

        #Set Table of storms:
        self.reset_storm_table()

    def button_box_ok_clicked(self):
        self.signalclass.button_box_ok_emittor.emit()

    def button_box_cancel_clicked(self):
        self.signalclass.button_box_cancel_emittor.emit()
        self.close()

    def results_display_currentItemChanged(self,current,pre):
        try:
            self.results_display_currentItem = current
            self.results_display_currentItemIndex = current.row()
        except:
            self.results_display_currentItem = None
            self.results_display_currentItemIndex = -1
        self.updateButtonBox()
        

    def fixSizePolicy(self,widget):
        sizePolicy = widget.sizePolicy()
        sizePolicy.setRetainSizeWhenHidden(True)
        widget.setSizePolicy(sizePolicy)


    def plugin_loading_state(self):
        self.filter_stats.setVisible(False)
        self.loading_icon.setVisible(True)
        self.results_display.setRowCount(0)
        self.results_display.repaint()
        self.filter_stats.repaint()
        self.loading_icon.repaint()
        
    def plugin_finished_loading_state(self):
        self.filter_stats.setVisible(True)
        self.loading_icon.setVisible(False)

    def clear_table_button_clicked(self):
        self.results_display.setRowCount(0)
        self.grs_edit_path.setText("")
        self.clear_table_button.setVisible(False)
        self.filter_stats.setVisible(False)
        self.button_clear.setVisible(False)
        self.results_display_currentItem = None
        self.results_display_currentItemIndex = -1


    def button_clear_clicked(self):
        for i in range (self.results_display.rowCount()):
            self.results_display.setRowHidden(i,False);
        self.filter_1_value.setText("")
        self.filter_stats.setText("Displaying:\n" + str(self.len_storm_list) +" out of " + str(len(self.storm_list))+self.time_to_display)
        self.button_clear.setVisible(False)

    def button_filter_further_clicked(self):
        self.filterfurther=True
        self.filter_table_results()

    def button_filter_clicked(self):
        self.filterfurther=False
        self.filter_table_results()

    def filter_table_results(self):
        try:
            filter_1_value = float(self.filter_1_value.text())
        except ValueError:
            self.filter_1_value.setStyleSheet("border: 1px solid red;")
            return

        self.filter_1_value.setStyleSheet(self.filter_1_valueStyle)
        self.button_clear.setVisible(True)
        filter_1_combo_index = self.filter_1_combo.currentIndex()
        comparitor = self.filter_1_operator.currentText()

        if comparitor=="Top":
            column_data=[]
            for i in range (self.results_display.rowCount()):
                if self.filterfurther and self.results_display.isRowHidden(i):
                    continue
                else:
                    column_data.append(float(self.results_display.item(i,filter_1_combo_index).text()))
            column_data.sort()
            self.results_display_top=column_data[-int(filter_1_value)]
        if comparitor=="Bottom":
            column_data=[]
            for i in range (self.results_display.rowCount()):
                if self.filterfurther and self.results_display.isRowHidden(i):
                    continue
                else:
                    column_data.append(float(self.results_display.item(i,filter_1_combo_index).text()))
            column_data.sort()
            self.results_display_bottom=column_data[int(filter_1_value)-1]

        counter=0
        for i in range (self.results_display.rowCount()):
            if self.filterfurther and self.results_display.isRowHidden(i):
                continue
            elif self.operatorCompare(float(self.results_display.item(i,filter_1_combo_index).text()),filter_1_value,comparitor):
                counter=counter+1
                self.results_display.setRowHidden(i,False);
            else:
                self.results_display.setRowHidden(i,True);
        self.filter_stats.setText("Displaying:\n" + str(counter) +" out of " + str(len(self.storm_list))+self.time_to_display)
        self.updateButtonBox()
        
    def operatorCompare(self,item1,item2,comparitor):
        if comparitor==">":
            return (item1 > item2)
        elif comparitor==">=":
            return (item1 >= item2)
        elif comparitor=="<":
            return (item1 < item2)
        elif comparitor=="<=":
            return (item1 <= item2)
        elif comparitor=="=":
            return (item1 == item2)
        elif comparitor=="!=":
            return (item1 != item2)
        elif comparitor=="Top":
            return item1 >= self.results_display_top
        elif comparitor=="Bottom":
            return item1 <= self.results_display_bottom
        else:
            return False

    def populate_filter_1_combo(self):
        #Or should we do manual population?
        self.filter_1_combo.clear()
        for header in self.storm_file_headers:
            self.filter_1_combo.addItem(header.replace("_", " ").replace("\n", ""))
        self.signalclass.plugin_finished_loading_state_emittor.emit()

    def reset_storm_table(self):
        header = self.results_display.horizontalHeader()
        for i in range(10):
            header.setSectionResizeMode(i, QtWidgets.QHeaderView.ResizeToContents)
        

    def on_grs_browse_given(self):
        self.signalclass.plugin_loading_state_emittor.emit()
        self.results_display.setSortingEnabled(False)
        #self.storm_list = self.readstormfile(self.grs_path)
        self.clear_table_button.setVisible(True)
        self.results_display.blockSignals(True)
        

        #self.storm_list = self.readstormfile2(self.grs_path)
        #self.tableModel = TableModel(self.storm_list,self.storm_file_headers)
        #self.results_display.setSortingEnabled(True)
        #self.sortModel =  SortModel(self)
        #self.sortModel.setSourceModel(self.tableModel)
        #self.results_display.setModel(self.sortModel)
        #self.results_display.show()
        

        self.populateTable()
        self.results_display.blockSignals(False)

    def populateTable(self):
        start = time.time()
        header = self.results_display.horizontalHeader()
        for i in range(10):
            header.setSectionResizeMode(i, QtWidgets.QHeaderView.Fixed)
        self.results_display.setRowCount(0)
        DISPLAY_LIMIT=9999999
        self.len_storm_list = len(self.storm_list) if len(self.storm_list) <= DISPLAY_LIMIT else DISPLAY_LIMIT
        for x in range(0,self.len_storm_list):
            self.results_display.insertRow(x)
            #if(x%100==0):
            #    QApplication.instance().processEvents()
            for y in range(10):
                if y>2:
                    value=round(float(self.storm_list[x][y]),4)
                else:
                    value=int(self.storm_list[x][y])
                item = QtWidgets.QTableWidgetItem()
                item.setData(Qt.DisplayRole,value)
                item.setTextAlignment(Qt.AlignHCenter)
                item.setTextAlignment(Qt.AlignVCenter)
                self.results_display.setItem(x, y, item)
        self.results_display.setSortingEnabled(True)
        self.time_to_display= "\n\nDisplayed in: \n" + str(round(time.time()-start,3)) + "ms"
        self.filter_stats.setText("Displaying:\n" + str(self.len_storm_list) +" out of " + str(len(self.storm_list))+self.time_to_display)
        self.populate_filter_1_combo()

    def readstormfile2(self,path):
        with open(path) as f:
            lines = f.readlines()
            grs=[]
            for i in range(len(lines)):
                line=lines[i].split(" ")
                newline=[]
                if i>0:
                    for j in range(len(line)):
                        newline.append(round(float(line[j]),4))
                    grs.append(newline)
                else:
                    grs.append(line)
            self.storm_file_headers=grs[0]
            return grs[1:]

    def readstormfile(self,path):
        with open(path) as f:
            lines = f.readlines()
            grs=[]
            for line in lines:
                grs.append(line.split(" "))
            self.storm_file_headers=grs[0]
            return grs[1:]

    def checkGRSFile(self,path):
        try:
            self.storm_list = self.readstormfile(path)
        except:
            return False
        if self.storm_file_headers!=['Storm_ID', 'Storm_StartingTimestep', 'Storm_Duration', 'Storm_Volume', 'Storm_PeakIntensity', 'Storm_TotalArea', 'Return_Period_Duration', 'Return_Period_Volume', 'Return_Period_Peak', 'Return_Period_Area\n']:
            return False
        return True


    def grs_browse_clicked(self):
        current_path = self.grs_edit_path.text()
        self.grs_path, _ = QFileDialog.getOpenFileName(self.iface.mainWindow(), 'Generated Rainfall Statistics', current_path,  "Text & CSV files (*.txt *.csv);;All files (*)")
        if self.grs_path != '':
            if self.checkGRSFile(self.grs_path):
                self.grs_edit_path.setText(self.grs_path)
                self.on_grs_browse_given()
            else:
                msgBox = QMessageBox()
                msgBox.setText("<center> The data file used seems not to fit with what is expected.<br><br>Do you want to force the plugin to use this file? (Not Recommended).</center> ")
                msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel);
                msgBox.setDefaultButton(QMessageBox.Cancel);
                returnValue = msgBox.exec()
                if returnValue == QMessageBox.Yes:
                    self.grs_edit_path.setText(self.grs_path)
                    self.on_grs_browse_given()

    def readCSVData(self,path):
        with open(path) as f:
            lines = f.readlines()
            grc=[]
            for line in lines:
                grc.append(line.split(" ")[:-1])
        return grc

    def checkGRCFile(self,path):
        try:
            self.csv_list = self.readCSVData(path)
        except:
            return False
        if self.csv_list[0][0] != "Timestep/CellID":
            return False
        return True

    def grc_browse_clicked(self):
        current_path = self.grc_edit_path.text()
        self.grc_path, _ = QFileDialog.getOpenFileName(self.iface.mainWindow(), 'Generated Rainfall Statistics', current_path,  "Text & CSV files (*.txt *.csv);;All files (*)")
        if self.grc_path != '':
            if self.checkGRCFile(self.grc_path):
                self.grc_edit_path.setText(self.grc_path)
            else:
                msgBox = QMessageBox()
                msgBox.setText("<center> The data file used seems not to fit with what is expected.<br><br>Do you want to force the plugin to use this file? (Not Recommended).</center> ")
                msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel);
                msgBox.setDefaultButton(QMessageBox.Cancel);
                returnValue = msgBox.exec()
                if returnValue == QMessageBox.Yes:
                    self.grc_edit_path.setText(self.grc_path)

    def output_browse_clicked(self):
        current_path = self.output_edit_path.text()
        self.output_path, _ = QFileDialog.getSaveFileName(self.iface.mainWindow(), 'Output File Path', current_path,  "Text file (*.txt);;CSV file (*.csv);;All files (*)")
        if self.output_path != '':
            self.output_edit_path.setText(self.output_path)

    def grs_text_edited(self,new_path):
        self.grs_path=new_path
        self.updateButtonBox()

    def grc_text_edited(self,newpath):
        self.grc_path=newpath
        self.updateButtonBox()

    def output_text_edited(self,newpath):
        self.output_path=newpath
        self.updateButtonBox()

    def updateButtonBox(self):
        if self.grs_edit_path.text() != '' and self.grc_edit_path.text()  != '' and self.output_edit_path.text() != '' and self.results_display_currentItem is not None:
            if not self.results_display.isRowHidden(self.results_display_currentItemIndex) and self.results_display_currentItemIndex!=-1:
                self.button_box_ok.setEnabled(True)
            else:
                self.button_box_ok.setEnabled(False)
        else:
            self.button_box_ok.setEnabled(False)

    def Help(self):
        #Please Change me soon
        webbrowser.open("https://promaides.myjetbrains.com/youtrack/articles/PMDP-A-52/Hello-World")

class SignalClass(QObject):
    plugin_loading_state_emittor = pyqtSignal()
    plugin_finished_loading_state_emittor = pyqtSignal()
    button_box_ok_emittor = pyqtSignal()
    button_box_cancel_emittor = pyqtSignal()


'''
class SortModel (QtCore.QSortFilterProxyModel): #Custom Proxy Model
    def __init__(self, _type, parent=None):
        super(SortModel,self).__init__(parent)
        self._type = _type



class TableModel(QtCore.QAbstractTableModel):
    def __init__(self, data=None, header=None, parent=None):
        super(TableModel, self).__init__(parent)
        self._data = [] if data is None else data
        self._headers = header

    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(self._data[0]) if self.rowCount() else 0

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.DisplayRole:
            row = index.row()
            if 0 <= row < self.rowCount():
                column = index.column()
                if 0 <= column < self.columnCount():
                    return self._data[row][column]
                    
    def headerData(self, section, orientation, role):
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                return self._headers[section]
            else:
                # set row names: color 0, color 1, ...
                return "%s" % str(section+1)

    def insertRows(self, position, rows, parent=QtCore.QModelIndex()):
        self.beginInsertRows(parent, position, position + rows - 1)
        row = ["a", "b", "c", "d"]
        for i in range(rows):
            self._data.insert(position, row)
        self.endInsertRows()
        return True
'''

class StormExport(object):

    def __init__(self, iface):
        self.iface = iface
        self.dialog = None
        self.cancel = False
        self.act = QAction('Storm Export', iface.mainWindow())
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
        self.dialog = PluginDialog(self.iface, self.iface.mainWindow())
        self.dialog.button_box_ok_emittor.connect(self.execTool)
        self.dialog.button_box_cancel_emittor.connect(self.quitDialog)
        self.dialog.show()

    def scheduleAbort(self):
        self.cancel = True

    def quitDialog(self):
        self.dialog = None
        self.act.setEnabled(True)
        self.cancel = False

    def execTool(self):
        quit=False
        try:
            sss_choice = self.dialog.results_display.item(self.dialog.results_display_currentItem.row(),1).text()
        except:
            QMessageBox.information(None, "Message:", "<center>Something went wrong while exporting. [ER:1]</center>")
            return
        try:
            grc= self.dialog.csv_list
        except:
            QMessageBox.information(None, "Message:", "<center>Your CSV seems to have a wrong format. Can you check the path or content of the file?</center>")
            return
        try:
            grs= self.dialog.storm_list
        except:
            QMessageBox.information(None, "Message:", "<center>Your storms list file seems to have a wrong format. Can you check the path or content of the file?</center>")
            return
        try:
            output_path = self.dialog.output_path
            Found=False
            grc_index=0
            for i in range(len(grc)):
                if grc[i][0]==sss_choice:
                    grc_index=i
                    Found=True
                    break
        except:
            QMessageBox.information(None, "Message:", "<center>Something went wrong while exporting.[ER:2]</center>")
            return
        if Found:
            try:
                with open(output_path,"w+") as f:
                    x = """
# comment
# !BEGIN
# number begining from 0 ++ number of points
# hour [h] discharge [m³/s]
# !END


"""
                    writeString=x[1:]
                    grs_index=0
                    for j in range(len(grs)):
                        if grs[j][1]==sss_choice:
                            grs_index=j
                            NumDataPointsForEachCell=grs[grs_index][2]
                            break
                    for i in range(1,len(grc[grc_index])):
                        writeString=writeString+"!BEGIN   #raingaugename\n"
                        writeString=writeString+str(i-1) + " " + NumDataPointsForEachCell + "             area #Length [m²/s], Area [m/s], waterlevel [m], point [m³/s]"

                        for k in range(int(NumDataPointsForEachCell)):
                            writeString=writeString+ "\n" + str(k) + " " + str(float(grc[grc_index+k][i])/3600000) + "   #"+ grc[grc_index+k][i] +" mm/h"

                        writeString=writeString+"\n!END\n\n"


                    f.writelines(writeString)
                    self.iface.messageBar().pushSuccess('Storm Export','File Exported Successfully!')
                    quit=True
            except:
                QMessageBox.information(None, "Message:", "<center>Something went wrong while exporting.[ER:3]</center>")
        else:
            QMessageBox.information(None, "Message:", "<center>The choosen storm could not be found in the CSV file. Could you check your CSV file has the storm data choosen?</center>")
        if quit:
            self.dialog.close()
            self.quitDialog()