from __future__ import unicode_literals
from __future__ import absolute_import

# system modules
import os

# 3rd party modules
import psycopg2

# QGIS modules
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import QDialog, QFileDialog, QMessageBox, QAction
from qgis.PyQt import uic

# promaides modules
from .environment import get_ui_path

#general
from datetime import datetime
from .version import *

UI_PATH = get_ui_path('ui_database_export.ui')


class PluginDialog(QDialog):

    def __init__(self, iface, parent=None, flags=Qt.WindowFlags()):
        QDialog.__init__(self, parent=parent, flags=flags)
        uic.loadUi(UI_PATH, self)
        self.iface = iface

        self.db_host.editingFinished.connect(self.onConnectionSettingsEdited)
        self.db_name.editingFinished.connect(self.onConnectionSettingsEdited)
        self.db_user.editingFinished.connect(self.onConnectionSettingsEdited)
        self.db_pass.editingFinished.connect(self.onConnectionSettingsEdited)
        self.browse_button.clicked.connect(self.onBrowseButtonClicked)
        self.connect_button.clicked.connect(self.onConnectClicked)

    def getDatabaseSchemas(self, conn, user):
        curs = conn.cursor()
        curs.execute("""
            SELECT nspname, pg_catalog.pg_get_userbyid(nspowner)
            FROM pg_catalog.pg_namespace
        """)

        schemas = []
        for record in curs:
            owner = record[1]
            if owner != user:
                continue
            schemas.append(record[0])
        return tuple(schemas)

    def onConnectionSettingsEdited(self):
        host = self.db_host.text()
        # port = self.db_port.value()
        name = self.db_name.text()
        user = self.db_user.text()
        pwrd = self.db_pass.text()

        if host == '' or name == '' or user == '':
            self.connect_button.setEnabled(False)
        else:
            self.connect_button.setEnabled(True)

    def onBrowseButtonClicked(self):
        current_folder = self.out_folder.text()
        new_folder = QFileDialog.getExistingDirectory(self.iface.mainWindow(), 'Database Export', current_folder)
        if new_folder != '':
            self.out_folder.setText(new_folder)
            self.out_folder.editingFinished.emit()

    def onConnectClicked(self):
        host = self.db_host.text()
        port = self.db_port.value()
        name = self.db_name.text()
        user = self.db_user.text()
        pwrd = self.db_pass.text()

        conn_str = "dbname='{}' user='{}' host='{}' port={} password='{}'".format(name, user, host, port, pwrd)

        # connection string contains non-ascii characters
        if len(conn_str) != len(conn_str.encode()):
            QMessageBox.critical(self, "Invalid connection settings",
                                 "The connection settings must not contain non-ascii characters")
            self.connect_button.setEnabled(False)
            self.project_box.clear()
            self.project_box.setEnabled(False)
            return

        # try to set up a database connection
        try:
            conn = psycopg2.connect(conn_str)
        except psycopg2.DatabaseError as e:
            QMessageBox.critical(self, "Connection failed", str(e))
            self.connect_button.setEnabled(False)
            self.project_box.clear()
            self.project_box.setEnabled(False)
            return

        QMessageBox.information(self, "Connection Established", "A connection was successfully established.")
        self.project_box.setEnabled(True)
        for schema in self.getDatabaseSchemas(conn, user):
            if schema.endswith('_prm'):
                self.project_box.addItem(schema)


class DatabaseExport(object):

    def __init__(self, iface):
        self.iface = iface
        self.dialog = None
        self.cancel = False
        self.act = QAction('Database Export', iface.mainWindow())
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
        """
        """
        self.dialog = PluginDialog(self.iface, self.iface.mainWindow())
        self.dialog.accepted.connect(self.execTool)
        self.dialog.rejected.connect(self.quitDialog)
        self.dialog.setModal(False)
        self.act.setEnabled(False)
        self.dialog.show()

    def scheduleAbort(self):
        self.cancel = True

    def quitDialog(self):
        self.dialog = None
        self.act.setEnabled(True)
        self.cancel = False

    def execTool(self):
        # check if export folder exists
        folder = self.dialog.out_folder.text()
        if not os.path.exists(folder):
            self.quitDialog()
            return

        proj_name = self.dialog.project_box.currentText()
        if proj_name == '':
            self.quitDialog()
            return

        host = self.dialog.db_host.text()
        port = self.dialog.db_port.value()
        name = self.dialog.db_name.text()
        user = self.dialog.db_user.text()
        pwrd = self.dialog.db_pass.text()

        # try to set up a database connection
        try:
            conn_str = "dbname='{}' user='{}' host='{}' port={} password='{}'".format(name, user, host, port, pwrd)
            conn = psycopg2.connect(conn_str)
        except psycopg2.DatabaseError:
            self.quitDialog()
            return

        cur = conn.cursor()


