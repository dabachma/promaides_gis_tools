import typing

from PyQt5 import QtCore
from PyQt5.QtWidgets import * 
from PyQt5.QtCore import Qt

import sys


BCNAME = ["Air Temperatur", "Solar Radiation", "Humidity", "Windspeed", "Shadow factor", "Inlet Temperatur"]

class BCRiverDialog(QDialog):
    def __init__(self, parent=None, riverName=str()) -> None:
        super(BCRiverDialog, self).__init__(parent)
        self.setWindowTitle("Custom Boundary Condition")
        self.adjustSize()
        self.resize(223,452)
        self.verticalLayout = QVBoxLayout(self)
        self.setLayout(self.verticalLayout)     

        label = QLabel(f"River Profile {riverName}")
        self.verticalLayout.addWidget(label)

        self.table = self.__setUpTable()
        # self.verticalLayout.addWidget(self.table)

        for name in BCNAME:
            groupBox = self.__groupBox(name)
            self.verticalLayout.addWidget(groupBox)
        
        # self.btn = QPushButton("Get Values", clicked=self.getValues)
        # self.verticalLayout.addWidget(self.btn)

    def closeEvent(self, a0) -> None:
        parent = self.parent()
        if parent:
            children = parent.children()
            for child in children:
                if type(child) == QCheckBox and self.getValues():
                    parent.data = self.getValues()
                    child.setChecked(True)
        return super().closeEvent(a0)

    def __setUpTable(self) -> QTableWidget:
        table = QTableWidget(len(BCNAME), 3)

        table.setHorizontalHeaderLabels(["Boundary Condition","Stationary", "ID"])

        for row in range(len(BCNAME)):
            for col in range(3):
                if col == 0:
                    item = QTableWidgetItem(BCNAME[row])
                    item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                    item.setCheckState(Qt.CheckState.Unchecked)
                    table.setItem(row, 0, item)
                else:
                    table.setItem(row, col, QTableWidgetItem(f"Item {row}-{col}"))
        return table

    def __groupBox(self, name=str()):
        box = QGroupBox()
        box.setCheckable(True)
        box.setChecked(False)
        box.setTitle(name)

        layout = QHBoxLayout(box)

        check = QCheckBox()
        check.setText("true")
        layout.addWidget(check)

        spin = QSpinBox()
        spin.setMinimum(0)
        layout.addWidget(spin)
        return box

    def getValues(self):
        data = dict()
        checkedBoxen = [child for child in self.children() if type(child) == QGroupBox]
        for box in checkedBoxen:
            if box.isChecked():
                name = box.title()
                data[name] = self.__extractBoxValues(box)
        # print(data)
        return data                
    
    def __extractBoxValues(self, box: QGroupBox):
        checked = [child for child in box.children() if type(child) == QCheckBox][0]
        id = [child for child in box.children() if type(child) == QSpinBox][0]
        return {"stat": str(checked.isChecked()).lower(),
                "ID": id.value()}



def setup():
        name = "Selke_1"
        app = QApplication(sys.argv)
        # Create and show the form
        setupDialog = BCRiverDialog(parent=None, riverName=name)
        setupDialog.setModal(False)
        setupDialog.show()
        # Run the main Qt loop
        sys.exit(app.exec())
        


if __name__ == "__main__":
    setup()