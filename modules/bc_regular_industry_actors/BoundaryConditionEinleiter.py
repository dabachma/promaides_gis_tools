#Function that takes a set of parameters and generates the corresponding boundary conditions

from dataclasses import dataclass
import datetime
import pathlib
from matplotlib.backend_tools import ToolSetCursor
import pandas

from qgis.core import QgsVectorLayer

try:
    from .ClassEinleiter import Einleiter
    from .ClassEinleiterLoader import EinleiterLoader, HEADERS, HEADERS_pretty
    from . import tools
except:
    from ClassEinleiter import Einleiter
    from ClassEinleiterLoader import EinleiterLoader, HEADERS, HEADERS_pretty
    import tools



DISTANCE = float
PROFILE_INDEX = int
BC_INDEX = int


def get_database_table(connection_params)->pandas.DataFrame:
    """
    #TODO
    Gets the database table with the Querschnitte information
    """

    pass




def bc_to_text(hours : list[int], abflüsse : list[float], bc : int, comment : str = "", precision : int = 6)->str:
    """
    Abflüsse and Stunden into the boundary condition format
    bc: boundary condition number, has to be continuous
    precision: how many decimals for the Abflüße L/s
    """
    assert len(hours) == len(abflüsse)
    num_points = len(hours)
    _BEGIN = "!BEGIN\n"
    _INFO = f"{bc} {num_points} point #{comment}\n"
    _END = "!END\n\n"

    mid_text = "".join([f"{h} {q:.{precision}f}\n" for h,q in zip(hours, abflüsse)])
    text = _BEGIN + _INFO + mid_text + _END

    return text



def read_zufluss_file(lines : list[str], datum_time : datetime.datetime) -> dict[int, list[pandas.Series]]:
    """
    Reads the txt file with the !BEGIN and !END values for the hours and turns it into a time series
    datum_time: datetime object with hour precision. The hours from the beginning will be summed up to this one
    """
    data = lines    
    bc_series : dict[int, list[pandas.Series]] = {}

    #find the pairs of !BEGIN and !END
    pairs : list[tuple[int,int]] = []
    i,j = 0,0
    for n, line in enumerate(data):
        if line.startswith("!BEGIN"):   i = n
        if line.startswith("!END"):     j = n; pairs.append((i,j)); i,j = 0,0
    
    #Boundary Condition index to int. #skip !BEGIN, keep bc, skip comment and skip !END
    groups = [(int(data[i+1].split(" ")[0]), data[i+2:j]) for i,j in pairs] 
    
    #Pre-populate the bc
    for bc, _ in groups: 
        bc_series[bc] = []

    #Populate the bc
    for bc_num, group in groups:
        hour_value = [l.split(" ") for l in group]
        hours = [datum_time + datetime.timedelta(hours = float(h)) for h,v in hour_value]
        values = [v for h,v in hour_value]
        series = pandas.Series({h:float(v) for h,v in zip(hours,values)})
        bc_series[bc_num].append(series)


    return bc_series
    

def einleiter_to_qgsvectorlayer(einleiter : list[Einleiter]) -> QgsVectorLayer:
    """
    #TODO
    Takes a list of Einleiter and returns a QgsVectorLayer
    """
    return None



def generate_boundary_conditions_text(inflows : dict[int, list[pandas.Series]], datum : datetime.datetime) -> str:
    """
    Generates the boundary condition file for each bc:int, summing up the timestamped series of flow values.
    The units must agree (L/s)
    """
    text = ""

    for bc, series_list in inflows.items():
        combined_series = tools.sum_timestamped_series(series = series_list)
        hours, values = tools.timestamp_to_hourlists(combined_series, datum = datum)
        sub_text = bc_to_text(hours = hours, abflüsse = values, bc = bc, comment = f"BC {bc}. Sum of {len(series_list)} different inflows.")
        text += sub_text

    return text