#Start here the export function
        if self.dialog.profiles_box.isChecked():
            self.export_river_profiles(proj_name, cur, folder, self.dialog.db_name.text())
        if self.dialog.floodplain_box.isChecked():
            self.export_floodplains(proj_name, cur, folder, self.dialog.db_name.text())
        if self.dialog.materials_box.isChecked():
            self.export_materials(proj_name, cur, folder, self.dialog.db_name.text())

        QMessageBox.information(self.iface.mainWindow(), "Database Export", "Export finished successfully.")
        self.quitDialog()


#Export function  (Why static?)
#Export river profiles
    @staticmethod
    def export_river_profiles(proj_name, cursor, folder, db_name):

        cursor.execute('SELECT "model_id", "name" FROM {}.hyd_river_general_prm'.format(proj_name))

        for r in cursor.fetchall():
            filename = os.path.join(folder, 'river_{:d}.txt'.format(r[0]))
            with open(filename, 'w') as rvr_file:

                cursor.execute("""
                    SELECT "profile_glob_id", "profile_id", "name", "riverstation", "delta_x",
                           "connection_type", "profile_type", "init_condition", "left_overflow",
                           "left_poleni", "right_overflow", "right_poleni"
                    FROM {}.hyd_river_profile_prm
                    WHERE river_id = {}
                    ORDER BY "riverstation" DESC
                """.format(proj_name, r[0]))
                rvr_file.write('########################################################################\n')
                rvr_file.write('# This file was automatically generated by ProMaIDes Database '
                                   'Export-QGIS-Plugin Version {version_1} \n'.format(version_1=VERSION))
                # date and time output
                now = datetime.now()
                dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
                rvr_file.write('# Generated at {dt_string_1} '.format(dt_string_1=dt_string))
                rvr_file.write('from project {filename_1} from database {db} \n'.format(filename_1=proj_name,
                                                                                       db = db_name))
                rvr_file.write('# Comments are marked with #\n')
                rvr_file.write('########################################################################\n')
                rvr_file.write("""
TITLE = "{}"
VARIABLES = "X", "Y", "Z", "MathType", "Distance", "Ident"
DATASETAUXDATA  NumProf = "{:d}"
                """.format(r[1], cursor.rowcount))

                for p in cursor.fetchall():

                    cursor.execute("""
                        SELECT "point_x", "point_y", "point_z", "material_id", "distance", "bank_channel_id"
                        FROM {}.hyd_river_profile_points_prm
                        WHERE profile_id = {}
                        ORDER BY "distance" ASC
                    """.format(proj_name, p[0]))

                    num_points = cursor.rowcount
                    points = cursor.fetchall()

                    bc_point = False
                    bc_point_stat = True
                    bc_point_val = 0
                    bc_lat = False
                    bc_lat_stat = True
                    bc_lat_val = 0
                    bc_waterl = False
                    bc_waterl_stat = True
                    bc_waterl_val = 0

                    cursor.execute("""
                        SELECT "boundary_type", "stationary", "value"
                        FROM {}.hyd_river_prof_bound_condition_prm
                        WHERE profile_glob_id = {}
                    """.format(proj_name, p[0]))

                    for bc in cursor:
                        if bc[0] == "point":
                            bc_point = True
                            bc_point_stat = bc[1]
                            bc_point_val = bc[2]
                        elif bc[0] == "lateral":
                            bc_lat = True
                            bc_lat_stat = bc[1]
                            bc_lat_val = bc[2]
                        elif bc[0] == "waterlevel":
                            bc_waterl = True
                            bc_waterl_stat = bc[1]
                            bc_waterl_val = bc[2]

                    rvr_file.write("""
ZONE T="{}" I={:d}
AUXDATA ProfLDist = "{}"
AUXDATA DeltaXtable = "{}"
AUXDATA ConnectionType = "{}"
AUXDATA ProfType = "{}"
AUXDATA InitCondition = "{}"
AUXDATA BoundaryPointCondition = "{}"
AUXDATA BoundaryPointStationary = "{}"
AUXDATA BoundaryPointValue = "{}"
AUXDATA BoundaryLateralCondition = "{}"
AUXDATA BoundaryLateralStationary = "{}"
AUXDATA BoundaryLateralValue = "{}"
AUXDATA BoundaryWaterlevelCondition = "{}"
AUXDATA BoundaryWaterlevelStationary = "{}"
AUXDATA BoundaryWaterlevelValue = "{}"
AUXDATA OverflowCouplingLeft = "{}"
AUXDATA PoleniFacLeft = "{}"
AUXDATA OverCouplingRight = "{}"
AUXDATA PoleniFacRight = "{}"
                        \n""".format(p[2], num_points, p[3], p[4], p[5], p[6], p[7],
                               str(bc_point).lower(), str(bc_point_stat).lower(), int(bc_point_val) if not bc_point_stat else bc_point_val,
                               str(bc_lat).lower(), str(bc_lat_stat).lower(), int(bc_lat_val) if not bc_lat_stat else bc_lat_val,
                               str(bc_waterl).lower(), str(bc_waterl_stat).lower(), int(bc_waterl_val) if not bc_waterl_stat else bc_waterl_val,
                               str(p[8]).lower(), p[9], str(p[10]).lower(), p[11]))

                    for point in points:
                        rvr_file.write('\t'.join(map(str, point)) + '\n')
