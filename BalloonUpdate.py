from PointingMath import *
import geomag


class BalloonUpdate(object):
    """
    A class to hold all of the information in a new balloon position and pointing update
    """

    def __init__(self, time, seconds, lat, lon, alt, trackingMethod, groundLat, groundLon, groundAlt):
        self.time = time
        self.seconds = seconds
        self.lat = lat
        self.lon = lon
        self.alt = alt
        self.trackingMethod = trackingMethod

        ### Calculate pointing values and distances ###
        distanceToTarget = haversine(groundLat, groundLon, self.lat, self.lon)
        self.bear = bearing(groundLat, groundLon, self.lat, self.lon)
        self.ele = elevationAngle(self.alt, groundAlt, distanceToTarget)
        self.los = losDistance(self.alt, groundAlt, distanceToTarget)
        self.magDec = geomag.declination(
            dlat=self.lat, dlon=self.lon, h=self.alt)

    def getTime(self):
        return self.time

    def getLat(self):
        return self.lat

    def getLon(self):
        return self.lon

    def getAlt(self):
        return self.alt

    def getBear(self):
        return self.bear

    def getEle(self):
        return self.ele

    def getLOS(self):
        return self.los

    def getMagDec(self):
        return self.magDec

    def getTrackingMethod(self):
        return self.trackingMethod

    def getSeconds(self):
        return self.seconds
