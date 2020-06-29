"""

"""
from __future__ import absolute_import

from qgis.PyQt.QtWidgets import QMenu, QMessageBox

from .environment import BASE_DIR
from .version import VERSION
#include here the new function for a connection with the menu
from .dikeline_export import DikelineExport
from .coastline_export import CoastlineExport
from .densify_linestring import DensifyLinestring
from .river_profile_export import RiverProfileExport
from .dem_export import DEMExport
from .database_export import DatabaseExport
from .hello_world import HelloWorld

import os


class PromaidesToolbox(object):

    def __init__(self, iface):
        self.iface = iface
        #init
        self.plugin_menu = None
        self.submenu_hyd = None
        self.submenu_general = None

        #HYD
        self.dikeline_exprt = DikelineExport(self.iface)
        self.coastline_exprt = CoastlineExport(self.iface)
        self.densify = DensifyLinestring(self.iface)
        self.river_profile_exprt = RiverProfileExport(self.iface)
        self.dem_export = DEMExport(self.iface)
        #General
        self.db_exprt = DatabaseExport(self.iface)
        self.hello_world = HelloWorld(self.iface)

    def initGui(self):
        """
        """
        self.plugin_menu = QMenu('ProMaIDes Toolbox', self.iface.mainWindow())
        #Add a submenu
        self.submenu_hyd = self.plugin_menu.addMenu('HYD')
        self.submenu_general = self.plugin_menu.addMenu('General')

        #Add and coonnect to funtions in other .py-files
        #HYD
        self.densify.initGui(self.submenu_hyd)
        self.river_profile_exprt.initGui(self.submenu_hyd)
        self.dikeline_exprt.initGui(self.submenu_hyd)
        self.coastline_exprt.initGui(self.submenu_hyd)
        self.dem_export.initGui(self.submenu_hyd)
        #General
        self.db_exprt.initGui(self.submenu_general)
        self.hello_world.initGui(self.submenu_general)

        #Add about
        self.plugin_menu.addAction('About', self.showAbout)
        self.iface.pluginMenu().addMenu(self.plugin_menu)

    def unload(self):
        """
        """
        #HYD
        self.dikeline_exprt.unload(self.submenu_hyd)
        self.coastline_exprt.unload(self.submenu_hyd)
        self.densify.unload(self.submenu_hyd)
        self.river_profile_exprt.unload(self.submenu_hyd)
        self.dem_export.unload(self.submenu_hyd)
        #General
        self.db_exprt.unload(self.submenu_general)
        self.hello_world.unload(self.submenu_general)

        self.iface.pluginMenu().removeAction(self.plugin_menu.menuAction())

    def showAbout(self):
        about = open(os.path.join(BASE_DIR, 'ABOUT.html')).read().format(version='.'.join(map(str, VERSION)))
        QMessageBox.about(self.iface.mainWindow(), 'ProMaIDes Toolbox', about)
