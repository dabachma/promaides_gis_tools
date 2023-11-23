import datetime
from typing import Union
import numpy
import pandas
from qgis.core import QgsVectorLayer

EINLEITER_ID = str
PROFILE_INDEX = str
#TODO
def find_closest_river_profiles_id(einleiter : QgsVectorLayer, xsections : QgsVectorLayer, einleiter_col : str, xsections_col : str) -> dict[EINLEITER_ID, PROFILE_INDEX]:
    """
    #TODO
    Returns a dictionary with the einleiter_id and the boundary condition associated with the closest river profile
    Einleiter is a Point Layer
    xsections is a multilinestring layer.
    xsections_col is the name of the column that is the boundary condition for that profile
    einleiter_col is an identificator for the einleiter.
    """
    return {}

def index_to_datetime(index : pandas.Index) -> Union[numpy.ndarray, list[datetime.datetime]]:
    if numpy.issubdtype(index.dtype, numpy.datetime64) :
        datetimes = index.to_pydatetime()
    elif isinstance(index, pandas.DatetimeIndex):
        datetimes = index.to_pydatetime()
    else:
        datetimes = index.values
    return datetimes

#TODO
def sum_timestamped_series(series : list[pandas.Series]) -> pandas.Series:
    """
    Sums the values of timestamped series only when the timestamps are simultaneous.
    Example:
    t v
    0 10
    1 10
    2 10
    3 0
    and
    t v
    1.5 2
    4.5 3
    result:
    t v
    0 10
    1 10
    1.5 12
    2 12
    3 2
    4.5 3
    """

    #Finding all the indexes
    indices : set[datetime.datetime] = set()
    for s in series:
        mod_index = index_to_datetime(index = s.index)
        indices.update(mod_index)

    indices = sorted(list(indices))
    values = [0 for n in range(len(indices))]
    
    #For each index, get value of index <= to that index. Sum
    for n, time in enumerate(indices):
        for s in series:
            if time in s:           values[n] += s[time] # if the time is in the series just get the value
            elif time < s.index[0]: continue # timestamp not in range.
            elif time > s.index[-1]: values[n] += s[s.index[-1]]

            #get value immediately smaller than the time
            else: #Timestamp is in the middle. get latest smaller value. Timestamp is not in the series.
                idx = s.index.get_indexer([time], method='ffill') #Undocumented method parameter
                values[n] += s[s.index[idx]].item()

                
    val = pandas.Series({i:v for i,v in zip(indices,values)})

    return val

def timestamp_to_hourlists(series : pandas.Series, datum : datetime.datetime) -> tuple[list[int], list[float]]:
    """
    Turns a Series with timestamp index into a list of hours and list of values.
    pandas Timestamps cant go farther than 2200y so we try to convert them to python datetime objects
    """
    datetimes = index_to_datetime(series.index)
        
    diffs : list[datetime.timedelta] = datetimes - datum
    days, seconds = numpy.array(list(zip(*[[d.days, d.seconds] for d in diffs])))
    hours = days * 24 + seconds // 3600  
    
    values = series.values.tolist()

    return hours.tolist(), values

if __name__ == "__main__":

    pass