def generate_boundary_conditions(path_einleiter_data : str,
                                path_zuflusse_Ls : str,
                                date_begin : datetime.datetime, date_end : datetime.datetime,
                                path_save_to : str,
                                einleiter_col : str = "EL_id",  #TODO Not implemented
                                xsections : QgsVectorLayer = None,
                                xsections_col : str = "profile_glob_id"
                                ) -> tuple[bool, list[str]]:
    """
    Takes the necessary data to generate the boundary condition file for the Einleiter/Entnehmer and generates it.
    path_einleiter_data : csv file with a specific order. Check documentation.
    path_zuflusse_Ls : manually created zuflusse. Will be read as a dict[int, pandas.Series], natural timestamped flows of rivers
    xsections: the QgsVectorLayer with the crosssections. Each einleiter will have one of these assigned to them if their BCindex is not specified
    xsections_id : name of the id associated to the boundary condition in the cross sections layer
    
    Each boundary condition index is associated with one xsection id. The final flows will be the sum of all flows
    coming into that boundary condition

    Finds all the boundary conditions included in the Einleiter and Inflow files and recreates the summed-up version of them
    Returns whether successful and list of errors
    """
    #check for errors
    errors = []
    if not pathlib.Path(path_einleiter_data).exists() : errors.append("Invalid Industry input.")
    if not pathlib.Path(path_zuflusse_Ls).exists() : errors.append("Invalid Inflows input.")
    if date_end <= date_begin : errors.append("Invalid dates.")
    if len(errors) > 0 : return False, errors


    #datetime used to generate the flow with the patterns
    diff = date_end - date_begin
    days, seconds = diff.days, diff.seconds,
    hours = days * 24 + seconds // 3600    
    hour_series = list(range(hours)) #0, 1... n hours
    dates = [date_begin + datetime.timedelta(hours=h) for h in hour_series] 
    

    #Get Einleiters and Zufluss assigned to Crosssections
    

    #Get Zufluss boundary conditions
    data : list[str] = []
    with open(path_zuflusse_Ls, "r") as f:
        ls = f.readlines()
        data = [l.rstrip() for l in ls]
    bc_zuflusse : dict[int, list[pandas.Series]] = read_zufluss_file(lines = data, datum_time = date_begin)


    #Get Einleiter boundary conditions
    loader = EinleiterLoader(path_csv = path_einleiter_data)
    einleiters = loader.import_einleiter()

    #Get the profile index associated to each Einleiter. Get the Boundary condition index associated with each profile
    einleiter_qgis = einleiter_to_qgsvectorlayer(einleiter = einleiters)
    profile_index = tools.find_closest_river_profiles_id(einleiter = einleiter_qgis, xsections = xsections, einleiter_col = einleiter_col, xsections_col = xsections_col)
    boundary_index_profile : dict[PROFILE_INDEX, BC_INDEX] = {}

    bc_einleiter : dict[int, list[pandas.Series]] = {}
    for num, einleiter in enumerate(einleiters):
        #Get Abflüße
        abf = einleiter.estimate_abfluss(dates = dates)
        if not bool(einleiter.bc) : #DEBUG
            einleiter.bc = boundary_index_profile.get(profile_index.get(einleiter.id), -1) #raise ValueError("Missing boundary conditions") #DEBUG

        bc = int(einleiter.bc) 
        if not bc in bc_einleiter: bc_einleiter[bc] = []
        bc_einleiter[bc].append(abf)
        
    
    #Boundary conditions and time series
    bc_inflows : dict[int, list[pandas.Series]] = {}

    #Sum the timeseries
    for bc in set.union(set(bc_zuflusse.keys()), (bc_einleiter.keys())):
        zf_series = bc_zuflusse.get(bc, [])
        el_series = bc_einleiter.get(bc, [])
        bc_inflows[bc] = zf_series + el_series


    text = generate_boundary_conditions_text(inflows = bc_inflows, datum = date_begin)

    with open(path_save_to, "w") as f:
        f.write(text)

    return True, errors

if __name__ == "__main__":
    pass