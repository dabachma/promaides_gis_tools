import typing

from PyQt5 import QtCore
from PyQt5.QtWidgets import * 
from PyQt5.QtCore import Qt

import sys

#QGIS import
try:
    from .bc_river_dialog import BCRiverDialog
#Intern import
except:
    from bc_river_dialog import BCRiverDialog

class SetupDialog(QDialog):
    def __init__(self, parent=None, riverProfiles=[]) -> None:
        super(SetupDialog, self).__init__(parent)
        
        self.riverProfiles = riverProfiles
        self.bcDialogList: list[BCRiverDialog] = []

        self.setWindowTitle("Setup Boundary Contitions")
        self.verticalLayout = QVBoxLayout(self)



        self.table = self.__setUpTable()

        self.verticalLayout.addWidget(self.table)

        button = QPushButton("Get Values", clicked=self.getValues)
        self.verticalLayout.addWidget(button)


        # self.buttonBox = QDialogButtonBox()
        # self.buttonBox.setObjectName(u"buttonBox")
        # self.buttonBox.setOrientation(Qt.Orientation.Horizontal)
        # self.buttonBox.setStandardButtons(QDialogButtonBox.StandardButton.Close)
        # self.verticalLayout.addWidget(self.buttonBox)


        # self.buttonBox.rejected.connect(self.closeEvent)

        self.adjustSize()
        self.resize(405,300)
        self.setMinimumWidth(405)
        
    def quiteDialog(self):
        self.__closeChildren()
        self.close()

    def closeEvent(self, a0) -> None:
        self.__closeChildren()
        return super().closeEvent(a0)
    
    def __closeChildren(self):
        for dialog in self.bcDialogList:
            dialog.close()

    def __setUpTable(self) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["River Profile","BC", "", ""])
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

        header.setMinimumSectionSize(50)
        self.__addRow(table)

        return table
    
    def __riverProfileBox(self) -> QComboBox:
        box = QComboBox()
        box.addItems(self.riverProfiles)
        box.setEditable(True)

        completer = QCompleter(self.riverProfiles)
        box.setCompleter(completer)
        box.completer().setCompletionMode(QCompleter.PopupCompletion)
        box.completer().setCaseSensitivity(Qt.CaseInsensitive)

        # btn = QPushButton("Selekt River", clicked=lambda: self.__riverBtn(btn))

        return box

    def __riverBtn(self, btn: QPushButton):
        pass
    
    def __addButton(self) -> QPushButton:
        button = QPushButton("ADD", clicked=self.__addRow)
        return button
    
    def __delButton(self) -> QPushButton:
        button = QPushButton("DEL", clicked=self.__delRow)
        return button
    
    def __addRow(self, table=None):
        if table:
            self.table = table
        count = self.table.rowCount()
        self.table.setRowCount(count + 1)
        self.table.setCellWidget(count, 0, self.__riverProfileBox())
        self.table.setCellWidget(count, 1, self.__bcButton())
        self.table.setCellWidget(count, 2, self.__addButton())
        self.table.setCellWidget(count, 3, self.__delButton())
        self.table.resizeRowsToContents()
        self.table.resizeColumnsToContents()
    
    def __delRow(self):
        selection = self.table.selectedIndexes()
        if len(selection) <= 0:
            row = 0
        else:
            row = selection[0].row()
        if self.table.rowCount() > 1:
            self.table.removeRow(row)
    
    def __bcButton(self) -> QPushButton:
        box = DataGroupBox()
        box.setFlat(True)
        horizontal = QHBoxLayout(box)

        button = QPushButton("Set BC", clicked=lambda: self.__bcDialog(box))
        
        horizontal.addWidget(button)

        check = QCheckBox()
        check.setDisabled(True)
        horizontal.addWidget(check)
        return box

    def __bcDialog(self, widget: QGroupBox):
        pos = int()
        for row in range(self.table.rowCount()):
            item = self.table.cellWidget(row, 1)
            if item == widget:
                pos = row
        

        """EXTREM WICHTIG
        ERMÖGLICHT ERNEUTES ÖFFNEN DES DIALOGS OHNE INFORMATIONSVERLUST""" 
        item: QComboBox = self.table.cellWidget(pos, 0)
        name = item.currentText()
        exist = False
        for child in widget.children():
            if type(child) == type(BCRiverDialog()):
                exist = True
                BCdialog = child
                
               
        if not exist:
            BCdialog = BCRiverDialog(parent=widget, riverName=name)
            self.bcDialogList.append(BCdialog)

        BCdialog.setModal(False)
        BCdialog.show()    
    
    def __checkWidget(self):
        #INERN USE
        print("\n\nCHECK WIDGET")
        for row in range(self.table.rowCount()):
            print(f"REIHE {row+1}")
            widget = self.table.cellWidget(row, 1)
            children = [(type(child) == type(BCRiverDialog()), child) for child in widget.children()]
            for text in children:
                print(text)
    
    def getValues(self):
        data = dict()
        for row in range(self.table.rowCount()):
            nameWidget: QComboBox = self.table.cellWidget(row, 0)
            name = nameWidget.currentText()
            dataWidget: DataGroupBox = self.table.cellWidget(row, 1)
            data[name] = dataWidget.data
        
        for key, valuie in data.items():
            print(key, valuie)
        return data
        
class DataGroupBox(QGroupBox):
    def __init__(self):
        super(DataGroupBox, self).__init__()
        self.data = None


def setupRivers():
        rivers = [f"Selke_{id}" for id in range(10)]
        app = QApplication(sys.argv)
        # Create and show the form
        setupDialog = SetupDialog(parent=None, riverProfiles=rivers)
        setupDialog.setModal(False)
        setupDialog.show()
        # Run the main Qt loop
        sys.exit(app.exec())
        


if __name__ == "__main__":
    setupRivers()