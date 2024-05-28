#Tool for the quick creation of:
#-Voronoi layer from a Point layer
#-Aggregation from a Subcatchment layer with area as a weight
#-Application of a formula for evapotranspiration


#------Interface
from __future__ import unicode_literals
from __future__ import absolute_import


# system modules
import datetime
import os
import pathlib
import webbrowser

# QGIS modules 
import PyQt5
from dataclasses import dataclass

import pandas

from promaides_gis_tools.environment import get_ui_path
from qgis.core import *
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import *
from qgis.PyQt.QtWidgets import QDialog, QApplication, QWidget, QInputDialog, QLineEdit, QFileDialog, QAction
from qgis.PyQt import uic
# from qgis.PyQt.QtWidgets.QWidget import QComboBox, QPushButton, QLineEdit, QLabel
from qgis.gui import QgsFieldComboBox, QgsMapLayerComboBox


#//----Interface
UI_PATH = get_ui_path('ui_evaporation_ptq.ui')
HELP_PATH = "https://promaides.myjetbrains.com/youtrack/articles/LFDH-A-11"

#---QGIS
from qgis.core import (QgsVectorLayer, QgsRasterLayer)
from qgis import processing
#/---QGIS

from typing import Callable, Dict, List, Set, Tuple, Union
import numpy
import warnings 

PREFIX_SC = "subcatchment_"
AREA_FIELD = "AREA"
#Types
@dataclass
class VariableMap:
    p : str
    t : str
    q : str
    def tolist(self) -> list:
        return [self.p, self.t, self.q]
    
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

def generate_intersection(stations : QgsVectorLayer, stations_id : str, subcatchments : QgsVectorLayer, subcatchments_id : str) -> Tuple[QgsVectorLayer, str]:
    """Generates a voronoi pattern from the stations layer, then intersects with the subcatchment layer
        Returns a layer: geometry, station_id, subcatchment_id, area with the modified subcatchment_id name"""
    
    if not subcatchments_id in [f.name() for f in subcatchments.fields()]: raise ValueError(f"Missing subcatchment id in subcatchments layer...Chosen col {subcatchments}")
    if not stations_id in [f.name() for f in stations.fields()]: raise ValueError(f"Missing station id in stations layer...Chosen col {stations_id}")

    #Prefix check    #Check that nothing starts with sc_
    sc_new_fieldname = PREFIX_SC + subcatchments_id
    if sc_new_fieldname == stations_id: raise ValueError("Name collision! station names must not start with {}.".format(PREFIX_SC))

    #Stations to single parts
    single_parts = processing.run("native:multiparttosingleparts",
                                   {'INPUT':stations,
                                    'OUTPUT': QgsProcessingUtils.generateTempFilename('StationSingleParts.gpkg')}
                                    )["OUTPUT"]
    vstations = QgsVectorLayer(single_parts, "Stations_single_parts")

    #Check number of stations:
    #1 station -> extent is the subcatchments whole extent
    #>1 stations -> normal voronoi pattern from GRASS, with extent as limit
    num_features = sum(1 for f in vstations.getFeatures())
    crs_stations = QgsCoordinateReferenceSystem(vstations.crs())
    crs_subcatchments = QgsCoordinateReferenceSystem(subcatchments.crs())
    transform = QgsCoordinateTransform(crs_subcatchments, crs_stations, QgsProject.instance())
    bb = QgsGeometry.fromRect(subcatchments.extent())
    bb.transform(transform)

    if num_features == 1:
        bounding_box = processing.run("native:extenttolayer", {'INPUT': bb.boundingBox(),
                                                               'OUTPUT': QgsProcessingUtils.generateTempFilename('bbox.gpkg')}
                                                               )["OUTPUT"]
        vVoronoi = QgsVectorLayer(bounding_box)
        
        vVoronoi.dataProvider().addAttributes([field for field in vstations.fields() if field.name() not in ["fid"]])
        vVoronoi.updateFields()

        single_station : QgsFeature = list(vstations.getFeatures())[0]
        attr_d = {i : v for i, v in enumerate(single_station.attributes())}
        
        single_bb : QgsFeature = list(vVoronoi.getFeatures())[0] #Only one
        vVoronoi.dataProvider().changeAttributeValues({single_bb.id() : attr_d})
    
    else:
        
        #Voronoi stations
        output = QgsProcessingUtils.generateTempFilename('Voronoi.gpkg')
        _    = processing.run("grass7:v.voronoi", {'input': vstations,
                                                      '-l':False,
                                                      '-t':False,
                                                      'output': output,
                                                      'GRASS_REGION_PARAMETER': bb,
                                                      'GRASS_SNAP_TOLERANCE_PARAMETER':-1,
                                                      'GRASS_MIN_AREA_PARAMETER':0.0001,
                                                      'GRASS_OUTPUT_TYPE_PARAMETER':0,
                                                      'GRASS_VECTOR_DSCO':'',
                                                      'GRASS_VECTOR_LCO':'',
                                                      'GRASS_VECTOR_EXPORT_NOCAT':False}
                                                      )
        
        vVoronoi = QgsVectorLayer(output, "voronoi")
        
    #Intersection with subcatchment. Keep columns    
    intersection = processing.run("qgis:intersection", {'INPUT':vVoronoi,
                                                        'OVERLAY':subcatchments,
                                                         'INPUT_FIELDS': [stations_id],
                                                         'OVERLAY_FIELDS':[subcatchments_id],
                                                         'OVERLAY_FIELDS_PREFIX': PREFIX_SC, #risk of duplicated field names...
                                                        'OUTPUT': QgsProcessingUtils.generateTempFilename('intersection.gpkg')},
                                                            )["OUTPUT"]
    vintersection = QgsVectorLayer(intersection, "Intersection")

    #Adds area
    result_area = processing.run("qgis:fieldcalculator", {'INPUT':vintersection,
                                                                    'FIELD_NAME': AREA_FIELD,
                                                                    'FIELD_TYPE':0, #float
                                                                    'FIELD_LENGTH':80,
                                                                    'FIELD_PRECISION':3,
                                                                    'NEW_FIELD':True,
                                                                    'FORMULA':f'$area',
                                                                    'OUTPUT': QgsProcessingUtils.generateTempFilename('StationsVoronoiComplete.gpkg')}
                                                                    )["OUTPUT"]
    result = QgsVectorLayer(result_area, "StationsVoronoi")


    return result, sc_new_fieldname
    
