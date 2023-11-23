#TESTING
#TODO: Using an actual library


import datetime
import pathlib
from typing import Callable

import numpy
import pandas
from ClassEinleiter import Einleiter
from ClassEinleiterLoader import EinleiterLoader
from ClassWaterPatterns import PatternDaily, PatternWeekly, PatternHolder
import BoundaryConditionEinleiter as BCE
import tools as tools

try:
    from qgis.core import (QgsApplication, QgsProcessing, QgsProcessingUtils,
                        QgsVectorDataProvider,QgsVectorLayer,# for modifying attributes
                        QgsFeature,QgsField, QgsGeometry, QgsCoordinateReferenceSystem
                        )
    from qgis.PyQt.QtCore import QVariant #QVariant.Int / String / Double
except:
    pass #

BASEDIR = pathlib.Path(__file__).parent.absolute().resolve().as_posix()

def tests_ClassWaterPatterns():
    dailyp = PatternDaily(factor = [1 for n in range(24)])
    assert dailyp.get_value(fraction=0) == 1
    assert dailyp.get_value(fraction=0.5) == 1
    assert dailyp.get_value(fraction=1) == 1

    week = [1, 1, 1, 1, 1, 0, 0] #all but satsun
    weeklyp = PatternWeekly(factor = week ) 
    wfactors = [weeklyp.get_value(fraction = n/7) for n in range(7)]
    assert wfactors[5] == 0 and wfactors[6] == 0   
    assert wfactors[0] > 1 and wfactors[1] >1   
    assert weeklyp.get_value(fraction=-2/7) == 0 #Sat
    assert weeklyp.get_value(fraction=-3/7) >= 1 #Fri

    holder = PatternHolder(daily = dailyp, weekly=weeklyp)

    assert holder.get_value(day_fraction=0.5, weekday=0) >1
    assert holder.get_value(day_fraction=0.5, weekday=6) == 0 #Sun
    assert holder.get_value(day_fraction=0.5, weekday=5) == 0 #Sat

    dates = [datetime.datetime(2023,11,3, 12,0), datetime.datetime(2023,11, 4 , 12,0)] #Friday and Saturday
    assert numpy.allclose(holder.get_factors(dates = dates) , numpy.array([wfactors[4], wfactors[5]]))

    holder_empty = PatternHolder()
    assert holder_empty.get_value(day_fraction=0, weekday=0) == 1

    holder_none = PatternHolder(daily=None, weekly=None)
    assert holder_none.get_value(day_fraction=0, weekday=0) == 1

    pass


def tests_ClassEinleiter():
    data = dict(id = "HSMD", lat_long = (54.004, 11.4422), )
    obj1 = Einleiter(**data, abf_constant_L_s= 100, patterns = PatternHolder()) #default pttern
    obj2 = Einleiter(**data, abf_constant_L_s= 100, patterns = PatternHolder(weekly=PatternWeekly(factor = [1,1,1,1,1,0,0]))) #default pttern

    #Test the day of the week and hours, friday /saturday at 12:00
    dates =  [datetime.datetime(2023,11,3, 12,0), datetime.datetime(2023,11, 4 , 12,0)]

    assert numpy.allclose(obj1.estimate_abfluss(dates = dates).values, numpy.array([100.0, 100.0]))
    assert numpy.allclose(obj2.estimate_abfluss(dates = dates).values, numpy.array([140.0, 0.0]))
    pass


