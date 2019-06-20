from PySide2 import *
from PySide2 import QtCore, QtGui
from PySide2.QtCore import *
from PySide2.QtCore import Signal as pyqtSignal
import time
from time import sleep
from BalloonUpdate import *			# Class to hold balloon info

import SignalScraper as scraper


class UbiquitySignalTracker(QtCore.QObject):

    # Received Signals
    start = pyqtSignal()
    setInterrupt = pyqtSignal()
    
    def __init__(self, MainWindow, IP):
        super(UbiquitySignalTracker, self).__init__()
        self.mainWindow = MainWindow
        self.signalTrackerInterrupt = False

        # Characteristics
        self.updateSpeed = 0.25    # in seconds

        # Emitted Signals
        self.mainWindow.ubiquityNewSignalStrength.connect(
            self.mainWindow.updateUbiquitySignalStrength)

        self.ip = IP
        # Start the scraper
        scraper.begin('C://chromedriver.exe', self.ip, password='ground')

    def run(self):
        """ Interpolates Iridium tracking information to provide smoother tracking """
        self.signalTrackerInterrupt = False
        
        while not self.signalTrackerInterrupt:
            time.sleep(self.updateSpeed)  # frequency
            strength = scraper.fetch_signal(self.ip)
            self.mainWindow.ubiquityNewSignalStrength.emit(strength)
            QCoreApplication.processEvents()  # Allow the thread to process events

    def interrupt(self):
        self.ready = False
        self.signalTrackerInterrupt = True

    def setUpdateSpeed(self, speed):
        self.updateSpeed = speed
        print("Set update speed to: " + str(self.updateSpeed))

