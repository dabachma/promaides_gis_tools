import datetime
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
        indices.update(s.index.to_list())
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
    """
    diff : datetime.timedelta = series.index - datum
    days, seconds = diff.days, diff.seconds,
    hours = days * 24 + seconds // 3600  
    
    values = series.values.tolist()

    return hours.to_list(), values

if __name__ == "__main__":

    pass