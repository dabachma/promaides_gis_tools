#Process that transforms and combines a DEM Raster, a Land use polygon layer,
#and a subcatchment polygon layer together into a land classification layer.
#This land classification layer can then be exported by land use, elevation group
#and subcatchment into separate layers.
#Options: The algorithm is based on a subdivision of the extent area by means of
#a grid of a specified size.

#------Interface
from __future__ import unicode_literals
from __future__ import absolute_import


# system modules
import os
import pathlib
import webbrowser

# QGIS modules 
import PyQt5
from dataclasses import dataclass

from promaides_gis_tools.environment import get_ui_path
from qgis.core import *
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import *
from qgis.PyQt.QtWidgets import QDialog, QApplication, QWidget, QInputDialog, QLineEdit, QFileDialog, QAction
from qgis.PyQt import uic

#//----Interface



#---QGIS
from qgis.core import (QgsVectorLayer, QgsRasterLayer)
from qgis import processing
#/---QGIS

from typing import Callable, List, Set, Tuple, Union
import numpy
import warnings 


#Types
DEM = QgsRasterLayer
SUBCATCHMENTS = QgsVectorLayer
LAND_USE = QgsVectorLayer
ELEVATION_KEY = "ELEV_KEY"
PREFIX_LANDUSE = "LU_"
PREFIX_SUBCATCHMENTS = "SC_"


def pseudodelete_raster(path :str) -> None:
    """
    QGIS doesnt let go of file handles so this reduces the raster size to something small.
    """
    rwriter = QgsRasterFileWriter(path)
    provider = QgsRasterFileWriter.createOneBandRaster(rwriter, dataType=Qgis.Float32,
                                            width = 1,
                                            height = 1,
                                            extent = QgsRectangle(0,0,1,1),
                                            crs = QgsCoordinateReferenceSystem(25832),
                                            )
    provider.setNoDataValue(1, -1)
    provider.setEditable(True)
    
    block = provider.block(
        bandNo=1,
        boundingBox=provider.extent(),
        width=provider.xSize(),
        height=provider.ySize()
    )
    
    block.setValue(0, 0, 1)
    
    provider.writeBlock(
        block = block, 
        band = 1,
        xOffset = 0,
        yOffset = 0
    )
    


def free_memory_vlayer(vlayer : QgsVectorLayer, context : QgsProcessingContext = None) ->bool:
    """
    Deletes the disk file of this layer. Qgis seems to not let go of the handles while its running the script.
    Alternative solution: overwrite the files with nothing (0 KB).

    """
    vlayer_path = vlayer.publicSource()
    try:
        print("Deleting cache file at {}".format(vlayer_path))
        with open(vlayer_path, "w"):
            pass
        print("--Successfully deleted {}".format(vlayer_path))
        return True
    except Exception as e:
        warnings.warn("Tried to delete layer {} but couldnt...{}".format(vlayer_path, e))
        return False


def save_layer_gpkg(input : QgsVectorLayer, output : str, crs : QgsCoordinateReferenceSystem = None, layername = None, drivername = "GPKG")-> QgsVectorLayer:
    """
    Output has to be a normal filepath.
    Drivername has to be GPKG, ESRI Shapefile, xlsx
    """
    if crs is None: crs = input.crs() #used for versions before v2
    if layername is None: layername = input.name()

    context =  QgsCoordinateTransformContext()
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = drivername
    options.fileEncoding = "UTF-8" #TODO 
    options.layerName = layername

    if not os.path.exists(output):
        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
    else:
        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer

    save_result = QgsVectorFileWriter.writeAsVectorFormatV2(layer = input,
                                                    fileName = output, #simple path
                                                    transformContext = context,
                                                    options = options
                                                    )
    if save_result[0] != 0 : print("Error while saving:", layername, save_result)
    return input


