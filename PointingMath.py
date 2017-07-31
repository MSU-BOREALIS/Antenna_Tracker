import math


def bearing(trackerLat, trackerLon, remoteLat, remoteLon):
    """ great circle bearing, see: http://www.movable-type.co.uk/scripts/latlong.html  """

    dLat = math.radians(remoteLat - trackerLat)	   # delta latitude in radians
    dLon = math.radians(remoteLon - trackerLon)	   # delta longitude in radians

    y = math.sin(dLon) * math.cos(math.radians(remoteLat))
    x = math.cos(math.radians(trackerLat)) * math.sin(math.radians(remoteLat)) - \
        math.sin(math.radians(trackerLat)) * \
        math.cos(math.radians(remoteLat)) * math.cos(dLat)
    # returns the bearing from true north
    tempBearing = math.degrees(math.atan2(y, x))
    while tempBearing < 0:		# Makes sure the bearing is between 0 and 360
        tempBearing += 360
    while tempBearing > 360:
        tempBearing -= 360
    return tempBearing


def elevationAngle(skyAlt, trackerAlt, distance):
    """ elevation angle from ground distance and altitudes """

    return math.degrees(math.atan2(skyAlt - trackerAlt, distance))


def haversine(trackerLat, trackerLon, remoteLat, remoteLon):
    """ haversine formula, see: http://www.movable-type.co.uk/scripts/latlong.html """

    R = 6371		# radius of earth in Km
    dLat = math.radians(remoteLat - trackerLat)	   # delta latitude in radians
    dLon = math.radians(remoteLon - trackerLon)	   # delta longitude in radians

    a = math.sin(dLat / 2) * math.sin(dLat / 2) + math.cos(math.radians(trackerLat)) * \
        math.cos(math.radians(remoteLat)) * \
        math.sin(dLon / 2) * math.sin(dLon / 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    d = R * c

    return d * 3280.839895  # multiply distance in Km by 3280 for feet


def losDistance(alt, trackerAlt, distance):
    """ The line of sight distance based on ground distance and altitude """

    return math.sqrt(math.pow(distance / 3.2808, 2) + math.pow((alt - trackerAlt) / 3.2808, 2)) / 1000