def tests_ClassEinleiterLoader():
    """Tests a made up importer function
    Files should have the format:
    id; lat; long; abflussjahr_m3; ew(120L); constantabfluss_l/s; filepath_patterndaily; filepath_patternweekly"""
    lines = [
            "a;54.003;13.00;;;100;;",
            "b;54.003;13.00;;;100;dailypattern.txt;",
    ]

    line0 = lines[0].split(";")
    assert len(line0) == 8
    lines_split = [l.split(";") for l in lines]

    test_csv = pathlib.Path(BASEDIR).joinpath("tests_data/test_einleiters.csv").absolute().resolve().as_posix()
    test_pattern = pathlib.Path(BASEDIR).joinpath("tests_data/dailypattern.txt").absolute().resolve().as_posix()

    loader = EinleiterLoader(path_csv = test_csv)
    einleiter = loader.import_einleiter() #Forcing to use a line split
    
    #Check if pattern is correctly loaded. Static function
    pattern = EinleiterLoader.get_pattern_content(pattern_path= test_pattern, length = 24 )
    assert pattern.factor[11]>1 #12h above average. Note 0000 to 0059 is [0]

    e0, e1 = einleiter[0], einleiter[1]
    assert e0.abf_constant_L_s == 100
    assert e0.estimate_abfluss(dates = [datetime.datetime(2022, 1, 1, 11, 0)]).values == [100] #Factor 1

    assert e1.abf_constant_L_s == 100
    assert e1.estimate_abfluss(dates = [datetime.datetime(2022, 1, 1,   0, 10)]).values      == [0]
    assert e1.estimate_abfluss(dates = [datetime.datetime(2022, 1, 1,   11, 12)]).values[0]  > 100 #should be higher than the average in the pattern


    #Reading the  whole file
    loader2 = EinleiterLoader(path_csv = test_csv)
    for (e0, e1, e2) in [loader2.import_einleiter()]:
        assert e0.estimate_abfluss(dates = [datetime.datetime(2023, 11, 5, 11, 0)]).values[0] == 100 #No pattern
        assert e1.estimate_abfluss(dates = [datetime.datetime(2023, 11, 5, 11, 11)]).values[0] > 100 #Only daily pattern
        assert e2.estimate_abfluss(dates = [datetime.datetime(2023, 11, 5, 11, 11)]).values[0] == 0 #Daily and weekly pattern (no Saturday)

    pass

def tests_BoundaryConditionEinleiter():

    hours = [0, 1]
    abf = [0.22345, 0.33333]
    bc = 1
    
    soll = "!BEGIN\n1 2 point #\n0 0.2235\n1 0.3333\n!END\n\n"
    ist  = BCE.bc_to_text(hours = hours, abflüsse=abf, bc = bc, precision = 4)
    assert soll == ist

    path_einleiter = pathlib.Path(BASEDIR).joinpath("tests_data/test_einleiters.csv").absolute().resolve().as_posix()
    path_inflows = pathlib.Path(BASEDIR).joinpath("tests_data/test_manual_inflows.txt").absolute().resolve().as_posix()
    path_save_to = pathlib.Path(BASEDIR).joinpath("tests_data/generated_boundary_condition.txt").absolute().resolve().as_posix()

    date_begin = datetime.datetime(2022,11,6,0)
    BCE.generate_boundary_conditions(path_einleiter_data = path_einleiter,
                                    path_zuflusse_Ls = path_inflows,
                                    date_begin = date_begin,
                                    date_end = datetime.datetime(2022,12,13,0), #1 week
                                    path_save_to = path_save_to,
                                    )
    
    
    #Check that the generated file is correct
    lines : list[str]
    with open(path_save_to, "r") as f:
        ls = f.readlines()
        lines = [l.rstrip() for l in ls]
    file = BCE.read_zufluss_file(lines = lines, datum_time = date_begin)

    assert file[1][0] [datetime.datetime(2022,11,6, 7 )] > 100 #100 + 50

    pass



def create_xsections_einleiter() -> tuple[QgsVectorLayer, QgsVectorLayer]:
    """
    Example QgsVectorLayers for testing. Returns XSections, Einleiter.
    Einleiter with EL_id 3 is closer to xsection with profile_glob_id 1
    Coordinates in the south of Magdeburg
    """
 
    def set_crs(vl : QgsVectorLayer, crsid : int) -> None:
        crs = QgsCoordinateReferenceSystem()
        crs.createFromId(crsid)
        vl.setCrs(crs)
    
    #CROSSSECTIONS
    xsections = QgsVectorLayer("multilinestring", "temp_xsections", "memory")
    set_crs(xsections, 25832)

    pr = xsections.dataProvider()
    pr.addAttributes([
                        QgsField("profile_glob_id", QVariant.Int),
                    ])
    xsections.updateFields() 

    features_xsections = [
                    (1,	"MULTILINESTRING((285970.324041 5762901.918281, 286583.751068 5763159.338551, 287876.329447 5763408.543281))"),
                    (2,	"MULTILINESTRING((285849.829447 5763827.535848, 286471.472014 5763882.306118, 287495.676068 5763950.768956))")
                ]

    for globid, line  in features_xsections:
        f = QgsFeature()
        f.setGeometry(QgsGeometry.fromWkt(line))
        f.setAttributes([globid])
        pr.addFeature(f)
        xsections.updateExtents() 
    

    #EINLEITER
    einleiter = QgsVectorLayer("Point", "temp_einleiter", "memory")
    set_crs(einleiter, 25832)

    pr = einleiter.dataProvider()
    pr.addAttributes([
                        QgsField("EL_id", QVariant.String),
                    ])
    einleiter.updateFields() 

    features_einleiter = [
                            (3, "POINT(288175,5763226)"), #closer to id 1
                            (4, "POINT(285654,5763999)") #closer to id 2
        ]
    
    for el_id, line  in features_einleiter:
        f = QgsFeature()
        f.setGeometry(QgsGeometry.fromWkt(line))
        f.setAttributes([el_id])
        pr.addFeature(f)
        einleiter.updateExtents() 

    return xsections, einleiter

