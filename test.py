# from PyQt4 import *
# from PyQt4 import QtCore
# from PyQt4 import QtGui
# from PyQt4.QtCore import *
# from BalloonUpdate import *
import MySQLdb
import datetime
import serial
import threading
import json
try:
    # For Python 3.0 and later
    from urllib.request import urlopen
except ImportError:
    # Fall back to Python 2's urllib2
    from urllib2 import urlopen
from datetime import datetime

startTime = datetime.now()

# Copy code out of GetData.py to test it
global IMEI, dataMethod, remoteTime, remoteHours, remoteMinutes, remoteSeconds, remoteLat, remoteLon, remoteAlt
IMEI = 0
dataMethod = ""
remoteTime    = ""
remoteHours   = 0
remoteMinutes = 0
remoteSeconds = 0
remoteLat     = 0.0
remoteLon     = 0.0
remoteAlt     = 0.0

global db_host, db_user, db_passwd, db_name
db_host = "153.90.203.195"
db_user = "scott"
db_passwd = "Jewe1947"
db_name = "freemanproject"

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

def run():
    """ Gets tracking information from the Iridium satellite modem by taking the information from the web api OR the SQL database at Montana State University """
    # modified this to use the Web API - pol.llovet@montana.edu
    #     the modification is crude and should be refactored. :P
    global IMEI, dataMethod, remoteTime, remoteHours, remoteMinutes, remoteSeconds, remoteLat, remoteLon, remoteAlt
    global db_host, db_user, db_passwd, db_name

    IMEI = 300234064802740

    # self.iridiumInterrupt = False
    prev = ''
    time = 0
    connectAttempts = 0
    while(time < 1):
        # Fetch the data from the API
        get_data = getApiData(IMEI)
        if get_data:
            # set the data from the API values
            dataMethod = "API"
            remoteTime    = get_data['remoteTime']
            remoteHours   = int(get_data['remoteHours'])
            remoteMinutes = int(get_data['remoteMinutes'])
            remoteSeconds = int(get_data['remoteSeconds']) + (60*remoteMinutes) + (3600*remoteHours)
            remoteLat     = float(get_data['remoteLat'])
            remoteLon     = float(get_data['remoteLon'])
            remoteAlt     = float(get_data['remoteAlt'])
            ### Create a new location object ###
            try:
                # newLocation = BalloonUpdate(remoteTime,remoteSeconds,remoteLat,remoteLon,remoteAlt,"Iridium",self.mainWindow.groundLat,self.mainWindow.groundLon,self.mainWindow.groundAlt)
                time = 1
            except:
                print("Error creating a new balloon location object from Iridium Data")

            try:
                # self.mainWindow.iridiumNewLocation.emit(newLocation)                # Notify the main GUI of the new location
                true
            except Exception, e:
                print(str(e))

        else:
            # use the database
            # Connect to the SQL Database (try 20 times)
            connected = False
            while(not connected and connectAttempts < 20):
                # QtGui.QApplication.processEvents()
                if connectAttempts < 20:
                    try:
                        # db_local = MySQLdb.connect(host=self.dbHost,user=self.dbUser,passwd=self.dbPass,db=self.dbName)     # Connect to the database
                        db_local = MySQLdb.connect(host=db_host,user=db_user,passwd=db_passwd,db=db_name)
                        cursor = db_local.cursor()                                                              # prepare a cursor object using cursor() method
                        sql = "select gps_fltDate,gps_time,gps_lat,gps_long,gps_alt from gps where gps_IMEI = %s order by pri_key DESC LIMIT 1" % (IMEI)
                        cursor.execute(sql)
                        print(sql)
                        connected = True
                        # if self.iridiumInterrupt:
                        #     cursor.close()
                        #     db_local.close()
                        #     connected = True
                    except:
                        print("Failed to connect to database, trying again")
                        connectAttempts += 1
                else:
                    print("Failed to connect to database too many times")
                    # self.interrupt()
                    # self.mainWindow.noIridium.emit()
            if connected:
            ### Fetch a single row using fetchone() method. ###
            # POL: Note, there will only ever be one row, since we are using "LIMIT 1"
                try:
                    results = cursor.fetchone()
                    if(results != prev):
                        prev = results
                        dataMethod = "DB"
                        remoteTime = results[1].split(":")
                        remoteHours = int(remoteTime[0])
                        remoteMinutes = int(remoteTime[1])
                        remoteSeconds = int(remoteTime[2])
                        remoteTime = results[1]
                        remoteSeconds = remoteSeconds + (60*remoteMinutes) + (3600*remoteHours)
                        remoteLat = float(results[2])                  #http://stackoverflow.com/questions/379906/parse-string-to-float-or-int
                        remoteLon = float(results[3])
                        remoteAlt = float(results[4]) * 3.280839895  #(meters to feet conversion)

                        ### Create a new location object ###
                        try:
                            # newLocation = BalloonUpdate(remoteTime,remoteSeconds,remoteLat,remoteLon,remoteAlt,"Iridium",self.mainWindow.groundLat,self.mainWindow.groundLon,self.mainWindow.groundAlt)
                            time = 1
                        except:
                            print("Error creating a new balloon location object from Iridium Data")

                        try:
                            # self.mainWindow.iridiumNewLocation.emit(newLocation)                # Notify the main GUI of the new location
                            true
                        except Exception, e:
                            print(str(e))
                except:
                    print("ERROR PARSING DATA FROM DATABASE: Cannot parse data or data may not exist, please double check your IMEI number")
            else:
                print("ERROR: Unable to connect to database!")
                time = 3



run()

print '''
IMEI: %s
Data Method: %s

CALCULATED POSITION
===================
remoteTime    %s
remoteHours   %s
remoteMinutes %s
remoteSeconds %s
remoteLat     %s
remoteLon     %s
remoteAlt     %s

Script Runtime: %s
''' % (IMEI, dataMethod, remoteTime, remoteHours, remoteMinutes, remoteSeconds, remoteLat, remoteLon, remoteAlt, datetime.now() - startTime)


