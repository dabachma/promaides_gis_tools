from __future__ import unicode_literals
from __future__ import absolute_import
import typing


# QGIS modules
from qgis.core import *
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import *
from qgis.PyQt import uic

# promaides modules
from .environment import get_ui_path

# system modules
import webbrowser
import sys
#general
from datetime import datetime
from .version import *

from .setup_dialog import SetupDialog

UI_PATH = get_ui_path('ui_river_temp_export.ui')

# This plugin exports the SCs point element file for the DAM-SC-module of ProMaIdes from a point shape file;
class PluginDialog(QDialog):

    def __init__(self, iface, parent=None, flags=Qt.WindowFlags()):
        QDialog.__init__(self, parent, flags)
        uic.loadUi(UI_PATH, self)
        self.iface = iface
        self.riverProfile = []
        self.browseOutputButton: QPushButton
        self.HelpButton: QPushButton
        self.browseInputButton: QPushButton
        self.loadButton: QPushButton
        

        self.browseOutputButton.clicked.connect(self.onBrowseOutputButtonClicked)        
        self.HelpButton.clicked.connect(self.Help)
        self.browseInputButton.clicked.connect(self.onBrowseInputButtonClicked)
        self.loadButton.setEnabled(False)
        self.loadButton.clicked.connect(self.loadRiverFile)
        self.updateButtonBox()

        self.pushButton.clicked.connect(self.setupRivers)

    def setupRivers(self):
        """EXTREM WICHTIG
        ERMÖGLICHT ERNEUTES ÖFFNEN DES DIALOGS OHNE INFORMATIONSVERLUST""" 
        exist = False
        for child in self.children():
            if type(child) == type(SetupDialog()):
                exist = True
                self.setupDialog = child
                
               
        if not exist:
            self.setupDialog = SetupDialog(parent=self, riverProfiles=self.riverProfile)
        self.setupDialog.setModal(False)
        self.setupDialog.show()



    def onBrowseOutputButtonClicked(self):
        self.filenameEdit: QLineEdit
        current_filename = self.filenameEdit.text()
        new_filename, __ = QFileDialog.getSaveFileName(self.iface.mainWindow(), 'SC Points Export', current_filename, "*.txt *.TXT")
        if new_filename != '':
            self.filenameEdit.setText(new_filename)
            self.filenameEdit.editingFinished.emit()
    
    def onBrowseInputButtonClicked(self):
        self.riverfileEdit: QLineEdit
        current_filename = self.riverfileEdit.text()
        new_filename, __ = QFileDialog.getOpenFileName(self.iface.mainWindow(), 'SC Points Export', current_filename)
        if new_filename != '':
            self.riverfileEdit.setText(new_filename)
            self.riverfileEdit.editingFinished.emit()
            self.riverProfile = []
            self.loadButton.setEnabled(True)
    
    def loadRiverFile(self):
        path = self.riverfileEdit.text()
        self.boundaryFlag = []
        with open(path, "r") as file:
            for line in file:
                if "ZONE" in line and not "#" in line:
                    self.boundaryFlag.append(False)
                    begin = line.index('"') + 1
                    end = len(line) - (line[::-1].index('"') + 1)
                    self.riverProfile.append(line[begin:end])
                if 'AUXDATA BoundaryPointCondition="true"' in line and not "#" in line:
                    self.boundaryFlag[-1] = True

        self.updateButtonBox()

            
    def Help(self):
        webbrowser.open("https://promaides.myjetbrains.com/youtrack/articles/LFDH-A-4/1d-River-Export")

    
    def updateButtonBox(self):
        if self.riverProfile:
            self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(True)
        else:
            self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(False)

