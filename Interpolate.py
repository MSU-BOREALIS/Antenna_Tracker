from PySide2 import *
from PySide2 import QtCore, QtGui
from PySide2.QtCore import *
from PySide2.QtCore import Signal as pyqtSignal
import time
from time import sleep
from BalloonUpdate import *			# Class to hold balloon info

class InterpolateIridium(QtCore.QObject):

    #Received Signals
    start = pyqtSignal()
    setInterrupt = pyqtSignal()
    setPredictionUpdateSpeed = pyqtSignal(float)
    
    def __init__(self, MainWindow):
        super(InterpolateIridium, self).__init__()
        self.mainWindow = MainWindow
        self.interpolateInterrupt = False

        self.ready = False

        #List holding all known updates
        self.balloonLocations = []

        #Panning Characteristics
        self.updateSpeed = 2    #in seconds
        self.latSpeed = 0       #in seconds
        self.lonSpeed = 0       #in seconds
        self.altSpeed = 0       #in seconds
        self.ticksSinceLastLocation = 0

        #Emitted Signals
        self.mainWindow.iridiumInterpolateNewLocation.connect(
            self.mainWindow.updateBalloonInterpolation)

    def run(self):
        """ Interpolates Iridium tracking information to provide smoother tracking """
        self.interpolateInterrupt = False
        
        while(not self.interpolateInterrupt):
            time.sleep(self.updateSpeed) #update frequency
            
            if self.ready:
                print("Moving at " + "latSpeed: " + str(self.latSpeed) + " lonSpeed: " + str(self.lonSpeed) + " altSpeed: " + str(self.altSpeed))
                self.ticksSinceLastLocation += 1
                # Add speeds*ticks to last known location
                simulatedTime = self.balloonLocations[len(self.balloonLocations)-1].getTime() #keep same timestamp -- meh?

                # Add last known location value + (speed per second) * (update speed in seconds) * ticks
                simulatedSeconds = self.balloonLocations[len(self.balloonLocations)-1].getSeconds() + (self.updateSpeed * self.ticksSinceLastLocation)#Add updateSpeed * ticks for new seconds
                simulatedLat = self.balloonLocations[len(self.balloonLocations)-1].getLat() + (self.latSpeed * self.updateSpeed * self.ticksSinceLastLocation)
                simulatedLon = self.balloonLocations[len(self.balloonLocations)-1].getLon() + (self.lonSpeed * self.updateSpeed * self.ticksSinceLastLocation)
                simulatedAlt = self.balloonLocations[len(self.balloonLocations)-1].getAlt() + (self.altSpeed * self.updateSpeed * self.ticksSinceLastLocation)
                # Make new location object
                print("Simulated Location Update>>> " + "lat: " + str(simulatedLat) + " lon: " + str(simulatedLon) + " alt: " + str(simulatedAlt) + "\n")
                simulatedLocation = BalloonUpdate(simulatedTime, simulatedSeconds, simulatedLat, simulatedLon, simulatedAlt,
                                            "Iridium", self.mainWindow.groundLat, self.mainWindow.groundLon, self.mainWindow.groundAlt)
                # Notify main GUI of new location request
                self.mainWindow.iridiumInterpolateNewLocation.emit(simulatedLocation)
            QCoreApplication.processEvents()
            
    def addPosition(self, update):
         # Make sure it's a good location
        # Don't consider updates with bad info to be new updates
        if ((update.getLat() == 0.0) or (update.getLon() == 0.0) or (update.getAlt() == 0.0)):
            return

        # Makes sure it's the newest location
        if len(self.balloonLocations) >= 1 and update.getSeconds() <= self.balloonLocations[len(self.balloonLocations) - 1].getSeconds():
            return

        
        self.ticksSinceLastLocation = 0
        self.balloonLocations.append(update)
        if len(self.balloonLocations) >= 2:
            self.interpolate()

    def interpolate(self):
        print("-------NEW PREDICTION-------")
        #Simple prediction
        self.latDiff = self.balloonLocations[len(self.balloonLocations) - 1].getLat() - self.balloonLocations[len(self.balloonLocations) - 2].getLat()
        self.lonDiff = self.balloonLocations[len(self.balloonLocations) - 1].getLon() - self.balloonLocations[len(self.balloonLocations) - 2].getLon()
        self.altDiff = self.balloonLocations[len(self.balloonLocations) - 1].getAlt() - self.balloonLocations[len(self.balloonLocations) - 2].getAlt()
        self.timeDiff = self.balloonLocations[len(self.balloonLocations) - 1].getSeconds() - self.balloonLocations[len(self.balloonLocations) - 2].getSeconds()

        print("latDiff: " + str(self.latDiff))
        print("lonDiff: " + str(self.lonDiff))
        print("altDiff: " + str(self.altDiff))
        print("timeDiff : " + str(self.timeDiff) + "\n")
        print("----------------------------")
        self.latSpeed = self.latDiff / self.timeDiff
        self.lonSpeed = self.lonDiff / self.timeDiff
        self.altSpeed = self.altDiff / self.timeDiff    
        
        self.ready = True

    def interrupt(self):
        self.ready = False
        self.interpolateInterrupt = True

    def setUpdateSpeed(self, speed):
        self.updateSpeed = speed
        print("Set update speed to: " + str(self.updateSpeed))