def intersect_classification_naive (dem : QgsRasterLayer,
                        dem_band : int,
                        height_offset : float,
                        height_interval : float,
                        subcatchments : QgsVectorLayer,
                        land_use : QgsVectorLayer,
                        land_use_column : str,
                        subcatchments_column : str = "fid",
                        keep_fid = False) -> QgsVectorLayer:
    """
    dem : QgsRasterLayer with elevations
    dem_band : Band indicating the elevation
    subcatchments : QgsVectorLayer with the multipolygon subcatchments
    land_use : QgsVectorLayer with simplified land use multipolygons
    land_use_column : Name of the column indicating the land use, code.
    keep_fid if keeping the SC_fid and LU_fid
    """

    #Check for validity of parameters
    if not isinstance(dem, QgsRasterLayer) : raise ValueError("Invalid Raster, passed a {}".format(type(dem)))
    if not QgsRasterLayer.isValidRasterFileName(dem.source()) : raise ValueError("Invalid Raster Filename")
    if not isinstance(subcatchments, QgsVectorLayer) : raise ValueError("Invalid Subcatchments, passed a {}".format(type(subcatchments)))
    if not isinstance(land_use, QgsVectorLayer) : raise ValueError("Invalid Land use Layer, passed a {}".format(type(land_use)))
    
    #check fid attrib in contours, column names that are correct
    if not "fid" in [f.name() for f in subcatchments.fields()]: raise ValueError(f"Missing fid in Subcatchments layer")
    if not "fid" in [f.name() for f in land_use.fields()]: raise ValueError(f"Missing fid in Land use layer")
    if not land_use_column in [f.name() for f in land_use.fields()]: raise ValueError(f"Missing land use code in Land use layer...Chosen col {land_use_column}")
    if not subcatchments_column in [f.name() for f in subcatchments.fields()]: raise ValueError(f"Missing subcatchments code in Subcatchments layer...Chosen col {subcatchments_column}")
    
    if keep_fid:
        land_use_columns = list(set(["fid", land_use_column])) #Removed obligatory fid
        subcatchments_columns = list(set(["fid", subcatchments_column]))
    else:
        land_use_columns = list(set(["fid", land_use_column])) #Removed obligatory fid
        subcatchments_columns = list(set(["fid", subcatchments_column]))

    

    context = QgsProcessingContext()
    #GDAL command for polygon contours:
    #gdal_contour -b 1 -a ELEV -i 100.0 -f "GPKG" -p -amin elevmin -amax elevmax 
    result_contouro : str = processing.run("gdal:contour", { 'BAND' : dem_band,
                                                        'CREATE_3D' : False,
                                                        'EXTRA' : '-p -amin ELEV_min -amax ELEV_max', #ELEV as prefix
                                                        'FIELD_NAME' : 'ELEV',
                                                        'IGNORE_NODATA' : True,
                                                        'INPUT' : dem.source(),
                                                        'INTERVAL' : height_interval,
                                                        'NODATA' : numpy.nan,
                                                        'OFFSET' : height_offset,
                                                        'OUTPUT' : QgsProcessingUtils.generateTempFilename('Contour.gpkg') },
                                                        context = context)["OUTPUT"]
    result_contour = QgsVectorLayer(result_contouro)
    
    #Intersection contours with subcatchments
    vContourPolySc : QgsVectorLayer = processing.run("native:intersection", {'INPUT': result_contour,
                                            'OVERLAY': subcatchments,
                                            'INPUT_FIELDS':[],
                                            'OVERLAY_FIELDS':subcatchments_columns,
                                            'OVERLAY_FIELDS_PREFIX':PREFIX_SUBCATCHMENTS,
                                            'OUTPUT': QgsProcessingUtils.generateTempFilename('ContourSc.gpkg')},
                                            context = context
                                            )["OUTPUT"]
    free_memory_vlayer(vlayer = result_contour, context = context)
    del result_contour

    #Intersection contours|subcatchments with land use    
    vContourPolyScLUo = processing.run("native:intersection", {'INPUT':vContourPolySc,
                                                            'OVERLAY': land_use,
                                                            'INPUT_FIELDS':[],
                                                            'OVERLAY_FIELDS': land_use_columns,
                                                            'OVERLAY_FIELDS_PREFIX':PREFIX_LANDUSE,
                                                            'OUTPUT': QgsProcessingUtils.generateTempFilename('ContourScLu.gpkg')},
                                                            context = context
                                                            )["OUTPUT"]
    vContourPolyScLU = QgsVectorLayer(vContourPolyScLUo)
    
    free_memory_vlayer(vlayer = QgsVectorLayer(vContourPolySc), context = context)
    del vContourPolySc

    
    #Rename ID and fix elevations
    with edit(vContourPolyScLU):
        idx = vContourPolyScLU.fields().indexFromName("ID")
        vContourPolyScLU.dataProvider().deleteAttributes([idx])

    vContourPolyScLUKeyo = processing.run("qgis:fieldcalculator", {'INPUT':vContourPolyScLU,
                                            'FIELD_NAME':ELEVATION_KEY,
                                            'FIELD_TYPE':2, #str
                                            'FIELD_LENGTH':80,
                                            'FIELD_PRECISION':3,
                                            'NEW_FIELD':True,
                                            'FORMULA':f'concat( \"ELEV_max\" - {height_interval}, \'_\', \"ELEV_max\"  )',
                                            'OUTPUT': QgsProcessingUtils.generateTempFilename('ContourScLuElev.gpkg')}
                                            )["OUTPUT"]
    vContourPolyScLUKey = QgsVectorLayer(vContourPolyScLUKeyo)
    
    free_memory_vlayer(vlayer = vContourPolyScLU, context = context)
    del vContourPolyScLU

    return vContourPolyScLUKey