class RiverTempExport:

    def __init__(self, iface):
        self.iface = iface
        self.dialog = None
        self.cancel = False
        self.act = QAction('1D River Temp Export', iface.mainWindow())
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

        self.dialog.accepted.connect(self.execTool)
        self.dialog.rejected.connect(self.quitDialog)
        self.dialog.setModal(False)
        self.act.setEnabled(False)

        self.dialog.show()

    def scheduleAbort(self):
        self.cancel = True

    def quitDialog(self):
        self.act.setEnabled(True)
        self.cancel = False
        self.dialog.close()
        try:
            self.dialog.setupDialog.close()
        except:
            pass
        
    def verificationInput(self):      
        raise NotImplementedError
    
    def execTool(self):
        #TODO Verification
        filename = self.dialog.filenameEdit.text()
        
        with open(filename, "w") as tempFile:
            tempFile.write('########################################################################\n')
            tempFile.write(f'# This file was automatically generated by ProMaiDes 1D-River Profile Export'
                                 '-QGIS-Plugin Version {VERSION} \n')
            # date and time output
            now = datetime.now()
            dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
            tempFile.write(f'# Generated at {dt_string} \n')
            tempFile.write('# Comments are marked with #\n')
            tempFile.write('#\n')
            tempFile.write('########################################################################\n\n')
            for id, (river, flag) in enumerate(zip(self.dialog.riverProfile, self.dialog.boundaryFlag)):
                tempFile.write(f'ZONE T="{river}"\n')
                tempFile.write(f'AUXDATA InitCondition {self.dialog.initConditionBox.value()}\t#in [K]\n')

                if not id:
                    tempFile.write(f'WATER_TEMP {str(self.dialog.airCheck.isChecked()).lower()} {self.dialog.airID.value()}\t')
                    tempFile.write('\t#Key for water temperature [K]\n')
                else:
                    tempFile.write(f'AIR_TEMP {str(self.dialog.airCheck.isChecked()).lower()} {self.dialog.airID.value()}\t')
                    tempFile.write('\t\t#Key for air temperature [K]\n')

                tempFile.write(f'SOLAR_RAD {str(self.dialog.solarCheck.isChecked()).lower()} {self.dialog.solarID.value()}\t')
                tempFile.write('\t#Key for solar radiation  [W/m^2]\n')
                tempFile.write(f'HUMID {str(self.dialog.humidCheck.isChecked()).lower()} {self.dialog.humidID.value()}\t')
                tempFile.write('\t#Key for humidity [-] (0..1)\n')
                tempFile.write(f'WIND {str(self.dialog.windCheck.isChecked()).lower()} {self.dialog.windID.value()}\t')
                tempFile.write('\t#Key for wind speed [m/s]\n')
                tempFile.write(f'SHADOW {str(self.dialog.shadowCheck.isChecked()).lower()} {self.dialog.shadowID.value()}\t')
                tempFile.write('\t#Key for shadow factor [-] (0..1)\n')
                if flag:
                    tempFile.write(f'INLET_TEMP {str(self.dialog.inletCheck.isChecked()).lower()} {self.dialog.inletID.value()}\t')
                    tempFile.write('\t#Key for inlet temperature [K]; a point discharge boundary needs to be set in the hydraulic settings (optional)\n')
                tempFile.write('\n')
        
        self.iface.messageBar().pushInfo('1D-River Profile Export', 'Export finished successfully!')
        self.quitDialog()

class XSetupDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super(SetupDialog, self).__init__(parent)
        self.verticalLayout = QVBoxLayout(self)

        self.label = QLabel()
        self.label.setText(f"Hallo")
        self.verticalLayout.addWidget(self.label)
        self.setWindowTitle("Setup Boundary Contitions")

        

        self.buttonBox = QDialogButtonBox()
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)

        self.verticalLayout.addWidget(self.buttonBox)


        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

def setupRivers():
        # self.app = QApplication(sys.argv)
        # Create and show the form
        setupDialog = XSetupDialog()
        setupDialog.setModal(False)
        setupDialog.show()
        # Run the main Qt loop
        
    


if __name__ == "__main__":
    setupRivers()