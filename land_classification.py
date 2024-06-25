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
import uuid
import webbrowser

# QGIS modules 
import PyQt5
from dataclasses import dataclass
import xml.etree.ElementTree as ET
import pandas

from promaides_gis_tools.environment import get_ui_path
from qgis.core import *
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import *
from qgis.PyQt.QtWidgets import QDialog, QApplication, QWidget, QInputDialog, QLineEdit, QFileDialog, QAction
from qgis.PyQt import uic
from qgis.gui import QgsFieldComboBox, QgsMapLayerComboBox
#//----Interface


#---QGIS
from qgis.core import (QgsVectorLayer, QgsRasterLayer)
from qgis import processing
#/---QGIS

from typing import Callable, Dict, List, Set, Tuple, Union
import numpy
import warnings 


#Types
DEM = QgsRasterLayer
SUBCATCHMENTS = QgsVectorLayer
LAND_USE = QgsVectorLayer
ELEVATION_KEY = "ELEV_KEY"
PREFIX_LANDUSE = "LU_"
PREFIX_SUBCATCHMENTS = "SC_"


def prettify_xml(element : ET.Element, parent : ET.Element = None, index = -1, depth = 0):
    """Prettify XML in pre-3.9 python since there is no indent"""
    for i, node in enumerate(element):
        prettify_xml(node, element, i, depth + 1)
    if parent is not None:
        if index == 0:
            parent.text = '\n' + ('\t' * depth)
        else:
            parent[index - 1].tail = '\n' + ('\t' * depth)
        if index == len(parent) - 1:
            element.tail = '\n' + ('\t' * (depth - 1))