def calculate_fractions(voronoi_stations : pandas.DataFrame, stations_id : str, subcatchment_id : str, data : pandas.DataFrame, area_id : str = AREA_FIELD) -> pandas.DataFrame:
    """
    For each subcatchment: Calculates the fraction of the station voronoi area/total station voronoi area inside that subcatchment.
    Stations with null values dont contribute and consequently the fraction of the other stations goes up.
    Data has the datum as index and stations_id as columns...
    """
    subcatchments = sorted(voronoi_stations[subcatchment_id].unique()) #Ascending order     

    weighted_values = {d:{s:0.0 for s in subcatchments} for d in data.index}
    #For each row, find which columns are not empty, and query them against the voronoi station areas
    for sc in subcatchments:
        sub_df : pandas.DataFrame = voronoi_stations[voronoi_stations[subcatchment_id] == sc]
        if not (subcatchment_id in sub_df.columns) or  not (stations_id in sub_df.columns):
            raise ValueError(f"Missing columns for subcatchment_id or stations_id!! Current columns : {sub_df.columns}. Searched for columns: {subcatchment_id}, {stations_id}")
        lookup_table = sub_df.set_index([subcatchment_id, stations_id])[area_id].to_dict()
        for i, row in data.iterrows():
            datum = i
            clean_row = row.dropna()
            area_sum = 0.0
            value_sum = 0.0
            #Find station area and multiply by value.
            for station_i, value in clean_row.items():
                key = (sc, station_i)
                if key not in lookup_table : continue                
                area = lookup_table[key]
                area_sum += area
                value_sum += value * area
            if area_sum == 0.0 :
                # warnings.warn(f"Subcatchment {sc} at datum {i} doesnt seem to have stations inside. Ignoring silently...") 
                continue
            weighted_values[datum][sc] = value_sum / area_sum
    
    avg_df = pandas.DataFrame(weighted_values).T #T because Datum as column -> Datum as index
    avg_df = pandas.melt(avg_df.reset_index(), id_vars="index", value_vars = avg_df.columns,
                         var_name = subcatchment_id).set_index(["index", subcatchment_id])
    avg_df.index.rename(["Date", subcatchment_id], inplace = True)
    return avg_df



def calculate(stations : QgsVectorLayer, stations_id : str, subcatchments : QgsVectorLayer, subcatchments_id : str,
              data_layer : QgsMapLayer, data_datum_field : str,
              output_filepath : str = None)-> QgsVectorLayer:
    """
    Calculates the voronoi tesselation, then averages the values.
    Data must have column headers as stations id (apart of datum)
    """
    data = df_from_vlayer(data_layer)    
    data.set_index([data_datum_field], inplace = True)
    data = data.apply(pandas.to_numeric, errors='coerce')



    result_voronoi, new_sub_id = generate_intersection(stations = stations,
                                       stations_id = stations_id,
                                       subcatchments = subcatchments,
                                       subcatchments_id = subcatchments_id)
    
    result_voronoi_df = df_from_vlayer(result_voronoi)
    
    result_averages_df = calculate_fractions(voronoi_stations = result_voronoi_df, stations_id = stations_id, subcatchment_id = new_sub_id, data = data)

    
    if output_filepath in ["", None] : output_filepath = QgsProcessingUtils.generateTempFilename('AggregatedValues.csv')
    result_averages_df.to_csv(output_filepath)
    result = QgsVectorLayer(output_filepath, "AggregatedValues")
    return result


