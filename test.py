import MySQLdb 
import math
import numpy as np
import serial
import json
try:
    # For Python 3.0 and later
    from urllib.request import urlopen
except ImportError:
    # Fall back to Python 2's urllib2
    from urllib2 import urlopen
from datetime import datetime
startTime = datetime.now()

groundLat = 0.00
groundLon = 0.00
groundAlt = 0.00
centerBear = 0.00
antennaBear = 0.00
antennaEle = 0.00
calibrationGoal = 8
moveIncrement = 2.0

#Balloon location from iridium
iridiumTime = "NA"
iridiumLat = 0.00
iridiumLon = 0.00
iridiumAlt = 0.00
iridiumBear = 0.00
iridiumEle = 0.00
iridiumLOS = 0.00
iridiumMagDec = 0.00

#Balloon location from RFD900
rfdTime = "NA"
rfdLat = 0.00
rfdLon = 0.00
rfdAlt = 0.00
rfdBear = 0.00
rfdEle = 0.00
rfdLOS = 0.00
rfdMagDec = 0.00

#Simulation Settings
simDate = ""
simStartAlt = ""

#Booleans for settings
settingsUpdated = False
servoAttached = False
rfdAttached = False
arduinoAttached = False
manualOverride = False
useIridium = False
useRFD = False
usePrediction = False
useSim = False
autotrackOnline = False

#Ground Station Settings
getLocal = False
manualLocal = False
manualOverride = False
sendEmail = False

#Serial Settings
s = serial.Serial()
servoCOM = ""
servoBaud = 9600
servoTimeout = 0.5
rfdCOM = ""
rfdBaud = 38400
rfdTimeout = 2
arduinoCOM = ""
arduinoBaud = 115200
arduinoTimeout = 5

# use these to manually tweak the tracking (ie if its still off a little after aligning)
panOffset = 0          # increase to turn right, decrease to turn left
tiltOffset = 0          # increase to raise, decrease to lower
trackTiltOffset = 0.0
trackBearOffset = 0.0
previousPan = 127       #Memory for last position (To account for backlash)

moveCommand = 0xFF
accelCommand = 0x89             
speedCommand = 0x87

# Shouldn't need to change these unless you change to some exotic servos
servo_min = 0
servo_max = 254

# change the movement speed etc of ubiquity tilt servo
tiltChannel = 0
tiltRange = 360
tiltAccel = 1
tiltSpeed = 1
tilt_angle_min = -180        #-90
tilt_angle_max = 180         #90

# change the movement speed etc of ubiquity pan servo
panChannel = 1
panRange = 360
panAccel = 1
panSpeed = 3

#Graphing Arrays
receivedTime = np.array([])
receivedLat = np.array([])
receivedLon = np.array([])
receivedAlt = np.array([])
losLog = np.array([])
elevationLog = np.array([])
bearingLog = np.array([])

db_host = "153.90.203.195"
db_user = "scott"
db_passwd = "Jewe1947"
db_name = "freemanproject"
IMEI = "300234064802740"
dataMethod = ""

def haversine(trackerLat, trackerLon, remoteLat, remoteLon):
        R = 6371        # radius of earth in Km
        dLat = math.radians(remoteLat-trackerLat)
        dLon = math.radians(remoteLon-trackerLon)
        a = math.sin(dLat/2)*math.sin(dLat/2)+math.cos(math.radians(trackerLat))*math.cos(math.radians(remoteLat))*math.sin(dLon/2)*math.sin(dLon/2)
        c = 2*math.atan2(math.sqrt(a),math.sqrt(1-a))
        d = R*c
        return d*3280.839895 # multiply distance in Km by 3280 for feet

def bearing(trackerLat, trackerLon, remoteLat, remoteLon):
        dLat = math.radians(remoteLat-trackerLat)       # delta latitude in radians
        dLon = math.radians(remoteLon-trackerLon)       # delta longitude in radians
        y = math.sin(dLon)*math.cos(math.radians(remoteLat))
        x = math.cos(math.radians(trackerLat))*math.sin(math.radians(remoteLat))-math.sin(math.radians(trackerLat))*math.cos(math.radians(remoteLat))*math.cos(dLat)
        tempBearing = math.degrees(math.atan2(y,x))     # returns the bearing from true north
        if (tempBearing < 0):
                tempBearing = tempBearing + 360
        return tempBearing

def getApiData(imei):
    """
    Retrieve the most recent IMEI data from the database API

    Parameters
    ----------
    imei : str or int

    Returns
    -------
    dict
    """
    url = "http://eclipse.rci.montana.edu/php/antennaTracker.php?imei=%s" % imei
    try: 
        # Timeout may be redundant, if port 80 is timing out, port 3306 will probably also
        response = urlopen(url, timeout = 5)
        data = response.read().decode("utf-8")
        return json.loads(data)
    except:
        return {}


