from PySide2 import *
from PySide2 import QtCore, QtGui
from PySide2.QtCore import *
from PySide2.QtCore import Signal as pyqtSignal
import time
from time import sleep
from BalloonUpdate import *			# Class to hold balloon info
import json

import SignalScraper as scraper

class UbiquitiSignalScraper(QtCore.QObject):

    # Received Signals
    start = pyqtSignal()
    setInterrupt = pyqtSignal()
    
    def __init__(self, MainWindow, IP, username, password):
        super(UbiquitiSignalScraper, self).__init__()
        self.mainWindow = MainWindow
        self.signalScraperInterrupt = False

        # Characteristics
        self.updateSpeed = 0.5    # in seconds

        # Emitted Signals
        self.mainWindow.ubiquitiNewSignalStrength.connect(
            self.mainWindow.updateUbiquitiSignalStrength)
        self.mainWindow.ubiquitiScraperError.connect(
            self.mainWindow.handleUbiquitiScraperError)

        self.ip = IP
        # Start the scraper
        scraper.begin('Drivers/chromedriver.exe', self.ip, username=username, password=password)

    def run(self):
        """ Scrapes signal strength from the modem and provides info to main window """
        self.signalScraperInterrupt = False
        
        while not self.signalScraperInterrupt:
            time.sleep(self.updateSpeed)  # frequency
            try:
                strength = scraper.fetch_signal(self.ip)
                self.mainWindow.ubiquitiNewSignalStrength.emit(strength)
            except json.decoder.JSONDecodeError:
                self.mainWindow.ubiquitiScraperError.emit('JSON Fetch')

            QCoreApplication.processEvents()  # Allow the thread to process events

    def interrupt(self):
        self.signalScraperInterrupt = True

    def setUpdateSpeed(self, speed):
        self.updateSpeed = speed
        print("Set update speed to: " + str(self.updateSpeed))