def pivot_ptq (df : pandas.DataFrame, col : str) -> pandas.DataFrame:
    """Pivots a layer with datum, (ptq), id into -> datum, (p t q)1, (p t q)2, (p t q)3...
    The subcatchment id col is concatenated horizontally.
    """
    concat = [sub_df.reset_index(level=col, drop = True) for key, sub_df in df.groupby([col])]
    horizontal_df = pandas.concat(concat, axis = 1)
    return horizontal_df


def merge_pt(layer_p : QgsVectorLayer, datump : str, idp : str, valuep : str,
             layer_t : QgsVectorLayer, datumt : str, idt : str, valuet : str,
             output_filepath = None) -> QgsVectorLayer:
    """Merges the datetime|subcatchmentid|value   files and pivots them
    datum, id, value are the columns of the datasets
    """
    
    #Harmonization
    datetime_col = "Date"
    sc_col = "Subcatchment"

    dfp = (df_from_vlayer(layer_p)    
                            .rename(columns={datump:datetime_col, valuep:"P", idp:sc_col})
                            .set_index([datetime_col, sc_col])                            
                            )
    
    dft = (df_from_vlayer(layer_t)    
                            .rename(columns={datumt:datetime_col, valuet:"T", idt:sc_col})
                            .set_index([datetime_col, sc_col])                            
                            )


    merge = dfp.join(dft, how = "outer")

    merge["Qobs"] = 0

    merge = merge.sort_values(sc_col) #Ascending order     


    pivot = pivot_ptq(df = merge, col = sc_col)

    if output_filepath in ["", None] : output_filepath = QgsProcessingUtils.generateTempFilename('PivotedPTQ.csv')
    pivot.to_csv(output_filepath, sep = "\t")

    result = QgsVectorLayer(output_filepath, "PivotedPTQ")
    return result



def load_WG_file(filepath : str, col : str) -> pandas.DataFrame:
    """Loads a WG File in the form:
        date	TEMP	LUFEU	GLOST	WIND	NISCH
        50000101	-2.76	72.75	271.81	4.23	1
        Transforms date to datetime.datetime
    """
    if not pathlib.Path(filepath).is_absolute():
        filepath = os.path.join(QgsProject.instance().absolutePath(), filepath)
    
    #CHECK THAT PATH EXISTS IN FOLDER
    if not os.path.exists(filepath) : raise ValueError(f"Path doesnt exist! Relative paths are related to the project folder. Expected path: {filepath}")

    df = pandas.read_csv(filepath, usecols=["date", col], dtype = {"date":str})
    df["date"] = df["date"].apply(lambda x: datetime.datetime.strptime(x, '%Y%m%d').date()) #Done N times...
    df = df.set_index(["date"])
    return df


def calculate_wg_averages(df_paths : pandas.DataFrame, subcatchment_id : str, paths_column : str, area_id : str) -> pandas.DataFrame:
    """Takes a paths dataframe without indexing: subcatchment_id | path_to_WG_file | area.
        Calculates the averages using area inside subcatchment as weight.

    """
    paths = df_paths[paths_column].unique()
    
    dfs : List[pandas.DataFrame] =  []
    for col in ["TEMP", "LUFEU", "GLOST", "WIND", "NISCH"]:
        sub_dfs = {p:load_WG_file(p, col) for p in paths}
        for k,v in sub_dfs.items():
            v.columns = [k]
        data = pandas.concat(sub_dfs.values()) # date as index, name of path as header for the parameter col         

        avg = calculate_fractions(voronoi_stations = df_paths, stations_id = paths_column,
                                  subcatchment_id = subcatchment_id, data = data, area_id = area_id)
        avg.rename(columns={"value":col}, inplace = True)
        dfs.append(avg)
    
    final_df = dfs[0]
    for df in dfs[1:]:
        print(df.head(5))
        final_df = final_df.join(df, how = "outer")
    return final_df




