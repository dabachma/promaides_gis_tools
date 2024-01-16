#Einleiter objects


from dataclasses import dataclass, field
import datetime
from typing import List, Tuple, Dict

import numpy
import pandas

try:
    from .ClassWaterPatterns import PatternHolder
except:
    from ClassWaterPatterns import PatternHolder

@dataclass
class Einleiter:
    id : str
    lat_long : Tuple[float, float] #Unspecified 
    abf_constant_L_s : float = field(init = True)#l/s constant #TODO: eventually add support for measured flow rates with datetime-l/s
    patterns : PatternHolder = field(init = True, default=PatternHolder())
    bc : int = field(init = True, default = None) #Boundary condition index

    def __post_init__(self):
        pass

    def estimate_abfluss(self, dates : List[datetime.datetime]) -> pandas.Series:
        """
        Gets some dates and multiplies the pattern values by the constant in Liters/second
        """
  
        factors = self.patterns.get_factors(dates = dates)
        values = factors * self.abf_constant_L_s

        result = pandas.Series({d:v for d,v in zip(dates,values)})
        return result


if __name__ == "__main__":
    pass