#Export floodplain data
    @staticmethod
    def export_floodplains(proj_name, cursor, folder , db_name):

        cursor.execute("""
            SELECT "model_id", "nx", "ny", "low_left_x", "low_left_y", "elemwidth_x",
                   "elemwidth_y", "noinfo_value", "angle"
            FROM {}.hyd_floodplain_general_prm
            """.format(proj_name))

        for fpl in cursor.fetchall():
            filename = os.path.join(folder, 'floodplain_{:d}.txt'.format(fpl[0]))
            with open(filename, 'w') as fpl_file:
                fpl_file.write('########################################################################\n')
                fpl_file.write('# This file was automatically generated by ProMaIDes Database '
                                   'Export-QGIS-Plugin Version {version_1} \n'.format(version_1=VERSION))
                # date and time output
                now = datetime.now()
                dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
                fpl_file.write('# Generated at {dt_string_1} '.format(dt_string_1=dt_string))
                fpl_file.write('from project {filename_1} from database {db} \n'.format(filename_1=proj_name,
                                                                                       db = db_name))
                fpl_file.write('# Comments are marked with #\n')

                fpl_file.write("""#           
# The following metadata can be copied to a Promaides .ilm
# file to use this raster with Promaides.
#!GENERAL = <SET>
#    $NX = {}
#    $NY = {}
#    $LOWLEFTX = {}
#    $LOWLEFTY = {}
#    $ELEMWIDTH_X = {}
#    $ELEMWIdTH_Y = {}
#    $NOINFOVALUE = {}
#    $ANGLE = {}
#<SET>
                
!BEGIN\n""".format(fpl[1], fpl[2], fpl[3], fpl[4], fpl[5], fpl[6], fpl[7], fpl[8]))
                fpl_file.write('########################################################################\n')

                cursor.execute("""
                    SELECT "elem_glob_id", "elem_id", "geodetic_height", "material_id", "init_condition"
                    FROM {}.hyd_floodplain_element_prm
                    WHERE floodplain_id = {}
                    ORDER BY "elem_id" ASC
                """.format(proj_name, fpl[0]))
                elements = cursor.fetchall()

                cursor.execute("""
                    SELECT "elem_glob_id", "boundary_type", "stationary", "value"
                    FROM {}.hyd_floodplain_elem_bound_cond_prm
                """.format(proj_name))
                bcs = cursor.fetchall()

                bcs = {bc[0]: bc[1:] for bc in bcs}
                for element in elements:
                    element_id = element[0]
                    if element_id in bcs:
                        bc_type, bc_stat, bc_val = bcs[element_id]
                        bc_val = int(bc_val) if not bc_stat else bc_val
                        bc_stat = str(bc_stat).lower()
                        fpl_file.write('\t'.join(map(str, element[1:])) + '\ttrue\t{}\t{}\t{}\n'.format(bc_stat, bc_val, bc_type))
                    else:
                        fpl_file.write('\t'.join(map(str, element[1:])) + '\tfalse\ttrue\t0.0\n')
                fpl_file.write('!END\n')

# Export material id data
    @staticmethod
    def export_materials(proj_name, cursor, folder, db_name):

        cursor.execute("""
            SELECT "material_id", "value", "type"
            FROM {}.hyd_material_param_prm
            ORDER BY "material_id" ASC
        """.format(proj_name))

        num_mats = cursor.rowcount

        filename = os.path.join(folder, 'materials.txt')
        with open(filename, 'w') as mat_file:
            mat_file.write('########################################################################\n')
            mat_file.write('# This file was automatically generated by ProMaIDes Database '
                           'Export-QGIS-Plugin Version {version_1} \n'.format(version_1=VERSION))
            # date and time output
            now = datetime.now()
            dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
            mat_file.write('# Generated at {dt_string_1} '.format(dt_string_1=dt_string))
            mat_file.write('from project {filename_1} from database {db} \n'.format(filename_1=proj_name,
                                                                                       db = db_name))
            mat_file.write('# Comments are marked with #\n')
            mat_file.write('########################################################################\n')

            mat_file.write('{}\n'.format(num_mats))
            for record in cursor:
                mat_file.write('\t'.join(map(str, record)) + '\n')



