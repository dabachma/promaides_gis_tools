"""

"""
import math
from qgis.core import *

try:
    from scipy import interpolate
    ScipyAvailable = True
except ImportError:
    ScipyAvailable = False

# QGIS modules
from qgis.core import QgsRaster, QgsRectangle


def isin(value, array2d):
    return bool([x for x in array2d if value in x])


class RasterInterpolator(object):

    def __init__(self, raster_layer, band, requested_dx, requested_dy, method, nan=None):
        """

        Parameters
        ----------
        raster_layer: QgsRasterLayer
        band: int
        method: str
        nan: float or None
        """
        if raster_layer:
            self.dataProv = raster_layer.dataProvider()
            self.interpolMethod = method
            self.outputdx = requested_dx
            self.outputdy = requested_dy
            self.band = band
            self.raster_nan = self.dataProv.sourceNoDataValue(band)

            if nan is None:
                if self.dataProv.srcNoDataValue(band):
                    self.noDataValue = self.dataProv.sourceNoDataValue(band)
                else:
                    self.noDataValue = -9999.0
            else:
                self.noDataValue = nan

            self.myExtent = self.dataProv.extent()
            self.theWidth = self.dataProv.xSize()
            self.theHeight = self.dataProv.ySize()
            if 'nearest' in method:
                self.interpolate = lambda point: self._nearest(point)
            elif "linear" in method:
                self.interpolate = lambda point: self._linear(point)
            elif "cubic" in method:
                self.interpolate = lambda point : self._bicubic(point)
            elif "average" in method:
                self.interpolate = lambda point : self._average(point)
            elif "max" in method:
                self.interpolate = lambda point : self._max(point)
            elif "min" in method:
                self.interpolate = lambda point : self._min(point)
            else:
                raise ValueError('unsupported interpolation method "{}"'.format(methodhi))
        else:
            self.interpolate = lambda p: nan

    def __call__(self, point):
        return self.interpolate(point)

    def _nearest(self, point):
        ident = self.dataProv.identify(point, QgsRaster.IdentifyFormatValue)
        value = None
        if ident is not None:  # and ident.has_key(choosenBand+1):
            try:
                value = float(ident.results()[self.band])
            except TypeError:
                return self.noDataValue
        return value

    def _linear(self, point):
        # see the implementation of raster data provider, identify method
        # https://github.com/qgis/Quantum-GIS/blob/master/src/core/raster/qgsrasterdataprovider.cpp#L268
        x = point.x()
        y = point.y()
        xres = self.myExtent.width() / self.theWidth
        yres = self.myExtent.height() / self.theHeight
        col = round((x - self.myExtent.xMinimum()) / xres)
        row = round((self.myExtent.yMaximum() - y) / yres)
        xMin = self.myExtent.xMinimum() + (col-1) * xres
        xMax = xMin + 2*xres
        yMax = self.myExtent.yMaximum() - (row-1) * yres
        yMin = yMax - 2*yres
        pixelExtent = QgsRectangle(xMin, yMin, xMax, yMax)
        myBlock = self.dataProv.block(self.band, pixelExtent, 2, 2)
        # http://en.wikipedia.org/wiki/Bilinear_interpolation#Algorithm
        v12 = myBlock.value(0, 0)
        v22 = myBlock.value(0, 1)
        v11 = myBlock.value(1, 0)
        v21 = myBlock.value(1, 1)
        if self.raster_nan in (v12, v22, v11, v21):
            return self.noDataValue
        x1 = xMin+xres/2
        x2 = xMax-xres/2
        y1 = yMin+yres/2
        y2 = yMax-yres/2
        value = (v11*(x2 - x)*(y2 - y)
               + v21*(x - x1)*(y2 - y)
               + v12*(x2 - x)*(y - y1)
               + v22*(x - x1)*(y - y1)
               )/((x2 - x1)*(y2 - y1))
        return value

    def _bicubic(self, point):
        # see the implementation of raster data provider, identify method
        # https://github.com/qgis/Quantum-GIS/blob/master/src/core/raster/qgsrasterdataprovider.cpp#L268
        x = point.x()
        y = point.y()
        xres = self.myExtent.width() / self.theWidth
        yres = self.myExtent.height() / self.theHeight
        col = round((x - self.myExtent.xMinimum()) / xres)
        row = round((self.myExtent.yMaximum() - y) / yres)
        xMin = self.myExtent.xMinimum() + (col-2) * xres
        xMax = xMin + 4*xres
        yMax = self.myExtent.yMaximum() - (row-2) * yres
        yMin = yMax - 4*yres
        pixelExtent = QgsRectangle(xMin, yMin, xMax, yMax)
        myBlock = self.dataProv.block(self.band, pixelExtent, 4, 4)
        # http://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.interp2d.html
        vx = [xMin+.5*xres, xMin+1.5*xres, xMin+2.5*xres, xMin+3.5*xres]
        vy = [yMin+.5*yres, yMin+1.5*yres, yMin+2.5*yres, yMin+3.5*yres]
        vz = [[myBlock.value(3, 0), myBlock.value(3, 1), myBlock.value(3, 2), myBlock.value(3, 3)],
              [myBlock.value(2, 0), myBlock.value(2, 1), myBlock.value(2, 2), myBlock.value(2, 3)],
              [myBlock.value(1, 0), myBlock.value(1, 1), myBlock.value(1, 2), myBlock.value(1, 3)],
              [myBlock.value(0, 0), myBlock.value(0, 1), myBlock.value(0, 2), myBlock.value(0, 3)]]
        if myBlock.hasNoDataValue()and isin(self.raster_nan, vz):
            return self.noDataValue
        fz = interpolate.interp2d(vx, vy, vz, kind='cubic')
        value = fz(x, y)[0].item()
        return value

    def _average(self, point):
        x = point.x()
        y = point.y()
        xres = self.myExtent.width() / self.theWidth
        yres = self.myExtent.height() / self.theHeight
        col = round((x - self.myExtent.xMinimum()) / xres)
        row = round((self.myExtent.yMaximum() - y) / yres)
        nx= math.ceil(self.outputdx/xres) #number of cells in the x direction
        ny = math.ceil(self.outputdy/yres) #number of cells in the y direction
        xMin = self.myExtent.xMinimum() + (col-(nx/2)) * xres
        xMax = xMin + nx*xres
        yMax = self.myExtent.yMaximum() - (row-(ny/2)) * yres
        yMin = yMax - ny*yres
        pixelExtent = QgsRectangle(xMin, yMin, xMax, yMax)

        values = []
        y = yMax
        for i in range(ny):
            x = xMin
            for j in range(nx):
                ident = self.dataProv.identify(QgsPointXY(x, y), QgsRaster.IdentifyFormatValue)
                values.append(ident.results()[1])
                x += xres
            y -= yres
        for v in values:
            if v is None or v == self.noDataValue:
                return self.noDataValue
        total=0
        for k in range(0, len(values)):
            total = total + values[k]
        value=total/len(values)
        return value

    def _max(self, point):
        x = point.x()
        y = point.y()
        xres = self.myExtent.width() / self.theWidth
        yres = self.myExtent.height() / self.theHeight
        col = round((x - self.myExtent.xMinimum()) / xres)
        row = round((self.myExtent.yMaximum() - y) / yres)
        nx= math.ceil(self.outputdx/xres) #number of cells in the x direction
        ny = math.ceil(self.outputdy/yres) #number of cells in the y direction
        xMin = self.myExtent.xMinimum() + (col-(nx/2)) * xres
        xMax = xMin + nx*xres
        yMax = self.myExtent.yMaximum() - (row-(ny/2)) * yres
        yMin = yMax - ny*yres
        pixelExtent = QgsRectangle(xMin, yMin, xMax, yMax)

        values = []
        y = yMax
        for i in range(ny):
            x = xMin
            for j in range(nx):
                ident = self.dataProv.identify(QgsPointXY(x, y), QgsRaster.IdentifyFormatValue)
                values.append(ident.results()[1])
                x += xres
            y -= yres
        for v in values:
            if v is None:
                return self.noDataValue
        value=max(values)
        return value

    def _min(self, point):
        x = point.x()
        y = point.y()
        xres = self.myExtent.width() / self.theWidth
        yres = self.myExtent.height() / self.theHeight
        col = round((x - self.myExtent.xMinimum()) / xres)
        row = round((self.myExtent.yMaximum() - y) / yres)
        nx= math.ceil(self.outputdx/xres) #number of cells in the x direction
        ny = math.ceil(self.outputdy/yres) #number of cells in the y direction
        xMin = self.myExtent.xMinimum() + (col-(nx/2)) * xres
        xMax = xMin + nx*xres
        yMax = self.myExtent.yMaximum() - (row-(ny/2)) * yres
        yMin = yMax - ny*yres
        pixelExtent = QgsRectangle(xMin, yMin, xMax, yMax)

        values = []
        y = yMax
        for i in range(ny):
            x = xMin
            for j in range(nx):
                ident = self.dataProv.identify(QgsPointXY(x, y), QgsRaster.IdentifyFormatValue)
                values.append(ident.results()[1])
                x += xres
            y -= yres
        for v in values:
            if v is None:
                return self.noDataValue
        value=min(values)
        return value