def get_grid_from_extent(extent_layer : QgsVectorLayer, hspacing : float, vspacing : float) -> QgsVectorLayer:
    """
    Creates a polygon grid based on the extent_layer
    horizontal and vertical spacing in meters
    """

    grid = processing.run("native:creategrid", {'TYPE':2, #Polygon
                                                             'EXTENT': extent_layer, #Algorithm accepts a layer processing.algorithmHelp("qgis:creategrid")
                                                             'HSPACING':hspacing,
                                                             'VSPACING':vspacing,
                                                             'HOVERLAY':0,
                                                             'VOVERLAY':0,
                                                             'CRS':extent_layer.crs(),
                                                             'OUTPUT': QgsProcessingUtils.generateTempFilename('Grid.gpkg')})["OUTPUT"]
    return grid



    

def iterate_region(dem : QgsRasterLayer, subcatchments : QgsVectorLayer, land_use : QgsVectorLayer, hspacing = 20000, vspacing = 20000) -> Tuple[DEM, SUBCATCHMENTS, LAND_USE, int]:
    """
    Creates a grid from the subcatchment layer extent;
    cuts the DEM, Subcatchment layer and land use areas with each of the features;
    applies the combine_layers_naive function to get the intersection of them.
    hspacing, vspacing divide the subcatchment data in squares of this size.
    The layers then get dissolved by elevation fid, subcatchment fid, land use fid
    Returns iteratively a tuple[dem, subcatchment, land_use] with the corresponding cut areas

    """
    context = QgsProcessingContext()
    #Get grid and cut
    grid = get_grid_from_extent(extent_layer = subcatchments, hspacing = hspacing, vspacing = vspacing)
    grids = processing.run("qgis:splitvectorlayer", {'INPUT':grid,
                                                               'FIELD':'id',
                                                               'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT}
                            ,context = context)["OUTPUT_LAYERS"] #Hack instead of using f.geometry().boundingBox()
    
    number_of_grids = len(grids)

    #Get a smaller DEM, Subcatchment layer and land use layer
    sub_grid : QgsVectorLayer
    for i, sub_grid in enumerate(grids):        
        rsub_demp = processing.run("gdal:warpreproject", {'INPUT': dem.source(),
                                                              'SOURCE_CRS':None,
                                                              'TARGET_CRS':None,
                                                              'RESAMPLING':0,
                                                              'NODATA': numpy.nan,
                                                              'TARGET_RESOLUTION':None,
                                                              'OPTIONS':'',
                                                              'DATA_TYPE':0,
                                                              'TARGET_EXTENT': sub_grid,
                                                              'TARGET_EXTENT_CRS':None,
                                                              'MULTITHREADING':False,
                                                              'EXTRA':'-wo CUTLINE_ALL_TOUCHED=TRUE', #Needed not to miss any pixels
                                                              'OUTPUT': QgsProcessingUtils.generateTempFilename('subdem.tif')},
                                                                context = context)["OUTPUT"]     
        rsub_dem = QgsRasterLayer(rsub_demp)


        vsub_subcatchmentp = processing.run("native:clip", {'INPUT': subcatchments,
                                                                 'OVERLAY':sub_grid,
                                                                 'OUTPUT': QgsProcessingUtils.generateTempFilename('subsubcatchment.gpkg')}
                                    ,context = context)["OUTPUT"]
        
        vsub_land_usep = processing.run("native:clip", {'INPUT': land_use,
                                                                 'OVERLAY':sub_grid,
                                                                 'OUTPUT': QgsProcessingUtils.generateTempFilename('sublanduse.gpkg')}
                                    ,context = context)["OUTPUT"]
        
        vsub_subcatchment = QgsVectorLayer(vsub_subcatchmentp)
        vsub_land_use = QgsVectorLayer(vsub_land_usep)
        group = (rsub_dem, vsub_subcatchment, vsub_land_use, number_of_grids)
        print("Subdivision {}: passing group {}".format(i, group))
        yield group
        
        free_memory_vlayer(vlayer = vsub_subcatchment, context=context)
        free_memory_vlayer(vlayer = vsub_land_use, context=context)
        pseudodelete_raster(path = rsub_demp)
        del rsub_dem, vsub_land_use, vsub_subcatchment



def intersect_classification(dem : QgsRasterLayer,
                            dem_band : int,
                            height_offset : float,
                            height_interval : float,
                            subcatchments : QgsVectorLayer,
                            land_use : QgsVectorLayer,
                            land_use_column : str,
                            subcatchments_column : str = "fid",
                            output_filepath : str = None,
                            grid_res : float = 20000,
                            callback : Callable = None) -> QgsVectorLayer:
    
    """
    Intersects the digital elevation model (dem raster) with subcatchment areas (multipolygon) with land use areas (multipolygon)
    preserves the land_use_column subcatchments_column attribute.
    Returns a vector layer with ELEV_ID, SC_fid (plus subcatchments_column), LU_fid (plus land_use_column) to edit.
    Saves it to output_filepath if a valid filepath is passed to it
    If grid_res has a value, then use the complex approach by dividing the dataset into squares of this size
    Passes a Callable function that takes an int with the percentage of completion
    """
    naive_approach = True

    #Check that subdivision of calculation is not bigger than the region itself.
    if grid_res is not None:
        sc_w, sc_h = subcatchments.extent().width(), subcatchments.extent().height()
        if  sc_w < grid_res or  sc_h < grid_res :
                warnings.warn(f"Processing resolution ({grid_res}) bigger than catchment ({sc_w} x {sc_h})!! Silently ignoring it...")
        else: naive_approach = False

    result : QgsVectorLayer = None #Initializing
    context = QgsProcessingContext()
    if naive_approach:
        result = intersect_classification_naive(dem = dem,
                                        dem_band = dem_band,
                                        height_offset = height_offset,
                                        height_interval = height_interval,
                                        subcatchments = subcatchments,
                                        land_use = land_use,
                                        land_use_column = land_use_column,
                                        subcatchments_column = subcatchments_column)


    else:
        #intersect classification progressively
        sub_results : List[QgsVectorLayer] = []
        sub_regions = iterate_region(dem = dem, subcatchments=subcatchments,land_use = land_use, hspacing = grid_res, vspacing = grid_res)
        for i, (sub_dem, sub_sc, sub_lu, number_of_grids) in enumerate(sub_regions):

            sub_result = intersect_classification_naive(dem = sub_dem,
                                                            dem_band = dem_band,
                                                            height_offset = height_offset,
                                                            height_interval = height_interval,
                                                            subcatchments = sub_sc,
                                                            land_use = sub_lu,
                                                            land_use_column = land_use_column,
                                                            subcatchments_column = subcatchments_column,
                                                            keep_fid = True)
            
            sub_results.append(sub_result)
            if callback is not None: callback(int(i/number_of_grids))


        #Combine the different layerss
        merged_vectorso = processing.run("native:mergevectorlayers", {'LAYERS':sub_results,
                                                                    'CRS':None,
                                                                    'OUTPUT': QgsProcessingUtils.generateTempFilename('mergedvectors.gpkg')},
                                    context = context
                                    )["OUTPUT"]
        merged_vectors = QgsVectorLayer(merged_vectorso)

        #cleanup
        for v in sub_results[:]:
            free_memory_vlayer(vlayer = v, context = context)
            del sub_results[sub_results.index(v)]

        result_dissolveo = processing.run("native:dissolve",
                                      {'INPUT': merged_vectors,
                                       'FIELD':list(set([f"{PREFIX_SUBCATCHMENTS}{subcatchments_column}",
                                                         f"{PREFIX_SUBCATCHMENTS}fid",
                                                        ELEVATION_KEY,
                                                        f"{PREFIX_LANDUSE}{land_use_column}",
                                                        f"{PREFIX_LANDUSE}fid"])),
                                       'OUTPUT': QgsProcessingUtils.generateTempFilename('dissolve.gpkg')},
                                       context = context)["OUTPUT"]
        result_dissolve = QgsVectorLayer(result_dissolveo)

        free_memory_vlayer(vlayer = merged_vectors, context = context)
        del merged_vectors

        fields = [f.name() for f in result_dissolve.fields()]
        fields_to_retain = ['fid',
                            f"{PREFIX_SUBCATCHMENTS}{subcatchments_column}",
                            ELEVATION_KEY,
                            f"{PREFIX_LANDUSE}{land_use_column}"]
        fields_to_delete = [f for f in fields if f not in fields_to_retain]

        result = processing.run("qgis:deletecolumn", {'INPUT': result_dissolve,
                                                      'COLUMN':fields_to_delete,
                                                      'OUTPUT': "TEMPORARY_OUTPUT"},
                                                    context = context)["OUTPUT"]   
        
        result.setCrs(result_dissolve.crs())
        free_memory_vlayer(vlayer = result_dissolve, context = context)


    #Redo the fid
    with edit(result):
        idx = result.fields().indexFromName("fid")
        for f in result.getFeatures():
            f[idx] = f.id()

    result.setName("Land_classification")

    if output_filepath in ["", None]: return result
    
    #Saving...
    drivername = "GPKG"
    if output_filepath.endswith("shp") : drivername = "ESRI Shapefile"
    save_layer_gpkg(input = result, output = output_filepath, layername = "Land_classification", drivername = drivername)

    
    free_memory_vlayer(vlayer = result, context = context)
    del result

    return QgsVectorLayer(output_filepath, "Land classification")          




def dissolve_classification(vlayer : QgsVectorLayer, subcatchment_key : str, elevation_key : str, landuse_key : str, output_filepath : str) -> bool:
    """
    Dissolves a classification vector layer with Subcatchment key, Elevation Key, Land Use Key.
    It generates a series of layers from all the pairings of Subcatchment, Elevation; with
    Land use as the sole attribute.
    """
    path = pathlib.Path(output_filepath)
    
    result_dissolve = processing.run("native:dissolve",
                                      {'INPUT': vlayer,
                                       'FIELD':[subcatchment_key, elevation_key, landuse_key],
                                       'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT})
    vDissolvedGeom : QgsVectorLayer = result_dissolve["OUTPUT"]
 
    #Get all subcatchment, elevation key pairs
    pairs : Set[Tuple[str, str]] = set()
    for f in vDissolvedGeom.getFeatures():
        pair = (f[subcatchment_key], f[elevation_key])
        pairs.add(pair)

    free_memory_vlayer(vlayer = vDissolvedGeom, context = None)

    #Naive approach without asyncio
    #For each pair value generate a new QgsVectorLayer in the specified path
    for sc_key, elev_key in pairs:
        sub_vlayer : QgsVectorLayer = processing.run("native:extractbyexpression", {'INPUT': vlayer,
                                                               'EXPRESSION':f"{subcatchment_key} = '{sc_key}' AND {elevation_key} = '{elev_key}'",
                                                               'OUTPUT':'TEMPORARY_OUTPUT'}
                                    )["OUTPUT"]

        #if the path is a folder then dump the layers as .shp, if its a gpkg then put everything in the same file
        if path.is_dir(): #Save as series of .shp
            save_layer_gpkg(input = sub_vlayer, output = path.joinpath(f"SC_{sc_key}_ELEV_{elev_key}.shp").resolve().as_posix(), layername = f"SC_{sc_key}_ELEV_{elev_key}", drivername="ESRI Shapefile")          
        else:
            save_layer_gpkg(input = sub_vlayer, output = output_filepath, layername = f"SC_{sc_key}_ELEV_{elev_key}", drivername="GPKG") 


    return True

#------------INTERFACE


UI_PATH = get_ui_path('ui_land_classification.ui')

class PluginDialog(QDialog):

    #set-up of the dialog
    def __init__(self, iface, parent=None, flags=Qt.WindowFlags()):
        QDialog.__init__(self, parent, flags) #superclass
        uic.loadUi(UI_PATH, self)
        self.iface = iface


        #---LAND CLASSIFICATION    
        self.button_help.clicked.connect(self.Help)
        self.button_ok.clicked.connect(self.button_ok_clicked)
        self.output_browse.clicked.connect(self.onBrowseOutputButtonClicked)       


        #Auxiliary functions for autoselect
        def set_fid_sc(*args,**kwargs):
            self.mFieldComboBoxSC.setLayer(*args,**kwargs)
            try: self.mFieldComboBoxSC.setField("fid")
            except: pass
            try: suggest_cellwidth()
            except: pass
        def set_fid_lu(*args,**kwargs):
            self.mFieldComboBoxLU.setLayer(*args,**kwargs)
            try: self.mFieldComboBoxLU.setField("fid")
            except: pass        
        def set_band_1(*args,**kwargs):
            print("rb fid")
            self.mRasterBandComboBox_demband.setLayer(*args,**kwargs)
            try: self.mRasterBandComboBox_demband.setBand(1)         
            except: pass
            try: suggest_cellwidth()
            except: pass

        def suggest_cellwidth():
            """
            Cell width for processing should be between 500 and 1000 times the DEM resolution for faster processing.
            """
            current_subcatchment : QgsVectorLayer = self.mMapLayerComboBox_Subcatchments.currentLayer()
            extent = current_subcatchment.extent()
            max_extent = max(extent.width(), extent.height())
            current_raster : QgsRasterLayer = self.mMapLayerComboBox_DEM.currentLayer()
            res_min = min(current_raster.rasterUnitsPerPixelX(), current_raster.rasterUnitsPerPixelY())
            suggested_cw = int(res_min*500)
            self.mQgsDoubleSpinBox_cellwidth.setValue(suggested_cw)
            
            if suggested_cw > max_extent:
                self.checkBox.setCheckState(False)
                ignore_cellwidth()

        def ignore_cellwidth():
            """
            Ignores cellwidth
            """
            if self.checkBox_cellwidth.isChecked():
                self.mQgsDoubleSpinBox_cellwidth.setDisabled(True)
            else:
                self.mQgsDoubleSpinBox_cellwidth.setDisabled(False)
            
        
        #Update field
        self.mMapLayerComboBox_Subcatchments.layerChanged.connect(set_fid_sc) #self.mFieldComboBoxSC.setLayer
        self.mMapLayerComboBox_DEM.layerChanged.connect(set_band_1)
        self.mMapLayerComboBox_Landuse.layerChanged.connect(set_fid_lu) #self.mFieldComboBoxLU.setLayer
        #---
        self.checkBox_cellwidth.stateChanged.connect(ignore_cellwidth)


        #Show crs
        self.mMapLayerComboBox_Subcatchments.setShowCrs(True)
        self.mMapLayerComboBox_DEM.setShowCrs(True)
        self.mMapLayerComboBox_Landuse.setShowCrs(True)

        #Filter layer types
        self.mMapLayerComboBox_Subcatchments.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.mMapLayerComboBox_DEM.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.mMapLayerComboBox_Landuse.setFilters(QgsMapLayerProxyModel.PolygonLayer)

        #Clean MaplayerComboBoxes
        self.mMapLayerComboBox_Subcatchments.setLayer(None)
        self.mMapLayerComboBox_DEM.setLayer(None)
        self.mMapLayerComboBox_Landuse.setLayer(None)

        #Set subcatchment layer to selected layer
        self.mMapLayerComboBox_Subcatchments.setLayer(iface.activeLayer())

        #Set default field
        self.mFieldComboBoxSC.setField("fid")
        self.mFieldComboBoxLU.setField("fid")
        self.mRasterBandComboBox_demband.setBand(-1)

        #---CLASSIFICATION EXPORT
        self.button_help.clicked.connect(self.Help)
        self.button_ok_CE.clicked.connect(self.button_ok_CE_clicked)
        self.export_browse_CE.clicked.connect(self.onBrowseExportButtonClicked)    

        #Update, force crs, filter Layer type, set to active
        self.mMapLayerComboBox_CE.layerChanged.connect(self.mFieldComboBoxCE_SC.setLayer)
        self.mMapLayerComboBox_CE.layerChanged.connect(self.mFieldComboBoxCE_ELEV.setLayer)
        self.mMapLayerComboBox_CE.layerChanged.connect(self.mFieldComboBoxCE_LU.setLayer)

        self.mMapLayerComboBox_CE.setShowCrs(True)
        self.mMapLayerComboBox_CE.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.mMapLayerComboBox_CE.setLayer(iface.activeLayer())

        self.tabWidget.setCurrentIndex(0)
        

    def Help(self):
        webbrowser.open("https://promaides.myjetbrains.com/youtrack/articles/PMDP-A-52/Hello-World")

    def __del__(self):
        pass


    def onBrowseOutputButtonClicked(self):
        current_filename = self.output_filename.text()
        if current_filename == "": current_filename = os.path.join(QgsProject.instance().absolutePath(),"land_classification.gpkg")
        new_filename, __ = QFileDialog.getSaveFileName(self.iface.mainWindow(), 'Choose where to save the land classification file', current_filename, filter = "GeoPackage (*.gpkg);;Shapefile (*.shp)")
        if new_filename != '':
            self.output_filename.setText(new_filename)
    
    def onBrowseExportButtonClicked(self):
        current_filename = self.export_filename_CE.text()
        if current_filename == "": current_filename = os.path.join(QgsProject.instance().absolutePath(),"classification_layers.gpkg")
        new_filename, __ = QFileDialog.getSaveFileName(self.iface.mainWindow(), 'Choose where to save the subdivided classification file', current_filename, filter = "GeoPackage (*.gpkg)")
        if new_filename != '':
            self.export_filename_CE.setText(new_filename)

    def button_ok_clicked(self):
        self.exec_land_classification()

    def button_ok_CE_clicked(self):
        self.exec_classification_export()

    def exec_land_classification(self):
        """Runs the land classification algorithm"""
        #Check output filepath validity
        output_filepath = self.output_filename.text()
        if output_filepath != "":
            if pathlib.Path(output_filepath).is_dir() : raise ValueError("Output filepath not valid because it is a folder! Enter a valid filepath")
        print("Save to", output_filepath)

        grid_res = self.mQgsDoubleSpinBox_cellwidth.valueFromText(self.mQgsDoubleSpinBox_cellwidth.text())
        ignore_res = self.checkBox_cellwidth.isChecked()
        #Check
           
        result = intersect_classification(dem = self.mMapLayerComboBox_DEM.currentLayer(),
                                        dem_band = self.mRasterBandComboBox_demband.currentBand(),
                                        height_offset = self.mQgsDoubleSpinBox_demoffset.valueFromText(self.mQgsDoubleSpinBox_demoffset.text()),
                                        height_interval = self.mQgsDoubleSpinBox_deminterval.valueFromText(self.mQgsDoubleSpinBox_deminterval.text()),
                                        subcatchments = self.mMapLayerComboBox_Subcatchments.currentLayer(),
                                        land_use = self.mMapLayerComboBox_Landuse.currentLayer(),
                                        land_use_column = self.mFieldComboBoxLU.currentField(),
                                        subcatchments_column = self.mFieldComboBoxSC.currentField(),
                                        grid_res= grid_res if not ignore_res else None,
                                        output_filepath = output_filepath)
                                                    

        if not result: raise ValueError("No result! Something went wrong in land classification")         
        self.label_completed.setText("Success!")
        self.button_cancel.setText("Exit")
        
        QgsProject.instance().addMapLayer(result)
        

        return True


    def exec_classification_export(self):
        """
        Runs the classification export algorithm.
        """
        output_filepath = self.export_filename_CE.text()
        if output_filepath == "":
            raise ValueError("You need to enter a path to export!") #FOLDER to shapefile collection, FILE to GPKG
        print("Save to", output_filepath)

        result = dissolve_classification(vlayer = self.mMapLayerComboBox_CE.currentLayer(),
                                         subcatchment_key= self.mFieldComboBoxCE_SC.currentField(),
                                         elevation_key = self.mFieldComboBoxCE_ELEV.currentField(),
                                         landuse_key = self.mFieldComboBoxCE_LU.currentField(),
                                         output_filepath = output_filepath
        )

        if not result: raise ValueError("No result! Something went wrong")         
        
        self.label_completed_CE.setText("Success!")
        self.button_cancel_CE.setText("Exit")




class LandClassificationTool(object):
#Menu entry and plugin window launcher
    def __init__(self, iface):
        self.iface = iface
        self.dialog = None
        self.cancel = False
        self.act = QAction('Land classification tools', iface.mainWindow())
        self.act.triggered.connect(self.execDialog) #Clicking on menu option launches execDialog

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
        self.dialog.button_cancel.clicked.connect(self.button_cancel_clicked)
        self.dialog.button_cancel_CE.clicked.connect(self.button_cancel_clicked)
        self.dialog.show()

    def scheduleAbort(self):
        self.cancel = True

    def button_cancel_clicked(self):
        self.quitDialog()

    def quitDialog(self):
        self.act.setEnabled(True)
        self.cancel = False
        self.dialog.close()


if __name__ == "__main__":
    test()
    pass