from __future__ import unicode_literals
from __future__ import absolute_import

# system modules
import time
import webbrowser
import os
from math import ceil
from math import floor

# QGIS modules 
from qgis.core import *
from qgis.PyQt.QtCore import * #change
from qgis.PyQt.QtCore import Qt, QAbstractTableModel, QModelIndex, pyqtSignal, QObject, QSettings
from qgis.PyQt.QtWidgets import *
from qgis.PyQt.QtGui import QColor
from qgis.PyQt import uic
from PyQt5 import QtWidgets
from PyQt5 import QtCore

#Promaides modules
from .environment import get_ui_path
from .time_viewer import TimeViewer

#Connection to the UI-file (GUI); Edit the ui-file  via QTCreator
UI_PATH = get_ui_path('ui_storm_visualize.ui')

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
        self.cellNumberMatching=False
        self.filter_1_valueStyle = self.filter_1_value.styleSheet()
        self.extentGenerationAreaLayer_Frame_valueStyle = self.extentGenerationAreaLayer_Frame.styleSheet()
        self.results_display_currentItem = None
        self.holdedSelectedHiddenItems=[]
        self.selectedItemsBeforeFilter=[]
        self.SelectedRows=[]
        self.GenerationAreaLayer.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.GenerationAreaLayer.setLayer(None)
        self.extentGenerationAreaLayer.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.extentGenerationAreaLayer.setLayer(None)

        #Fix Focus and Size Policy
        sizePolicyWidgets=[self.button_clear, self.clear_table_button, self.loading_icon, self.filter_stats]
        focusWidgets=[self.grs_browse, self.grc_browse, self.button_clear, self.button_filter, self.button_filter_further, self.button_box_ok, self.button_box_cancel, self.clear_table_button, self.button_clear_selectedStorms, self.HelpButton]
        for widget in sizePolicyWidgets: self.fixSizePolicy(widget)
        for widget in sizePolicyWidgets: widget.setVisible(False)
        for widget in focusWidgets: widget.setAutoDefault(False)

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
        self.grs_edit_path.textChanged.connect(self.grs_text_edited)
        self.grc_edit_path.textChanged.connect(self.grc_text_edited)

        #Allow user to open file dialog using the Enter Event inside the edit text
        self.grs_edit_path.returnPressed.connect(self.grs_browse_clicked)
        self.grc_edit_path.returnPressed.connect(self.grc_browse_clicked)
        self.filter_1_value.returnPressed.connect(self.button_filter_further_clicked)

        #Connect the buttons to their relative actions
        self.button_filter.clicked.connect(self.button_filter_clicked)
        self.button_filter_further.clicked.connect(self.button_filter_further_clicked)
        self.button_clear.clicked.connect(self.button_clear_filter_clicked)
        self.clear_table_button.clicked.connect(self.clear_table_button_clicked)
        self.results_display.currentItemChanged.connect(self.results_display_currentItemChanged)
        self.results_display.itemSelectionChanged.connect(self.results_display_itemSelectionChanged)
        self.cb_selectedStorms.checkedItemsChanged.connect(self.cb_selectedStorms_checkedItemsChanged)
        self.button_clear_selectedStorms.clicked.connect(self.button_clear_selectedStorms_clicked)
        self.ProcessAreaButton.clicked.connect(self.CheckGenerationArea)
        self.GenerationAreaLayer.layerChanged.connect(self.GenerationAreaLayer_layerChanged)

        self.dxBox.setValue(5000)
        self.dyBox.setValue(5000)
        #Set Table of storms:
        self.reset_storm_table()

    def button_clear_selectedStorms_clicked(self):
        self.cb_selectedStorms.clear()
        self.holdedSelectedHiddenItems=[]
        self.selectedItemsBeforeFilter=[]
        self.results_display.clearSelection()
        self.updateButtonBox()

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

    def populateSelectedRows(self,SelectedRows):
        self.cb_selectedStorms.clear()
        for row in SelectedRows:
            self.cb_selectedStorms.addItemWithCheckState(self.results_display.item(row,0).text(), 2,str(row))
            self.cb_selectedStorms.setCheckedItems([self.results_display.item(row,0).text()])

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

    #Using signals with okay so that the dialog doesn't close in case of error as well as allowing for using custom ok and cancel button instead of default ones
    def button_box_ok_clicked(self):
        self.importRainData()
        self.CreateTimeViewerLayer()
        self.time = TimeViewer(self.iface)
        self.time.execDialog()
        self.time.dialog.InputLayerBox.setLayer(self.tvl)
        self.time.dialog.AddLayer()
        self.time.dialog.FieldIDBox.setField("date_time")
        #self.time.dialog.LoopBox.setCheckState(2)
        self.time.dialog.WriteProcessing()
        
        self.signalclass.button_box_ok_emittor.emit()
        
    def button_box_cancel_clicked(self):
        self.signalclass.button_box_cancel_emittor.emit()
        self.close()

    #Monitoring if user choose a storm. If no storm choosen then OK should be disabled
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
        
    def tr(self, className,message):
        return QCoreApplication.translate(className, message)

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
        self.time_to_display= "\n\n" + self.tr("PluginDialog","Displayed in:") + "\n" + str(round(time.time()-start,3)) + "ms"
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
                self.on_grs_browse_given()
            else:
                msgBox = QMessageBox()
                msgBox.setText(self.tr("PluginDialog","<center> The data file used seems not to fit with what is expected.<br><br>Do you want to force the plugin to use this file? (Not Recommended).</center> "))
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

    #Function to check file is valid
    def checkGRCFile(self,path):
        try:
            self.csv_list = self.readCSVData(path)
        except:
            return False
        if self.csv_list[0][0] != "Timestep/CellID":
            return False
        self.no_cells_csv_text = int(self.csv_list[0][-1])+1
        return True

    def grc_browse_clicked(self):
        current_path = self.grc_edit_path.text()
        self.grc_path, _ = QFileDialog.getOpenFileName(self.iface.mainWindow(), self.tr("PluginDialog",'Generated Rainfall Statistics'), current_path,  "Text & CSV files (*.txt *.csv);;All files (*)")
        if self.grc_path != '':
            if self.checkGRCFile(self.grc_path):
                self.grc_edit_path.setText(self.grc_path)
                self.no_cells_csv.setText(str(self.no_cells_csv_text))
                if self.GenerationAreaLayer.currentLayer()!= None:
                    self.GenerationAreaLayer_layerChanged()
            else:
                msgBox = QMessageBox()
                msgBox.setText(self.tr("PluginDialog","<center> The data file used seems not to fit with what is expected.<br><br>Do you want to force the plugin to use this file? (Not Recommended).</center> "))
                msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel);
                msgBox.setDefaultButton(QMessageBox.Cancel);
                returnValue = msgBox.exec()
                if returnValue == QMessageBox.Yes:
                    self.grc_edit_path.setText(self.grc_path)


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
        if self.grs_edit_path.text() != '' and self.grc_edit_path.text()  != '' and len(self.SelectedRows)!=0 and self.cellNumberMatching==True:
            self.button_box_ok.setEnabled(True)
        else:
            self.button_box_ok.setEnabled(False)

    def Help(self):
        webbrowser.open("https://promaides.myjetbrains.com/youtrack/articles/PMDP-A-85/Storm-Export")

    def UpdateExponentFactorField(self):
        if self.SpatialInterpolationMethodBox.currentText() == "Inversed Distance Weighting":
            self.ExponentFactorBox.setEnabled(True)
            self.label_32.setEnabled(True)
        else:
            self.ExponentFactorBox.setEnabled(False)
            self.label_32.setEnabled(False)

    def CheckGenerationArea(self):
        if type(self.extentGenerationAreaLayer.currentLayer()) == type(None):
            self.extentGenerationAreaLayer_Frame.setStyleSheet("QFrame {border: 1px solid red;}")
            return
        else:
            self.extentGenerationAreaLayer_Frame.setStyleSheet(self.extentGenerationAreaLayer_Frame_valueStyle)
            QTimer.singleShot(50, self.CreateGenerationArea)

    def CreateGenerationArea(self):
        self.layer2 = QgsVectorLayer("Polygon", 'Generation_Area', 'memory')
        layer = self.extentGenerationAreaLayer.currentLayer()
        ex = layer.extent()
        xmax = ex.xMaximum()
        ymax = ex.yMaximum()
        xmin = ex.xMinimum()
        ymin = ex.yMinimum()
        prov = self.layer2.dataProvider()

        fields = QgsFields()
        fields.append(QgsField('ID', QVariant.Int, '', 10, 0))
        fields.append(QgsField('XMIN', QVariant.Double, '', 24, 6))
        fields.append(QgsField('XMAX', QVariant.Double, '', 24, 6))
        fields.append(QgsField('YMIN', QVariant.Double, '', 24, 6))
        fields.append(QgsField('YMAX', QVariant.Double, '', 24, 6))
        prov.addAttributes(fields)
        self.layer2.updateExtents()
        self.layer2.updateFields()

        if self.dxBox.value() <= 0 or self.dyBox.value() <= 0:
            self.iface.messageBar().pushCritical(
                'Rain Generator',
                'Invalid Values for dx or dy! Values are larger than extent of area'
            )
            return
        else:
            hspacing = self.dxBox.value()
            vspacing = self.dyBox.value()

        self.nx = ceil((xmax - xmin) / hspacing)
        self.ny = ceil((ymax - ymin) / vspacing)

        id = 0
        y = ymax
        while y >= ymin:
            x = xmin
            while x <= xmax:
                point1 = QgsPointXY(x, y)
                point2 = QgsPointXY(x + hspacing, y)
                point3 = QgsPointXY(x + hspacing, y - vspacing)
                point4 = QgsPointXY(x, y - vspacing)
                vertices = [point1, point2, point3, point4]
                inAttr = [id, x, x + hspacing, y - vspacing, y]
                feat = QgsFeature()
                feat.setGeometry(QgsGeometry().fromPolygonXY([vertices]))
                feat.setAttributes(inAttr)
                prov.addFeatures([feat])
                x = x + hspacing
                id += 1
            y = y - vspacing

        self.layer2.setCrs(QgsCoordinateReferenceSystem(self.iface.mapCanvas().mapSettings().destinationCrs().authid()))
        self.layer2.updateExtents()
        QgsProject.instance().addMapLayer(self.layer2)
        self.addNewlyBakedGenerationArea()
        #self.ProcessButton.setEnabled(True)

    def addNewlyBakedGenerationArea(self):
        self.GenerationAreaLayer.setLayer(self.layer2)
        self.bake_groupbox.setChecked(False)
        self.bake_groupbox.setCollapsed(True)

    def GenerationAreaLayer_layerChanged(self):
        SelectedGenerationLayer = self.GenerationAreaLayer.currentLayer()
        self.featurecount = str(SelectedGenerationLayer.featureCount())
        if self.no_cells_csv.text().isnumeric():
            if(int(self.featurecount) != int(self.no_cells_csv.text())):
                self.no_cells_area.setText(self.featurecount + " (Mismatch)")
                self.no_cells_area.setStyleSheet("color: red;")
                self.cellNumberMatching=False
                self.updateButtonBox()
            else:
                self.no_cells_area.setText(self.featurecount)
                self.no_cells_area.setStyleSheet("")
                self.cellNumberMatching=True
                self.updateButtonBox()
        else:
            self.no_cells_area.setText(self.featurecount)
            self.no_cells_area.setStyleSheet("")
            self.cellNumberMatching=True
            self.updateButtonBox()

    def importRainData(self):
        self.rain_data=[]
        SelectedRows = self.SelectedRows
        grc= self.csv_list
        grs= self.storm_list

        SelectedTimeSteps=[]
        SelectedIds=[]
        for row in SelectedRows:
            SelectedIds.append(self.results_display.item(row,0).text())
            SelectedTimeSteps.append(self.results_display.item(row,1).text())

        for l in range(len(SelectedTimeSteps)):
            sss_choice=str(SelectedTimeSteps[l])
            self.rain_data.append([sss_choice,[]])
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
                    grs_index=0
                    for j in range(len(grs)):
                        if grs[j][1]==sss_choice:
                            grs_index=j
                            NumDataPointsForEachCell=grs[grs_index][2]
                            break
                    for k in range(int(NumDataPointsForEachCell)):
                        for i in range(1,len(grc[grc_index])):
                            rainfall=float(grc[grc_index+k][i])
                            self.rain_data[l][1].append(rainfall)
                        quit=True
                except Exception as e:
                    QMessageBox.information(None, "Message:", self.tr("StormExport","<center>Something went wrong while exporting.[ER:3]<br>") + str(e) +"</center>")
            else:
                QMessageBox.information(None, "Message:", self.tr("StormExport","<center>The choosen storm could not be found in the CSV file. Could you check your CSV file has the storm data choosen?</center>"))

    def CreateTimeViewerLayer(self):
        for storm in self.rain_data:
            selected_g = self.GenerationAreaLayer.currentLayer()
            selected_g_feats = selected_g.getFeatures()
            geometrylist=[]
            for feat in selected_g_feats:
                geometrylist.append(feat.geometry())

            self.tvl = QgsVectorLayer("Polygon", 'Time_Viewer_Layer_Strom='+str(storm[0]), 'memory')
            tvl_dataProvider = self.tvl.dataProvider()
            #tvl_geoFeatures = [feat for feat in self.layer2.getFeatures()]
            fields = QgsFields()
            fields.append(QgsField('ID', QVariant.Int, '', 10, 0))
            fields.append(QgsField("Boundary Value", QVariant.Double))
            fields.append(QgsField("date_time", QVariant.Double))
            tvl_dataProvider.addAttributes(fields)

            feat_to_add=[]
            total_cells=int(self.featurecount)
            for i in range(len(storm[1])):
                feat = QgsFeature()
                feat.setAttributes([i%total_cells+1,storm[1][i],int(storm[0])+floor(i/total_cells)])
                feat.setGeometry(geometrylist[i%total_cells])
                feat_to_add.append(feat)
            tvl_dataProvider.addFeatures(feat_to_add)

            self.tvl.updateFields()
            self.tvl.setCrs(QgsCoordinateReferenceSystem(self.iface.mapCanvas().mapSettings().destinationCrs().authid()))

            renderer = QgsGraduatedSymbolRenderer()
            classification_method = QgsClassificationQuantile()
            format = QgsRendererRangeLabelFormat()
            format.setFormat("%1 - %2")
            format.setPrecision(2)
            format.setTrimTrailingZeroes(True)
            default_style = QgsStyle().defaultStyle()
            color_ramp = default_style.colorRamp('Greys')
            color_ramp.setColor1(QColor(230, 249, 250))
            color_ramp.setColor2(QColor(44, 131, 245))
            renderer.setClassAttribute("Boundary Value")
            renderer.setClassificationMethod(classification_method)
            renderer.setLabelFormat(format)
            renderer.updateClasses(self.tvl, 5)
            renderer.updateColorRamp(color_ramp)
            self.tvl.setRenderer(renderer)
            self.tvl.triggerRepaint()

            self.tvl.updateExtents()
            QgsProject.instance().addMapLayer(self.tvl)

class SignalClass(QObject):
    plugin_loading_state_emittor = pyqtSignal()
    plugin_finished_loading_state_emittor = pyqtSignal()
    button_box_ok_emittor = pyqtSignal()
    button_box_cancel_emittor = pyqtSignal()

class StormVisualize(object):

    def __init__(self, iface):
        self.iface = iface
        self.dialog = None
        self.cancel = False
        self.act = QAction('Storm Visualize', iface.mainWindow())
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
        self.dialog.close()
        #self.dialog = None
        self.act.setEnabled(True)
        self.cancel = False

    def execTool(self):
        print("exit")
        #Create a TimeViewLayer
        #Open the TimeView
        #Add layer to TimeView

        #self.quitDialog()

