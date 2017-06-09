from PyQt4 import *
from PyQt4 import QtCore
from PyQt4 import QtGui
from PyQt4.QtCore import *
from BalloonUpdate import *
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


class GetIridium(QtCore.QObject):

    # Received Signals
    start = pyqtSignal()
    setInterrupt = pyqtSignal()

    def __init__(self, MainWindow, host, user, password, name, IMEI):
        super(GetIridium, self).__init__()
        self.mainWindow = MainWindow
        self.dbHost = host
        self.dbUser = user
        self.dbPass = password
        self.dbName = name
        self.IMEI = IMEI
        self.iridiumInterrupt = False

        # Emitted Signals
        self.mainWindow.noIridium.connect(self.mainWindow.iridiumNoConnection)
        self.mainWindow.iridiumNewLocation.connect(
            self.mainWindow.updateBalloonLocation)

    def getApiData(self, imei):
        url = "http://eclipse.rci.montana.edu/php/antennaTracker.php?imei=%s" % imei
        try:
            # Timeout may be redundant, if port 80 is timing out, port 3306
            # will probably also
            response = urlopen(url, timeout=5)
            data = response.read().decode("utf-8")
            return json.loads(data)
        except:
            return {}

    def run(self):
        """ Gets tracking information from the Iridium satellite modem by taking the information from the web api OR the SQL database at Montana State University """
        # modified this to use the Web API - pol.llovet@montana.edu
        #     the modification is crude and should be refactored. :P

        self.iridiumInterrupt = False
        prev = ''
        connectAttempts = 0
        while(not self.iridiumInterrupt):
            time.sleep(2)
            # Fetch the data from the API
            get_data = self.getApiData(self.IMEI)
            if get_data:
                # set the data from the API values
                dataMethod = "API"
                remoteTime = get_data['remoteTime']
                remoteHours = int(get_data['remoteHours'])
                remoteMinutes = int(get_data['remoteMinutes'])
                remoteSeconds = int(
                    get_data['remoteSeconds']) + (60 * remoteMinutes) + (3600 * remoteHours)
                remoteLat = float(get_data['remoteLat'])
                remoteLon = float(get_data['remoteLon'])
                remoteAlt = float(get_data['remoteAlt'])
                ### Create a new location object ###
                try:
                    newLocation = BalloonUpdate(remoteTime, remoteSeconds, remoteLat, remoteLon, remoteAlt,
                                                "Iridium", self.mainWindow.groundLat, self.mainWindow.groundLon, self.mainWindow.groundAlt)
                except:
                    print(
                        "Error creating a new balloon location object from Iridium Data")

                try:
                    # Notify the main GUI of the new location
                    self.mainWindow.iridiumNewLocation.emit(newLocation)
                except Exception, e:
                    print(str(e))

            else:
                # use the database
                # Connect to the SQL Database (try 20 times)
                connected = False
                while(not connected and not self.iridiumInterrupt):
                    QtGui.QApplication.processEvents()
                    if connectAttempts < 20:
                        try:
                            # Connect to the database
                            db_local = MySQLdb.connect(
                                host=self.dbHost, user=self.dbUser, passwd=self.dbPass, db=self.dbName)
                            # prepare a cursor object using cursor() method
                            cursor = db_local.cursor()
                            sql = "select gps_fltDate,gps_time,gps_lat,gps_long,gps_alt from gps where gps_IMEI = %s order by pri_key DESC LIMIT 1" % (
                                IMEI)
                            cursor.execute(sql)
                            connected = True
                            if self.iridiumInterrupt:
                                cursor.close()
                                db_local.close()
                                connected = True
                        except:
                            print(
                                "Failed to connect to database, trying again in 1 sec")
                            connectAttempts += 1
                    else:
                        print("Failed to connect to database too many times")
                        self.interrupt()
                        self.mainWindow.noIridium.emit()
                if connected:
                    ### Fetch a single row using fetchone() method. ###
                    # POL: Note, there will only ever be one row, since we are
                    # using "LIMIT 1"
                    try:
                        results = cursor.fetchone()
                        if(results != prev):
                            prev = results
                            remoteTime = results[1].split(":")
                            remoteHours = int(remoteTime[0])
                            remoteMinutes = int(remoteTime[1])
                            remoteSeconds = int(remoteTime[2])
                            remoteTime = results[1]
                            remoteSeconds = remoteSeconds + \
                                (60 * remoteMinutes) + (3600 * remoteHours)
                            # http://stackoverflow.com/questions/379906/parse-string-to-float-or-int
                            remoteLat = float(results[2])
                            remoteLon = float(results[3])
                            # (meters to feet conversion)
                            remoteAlt = float(results[4]) * 3.280839895

                            ### Create a new location object ###
                            try:
                                newLocation = BalloonUpdate(remoteTime, remoteSeconds, remoteLat, remoteLon, remoteAlt,
                                                            "Iridium", self.mainWindow.groundLat, self.mainWindow.groundLon, self.mainWindow.groundAlt)
                            except:
                                print(
                                    "Error creating a new balloon location object from Iridium Data")

                            try:
                                # Notify the main GUI of the new location
                                self.mainWindow.iridiumNewLocation.emit(
                                    newLocation)
                            except Exception, e:
                                print(str(e))
                    except:
                        print(
                            "ERROR PARSING DATA FROM DATABASE: Cannot parse data or data may not exist, please double check your IMEI number")
                else:
                    print("ERROR: Unable to connect to database!")

        ### Clean up ###
        try:
            cursor.close()
            db_local.close()
        except:
            print("Error closing database")

        self.iridiumInterrupt = False

    def interrupt(self):
        self.iridiumInterrupt = True