def getIridium():
    global receivedTime, receivedLat, receivedLon, receivedAlt, bearingLog, elevationLog, losLog
    global db_host, db_user, db_passwd, db_name, dataMethod

    get_data = getApiData(IMEI)
    if get_data: 
        dataMethod = "API"
        remoteTime    = get_data['remoteTime']
        remoteHours   = int(get_data['remoteHours'])
        remoteMinutes = int(get_data['remoteMinutes'])
        remoteSeconds = int(get_data['remoteSeconds']) + (60*remoteMinutes) + (3600*remoteHours)
        remoteLat     = float(get_data['remoteLat'])
        remoteLon     = float(get_data['remoteLon'])
        remoteAlt     = float(get_data['remoteAlt'])
    else:
        dataMethod = "DB"
        db_local = MySQLdb.connect(host=db_host,user=db_user,passwd=db_passwd,db=db_name)
        cursor = db_local.cursor()
        #sql = "select gps_fltDate,gps_time,gps_lat,gps_long,gps_alt from gps where pri_key = (select max(pri_key) from gps) and gps_IMEI = "+IMEI
        sql = "select gps_fltDate,gps_time,gps_lat,gps_long,gps_alt from gps where gps_IMEI = '"+IMEI+"' order by pri_key DESC LIMIT 1"   
        #sql = "select gps_fltDate,gps_time,gps_lat,gps_long,gps_alt from gps order by pri_key DESC"   
        #sql = "select gps_fltDate,gps_time,gps_lat,gps_long,gps_alt from gps where gps_fltDate = '2015-01-17' order by gps_time"
        cursor.execute(sql)
        try:
            results       = cursor.fetchone()
            remoteTime    = results[1].split(":")
            remoteHours   = int(remoteTime[0])
            remoteMinutes = int(remoteTime[1])
            remoteSeconds = int(remoteTime[2])
            remoteTime    = results[1]
            remoteSeconds = remoteSeconds + (60*remoteMinutes) + (3600*remoteHours)
            remoteLat     = float(results[2])                   #http://stackoverflow.com/questions/379906/parse-string-to-float-or-int
            remoteLon     = float(results[3])
            remoteAlt     = float(results[4]) * 3.280839895  #(meters to feet conversion)
            cursor.close()
            db_local.close()
        except:
            print "ERROR PARSING DATA FROM DATABASE: Cannot parse data or data may not exist, please double check your IMEI number at the top of the code"
            cursor.close()
            db_local.close()
            return


    deltaAlt = remoteAlt-groundAlt   
    distanceToTarget = 0.87 * haversine( groundLat,  groundLon, remoteLat, remoteLon)        
    bearingToTarget = bearing( groundLat,  groundLon, remoteLat, remoteLon)   
    elevationAngle = math.degrees(math.atan2(deltaAlt,distanceToTarget))
    global iridiumAlt
    iridiumAlt = remoteAlt
    global iridiumLon
    iridiumLon = remoteLon
    global iridiumLat
    iridiumLat = remoteLat
    global iridiumTime
    iridiumTime = remoteTime
    global iridiumEle
    iridiumEle = elevationAngle
    global iridiumBear
    iridiumBear = bearingToTarget
    global iridiumLOS
    iridiumLOS = math.sqrt(math.pow(distanceToTarget/3.2808,2) + math.pow(deltaAlt/3.2808,2))/1000
    if ((len(receivedTime) == 0)):
        receivedTime = np.append(receivedTime,remoteSeconds)
        receivedLon = np.append(receivedLon,iridiumLon)
        receivedLat = np.append(receivedLat,iridiumLat)
        receivedAlt = np.append(receivedAlt,iridiumAlt)
        bearingLog = np.append(bearingLog,iridiumBear)
        elevationLog = np.append(elevationLog,iridiumEle)
        losLog = np.append(losLog,iridiumLOS)
    elif(receivedTime[len(receivedTime) - 1] < remoteSeconds):
        receivedTime = np.append(receivedTime,remoteSeconds)
        receivedLon = np.append(receivedLon,iridiumLon)
        receivedLat = np.append(receivedLat,iridiumLat)
        receivedAlt = np.append(receivedAlt,iridiumAlt)
        bearingLog = np.append(bearingLog,iridiumBear)
        elevationLog = np.append(elevationLog,iridiumEle)
        losLog = np.append(losLog,iridiumLOS)

getIridium()

print '''
IMEI: %s
Data Method: %s

CALCULATED POSITION
===================
iridiumAlt:  %s
iridiumLat:  %s
iridiumLon:  %s
iridiumTime: %s
iridiumEle:  %s
iridiumBear: %s
iridiumLOS:  %s

Script Runtime: %s
''' % (IMEI, dataMethod, iridiumAlt, iridiumLat, iridiumLon, iridiumTime, iridiumEle, iridiumBear, iridiumLOS, datetime.now() - startTime)


