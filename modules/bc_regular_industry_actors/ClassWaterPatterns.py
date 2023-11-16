#Classes for the water patterns 
#Possible to abstract the pattern mechanisms

from dataclasses import dataclass, field
import datetime

import numpy

@dataclass()
class Pattern():
    """Abstraction of the pattern mechanism"""
    factor : numpy.ndarray
    length : int
    def __post_init__(self):
        assert len(self.factor) == self.length
        if isinstance(self.factor, list): self.factor = numpy.array(self.factor)

        #Normalize pattern
        scaling = self.length/sum(self.factor)
        self.factor = [f*scaling for f in self.factor]


    def get_value(self, fraction : float):
        """
        Gets the value of the pattern at that daily fraction.
        0.5 = 12.00
        """
        pos = int(fraction*self.length)
        return self.factor[pos%self.length]
    



@dataclass
class PatternDaily(Pattern):
    """Pattern from 00h to 24h
    Assumes that the values are given as hourly factors.
    """
    factor : numpy.ndarray
    length : int = field(init=False, default = 24)
    
        
@dataclass
class PatternWeekly(Pattern):
    """Pattern. Be careful that monday is 0 for datetime.weekday
    """
    factor : numpy.ndarray
    length : int = field(init=False, default = 7)



@dataclass
class PatternHolder:
    """Holds the Daily and Weekly patterns. Calculates the combined factor."""
    _daily : PatternDaily = field(init=False, default=PatternDaily(factor = numpy.ones(24)))
    _weekly : PatternWeekly = field(init=False, default=PatternWeekly(factor = numpy.ones(7)))

    daily : PatternDaily = field(init=True, default=PatternDaily(factor = numpy.ones(24)))
    weekly : PatternWeekly = field(init=True, default=PatternWeekly(factor = numpy.ones(7)))

    def __post_init__(self):
        if self.daily is None: self.daily = self._daily
        if self.weekly is None: self.weekly = self._weekly
        


    def get_value(self, day_fraction : float, weekday : int) -> float:
        """Returns the factor at that time
        fraction from 0 to 1, 0.5 = 12h
        Monday = 0; Sunday = 6"""
        return (self.daily.get_value(fraction=day_fraction)
                 * self.weekly.get_value(fraction=weekday/7)
                 )
    
    def get_factors (self, dates : list[datetime.datetime])-> numpy.ndarray:
        """
        Takes a list of dates and returns a list of factors related to that dates
        """
        gd = self.daily.get_value
        gw = self.weekly.get_value
        fractions = [(d.hour/24, d.weekday()/7) for d in dates ] #hour, day of week #monday is 0 in weekday
        values = numpy.array([gd(df) * gw(wf) for df, wf in fractions])
        return values

if __name__ == "__init__":
    pass