def evapotranspiration(tmax : float, tmin : float, tavg : float,
                        wind : float, solar_rad : float, hum_fraction : float,
                        latitude : float, height : float,
                        day : int,
                        albedo : float = 0.23,
                        # psy = 0.067    #psychrometric constant
                        ) -> float:
    """
    latitude: (radian)
    height: m, altitude above sea level
    tmax, tmin, tavg : Temperatures in °C
    wind : m/s wind speed
    solar_rad : solar radiation J/cm2
    hum : fraction air humidity
    day: day of the year 0-365
    """
    mean_solar_rad = solar_rad * 0.01 # GLOST
    i_vapor = 4098 * (0.6108 * numpy.exp((17.27 * tavg) / (tavg + 237.3))) / ((tavg + 237.3)**2) #slope saturation vapor pressure curve
    a_pressure = 101.3 * ((293 - 0.0065 * height) / 293)**5.26    #atmospheric pressure [kPa].
    psy = 0.000665 * a_pressure
    delta = i_vapor / (i_vapor / psy * (1 + 0.34 * wind))    #delta term
    psi = psy/(i_vapor + psy * (1 + 0.34 * wind))    #psi term
    tt = (900/(tavg + 273)) * wind    #temperature term
    etmax = 0.6108 * numpy.exp((17.27 * tmax)/(tmax + 237.3))    #eTmax
    etmin = 0.6108 * numpy.exp((17.27 * tmin)/(tmin + 237.3))    #eTmin
    es = (etmax + etmin) * 0.5    #mean satuaration vapor from air temp
    edew = hum_fraction * es 
    dr = 1 + 0.033 * numpy.cos(2 * numpy.pi * day / 365 )    #inverse relative distance earth-sun
    solar_delta = 0.409 * numpy.sin((2 * numpy.pi * day/365) - 1.39)    #solar declination
    omega = numpy.arccos(-1 * (numpy.tan((latitude)) * numpy.tan(solar_delta)))    #sunset hour angle
    ex_radiation = ((24 * 60/numpy.pi) * 0.082 * dr * 
                        (+ (omega * numpy.sin(latitude) * numpy.sin(solar_delta))
                         + (numpy.cos(latitude) * numpy.cos(solar_delta) * numpy.sin(omega))
                         )
                    )    #extraterrestrical radiation
    sky_radiation = (0.75 + height * 2 * 10**-5) * ex_radiation    #clear sky radiation
    nsr = (1 - albedo)*solar_rad    #net shortwave radiation
    nor = (0.5*((tmax + 273.16)**4 + (tmin + 273.16)**4) * (4.903 * 10**-9)) * (0.34 - 0.14 * numpy.sqrt(edew)) * (1.35 * (mean_solar_rad / sky_radiation) - 0.35)  #Net outgoing long wave solar radiation (Rnl)
    net_radiation = max( + nsr - nor, 0)    #net radiation
    eva_nr  = net_radiation * 0.408    #net radiation (Rn) in equivalent of evaporation (mm) (Rng )
    et_rad  = eva_nr * delta    #radiation term
    et_wind = psi * tt * (es - edew)    #wind term
    et = et_wind + et_rad    #final evapotranspiration

    return et



def calculate_weather_generator_voronoi_avg(stations : QgsVectorLayer, path_field : str,
                                            subcatchments : QgsVectorLayer, subcatchment_id_field : str,
                                            output_filepath : str) -> QgsVectorLayer:
    """Takes a point layer with stations and paths to Weather generator calculated files and 
    averages the values by weighting the area using the voronoi algorithm. The files referenced
    by the stations must have the following headers: date	TEMP	LUFEU	GLOST	WIND	NISCH

    """
    

    result_voronoi, new_sub_id = generate_intersection(stations = stations,
                                                        stations_id = path_field,
                                                        subcatchments = subcatchments,
                                                        subcatchments_id = subcatchment_id_field)
    #WG_Datei_Pfad | subcatchment_id | AREA
    result_voronoi_df = pandas.DataFrame([feat.attributes() for feat in result_voronoi.getFeatures()],
                                                columns = [field.name() for field in result_voronoi.fields()] )
    # QgsProject.instance().addMapLayer(result_voronoi)

    result_averages = calculate_wg_averages(df_paths = result_voronoi_df, subcatchment_id = new_sub_id,
                                            paths_column = path_field, area_id = AREA_FIELD)
    
    if output_filepath in ["", None] : output_filepath = QgsProcessingUtils.generateTempFilename('AggregatedWeatherGenValues.csv')
    result_averages.to_csv(output_filepath, sep="\t")

    return QgsVectorLayer(output_filepath, "WetterGenerator_Averaged")



def calculate_evap_timeseries(weather_generator_avgvalues : QgsVectorLayer,
                              wg_datetime : str, wg_subcatchment_id : str,
                              temp_min : str, temp_avg : str, temp_max : str,
                              humidity : str, solar_rad : str, wind_speed : str,
                              precipitation : str,
                              subcatchment_information : QgsVectorLayer,
                              subcatchment_id : str,
                              latitude : str,
                              height : str,
                              output_filepath : str) -> pandas.DataFrame:
    """
    Calculates the evapotranspiration from a weather_generator_avgvalues DataFrame:
    These parameters in the DF are related to a single subcatchment 
    TEMP: Average temperature [°C]
    LUFEU: Average humidity [percentage 0-100]
    GLOST: Average solar radiation [J/cm2]
    WIND: Average wind speed [m/s]
    NISCH: Precipitation [mm]

    
    Subcatchment_id, latitude and height are the columns that hold this information

    Latitude and height are related to a single subcatchment. They are an average of the subcatchment at its centroid.
    Returns an dataframe with date | EVAP
    """
    sub_df_sc = df_from_vlayer(subcatchment_information).set_index([subcatchment_id])[[subcatchment_id, latitude, height]]

    #Estimating min and max temperatures in case of missing column
    if temp_min == "": temp_min = temp_avg
    if temp_max == "": temp_max = temp_avg

    if temp_min == temp_avg:
        estimate_min = -2
    else: estimate_min = 0 

    if temp_max == temp_avg:
        estimate_max = +2
    else: estimate_max = 0
    print("temps", temp_min, temp_max, estimate_max)


    sub_df_wg = df_from_vlayer(weather_generator_avgvalues)
    sub_df_wg[wg_datetime] = sub_df_wg[wg_datetime].apply(lambda x: datetime.datetime.strptime(x, '%Y-%m-%d').date())
    sub_df_wg["day_of_year"] = sub_df_wg[wg_datetime].apply(lambda x : x.timetuple().tm_yday)

    sub_df_wg = sub_df_wg.set_index([wg_subcatchment_id, wg_datetime])

    #Merge values. Orphan rows will be kept for the record
    df_join = sub_df_wg.join(sub_df_sc, on = wg_subcatchment_id, how="left", lsuffix = "WG_", rsuffix= "SC_")

    df_join["EVAP"] = df_join.apply(lambda d: evapotranspiration(tavg = float(d[temp_avg]),
                                                                        tmin = float(d[temp_min]) - estimate_min, 
                                                                        tmax = float(d[temp_max]) + estimate_max,
                                                                        wind = float(d[wind_speed]),
                                                                        solar_rad = float(d[solar_rad]),
                                                                        hum_fraction = float(d[humidity])/100,
                                                                        latitude = float(d[latitude]),
                                                                        height = float(d[height]),
                                                                        day = d["day_of_year"])
                        , axis = 1)
    

    if output_filepath in ["", None] : output_filepath = QgsProcessingUtils.generateTempFilename('EVAP_Timeseries.csv')

    df_join.to_csv(output_filepath, sep = "\t", index = [wg_datetime, wg_subcatchment_id])    
    return QgsVectorLayer(output_filepath, "Evapotranspiration_Timeseries")




