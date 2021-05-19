"""

"""
from __future__ import absolute_import

from qgis.PyQt.QtWidgets import QMenu, QMessageBox

from .environment import BASE_DIR
from .version import VERSION
#include here the new function for a connection with the menu
from .dikeline_export import DikelineExport
from .observationpoint_export import ObservationPointExport
from .polygon_export import PolygonExport
from .coastline_export import CoastlineExport
from .densify_linestring import DensifyLinestring
from .river_profile_export import RiverProfileExport
from .dem_export import DEMExport
from .database_export import DatabaseExport
from .hello_world import HelloWorld
from .crosssectioncreator import CrossSectionCreator
from .time_viewer import TimeViewer
from .rain_generator import RainGenerator
from .dam_raster import DAMRasterExport
from .cin_point import CINPointExport
from .cin_connector import CINConnectorExport
from .cin_polygon import CINPolygonExport

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
        self.observationpoint_exprt = ObservationPointExport(self.iface)
        self.polygon_exprt = PolygonExport(self.iface)
        self.coastline_exprt = CoastlineExport(self.iface)
        self.crosssection = CrossSectionCreator(self.iface)
        self.densify = DensifyLinestring(self.iface)
        self.river_profile_exprt = RiverProfileExport(self.iface)
        self.dem_export = DEMExport(self.iface)
        self.time = TimeViewer(self.iface)
        #HAZ
        self.rain = RainGenerator(self.iface)
        #DAM
        self.dam_raster = DAMRasterExport(self.iface)
        #CIN
        self.cin_point = CINPointExport(self.iface)
        self.cin_connector = CINConnectorExport(self.iface)
        self.cin_polygon = CINPolygonExport(self.iface)

        #General
        self.hello_world = HelloWorld(self.iface)
        self.db_exprt = DatabaseExport(self.iface)



    def initGui(self):
        """
        """
        self.plugin_menu = QMenu('ProMaIDes Toolbox', self.iface.mainWindow())
        #Add a submenu
        self.submenu_general = self.plugin_menu.addMenu('General')
        self.submenu_haz = self.plugin_menu.addMenu('HAZ')
        self.submenu_hyd = self.plugin_menu.addMenu('HYD')

        self.submenu_dam = self.plugin_menu.addMenu('DAM')
        self.submenu_cin = self.plugin_menu.addMenu('CIN')


        #Add and coonnect to funtions in other .py-files
        #HYD

        self.observationpoint_exprt.initGui(self.submenu_hyd)
        self.submenu_hyd.addSeparator()

        self.crosssection.initGui(self.submenu_hyd)
        self.densify.initGui(self.submenu_hyd)

        self.river_profile_exprt.initGui(self.submenu_hyd)
        self.submenu_hyd.addSeparator()
        self.dem_export.initGui(self.submenu_hyd)
        self.dikeline_exprt.initGui(self.submenu_hyd)
        self.polygon_exprt.initGui(self.submenu_hyd)
        self.submenu_hyd.addSeparator()
        self.coastline_exprt.initGui(self.submenu_hyd)
        self.submenu_hyd.addSeparator()
        self.time.initGui(self.submenu_hyd)

        #HAZ
        self.rain.initGui(self.submenu_haz)

        #DAM
        self.dam_raster.initGui(self.submenu_dam)
        
        #CIN
        self.cin_point.initGui(self.submenu_cin)
        self.cin_connector.initGui(self.submenu_cin)
        self.cin_polygon.initGui(self.submenu_cin)

        #General
        self.hello_world.initGui(self.submenu_general)
        self.db_exprt.initGui(self.submenu_general)



        #Add about
        self.plugin_menu.addAction('About', self.showAbout)
        self.iface.pluginMenu().addMenu(self.plugin_menu)

    def unload(self):
        """
        """
        #HYD
        self.dikeline_exprt.unload(self.submenu_hyd)
        self.observationpoint_exprt.unload(self.submenu_hyd)
        self.polygon_exprt.unload(self.submenu_hyd)
        self.coastline_exprt.unload(self.submenu_hyd)
        self.densify.unload(self.submenu_hyd)
        self.crosssection.unload(self.submenu_hyd)
        self.river_profile_exprt.unload(self.submenu_hyd)
        self.dem_export.unload(self.submenu_hyd)
        self.time.unload(self.submenu_hyd)

        #HAZ
        self.rain.unload(self.submenu_haz)

        #DAM
        self.dam_raster.unload(self.submenu_dam)
        
        #CIN
        self.cin_point.unload(self.submenu_cin)
        self.cin_connector.unload(self.submenu_cin)
        self.cin_polygon.unload(self.submenu_cin)

        #General
        self.db_exprt.unload(self.submenu_general)
        self.hello_world.unload(self.submenu_general)
        
        self.iface.pluginMenu().removeAction(self.plugin_menu.menuAction())

    def showAbout(self):
        about = open(os.path.join(BASE_DIR, 'ABOUT.html')).read().format(version='.'.join(map(str, VERSION)))
        QMessageBox.about(self.iface.mainWindow(), 'ProMaIDes Toolbox', about)