class GetAPRS(QtCore.QObject):

    # Received Signals
    start = pyqtSignal()
    setInterrupt = pyqtSignal()

    def __init__(self, MainWindow, APRS):
        super(GetAPRS, self).__init__()
        self.mainWindow = MainWindow
        self.aprsSer = APRS
        self.aprsInterrupt = False

        # Emitted Signals
        self.mainWindow.aprsNewLocation.connect(
            self.mainWindow.updateBalloonLocation)

    def run(self):
        """ Gets tracking information from the APRS receiver """

        aprsSer = self.APRS.getDevice()

        while(not self.aprsInterrupt):
            ### Read the APRS serial port, and parse the string appropriately                               ###
            # Format:
            # "Callsign">CQ,WIDE1-1,WIDE2-2:!"Lat"N/"Lon"EO000/000/A="Alt"RadBug,23C,982mb,001
            # ###
            try:
                line = str(aprsSer.readline())
                print(line)
                idx = line.find(self.callsign)
                if(idx != -1):
                    line = line[idx:]
                    line = line[line.find("!") + 1:line.find("RadBug")]
                    line = line.split("/")

                    # Get the individual values from the newly created list ###
                    time = datetime.utcfromtimestamp(
                        time.time()).strftime('%H:%M:%S')
                    lat = line[0][0:-1]
                    latDeg = float(lat[0:2])
                    latMin = float(lat[2:])
                    lon = line[1][0:line[1].find("W")]
                    lonDeg = float(lon[0:3])
                    lonMin = float(lon[3:])
                    lat = latDeg + (latMin / 60)
                    lon = -lonDeg - (lonMin / 60)
                    alt = float(line[3][2:])
                    aprsSeconds = float(time.split(
                        ':')[0]) * 3600 + float(time.split(':')[1]) * 60 + float(time.split(':')[2])

                    ### Create a new location object ###
                    try:
                        newLocation = BalloonUpdate(
                            time, aprsSeconds, lat, lon, alt, "APRS", self.mainWindow.groundLat, self.mainWindow.groundLon, self.mainWindow.groundAlt)
                    except:
                        print(
                            "Error creating a new balloon location object from APRS Data")

                    try:
                        # Notify the main GUI of the new location
                        self.aprsNewLocation.emit(newLocation)
                    except Exception, e:
                        print(str(e))
            except:
                print("Error retrieving APRS Data")

        ### Clean Up ###
        try:
            aprsSer.close()         # Close the APRS Serial Port
        except:
            print("Error closing APRS serial port")

        self.aprsInterrupt = False

    def interrupt(self):
        self.aprsInterrupt = True
