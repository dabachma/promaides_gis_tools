from __future__ import unicode_literals
from __future__ import absolute_import

# system modules
import time
import webbrowser
import os

# QGIS modules 
from qgis.core import *
from qgis.PyQt.QtCore import * #change
from qgis.PyQt.QtCore import Qt, QAbstractTableModel, QModelIndex, pyqtSignal, QObject, QSettings
from qgis.PyQt.QtWidgets import *
from qgis.PyQt import uic
from PyQt5 import QtWidgets
from PyQt5 import QtCore

#Promaides modules
from .environment import get_ui_path

#Connection to the UI-file (GUI); Edit the ui-file  via QTCreator
UI_PATH = get_ui_path('ui_storm_export.ui')

class PluginDialog(QDialog):

    #set-up of the dialog
    def __init__(self, iface, parent=None, flags=Qt.WindowFlags()):
        QDialog.__init__(self, parent, flags)
        uic.loadUi(UI_PATH, self)
        self.iface = iface
        self.HelpButton.clicked.connect(self.Help)

        #Initialize:
        #As a part of the initialization phase of variables, the styling of the edit box for input of filter value is stored to later have it as default if value entered is numerical
        #Current selected storm is initialized as well as units for the filter
        self.filter_1_valueStyle = self.filter_1_value.styleSheet()
        self.results_display_currentItem = None
        self.holdedSelectedHiddenItems=[]
        self.selectedItemsBeforeFilter=[]
        self.SelectedRows=[]
        self.filter_1_unit.setCurrentText("mm/hr")

        #Setting rectangle pulse option to the users preference
        self.qsettings = QSettings('StormExport', 'StormExportSettings')
        if self.qsettings.contains("recPulse_state"):
            self.recPulse_state = self.qsettings.value("recPulse_state")
        else:
            self.recPulse_state = 0
        self.cb_recPulse.setCheckState(self.recPulse_state)

        #Set Size Policy as setRetainSizeWhenHidden(True) in allow hiding elements without changing the layout
        self.fixSizePolicy(self.button_clear)
        self.fixSizePolicy(self.clear_table_button)
        self.fixSizePolicy(self.loading_icon)
        self.fixSizePolicy(self.filter_stats)
        self.fixSizePolicy(self.cb_recPulse)

        #Set storm data and clear buttons to invisible
        self.button_clear.setVisible(False)
        self.clear_table_button.setVisible(False)
        self.loading_icon.setVisible(False)
        self.filter_stats.setVisible(False)

        #Prevent the below elements from taking tab or normal focus while edit texts are selected otherwise pressing enter while in 
        self.grs_browse.setAutoDefault(False)
        self.grc_browse.setAutoDefault(False)
        self.output_browse.setAutoDefault(False)
        self.button_clear.setAutoDefault(False)
        self.button_filter.setAutoDefault(False)
        self.button_filter_further.setAutoDefault(False)
        self.button_box_ok.setAutoDefault(False)
        self.button_box_cancel.setAutoDefault(False)
        self.clear_table_button.setAutoDefault(False)
        self.button_clear_selectedStorms.setAutoDefault(False)
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
        self.output_edit_path.textChanged.connect(self.output_text_edited)

        #Allow user to open file dialog using the Enter Event inside the edit text
        self.grs_edit_path.returnPressed.connect(self.grs_browse_clicked)
        self.grc_edit_path.returnPressed.connect(self.grc_browse_clicked)
        self.output_edit_path.returnPressed.connect(self.output_browse_clicked)
        self.filter_1_value.returnPressed.connect(self.button_filter_further_clicked)

        #Connect the buttons to their relative actions
        self.button_filter.clicked.connect(self.button_filter_clicked)
        self.button_filter_further.clicked.connect(self.button_filter_further_clicked)
        self.button_clear.clicked.connect(self.button_clear_filter_clicked)
        self.clear_table_button.clicked.connect(self.clear_table_button_clicked)
        self.results_display.currentItemChanged.connect(self.results_display_currentItemChanged)
        self.results_display.itemSelectionChanged.connect(self.results_display_itemSelectionChanged)
        self.cb_recPulse.stateChanged.connect(self.cb_recPulse_stateChanged)
        self.cb_selectedStorms.checkedItemsChanged.connect(self.cb_selectedStorms_checkedItemsChanged)
        self.button_clear_selectedStorms.clicked.connect(self.button_clear_selectedStorms_clicked)

        #Set Table of storms:
        self.reset_storm_table()

    #Action for clearing all the currently selected storms
    def button_clear_selectedStorms_clicked(self):
        self.cb_selectedStorms.clear()
        self.holdedSelectedHiddenItems=[]
        self.selectedItemsBeforeFilter=[]
        self.results_display.clearSelection()
        self.updateButtonBox()

    #Add/Remove newly un/selected storm to/from list of selected storms 
    def cb_selectedStorms_checkedItemsChanged(self):
        checked = self.cb_selectedStorms.checkedItems()
        checkeddata = self.cb_selectedStorms.checkedItemsData()
        self.results_display.blockSignals(True)
        self.cb_selectedStorms.clear()

        self.results_display.clearSelection()
        for i in range(len(checkeddata)):
            self.results_display.selectRow(int(checkeddata[i]))

        self.results_display.blockSignals(False)
        for x in range(len(checked)):
            self.cb_selectedStorms.addItemWithCheckState(checked[x],2,checkeddata[x])
        self.updateButtonBox()

    #Select storms based on contents of the list of selected storms
    def populateSelectedRows(self,SelectedRows):
        self.cb_selectedStorms.clear()
        for row in SelectedRows:
            self.cb_selectedStorms.addItemWithCheckState(self.results_display.item(row,0).text(), 2,str(row))
            self.cb_selectedStorms.setCheckedItems([self.results_display.item(row,0).text()])

    #Keep selected items selected even when filters are applied
    def holdSelectedHiddenItems(self):
        self.holdedSelectedHiddenItems=[]
        for item in self.selectedItemsBeforeFilter:
            if self.results_display.isRowHidden(item.row()) and item.row() not in self.holdedSelectedHiddenItems:
                self.holdedSelectedHiddenItems.append(item.row())
            else:
                try:
                    self.selectedItemsBeforeFilter.remove(item.row())
                except:
                    continue

    #Manager for selection of another item in the item display
    def results_display_itemSelectionChanged(self):
        self.SelectedRows=[]
        for item in self.results_display.selectedItems():
            if item.row() not in self.SelectedRows:
                if not self.results_display.isRowHidden(item.row()):
                    self.SelectedRows.append(item.row())
        for row in self.holdedSelectedHiddenItems:
                self.SelectedRows.append(row)
        self.SelectedRows.sort()
        self.populateSelectedRows(self.SelectedRows)
        self.updateButtonBox()

    #Allows for saving the preference of rectangular pulse checkbox state
    def cb_recPulse_stateChanged(self,state):
        self.qsettings.setValue("recPulse_state", state)

    #Using signals with okay so that the dialog doesn't close in case of error as well as allowing for using custom OK and Cancel buttons instead of default ones
    def button_box_ok_clicked(self):
        self.signalclass.button_box_ok_emittor.emit()
    def button_box_cancel_clicked(self):
        self.signalclass.button_box_cancel_emittor.emit()
        self.close()

    #Monitoring if user choose a storm. If no storm is chosen then OK should be disabled
    def results_display_currentItemChanged(self,current,pre):
        try:
            self.results_display_currentItem = current
        except:
            self.results_display_currentItem = None
        self.updateButtonBox()
    
    #Function to force widgets on the left side to retain there size when hidden to make left side look consistent 
    def fixSizePolicy(self,widget):
        sizePolicy = widget.sizePolicy()
        sizePolicy.setRetainSizeWhenHidden(True)
        widget.setSizePolicy(sizePolicy)

    #Puts the plugin in a loading state, and resets filter
    def plugin_loading_state(self):
        self.filter_stats.setVisible(False)
        self.loading_icon.setVisible(True)
        self.results_display.setRowCount(0)
        self.results_display.repaint()
        self.filter_stats.repaint()
        self.loading_icon.repaint()
    
    #Set "loading" message off when plugin finished loading
    def plugin_finished_loading_state(self):
        self.filter_stats.setVisible(True)
        self.loading_icon.setVisible(False)

    #Action when the user clears the table
    def clear_table_button_clicked(self):
        self.holdedSelectedHiddenItems=[]
        self.selectedItemsBeforeFilter=[]
        self.results_display.setRowCount(0)
        self.grs_edit_path.setText("")
        self.clear_table_button.setVisible(False)
        self.filter_stats.setVisible(False)
        self.button_clear.setVisible(False)
        self.results_display_currentItem = None

    #Action when user clears the filter
    def button_clear_filter_clicked(self):
        self.results_display.scrollToItem(self.results_display.item(0,0))
        self.holdedSelectedHiddenItems=[]
        for i in range (self.results_display.rowCount()):
            self.results_display.setRowHidden(i,False);
        self.filter_1_value.setText("")
        self.filter_stats.setText("Displaying:\n" + str(self.len_storm_list) +" out of " + str(len(self.storm_list))+self.time_to_display)
        self.button_clear.setVisible(False)

    #Check if user want to filter further or do a new filter
    def button_filter_further_clicked(self):
        self.filterfurther=True
        self.filter_table_results()

    def button_filter_clicked(self):
        self.filterfurther=False
        self.filter_table_results()

    #Converts units of filter input and return the converted value 
    def convertTompers(self ,value):
        if self.filter_1_unit.currentText() == "mm/s":
            return value/1000
        elif self.filter_1_unit.currentText() == "mm/hr":
            return value/1000/3600
        elif self.filter_1_unit.currentText() == "m/s":
            return value
        elif self.filter_1_unit.currentText() == "m/hr":
            return value/3600
        elif self.filter_1_unit.currentText() == "in/s":
            return value*0.0254
        elif self.filter_1_unit.currentText() == "in/hr":
            return value*0.0254/3600
        elif self.filter_1_unit.currentText() == "ft/s":
            return value*0.3048
        elif self.filter_1_unit.currentText() == "ft/hr":
            return value*0.3048/3600

    #Function to filter results
    def filter_table_results(self):
        self.selectedItemsBeforeFilter=self.selectedItemsBeforeFilter + self.results_display.selectedItems()

        #Check if value entered is a number value
        try:
            filter_1_value = float(self.filter_1_value.text())
        except ValueError:
            self.filter_1_value.setStyleSheet("border: 1px solid red;")
            return

        #Set correct styling of edit text
        self.filter_1_value.setStyleSheet(self.filter_1_valueStyle)
        self.button_clear.setVisible(True)
        filter_1_combo_index = self.filter_1_combo.currentIndex()
        comparitor = self.filter_1_operator.currentText()

        # Find the top x values
        if comparitor=="Top":
            column_data=[]
            for i in range (self.results_display.rowCount()):
                if self.filterfurther and self.results_display.isRowHidden(i):
                    continue
                else:
                    column_data.append(float(self.results_display.item(i,filter_1_combo_index).text()))
            column_data.sort()
            self.results_display_top=column_data[-int(filter_1_value)]

        #find the bottom x values
        if comparitor=="Bottom":
            column_data=[]
            for i in range (self.results_display.rowCount()):
                if self.filterfurther and self.results_display.isRowHidden(i):
                    continue
                else:
                    column_data.append(float(self.results_display.item(i,filter_1_combo_index).text()))
            column_data.sort()
            self.results_display_bottom=column_data[int(filter_1_value)-1]

        #Hide results based on filter (This is much faster than creating a table with the new values)
        counter=0
        firstrowset=False
        firstrowNotHidden=0
        for i in range (self.results_display.rowCount()):
            if self.filterfurther and self.results_display.isRowHidden(i):
                continue
            elif self.operatorCompare(float(self.results_display.item(i,filter_1_combo_index).text()),filter_1_value,comparitor):
                counter=counter+1
                self.results_display.setRowHidden(i,False)
                if not firstrowset:
                    firstrowNotHidden=i
                    firstrowset=True
            else:
                self.results_display.setRowHidden(i,True);
        self.filter_stats.setText(self.tr("PluginDialog","Displaying:") + "\n" + str(counter) +self.tr("PluginDialog"," out of ") + str(len(self.storm_list))+self.time_to_display)
        self.holdSelectedHiddenItems()
        self.updateButtonBox()
        self.results_display.scrollToItem(self.results_display.item(firstrowNotHidden,0))
    
    #Translation function to translate strings based on contents
    def tr(self, className,message):
        return QCoreApplication.translate(className, message)

    #Translation of the operators used by filter from text
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

    #Function to populate the filter combo box
    def populate_filter_1_combo(self):
        #Or should we do manual population?
        self.filter_1_combo.clear()
        for header in self.storm_file_headers:
            self.filter_1_combo.addItem(header.replace("_", " ").replace("\n", ""))
        self.signalclass.plugin_finished_loading_state_emittor.emit()

    #Function to reset storm table = 
    def reset_storm_table(self):
        header = self.results_display.horizontalHeader()
        for i in range(10):
            header.setSectionResizeMode(i, QtWidgets.QHeaderView.ResizeToContents)
        
    def on_grs_browse_given(self):
        self.signalclass.plugin_loading_state_emittor.emit()
        self.results_display.setSortingEnabled(False)
        #self.storm_list = self.readstormfile(self.grs_path)
        self.clear_table_button.setVisible(True)

        #Blocking signals makes loading data faster
        self.results_display.blockSignals(True)

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
        self.time_to_display= "\n\n" + self.tr("PluginDialog","Displayed in:") + "\n" + str(round(time.time()-start,3)) + " s"
        self.filter_stats.setText(self.tr("PluginDialog","Displaying:") + "\n" + str(self.len_storm_list) +self.tr("PluginDialog"," out of ") + str(len(self.storm_list))+self.time_to_display)
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

    #Function to check file is valid
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
        self.grs_path, _ = QFileDialog.getOpenFileName(self.iface.mainWindow(), self.tr("PluginDialog",'Generated Rainfall Statistics'), current_path,  "Text & CSV files (*.txt *.csv);;All files (*)")
        if self.grs_path != '':
            if self.checkGRSFile(self.grs_path):
                self.grs_edit_path.setText(self.grs_path)
                self.output_edit_path.setText("/".join(self.grs_path.split("/")[:-1])+"/output/StromID.txt")
                self.on_grs_browse_given()
            else:
                msgBox = QMessageBox()
                msgBox.setText(self.tr("PluginDialog","<center> The data file used seems not to fit with what is expected.<br><br>Do you want to force the plugin to use this file? (Not Recommended).</center> "))
                msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel);
                msgBox.setDefaultButton(QMessageBox.Cancel);
                returnValue = msgBox.exec()
                if returnValue == QMessageBox.Yes:
                    self.grs_edit_path.setText(self.grs_path)
                    self.output_edit_path.setText("/".join(self.grs_path.split("/")[:-1])+"/output/StromID.txt")
                    self.on_grs_browse_given()

    def readCSVData(self,path):
        with open(path) as f:
            lines = f.readlines()
            grc=[]
            for line in lines:
                grc.append(line.split(" ")[:-1])
        return grc

    #Function to check file is valid
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
        self.grc_path, _ = QFileDialog.getOpenFileName(self.iface.mainWindow(), self.tr("PluginDialog",'Generated Rainfall Statistics'), current_path,  "Text & CSV files (*.txt *.csv);;All files (*)")
        if self.grc_path != '':
            if self.checkGRCFile(self.grc_path):
                self.grc_edit_path.setText(self.grc_path)
            else:
                msgBox = QMessageBox()
                msgBox.setText(self.tr("PluginDialog","<center> The data file used seems not to fit with what is expected.<br><br>Do you want to force the plugin to use this file? (Not Recommended).</center> "))
                msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel);
                msgBox.setDefaultButton(QMessageBox.Cancel);
                returnValue = msgBox.exec()
                if returnValue == QMessageBox.Yes:
                    self.grc_edit_path.setText(self.grc_path)

    def output_browse_clicked(self):
        current_path = self.output_edit_path.text()
        self.output_path, _ = QFileDialog.getSaveFileName(self.iface.mainWindow(), self.tr("PluginDialog",'Output File Path'), current_path,  "Text file (*.txt);;CSV file (*.csv);;All files (*)")
        if self.output_path != '':
            self.output_edit_path.setText(self.output_path)
        else:
            self.output_path=current_path

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
        if self.grs_edit_path.text() != '' and self.grc_edit_path.text()  != '' and self.output_edit_path.text() != '' and len(self.SelectedRows)!=0:
            self.button_box_ok.setEnabled(True)
        else:
            self.button_box_ok.setEnabled(False)

    def Help(self):
        webbrowser.open("https://promaides.myjetbrains.com/youtrack/articles/PMDP-A-85/Storm-Export")

