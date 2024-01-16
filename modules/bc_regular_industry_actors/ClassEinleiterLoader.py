 #loads the filepath with the einleiter

from dataclasses import dataclass, field
import pathlib

import numpy
import csv
from enum import Enum
from typing import List, Tuple, Dict

import pandas

try:
    from .ClassEinleiter import Einleiter
    from .ClassWaterPatterns import Pattern, PatternDaily, PatternHolder, PatternWeekly
except:
    from ClassEinleiter import Einleiter
    from ClassWaterPatterns import Pattern, PatternDaily, PatternHolder, PatternWeekly


HEADERS = Enum("Header",["id","lat","long","ew_120L","abflussjahr_m3","constantabfluss_Ls","filepath_patterndaily","filepath_patternweekly","boundarycondition"])
HEADERS_pretty = Enum("Header",["Id","Latitude","Longitude","Population Equivalent(120L)","Yearly discharge m3","Constant discharge L/s","Filepath daily pattern","Filepath weekly pattern","Boundary condition index"])


@dataclass
class EinleiterLoader:
    """
    Loads the general Einleiter Information
    Assumes that path_csv has no header
    """
    path_csv : str    
    
    #Saving the loaded paths
    _pattern_paths : Dict[str, Pattern] = field(init=False, default_factory=dict)

    def __post_init__(self):
        self._csv_basefolder = pathlib.Path(self.path_csv).parent.absolute().resolve().as_posix()


    def get_contents(self)-> List[str]:
        """
        Gets the contents of the Einleiter file
        """

        line_split : List[List[str]]

        #CSV
        with open(self.path_csv, 'r') as f:
            csv_reader = csv.reader(f, delimiter = ";")
            line_split = list(csv_reader)
            
        try:
            assert all([len(ls) == len(HEADERS) for ls in line_split])
        except:
            raise ValueError(f"Malformed csv!!! {self.path_csv}. Should have the columns order of {[x for x in HEADERS]} ")
        return line_split

    
    def sanitized_path(self, path : str)->str:
        """
        Returns an absolute path
        """
        if path == "": return path
        p = pathlib.Path(path)
        if pathlib.Path(path).is_absolute():
            return p.resolve().absolute().as_posix()
        else:
            return pathlib.Path(self._csv_basefolder).joinpath(path).resolve().absolute().as_posix()

    @staticmethod
    def get_pattern_content(pattern_path : str, length : int) -> "Pattern":
        """
        Reads a pattern from a csv in the form of 1\n4.2\n0.2\n.1 ...
        Checks against length
        """
        r : List[float]
        
        with open(pattern_path, "r") as f:
            r = f.readlines()

        if length != len(r) : raise ValueError(f"Malformed pattern at {pattern_path}!!")
        p = Pattern(factor = numpy.array([float(v) for v in r]), length = length)
        return p

    def import_einleiter(self) -> List[Einleiter]:
        """
        Imports the einleiter from the csv.        
        """
        df : pandas.DataFrame = pandas.read_csv(self.path_csv, sep = ";", header = None, names = [h.name for h in HEADERS])
        df = df.fillna(value = "")

        def calculate_constabf(einleiter : pandas.Series)->bool:
            """
            Returns the calculated constant abfluss in L/s
            """
            if bool(constantls := einleiter[HEADERS.constantabfluss_Ls.name]): return float(constantls)
            elif bool(jahrm3 := einleiter[HEADERS.abflussjahr_m3.name]): return float(jahrm3)*1000/365.25/24/3600
            elif bool(ew120 := einleiter[HEADERS.ew_120L.name]): return float(ew120)/24/3600
            else: return 0.0

        created_einleiters = []
        for r, row in df.iterrows():
            name = row[HEADERS.id.name]
            cf = calculate_constabf(row)
            lat_long = (row[HEADERS.lat.name], row[HEADERS.long.name])

            fpd, fpw = self.sanitized_path(row[HEADERS.filepath_patterndaily.name]), self.sanitized_path(row[HEADERS.filepath_patternweekly.name]) 
            patd, patw = None, None

            if (fpd != ""):
                if (fpd not in self._pattern_paths) : self._pattern_paths[fpd] = self.get_pattern_content(fpd, 24)
                patd = self._pattern_paths[fpd]

            if (fpw != "") : 
                if (fpw not in self._pattern_paths): self._pattern_paths[fpw] = self.get_pattern_content(fpw, 7)
                patw = self._pattern_paths[fpw]
            ph = PatternHolder(daily = patd, weekly = patw)
            bc = row[HEADERS.boundarycondition.name] 

            cr_e =  Einleiter(id = name, lat_long = lat_long, abf_constant_L_s=cf, patterns = ph, bc = bc)
            created_einleiters.append(cr_e)

        return created_einleiters
    

if __name__ == "__main__":
    pass