def test_read_zufluss():
    file = [
            "!BEGIN",
            "5 26448 point #Einleiter id b 2020-November-06 to 2023-November-13",
            "0 0.0000",
            "1 50.0000",
            "2 50.0000",
            "!END"
            ]
    result = BCE.read_zufluss_file(lines = file, datum_time = datetime.datetime(2022,5,5,1,0))

def test_get_zufluss_lines():
    """
    Read a file that should be utf-8 with ' ' space as separator. But has \t as a separator instead
    """
    bad_utf8_tabs = pathlib.Path(BASEDIR).joinpath("tests_data/badly_formatted_inflows.txt").absolute().resolve().as_posix()
    data = BCE.get_zufluss_file_lines(path = bad_utf8_tabs)
    assert not "\t" in data

    lines = BCE.read_zufluss_file(lines = data, datum_time = datetime.datetime(2022,5,5,1,0))

def tests_tools():
    """
    Tests the closest crosssection available to an einleiter
    """
    #EINLEITER AND CLOSEST RIVER CROSSSECTION
    xsections, einleiter = create_xsections_einleiter()

    # result = tools.find_closest_river_profiles_id(einleiter = einleiter, xsections = xsections,
    #                                                 einleiter_col = "EL_id", xsections_col = "profile_glob_id")
    
    # assert result[3] == 1
    # assert result[4] == 2
    
    
    #SUM OF TIMESTAMPED SERIES AND VALUES
    dates1 = [datetime.datetime(2022,2,2,10), datetime.datetime(2022,2,2,15), datetime.datetime(2022,2,2,20)]
    values1 = [10, 20, 0]
    dates2 = [datetime.datetime(2022,2,2,13), datetime.datetime(2022,2,2,17), datetime.datetime(2022,2,2,23)]
    values2 = [3, 4, 5]

    dates_expected = [datetime.datetime(2022,2,2,10), datetime.datetime(2022,2,2,13), datetime.datetime(2022,2,2,15),
                      datetime.datetime(2022,2,2,17), datetime.datetime(2022,2,2,20), datetime.datetime(2022,2,2,23)]
    values_expected = [10, 13, 23, 24, 4, 5]
    series1 = pandas.Series({d:v for d,v in zip(dates1,values1)})
    series2 = pandas.Series({d:v for d,v in zip(dates2,values2)})
    series_expected = pandas.Series({d:v for d,v in zip(dates_expected,values_expected)})
    result = tools.sum_timestamped_series(series = [series1, series2])
    assert result.equals(series_expected)


    #TIMESTAMPED SERIES TO HOURS
    hours, values = tools.timestamp_to_hourlists(series = result, datum = datetime.datetime(2022,2,2,8))
    assert hours == [2, 5, 7, 9, 12, 15]


    #Verify that big timestamps work
    future = datetime.datetime(6544, 2, 2, 13, 45)
    future_series = pandas.Series({future:1})
    future_hourlist, values = tools.timestamp_to_hourlists(series = future_series, datum = datetime.datetime(2000,1,1))
    assert  future_hourlist[0] > (6544-2000)*365*24

def test_generate_boundary_conditions_text():
    datum_base = datetime.datetime(2000,1,1,12,45)
    future = datetime.datetime(6544, 2, 2, 13, 45)
    future_series = pandas.Series({future:100})
    empty_series = pandas.Series()

    inflows = {}
    inflows[5] = [future_series, empty_series]
    result = BCE.generate_boundary_conditions_text(inflows = inflows, datum = datum_base)

def tests():
    tests_ClassWaterPatterns()
    tests_ClassEinleiter()
    tests_ClassEinleiterLoader()
    tests_tools()
    test_get_zufluss_lines()
    test_read_zufluss()
    tests_BoundaryConditionEinleiter()

    pass





if __name__ == "__main__":
    tests() #use an actual library for this
    pass