#------------INTERFACE

class PluginDialog(QDialog):

    #set-up of the dialog
    def __init__(self, iface, parent=None, flags=Qt.WindowFlags()):
        QDialog.__init__(self, parent, flags) #superclass
        uic.loadUi(UI_PATH, self)
        self.iface = iface
        
        self.tabWidget.setCurrentIndex(0)

        #Typing general
        self.button_help : QPushButton
        self.button_ok : QPushButton

        #Output
        self.output_browse : QPushButton
        self.output_filename : QLineEdit

        #Typing specific
        self.mMapLayerComboBox_Subcatchments : QgsMapLayerComboBox
        self.mMapLayerComboBox_Stations : QgsMapLayerComboBox
        self.mMapLayerComboBox_Timeseries : QgsMapLayerComboBox


        self.mFieldComboBoxSC : QgsFieldComboBox
        self.mFieldComboBox_Station_id : QgsFieldComboBox
        self.mFieldComboBox_TimeseriesDatetime : QgsFieldComboBox
 
        

        #---Averaging   
        self.button_help.clicked.connect(self.Help)
        self.button_ok.clicked.connect(self.exec_calculate_averages)
        self.output_browse.clicked.connect(self.onBrowseOutputButtonClicked)       


        #Auxiliary functions for autoselect
        def set_fid_sc(*args,**kwargs):
            self.mFieldComboBoxSC.setLayer(*args,**kwargs)
            try: self.mFieldComboBoxSC.setField("fid")
            except: pass
        
        def set_fid_stations(*args,**kwargs):
            for o in [self.mFieldComboBox_Station_id]:
                o.setLayer(*args,**kwargs)
                try: o.setField("fid")
                except: pass   

        def set_fid_timeseries(*args,**kwargs):
            for o in [self.mFieldComboBox_TimeseriesDatetime]:
                o.setLayer(*args,**kwargs)
                try: o.setField("fid")
                except: pass        
        

        
        #Update field
        self.mMapLayerComboBox_Subcatchments.layerChanged.connect(set_fid_sc)
        self.mMapLayerComboBox_Stations.layerChanged.connect(set_fid_stations) 
        self.mMapLayerComboBox_Timeseries.layerChanged.connect(set_fid_timeseries) 

        #Show crs
        self.mMapLayerComboBox_Subcatchments.setShowCrs(True)
        self.mMapLayerComboBox_Stations.setShowCrs(True)
        self.mMapLayerComboBox_Timeseries.setShowCrs(True)

        #Filter layer types
        self.mMapLayerComboBox_Subcatchments.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.mMapLayerComboBox_Stations.setFilters(QgsMapLayerProxyModel.PointLayer)
        # self.mMapLayerComboBox_Timeseries.setFilters(QgsMapLayerProxyModel.PointLayer)

        #Clean MaplayerComboBoxes
        self.mMapLayerComboBox_Subcatchments.setLayer(None)
        self.mMapLayerComboBox_Stations.setLayer(None)
        self.mMapLayerComboBox_Timeseries.setLayer(None)

        #Set subcatchment layer to selected layer
        self.mMapLayerComboBox_Stations.setLayer(iface.activeLayer())

        #Set default field
        self.mFieldComboBoxSC.setField("fid")


        #TAB: PTQ PIVOTING
        def set_p_stations(*args,**kwargs):
            for o in [
                        self.mFieldComboBox_Datetime_p,
                        self.mFieldComboBox_Subcatchment_p,
                        self.mFieldComboBox_Values_p,
                      ]:
                o.setLayer(*args,**kwargs)
                try: o.setField("fid")
                except: pass   
        def set_t_stations(*args,**kwargs):
            for o in [
                        self.mFieldComboBox_Datetime_t,
                        self.mFieldComboBox_Subcatchment_t,
                        self.mFieldComboBox_Values_t,
                      ]:
                o.setLayer(*args,**kwargs)
                try: o.setField("fid")
                except: pass   

        self.mMapLayerComboBox_Precipitation : QgsMapLayerComboBox
        self.mMapLayerComboBox_Temperature : QgsMapLayerComboBox

        self.mFieldComboBox_Datetime_p : QgsFieldComboBox
        self.mFieldComboBox_Subcatchment_p : QgsFieldComboBox
        self.mFieldComboBox_Values_p : QgsFieldComboBox
        self.mFieldComboBox_Datetime_t : QgsFieldComboBox
        self.mFieldComboBox_Subcatchment_t : QgsFieldComboBox
        self.mFieldComboBox_Values_t : QgsFieldComboBox
        #Pivoted
        self.output_browse_pivot : QPushButton
        self.output_filename_pivot : QLineEdit
        self.button_help_2 : QPushButton
        self.button_ok_ptq : QPushButton
        self.output_browse_pivot.clicked.connect(self.onBrowseOutputTXTButtonClicked)       
        self.button_help_2.clicked.connect(self.Help)
        self.button_ok_ptq.clicked.connect(self.exec_calculate_pivot)



        self.mMapLayerComboBox_Precipitation.layerChanged.connect(set_p_stations)
        self.mMapLayerComboBox_Temperature.layerChanged.connect(set_t_stations)
        self.mMapLayerComboBox_Precipitation.setLayer(None)
        self.mMapLayerComboBox_Temperature.setLayer(None)


        self.mMapLayerComboBox_Precipitation.setLayer(iface.activeLayer())
        self.mMapLayerComboBox_Temperature.setLayer(iface.activeLayer())


        #TAB : VORONOI WEATHER GENERATOR
        self.mMapLayerComboBox_WG_Pfad : QgsMapLayerComboBox
        self.mFieldComboBox_Station_path_WG : QgsFieldComboBox

        self.mMapLayerComboBox_Subcatchments_WG : QgsMapLayerComboBox
        self.mFieldComboBoxSC_WG : QgsFieldComboBox

        self.output_filename_WG : QLineEdit
        self.output_browse_WG : QPushButton
        self.button_help_WG_AVG : QPushButton
        self.button_ok_WG : QPushButton

        def set_pfad_layer(*args,**kwargs):
            for o in [
                        self.mFieldComboBox_Station_path_WG
                      ]:
                o.setLayer(*args,**kwargs)
        def set_subcatchment_layer(*args,**kwargs):
            for o in [
                        self.mFieldComboBoxSC_WG
                      ]:
                o.setLayer(*args,**kwargs)
 
        
        self.mMapLayerComboBox_WG_Pfad.layerChanged.connect(set_pfad_layer)
        self.mMapLayerComboBox_Subcatchments_WG.layerChanged.connect(set_subcatchment_layer)
        self.mMapLayerComboBox_WG_Pfad.setShowCrs(True)
        self.mMapLayerComboBox_Subcatchments_WG.setShowCrs(True)

        #Filter layer types
        self.mMapLayerComboBox_WG_Pfad.setFilters(QgsMapLayerProxyModel.PointLayer)
        self.mMapLayerComboBox_Subcatchments_WG.setFilters(QgsMapLayerProxyModel.PolygonLayer)

        self.mMapLayerComboBox_WG_Pfad.setLayer(iface.activeLayer())
        self.mMapLayerComboBox_Subcatchments_WG.setLayer(None)

        self.output_browse_WG.clicked.connect(self.onBrowseOutputVoronoiWeatherGen)       
        self.button_help_WG_AVG.clicked.connect(self.Help)
        self.button_ok_WG.clicked.connect(self.exec_calculate_VoronoiWeatherGen)


        #TAB : EVAP 
        self.mMapLayerComboBox_EVAP : QgsMapLayerComboBox
        self.mFieldComboBox_Datetime_EVAP : QgsFieldComboBox
        self.mFieldComboBox_subcatchment : QgsFieldComboBox
        self.mFieldComboBox_tempmin : QgsFieldComboBox
        self.mFieldComboBox_tempavg : QgsFieldComboBox
        self.mFieldComboBox_tempmax : QgsFieldComboBox
        self.mFieldComboBox_humidityfr : QgsFieldComboBox
        self.mFieldComboBox_solarrad : QgsFieldComboBox
        self.mFieldComboBox_windspeed : QgsFieldComboBox
        self.mFieldComboBox_precipitationavg : QgsFieldComboBox

        self.mMapLayerComboBox_EVAP_SC : QgsMapLayerComboBox
        self.mFieldComboBox_EVAP_SC_id : QgsFieldComboBox
        self.mFieldComboBox_EVAP_SC_latitude : QgsFieldComboBox
        self.mFieldComboBox_EVAP_SC_height : QgsFieldComboBox
 
        self.output_filename_EVAP : QLineEdit
        self.output_browse_EVAP : QPushButton
        self.button_help_EVAP : QPushButton
        self.button_ok_EVAP : QPushButton

        def set_evap_layer(*args,**kwargs):
            for o in [
                        self.mFieldComboBox_Datetime_EVAP,
                        self.mFieldComboBox_subcatchment,
                        self.mFieldComboBox_tempmin,
                        self.mFieldComboBox_tempavg,
                        self.mFieldComboBox_tempmax,
                        self.mFieldComboBox_humidityfr,
                        self.mFieldComboBox_solarrad,
                        self.mFieldComboBox_windspeed,
                        self.mFieldComboBox_precipitationavg,
                    ]:
                o.setLayer(*args,**kwargs)

        def set_information_layer(*args, **kwargs):
            for o in [
                        self.mFieldComboBox_EVAP_SC_id,
                        self.mFieldComboBox_EVAP_SC_latitude,
                        self.mFieldComboBox_EVAP_SC_height,
            ]:
                o.setLayer(*args,**kwargs)

        self.mMapLayerComboBox_EVAP.layerChanged.connect(set_evap_layer)
        self.mMapLayerComboBox_EVAP_SC.layerChanged.connect(set_information_layer)

        self.mMapLayerComboBox_EVAP.setLayer(iface.activeLayer())

        self.mMapLayerComboBox_EVAP.setShowCrs(True)
        self.mMapLayerComboBox_EVAP_SC.setShowCrs(True)


        self.output_browse_EVAP.clicked.connect(self.onBrowseOutputEVAP)       
        self.button_help_EVAP.clicked.connect(self.Help)
        self.button_ok_EVAP.clicked.connect(self.exec_calculate_evap)


    def Help(self):
        webbrowser.open(HELP_PATH)

    def __del__(self):
        pass


    #SAVING FILES
    def onBrowseOutputButtonClicked(self):
        line = self.output_filename
        current_filename = line.text()
        if current_filename == "": current_filename = os.path.join(QgsProject.instance().absolutePath(),"AggregatedSubcatchmentTimeseries.tsv")
        new_filename, __ = QFileDialog.getSaveFileName(self.iface.mainWindow(), 'Choose where to save the STATIONS AVERAGED VALUES', current_filename, filter = "Tab Separated Values (*.tsv)")
        if new_filename != '':
            line.setText(new_filename)

    def onBrowseOutputTXTButtonClicked(self):
        line = self.output_filename_pivot
        current_filename = line.text()
        if current_filename == "": current_filename = os.path.join(QgsProject.instance().absolutePath(),"AggregatedSubcatchmentTimeseries_PTQ.tsv")
        new_filename, __ = QFileDialog.getSaveFileName(self.iface.mainWindow(), 'Choose where to save the EVAP PTQ PIVOTED file', current_filename, filter = "Tab Separated Values (*.tsv)")
        if new_filename != '':
            line.setText(new_filename) 

    def onBrowseOutputVoronoiWeatherGen(self):
        line = self.output_filename_WG
        current_filename = line.text()
        if current_filename == "": current_filename = os.path.join(QgsProject.instance().absolutePath(),"EVAP_parameters_weathergenerator_avg.tsv")
        new_filename, __ = QFileDialog.getSaveFileName(self.iface.mainWindow(), 'Choose where to save the EVAP WEATHER GENERATOR AVERAGE TIMESERIES file', current_filename, filter = "Tab Separated Values (*.tsv)")
        if new_filename != '':
            line.setText(new_filename) 

    def onBrowseOutputEVAP(self):
        line = self.output_filename_EVAP
        current_filename = line.text()
        if current_filename == "": current_filename = os.path.join(QgsProject.instance().absolutePath(),"EVAP_subcatchment_evapotranspiration_avg.tsv")
        new_filename, __ = QFileDialog.getSaveFileName(self.iface.mainWindow(), 'Choose where to save the EVAP BY SUBCATCHMENT TIMESERIES file', current_filename, filter = "Tab Separated Values (*.tsv)")
        if new_filename != '':
            line.setText(new_filename) 



    def exec_calculate_averages(self):
        """Runs an aggregator of values by weight using voronoi"""
        #Check output filepath validity
        output_filepath = self.output_filename.text()

        if output_filepath != "":
            if pathlib.Path(output_filepath).is_dir() : raise ValueError("Output filepath for the aggregated values not valid because it is a folder! Enter a valid filepath")

        
        result = calculate(stations = self.mMapLayerComboBox_Stations.currentLayer(),
                            stations_id = self.mFieldComboBox_Station_id.currentField(),
                            subcatchments = self.mMapLayerComboBox_Subcatchments.currentLayer(),
                            subcatchments_id = self.mFieldComboBoxSC.currentField(),
                            data_layer = self.mMapLayerComboBox_Timeseries.currentLayer(),
                            data_datum_field = self.mFieldComboBox_TimeseriesDatetime.currentField(),
                            output_filepath = output_filepath)
       

        if result is None: raise ValueError("No result! Something went wrong!!")                 
        QgsProject.instance().addMapLayer(result)

        self.label_completed.setText("Success!")
        self.button_cancel.setText("Exit")

        return True
    

    def exec_calculate_pivot(self):
        """Merges and pivots a Datetime | id | value   precipitation and temperature file
          in the repeated form   Datetime | P | T | Q | P | T | Q for each id
        """
        output_filepath = self.output_filename_pivot.text()
        if output_filepath != "":
            if pathlib.Path(output_filepath).is_dir() : raise ValueError("Output filepath for Pivoted values not valid because it is a folder! Enter a valid filepath")

        result = merge_pt(layer_p = self.mMapLayerComboBox_Precipitation.currentLayer(),
                          datump = self.mFieldComboBox_Datetime_p.currentField(),
                          idp = self.mFieldComboBox_Subcatchment_p.currentField(),
                          valuep = self.mFieldComboBox_Values_p.currentField(),
                          layer_t = self.mMapLayerComboBox_Temperature.currentLayer(),
                          datumt = self.mFieldComboBox_Datetime_t.currentField(),
                          idt = self.mFieldComboBox_Subcatchment_t.currentField(),
                          valuet = self.mFieldComboBox_Values_t.currentField(),
                          output_filepath = output_filepath
                          )
        
        if result is None: raise ValueError("No result! Something went wrong!!")                 
        QgsProject.instance().addMapLayer(result)

        self.label_completed_2.setText("Success!")
        self.button_cancel_ptq.setText("Exit")
        

        return True

    def exec_calculate_VoronoiWeatherGen(self):
        """Calculates the voronoi averaged by area weather generator parameters for each subcatchment"""
        print("wg")
        output_filepath = self.output_filename_WG.text()
        if output_filepath != "":
            if pathlib.Path(output_filepath).is_dir() : raise ValueError("Output filepath for Voronoi Weather Generator averages not valid because it is a folder! Enter a valid filepath")


        result = calculate_weather_generator_voronoi_avg(stations = self.mMapLayerComboBox_WG_Pfad.currentLayer(),
                                                         path_field = self.mFieldComboBox_Station_path_WG.currentField(),
                                                         subcatchments = self.mMapLayerComboBox_Subcatchments_WG.currentLayer(),
                                                         subcatchment_id_field = self.mFieldComboBoxSC_WG.currentField(),
                                                         output_filepath = output_filepath,
                                                         )
        
        QgsProject.instance().addMapLayer(result)
        self.label_completed_3.setText("Success!")
        self.button_cancel_WG.setText("Exit")


    def exec_calculate_evap(self):
        """Calculates the evapotranspiration for the subcatchments.
        """
        output_filepath = self.output_filename_EVAP.text()
        if output_filepath != "":
            if pathlib.Path(output_filepath).is_dir() : raise ValueError("Output filepath for Evapotranspiration calculation not valid because it is a folder! Enter a valid filepath")



        result = calculate_evap_timeseries(weather_generator_avgvalues = self.mMapLayerComboBox_EVAP.currentLayer(),
                                            wg_datetime = self.mFieldComboBox_Datetime_EVAP.currentField(),
                                            wg_subcatchment_id = self.mFieldComboBox_subcatchment.currentField(),
                                            temp_min = self.mFieldComboBox_tempmin.currentField(),
                                            temp_avg = self.mFieldComboBox_tempavg.currentField(),
                                            temp_max = self.mFieldComboBox_tempmax.currentField(),
                                            humidity = self.mFieldComboBox_humidityfr.currentField(),
                                            solar_rad = self.mFieldComboBox_solarrad.currentField(),
                                            wind_speed = self.mFieldComboBox_windspeed.currentField(),
                                            precipitation = self.mFieldComboBox_precipitationavg.currentField(),
                                            subcatchment_information = self.mMapLayerComboBox_EVAP_SC.currentLayer(),
                                            subcatchment_id = self.mFieldComboBox_EVAP_SC_id.currentField(),
                                            latitude = self.mFieldComboBox_EVAP_SC_latitude.currentField(),
                                            height = self.mFieldComboBox_EVAP_SC_height.currentField(),
                                            output_filepath = output_filepath
                                            )
        QgsProject.instance().addMapLayer(result)
        self.label_completed_4.setText("Success!")
        self.button_cancel_EVAP.setText("Exit")


class EvapotranspirationPTQTool(object):
#Menu entry and plugin window launcher
    def __init__(self, iface):
        self.iface = iface
        self.dialog = None
        self.cancel = False
        self.act = QAction('Evapotranspiration PTQ', iface.mainWindow())
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
        self.dialog.button_cancel_ptq.clicked.connect(self.button_cancel_clicked)
        self.dialog.button_cancel_WG.clicked.connect(self.button_cancel_clicked)
        self.dialog.button_cancel_EVAP.clicked.connect(self.button_cancel_clicked)
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