class SignalClass(QObject):
    plugin_loading_state_emittor = pyqtSignal()
    plugin_finished_loading_state_emittor = pyqtSignal()
    button_box_ok_emittor = pyqtSignal()
    button_box_cancel_emittor = pyqtSignal()

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

    def tr(self, className,message):
        return QCoreApplication.translate("StormExport", message)

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
            SelectedRows = self.dialog.SelectedRows
        except:
            QMessageBox.information(None, "Message:", self.tr("StormExport","<center>Something went wrong while exporting. [ER:1]</center>"))
            return
        try:
            grc= self.dialog.csv_list
        except:
            QMessageBox.information(None, "Message:", self.tr("StormExport","<center>Your CSV seems to have a wrong format. Can you check the path or content of the file?</center>"))
            return
        try:
            grs= self.dialog.storm_list
        except:
            QMessageBox.information(None, "Message:", self.tr("StormExport","<center>Your storms list file seems to have a wrong format. Can you check the path or content of the file?</center>"))
            return

        output_path_main = self.dialog.output_path
        dotindex=-1
        if "." in output_path_main.split("/")[-1]:
            dotindex = output_path_main.rfind(".")


        SelectedTimeSteps=[]
        SelectedIds=[]
        for row in SelectedRows:
            SelectedIds.append(self.dialog.results_display.item(row,0).text())
            SelectedTimeSteps.append(self.dialog.results_display.item(row,1).text())

        for l in range(len(SelectedTimeSteps)):
            sss_choice=SelectedTimeSteps[l]
            sss_choice=str(sss_choice)
            if dotindex!=-1:
                output_path = output_path_main[:dotindex] + "=" + SelectedIds[l] + output_path_main[dotindex:]
            elif output_path_main[-1] == "/":
                output_path = output_path_main + "StromID=" + SelectedIds[l]  + ".txt"
            else:
                output_path = output_path_main + "/StromID=" + SelectedIds[l] + ".txt"

            try:
                Found=False
                grc_index=0
                for i in range(len(grc)):
                    if grc[i][0]==sss_choice:
                        grc_index=i
                        Found=True
                        break
            except:
                QMessageBox.information(None, "Message:", self.tr("StormExport","<center>Something went wrong while exporting.[ER:2]</center>"))
                return
            if Found:
                try:

                    os.makedirs(os.path.dirname(output_path), exist_ok=True)
                    isRec = self.dialog.cb_recPulse.isChecked()
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
                                rainfall=float(grc[grc_index+k][i])
                                writeString=writeString+ "\n" + str(k) + " " + str(self.dialog.convertTompers(rainfall)) + "   #"+ str(self.dialog.convertTompers(rainfall)*3600000) +" mm/hr"
                                if isRec:
                                    writeString=writeString+ "\n" + str(k) + ".99 " + str(self.dialog.convertTompers(rainfall)) + "   #"+ str(self.dialog.convertTompers(rainfall)*3600000) +" mm/hr"


                            writeString=writeString+"\n!END\n\n"


                        f.writelines(writeString)
                        self.iface.messageBar().pushSuccess(self.tr("StormExport",'Storm Export'),self.tr("StormExport",'File Exported Successfully!'))
                        quit=True
                except Exception as e:
                    QMessageBox.information(None, "Message:", self.tr("StormExport","<center>Something went wrong while exporting.[ER:3]<br>") + str(e) +"</center>")
            else:
                QMessageBox.information(None, "Message:", self.tr("StormExport","<center>The choosen storm could not be found in the CSV file. Could you check your CSV file has the storm data choosen?</center>"))
        if quit:
            self.dialog.close()
            self.quitDialog()