def pseudodelete_raster(path :str) -> None:
    """
    QGIS doesnt let go of file handles so this reduces the raster size to something small.
    """
    rwriter = QgsRasterFileWriter(path)
    provider = QgsRasterFileWriter.createOneBandRaster(rwriter, dataType=Qgis.Float32,
                                            width = 1,
                                            height = 1,
                                            extent = QgsRectangle(0,0,1,1),
                                            crs = QgsCoordinateReferenceSystem.fromEpsgId(25832),
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
        # print("Deleting cache file at {}".format(vlayer_path))
        with open(vlayer_path, "w"):
            pass
        # print("--Successfully deleted {}".format(vlayer_path))
        return True
    except Exception as e:
        warnings.warn("Tried to delete layer {} but couldnt...{}".format(vlayer_path, e))
        return False

def df_from_vlayer(input : QgsVectorLayer) -> pandas.DataFrame:
    return pandas.DataFrame([feat.attributes() for feat in input.getFeatures()],
                            columns = [field.name() for field in input.fields()])


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

def classify_elevations(dem : QgsRasterLayer,
                        dem_band : int,
                        height_offset : float,
                        height_interval : float) -> QgsVectorLayer:
    """
    dem : QgsRasterLayer with elevations
    dem_band : Band indicating the elevation
    Returns polygons with gdal:contour. Key is defined in ELEVATION_KEY. Information in ELEV_min and ELEV_max
    """
    if not isinstance(dem, QgsRasterLayer) : raise ValueError("Invalid Raster, passed a {}".format(type(dem)))
    if not QgsRasterLayer.isValidRasterFileName(dem.source()) : raise ValueError("Invalid Raster Filename")

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
    result_contour.setCrs(dem.crs())

    vElevKeyo = processing.run("qgis:fieldcalculator", {'INPUT':result_contour,
                                                                    'FIELD_NAME':ELEVATION_KEY,
                                                                    'FIELD_TYPE':2, #str
                                                                    'FIELD_LENGTH':80,
                                                                    'FIELD_PRECISION':3,
                                                                    'NEW_FIELD':True,
                                                                    'FORMULA':f'concat( \"ELEV_max\" - {height_interval}, \'_\', \"ELEV_max\"  )',
                                                                    'OUTPUT': QgsProcessingUtils.generateTempFilename('ContourScLuElev.gpkg')}
                                                                    )["OUTPUT"]
    vElevKey = QgsVectorLayer(vElevKeyo)



    return vElevKey

def intersect_classification_naive (elevation_polygons : QgsVectorLayer,
                        subcatchments : QgsVectorLayer,
                        land_use : QgsVectorLayer,
                        land_use_column : str,
                        subcatchments_column : str = "fid",
                        keep_fid = False) -> QgsVectorLayer:
    """

    subcatchments : QgsVectorLayer with the multipolygon subcatchments
    land_use : QgsVectorLayer with simplified land use multipolygons
    land_use_column : Name of the column indicating the land use, code.
    keep_fid if keeping the SC_fid and LU_fid
    """

    #Check for validity of parameters

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
    #Intersection contours with subcatchments
    vContourPolySc : str = processing.run("native:intersection", {'INPUT': elevation_polygons,
                                                                            'OVERLAY': subcatchments,
                                                                            'INPUT_FIELDS':[],
                                                                            'OVERLAY_FIELDS':subcatchments_columns,
                                                                            'OVERLAY_FIELDS_PREFIX':PREFIX_SUBCATCHMENTS,
                                                                            'OUTPUT': QgsProcessingUtils.generateTempFilename('ContourSc.gpkg')},
                                                                            context = context
                                                                            )["OUTPUT"]
    crs = QgsVectorLayer(vContourPolySc, "ContourSc", "ogr").crs()#hack


    #Intersection contours|subcatchments with land use    
    vContourPolyScLU = processing.run("native:intersection", {'INPUT':vContourPolySc,
                                                            'OVERLAY': land_use,
                                                            'INPUT_FIELDS':[],
                                                            'OVERLAY_FIELDS': land_use_columns,
                                                            'OVERLAY_FIELDS_PREFIX':PREFIX_LANDUSE,
                                                            # 'OUTPUT': QgsProcessingUtils.generateTempFilename('ContourScLu.gpkg')},
                                                            'OUTPUT': "TEMPORARY_OUTPUT"},
                                                            context = context
                                                            )["OUTPUT"]
    # vContourPolyScLU = QgsVectorLayer(vContourPolyScLUo)
    vContourPolyScLU.setCrs(crs)
    
    free_memory_vlayer(vlayer = QgsVectorLayer(vContourPolySc), context = context)
    del vContourPolySc

    
    #Rename ID and fix elevations
    with edit(vContourPolyScLU):
        idx = vContourPolyScLU.fields().indexFromName("ID")
        vContourPolyScLU.dataProvider().deleteAttributes([idx])

    return vContourPolyScLU






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
                                                            #   'SOURCE_CRS':None,
                                                            #   'TARGET_CRS':None,
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
        rsub_dem.setCrs(dem.crs())


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
        yield group
        
        free_memory_vlayer(vlayer = vsub_subcatchment, context=context)
        free_memory_vlayer(vlayer = vsub_land_use, context=context)
        pseudodelete_raster(path = rsub_demp)
        del rsub_dem, vsub_land_use, vsub_subcatchment

def iterate_dems(dem : QgsRasterLayer, subcatchments = QgsVectorLayer, hspacing = 20000, vspacing = 20000) -> Tuple[DEM, int]:
    """
    Creates a grid from the subcatchment layer extent;
    cuts the DEM
    hspacing, vspacing divide the subcatchment data in squares of this size.
    Returns iteratively a sub-section of the DEM
    """
    context = QgsProcessingContext()
    #Get grid and cut
    grid = get_grid_from_extent(extent_layer = subcatchments, hspacing = hspacing, vspacing = vspacing)
    grids = processing.run("qgis:splitvectorlayer", {'INPUT':grid,
                                                               'FIELD':'id',
                                                               'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT}
                            ,context = context)["OUTPUT_LAYERS"] #Hack instead of using f.geometry().boundingBox()
    
    number_of_grids = len(grids)

    #Get a smaller DEM
    sub_grid : QgsVectorLayer
    for i, sub_grid in enumerate(grids):        
        rsub_demp = processing.run("gdal:warpreproject", {'INPUT': dem.source(),
                                                            #   'SOURCE_CRS':None,
                                                            #   'TARGET_CRS':None,
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
        rsub_dem.setCrs(dem.crs())
        yield rsub_dem, number_of_grids
        pseudodelete_raster(path = rsub_demp)
        del rsub_dem

def calculate_contours(dem : QgsRasterLayer,
                        dem_band : int,
                        height_offset : float,
                        height_interval : float,
                        subcatchments_mask : QgsVectorLayer = None,
                        grid_resolution : int = 20000,
                        naive : bool = True,
                        context = None,
                        callback : Callable = None) -> QgsVectorLayer:
    """
    Calculates the contours from gdal by either doing it all at once or by subdividing the raster into smaller rasters.
    """
    if context is None: context = QgsProcessingContext()

    if naive or subcatchments_mask is None:
        result = classify_elevations(dem = dem,
                                        dem_band = dem_band,
                                        height_offset = height_offset,
                                        height_interval = height_interval)
        return result
    elif not (subcatchments_mask is None):

        #calculate contours progressively, then merge them, then intersect
        sub_dems_results : List[QgsVectorLayer] = []
        sub_dems = iterate_dems(dem = dem, subcatchments= subcatchments_mask, hspacing = grid_resolution, vspacing = grid_resolution)
        for i, (sub_dem, number_of_grids) in enumerate(sub_dems):
            sub_base_elevations = classify_elevations(dem = sub_dem,
                                                    dem_band = dem_band,
                                                    height_offset = height_offset,
                                                    height_interval = height_interval)
            
            sub_dems_results.append(sub_base_elevations)
            if callback is not None: callback(int(i/number_of_grids))


        result = processing.run("native:mergevectorlayers", {'LAYERS':sub_dems_results,
                                                            'CRS':None,
                                                            'OUTPUT': QgsProcessingUtils.generateTempFilename('mergedcontourvectors.gpkg')},
                                    context = context
                                    )["OUTPUT"]
        #cleanup
        for v in sub_dems_results[:]:
            free_memory_vlayer(vlayer = v, context = context)
            del sub_dems_results[sub_dems_results.index(v)]

        return QgsVectorLayer(result)
    else:
        raise ValueError("Missing subcatchments_mask parameter!!")

def fid_reset_inplace(layer : QgsVectorLayer, col_name = "fid") -> None:
    #Redo the fid
    with edit(layer):
        idx = layer.fields().indexFromName(col_name)
        for f in layer.getFeatures():
            # f[idx] = f.id()
            f.setAttribute(idx,f.id())
            layer.updateFeature(f)
    return

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
                            callback : Callable = None) -> Tuple[QgsVectorLayer,QgsVectorLayer]:
    
    """
    Intersects the digital elevation model (dem raster) with subcatchment areas (multipolygon) with land use areas (multipolygon)
    preserves the land_use_column subcatchments_column attribute.
    Returns a vector layer with ELEV_ID, SC_fid (plus subcatchments_column), LU_fid (plus land_use_column) to edit.
    Saves it to output_filepath if a valid filepath is passed to it
    If grid_res has a value, then use the complex approach by dividing the dataset into squares of this size
    Passes a Callable function that takes an int with the percentage of completion
    Returns Land Classification, Land Elevations
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

    
    base_elevations : QgsVectorLayer
    base_elevations_clipped : QgsVectorLayer

    base_elevations = calculate_contours(dem = dem,
                                        dem_band = dem_band,
                                        height_offset = height_offset,
                                        height_interval = height_interval,
                                        subcatchments_mask = subcatchments,
                                        grid_resolution = grid_res,
                                        context = context,
                                        callback = callback,
                                        naive = naive_approach)
    base_elevations_clippedo = processing.run("native:clip", {'INPUT':base_elevations,
                                                                'OVERLAY':subcatchments,
                                                                'OUTPUT':QgsProcessingUtils.generateTempFilename('ClippedElevations.gpkg')})["OUTPUT"]
    base_elevations_clipped = QgsVectorLayer(base_elevations_clippedo)
    
    

    free_memory_vlayer(vlayer = base_elevations, context = context)

        
    intersect = intersect_classification_naive(elevation_polygons = base_elevations_clipped,
                                            subcatchments = subcatchments,
                                            land_use = land_use,
                                            land_use_column = land_use_column,
                                            subcatchments_column = subcatchments_column,
                                            keep_fid = not naive_approach)

    result_dissolve = processing.run("native:dissolve",
                                        {'INPUT': intersect,
                                        'FIELD':list(set([f"{PREFIX_SUBCATCHMENTS}{subcatchments_column}",
                                                            # f"{PREFIX_SUBCATCHMENTS}fid",# fid to keep every single feature
                                                        ELEVATION_KEY,
                                                        f"{PREFIX_LANDUSE}{land_use_column}",
                                                        # f"{PREFIX_LANDUSE}fid"# fid to keep every single feature
                                                        ])),
                                        'OUTPUT': "TEMPORARY_OUTPUT"},
                                        context = context)["OUTPUT"]
        
    free_memory_vlayer(vlayer = intersect, context = context)

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


    #Calculate elevation stats
    dissolved_elevationso = processing.run("native:dissolve",
                                                            {'INPUT': base_elevations_clipped,
                                                            'FIELD': [ELEVATION_KEY],
                                                            'OUTPUT': "TEMPORARY_OUTPUT"},
                                                            context = context)["OUTPUT"]
    
    processing.run("qgis:zonalstatistics", {'INPUT_RASTER':dem,
                                            'RASTER_BAND':dem_band,
                                            'INPUT_VECTOR':dissolved_elevationso,
                                            'COLUMN_PREFIX':'ELEV_',
                                            'STATS':[2]}) #This one modifies the layer directly
    
    #Clean Names
    fields = [f.name() for f in base_elevations_clipped.fields()]
    result_elevation_simple = processing.run("qgis:deletecolumn", {'INPUT': dissolved_elevationso,
                                                                    'COLUMN':[f for f in fields if f not in [ ELEVATION_KEY, "ELEV_mean"]],
                                                                    'OUTPUT': "TEMPORARY_OUTPUT"},
                                                                    context = context)["OUTPUT"]   
    
    
    result.setName("Land_classification")
    fid_reset_inplace(layer = result, col_name="fid") #Dont preserve fids^
 

    result_elevation_simple.setName("Elevation_Zones")

    if output_filepath in ["", None]: return result, result_elevation_simple
    
    #Saving...
    drivername = "GPKG"
    if output_filepath.endswith("shp") : drivername = "ESRI Shapefile"
    save_layer_gpkg(input = result, output = output_filepath, layername = "Land_classification", drivername = drivername)
    save_layer_gpkg(input = result_elevation_simple, output = output_filepath, layername = "Elevation_Zones", drivername = drivername)

    
    free_memory_vlayer(vlayer = result, context = context)
    free_memory_vlayer(vlayer = result_elevation_simple, context = context)
    del result

    return (QgsVectorLayer(output_filepath+"|layername=" + "Land_classification", "Land classification"),
            QgsVectorLayer(output_filepath+"|layername=" + "Elevation_Zones", "Elevation_Zones")
            )
    




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

def generate_clarea(land_classification : QgsVectorLayer,
                    key_LC_subcatchment : str,
                    key_LC_landuse : str,
                    key_LC_elevation : str,
                    elevation_layer : QgsVectorLayer,
                    key_ELEV_elevation : str,
                    key_ELEV_mean : str,
                    output_xml : str):
    """
    Takes a land classification multipolygon layer and an elevation layer.
    The classification layer must have a subcatchment key, a land use key,
    and an elevation key for the range of elevations.
    The elevation layer must have an elevation key and a mean height for that key.
    Elevation key values must coincide between layers.

    The clarea.xml file from HBV-Light will be generated using these values.
    Subcatchment ids, land use ids, and elevation ids will be sorted in ascending order.
    """
    elevations : Dict[str, float] = df_from_vlayer(input = elevation_layer)[[key_ELEV_elevation, key_ELEV_mean]].set_index([key_ELEV_elevation]).to_dict()[key_ELEV_mean]

    area_col = "area"
    while area_col in [key_LC_subcatchment, key_LC_landuse, key_LC_elevation]:
        area_col = area_col + uuid.uuid4().hex


    #Calculate polygon areas
    result = processing.run("qgis:fieldcalculator", {'INPUT':land_classification,
                                            'FIELD_NAME': area_col,
                                            'FIELD_TYPE':0,
                                            'FIELD_LENGTH':10,
                                            'FIELD_PRECISION':3,
                                            'NEW_FIELD':True,
                                            'FORMULA':'$area',
                                            'OUTPUT':"TEMPORARY_OUTPUT"})["OUTPUT"]
    
    #Calculate aggregation by land use, subcatchment.
    df = df_from_vlayer(input = result)

    all_sc = sorted(df[key_LC_subcatchment]. unique().tolist())
    all_lu = sorted(df[key_LC_landuse]. unique().tolist())
    all_elev = sorted(df[key_LC_elevation]. unique().tolist())

    if len(all_lu) > 3: raise ValueError("Maximum number of land use keys is 3!!! Please simplify your Land classification layer by combining multiple keys into one.")

    #Fraction is calculated by total subcatchment area
    sc_total_area : Dict[str, float] = df.groupby(by = [key_LC_subcatchment])[area_col].sum().to_dict()
    sc_elev_vegtype_area = df.groupby(by = [key_LC_subcatchment, key_LC_landuse, key_LC_elevation ])[area_col].sum()
    fractions : Dict[Tuple[str, str, str], float] = {}

    for (sc, lu, elev), value in sc_elev_vegtype_area.items():
        total_area = sc_total_area[sc]
        fraction = value/total_area
        fractions[(sc, lu, elev)] = fraction

    #Building the XML file from the data    
    catchment = ET.Element("Catchment")
    catchment.set("xmlns:xsi","http://www.w3.org/2001/XMLSchema-instance" )
    catchment.set("xmlns:xsd","http://www.w3.org/2001/XMLSchema" )
    vegzonecount = ET.SubElement(catchment, "VegetationZoneCount").text = str(len(all_lu)) #HARDCODED
    elevationzoneheight = ET.SubElement(catchment, "ElevationZoneHeight")
    for elev in all_elev:
        meanelev = elevations[elev]
        ET.SubElement(elevationzoneheight, "double").text = str(meanelev)
    
    for subcatchment in all_sc:
        sc = ET.SubElement(catchment, "SubCatchment")
        for veg in all_lu:
            veg_el = ET.SubElement(sc, "VegetationZone")
            for elev in all_elev:
                sub_fraction = 0.0
                if  (subcatchment, veg, elev) in fractions: sub_fraction = fractions[(subcatchment, veg, elev)]
                evu = ET.SubElement(veg_el, "EVU")
                evu.set("xsi:type","Basic_EVU")
                ET.SubElement(evu, "Area").text = str(sub_fraction)
        ET.SubElement(sc, "AbsoluteArea").text = str(sc_total_area[subcatchment]/1000/1000) #Assuming m2 for areas

    tree = ET.ElementTree(catchment)
    #Prettify
    prettify_xml(catchment)
    tree.write(output_xml, encoding="utf-8", xml_declaration=True)

    return True



def config_clarea_tab(handler : QDialog, dialog : "PluginDialog"):
    """Configs the tab for the clarea XML generator"""

    lu_layer: QgsMapLayerComboBox = dialog.mMapLayerComboBox_clarea_LU
    elev_layer : QgsMapLayerComboBox = dialog.mMapLayerComboBox_clarea_ELEV_layer


    elev_elev : QgsFieldComboBox = dialog.mFieldComboBox_clarea_ELEV_key
    elev_mean : QgsFieldComboBox = dialog.mFieldComboBox_clarea_ELEV_mean
    
    lu_sc : QgsFieldComboBox = dialog.mFieldComboBox_clarea_SC
    lu_lu : QgsFieldComboBox = dialog.mFieldComboBox_clarea_LU
    lu_elev : QgsFieldComboBox = dialog.mFieldComboBox_clarea_ELEV

    export_browse : QPushButton = dialog.export_browse_clarea
    export_input : QLineEdit = dialog.export_filename_clarea
    cancel : QPushButton = dialog.button_cancel_clarea
    help : QPushButton = dialog.button_help_3
    ok: QPushButton = dialog.button_ok_clarea 
    label_completed : QLabel = dialog.label_completed_clarea

    def set_LU_layer(*args,**kwargs):
        for o in [
                    lu_sc,
                    lu_lu,
                    lu_elev,
                ]:
            o.setLayer(*args,**kwargs)

    def set_ELEV_layer(*args,**kwargs):
        for o in [
                    elev_elev,
                    elev_mean,
                ]:
            o.setLayer(*args,**kwargs)

    #Update field
    lu_layer.layerChanged.connect(set_LU_layer) #self.mFieldComboBoxSC.setLayer
    elev_layer.layerChanged.connect(set_ELEV_layer) #self.mFieldComboBoxSC.setLayer

    #---LAND CLASSIFICATION    
    help.clicked.connect(dialog.Help)
    cancel.clicked.connect(handler.button_cancel_clicked)


    #Show crs
    lu_layer.setShowCrs(True)
    elev_layer.setShowCrs(True)

    #Filter layer types
    lu_layer.setFilters(QgsMapLayerProxyModel.PolygonLayer)

    #Clean MaplayerComboBoxes
    lu_layer.setLayer(None)
    elev_layer.setLayer(None)

    #Set subcatchment layer to selected layer
    lu_layer.setLayer(dialog.iface.activeLayer())




    def onBrowseButtonClicked(self):
        current_filename = export_input.text()
        if current_filename == "": current_filename = os.path.join(QgsProject.instance().absolutePath(),"Clarea.xml")
        new_filename, __ = QFileDialog.getSaveFileName(dialog.iface.mainWindow(), 'Choose where to save the file', current_filename, filter = "XML (*.xml)")
        if new_filename != '':
            export_input.setText(new_filename)

    export_browse.clicked.connect(onBrowseButtonClicked)   

    def exec_clarea_xml_gen():
        output_filepath = export_input.text()
        if output_filepath == "": raise ValueError("Output filepath is empty! Enter a valid filepath!")
        if output_filepath != "":
            if pathlib.Path(output_filepath).is_dir() : raise ValueError("Output filepath not valid because it is a folder! Enter a valid filepath!")

        result = generate_clarea(land_classification=lu_layer.currentLayer(),                                
                                key_LC_elevation=lu_elev.currentField(),
                                key_LC_landuse=lu_lu.currentField(),
                                key_LC_subcatchment=lu_sc.currentField(),
                                elevation_layer=elev_layer.currentLayer(),
                                key_ELEV_elevation=elev_elev.currentField(),
                                key_ELEV_mean=elev_mean.currentField(),
                                output_xml = output_filepath
                                )
        if result:
            label_completed.setText("Success!")
            cancel.setText("Exit")

    ok.clicked.connect(exec_clarea_xml_gen)


    


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
        self.button_help_2.clicked.connect(self.Help)
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
        webbrowser.open("https://promaides.myjetbrains.com/youtrack/articles/LFDH-A-10/Land-classification-tools")

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
        # print("Save to", output_filepath)
 


        grid_res = self.mQgsDoubleSpinBox_cellwidth.valueFromText(self.mQgsDoubleSpinBox_cellwidth.text())
        ignore_res = self.checkBox_cellwidth.isChecked()
        #Check
           
        result_landclassification, result_elevations = intersect_classification(dem = self.mMapLayerComboBox_DEM.currentLayer(),
                                                                                dem_band = self.mRasterBandComboBox_demband.currentBand(),
                                                                                height_offset = self.mQgsDoubleSpinBox_demoffset.valueFromText(self.mQgsDoubleSpinBox_demoffset.text()),
                                                                                height_interval = self.mQgsDoubleSpinBox_deminterval.valueFromText(self.mQgsDoubleSpinBox_deminterval.text()),
                                                                                subcatchments = self.mMapLayerComboBox_Subcatchments.currentLayer(),
                                                                                land_use = self.mMapLayerComboBox_Landuse.currentLayer(),
                                                                                land_use_column = self.mFieldComboBoxLU.currentField(),
                                                                                subcatchments_column = self.mFieldComboBoxSC.currentField(),
                                                                                grid_res= grid_res if not ignore_res else None,
                                                                                output_filepath = output_filepath,
                                                                                )
                                                    

        if not result_landclassification: raise ValueError("No result! Something went wrong in land classification")         

        QgsProject.instance().addMapLayer(result_elevations)
        QgsProject.instance().addMapLayer(result_landclassification)
        

        self.label_completed.setText("Success!")
        self.button_cancel.setText("Exit")

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
        config_clarea_tab(handler = self, dialog = self.dialog)
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
    pass