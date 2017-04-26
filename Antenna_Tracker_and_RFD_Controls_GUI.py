#!/usr/bin/env python
"""
Antenna Tracker Controller for Trident Antenna Array and RFD Radio Controller

Author:	Austin Langford, AEM
Based on work from Scott Miller, CpE, Dylan Trafford, CpE, and David Schwerr of the Montana Space Grant Consortium
Software created for use by the Minnesota Space Grant Consortium
Purpose: To acquire the location of a balloon in flight, and aim the array of antennae at the balloon
Additional Features: RFD 900 based Command Center and Image Reception
Creation Date: March 2016
Last Edit Date: September 14, 2016
"""

# System imports
import sys
import os
import time as t
from datetime import *
import serial
import serial.tools.list_ports
import threading

# Qt imports
import PyQt4
from PyQt4 import QtCore, QtGui
from PyQt4.QtWebKit import QWebView
from PyQt4.QtCore import *
from PyQt4.QtGui import *

# Scientific libraries
import math
import MySQLdb					  # database section, help from: http://www.tutorialspoint.com/python/python_database_access.htm
import numpy as np
import matplotlib
import geomag
import base64					   # = encodes an image in b64 Strings (and decodes)
import hashlib					  # = generates hashes

# Imports from files
from ui_trackermain import Ui_MainWindow	# UI file import
from ServoController import *			# Module for controlling Mini Maestro
from StillImageSystem import *			# RFD based Still Image system
from PointingMath import *				# Functions for calculating angles and distances
from RfdControls import *				# RFD commands and listen
from BalloonUpdate import *				# Class to hold balloon info
from GetData import *					# Module for tracking methods
from Payloads import *					# Module for handling payloads
from MapHTML import *						# Module for generating Google Maps HTML and JavaScript

# Matplotlib setup
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
matplotlib.use('Qt4Agg')
matplotlib.rcParams['backend.qt4']='PyQt4'

googleMapsApiKey = ''		# https://developers.google.com/maps/documentation/javascript/get-api-key

class EventThread(QThread):
    def run(self):
        self.exec_()


class WebView(QWebView):
	""" A class that allows messages from JavaScript being run in a QWebView to be printed """
	def javaScriptConsoleMessage(self, message, line, source):
		if source:
			print('line(%s) source(%s): %s' % (line, source, message))
		else:
			print(message)


class SerialDevice:
	""" A class to manage serial devices """

	def __init__(self,port,baud,timeout):
		self.port = port
		self.baud = baud
		self.timeout = timeout
		self.device = serial.Serial(port=self.port, baudrate=self.baud, timeout=self.timeout)

	def getPort(self):
		return self.port

	def getBaud(self):
		return self.baud

	def getTimeout(self):
		return self.timeout

	def getDevice(self):
		return self.device


class Unbuffered:
	""" A class to eliminate the serial buffer """
	def __init__(self, stream):
		self.stream = stream

	def write(self, data):
		self.stream.write(data)
		self.stream.flush()

	def flush(self):
		self.stream.flush()

	def close(self):
		self.stream.close()


class MainWindow(QMainWindow, Ui_MainWindow):
	""" The Main GUI Window """
	# Signals
	# RFD Command Signals
	commandFinished = pyqtSignal()
	rfdCommandNewText = pyqtSignal(str)
	rfdListenNewText = pyqtSignal(str)
	piruntimeFinished = pyqtSignal()

	# RFD Listen Signals
	rfdNewLocation = pyqtSignal(BalloonUpdate)
	iridiumNewLocation = pyqtSignal(BalloonUpdate)
	aprsNewLocation = pyqtSignal(BalloonUpdate)
	payloadUpdate = pyqtSignal(str)

	# Still Image Signals
	stillNewText = pyqtSignal(str)
	listboxUpdate = pyqtSignal(str)
	stillNewProgress = pyqtSignal(int,int)
	newPicture = pyqtSignal(str)
	requestConfirmation = pyqtSignal(str)
	newPicSliderValues = pyqtSignal(list)
	stillSystemFinished = pyqtSignal()

	# Data Signals
	noIridium = pyqtSignal()

	def __init__(self, parent=None):
		super(MainWindow, self).__init__(parent)
		self.setupUi(self)		# Uses the GUI built in QtCreator and interpreted using pyuic
		
		# Side Thread Setup
		# RFD Threads
		self.rfdListenThread = EventThread()
		self.rfdListenThread.daemon = True		# If you make a side thread's daemon True, it dies when the main GUI is killed
		self.rfdCommandThread = EventThread()
		self.rfdCommandThread.daemon = True
		self.stillImageThread = EventThread()
		self.stillImageThread.daemon = True

		# Data Threads
		self.iridiumThread = EventThread()
		self.iridiumThread.daemon = True
		self.aprsThread = EventThread()
		self.aprsThread.daemon = True

		# Start the threads, they should run forever, and add them to the thread pool
		self.rfdListenThread.start()
		self.rfdCommandThread.start()
		self.stillImageThread.start()
		self.iridiumThread.start()
		self.aprsThread.start()
		
		# Button Function Link Setup
		# Settings Tab Button Links
		self.updateSettings.clicked.connect(self.getSettings)
		self.antennaCenter.clicked.connect(self.moveToCenterPos)
		self.pointAtBalloon.clicked.connect(self.pointToMostRecentBalloon)
		self.trackerLaunch.clicked.connect(self.setAutotrack)
		self.recalibrateCenterBearing.clicked.connect(self.calibrateIMU)
		self.checkComPorts.clicked.connect(self.searchComPorts)

		# Manual Entry Button Links
		self.ManualEntryUpdateButton.clicked.connect(self.manualEntryUpdate)
		self.ManualAngleEntryButton.clicked.connect(self.manualAngleEntryUpdate)
		self.sliderButton.clicked.connect(lambda: self.sliderControl("click"))
		self.panServoSlider.valueChanged.connect(lambda: self.sliderControl("slide"))
		self.tiltServoSlider.valueChanged.connect(lambda: self.sliderControl("slide"))

		# Trim Button Links
		self.trimUpButton.clicked.connect(lambda: self.trimControl('up'))
		self.trimDownButton.clicked.connect(lambda: self.trimControl('down'))
		self.trimLeftButton.clicked.connect(lambda: self.trimControl('left'))
		self.trimRightButton.clicked.connect(lambda: self.trimControl('right'))
		self.trimResetButton.clicked.connect(lambda: self.trimControl('reset'))

		# RFD Control Button Links
		self.rfdCommandButton.clicked.connect(self.rfdCommandsButtonPress)
		self.rfdListenButton.clicked.connect(self.rfdListenButtonPress)
		self.getPiRuntimeDataButton.clicked.connect(self.getPiRuntimeDataButtonPress)
		self.requestStatusButton.clicked.connect(self.requestDeviceStatus)

		# Still Image Control Button Links
		self.mostRecentImageButton.clicked.connect(lambda: self.stillImageButtonPress('mostRecent'))
		self.imageDataTxtButton.clicked.connect(lambda: self.stillImageButtonPress('selectImage'))
		self.picDefaultSettingsButton.clicked.connect(self.picDefaultSettings)
		self.picSendNewSettingsButton.clicked.connect(lambda: self.stillImageButtonPress('sendNewSettings'))
		self.picGetSettingsButton.clicked.connect(lambda: self.stillImageButtonPress('getPicSettings'))
		self.connectionTestButton.clicked.connect(lambda: self.stillImageButtonPress('timeSync'))
		self.picHorizontalFlipButton.clicked.connect(lambda: self.stillImageButtonPress('HFlip'))
		self.picVerticalFlipButton.clicked.connect(lambda: self.stillImageButtonPress('VFlip'))

		# Make sure the allowed combination of auto tracking checkboxes are enabled
		self.autoDisabled.stateChanged.connect(self.disabledChecked)
		self.autoIridium.stateChanged.connect(self.autotrackChecked)
		self.autoAPRS.stateChanged.connect(self.autotrackChecked)
		self.autoRFD.stateChanged.connect(self.autotrackChecked)
	
		# Initial Still Image System Picture Display Setup
		self.stillImageOnline = False
		self.stillImageStall = False
		self.displayPhotoPath = "Images/MnSGC_Logo_highRes.png"  # The starting display photo is the logo of the MnSGC
		self.tabs.resizeEvent = self.resizePicture
		self.picLabel.setScaledContents(True)
		pm = QPixmap(self.displayPhotoPath)		# Create a pixmap from the default image
		scaledPm = pm.scaled(self.picLabel.size(),QtCore.Qt.KeepAspectRatio,QtCore.Qt.SmoothTransformation)
		self.picLabel.setPixmap(scaledPm)		# Set the label to the map
		self.picLabel.show()		# Show the image

		# Picture Qualities
		self.picWidth = 650
		self.picHeight = 450
		self.picSharpness = 0
		self.picBrightness = 50
		self.picContrast = 0
		self.picSaturation = 0
		self.picISO = 400
		
		# Still Image Slider Updates
		self.picWidthSlider.valueChanged.connect(self.updatePicSliderValues)
		self.picHeightSlider.valueChanged.connect(self.updatePicSliderValues)
		self.picSharpSlider.valueChanged.connect(self.updatePicSliderValues)
		self.picBrightSlider.valueChanged.connect(self.updatePicSliderValues)
		self.picContrastSlider.valueChanged.connect(self.updatePicSliderValues)
		self.picSaturationSlider.valueChanged.connect(self.updatePicSliderValues)
		self.picISOSlider.valueChanged.connect(self.updatePicSliderValues)

		# Booleans for Ground Station and Tracking Method settings
		self.servosAttached = False

		# Booleans for Ground Station and Tracking Method settings
		self.RFDAttached = False
		self.ardAttached = False
		self.APRSAttached = False
		self.useIridium = False
		self.useRFD = False
		self.useAPRS = False
		self.autotrackOnline = False
		self.useArduino = False
		self.manualLocal = False
		self.centerBearSet = False
		self.aprsStarted = False
		self.iridiumStarted = False
		self.autotrackBlock = False
		self.calibrationReady = False
		self.inSliderMode = False
		self.rfdStarted = False
		self.servosStarted = False
		self.arduinoStarted = False

		# RFD Commands Controls
		self.rfdCommandsOnline = False
		self.rfdListenOnline = False

		# Ground Station Variables
		self.groundLat = 0.00
		self.groundLon = 0.00
		self.groundAlt = 0.00
		self.antennaBear = 0.00
		self.antennaEle = 0.00
		self.centerBear = 0.00
		self.panOffset = 0.00
		self.tiltOffset = 0.00

		# Save Data Boolean
		self.saveData = False

		# SQL Access
		self.dbHost = "eclipse.rci.montana.edu"
		self.dbUser = "antenna"
		self.dbPass = "tracker"
		self.dbName = "freemanproject"

		# Tracking Labels for APRS and Iridium
		self.callsign = ""		# For the EAGLE Flight Computer
		self.IMEI = ""			# For the Iridium Modem

		self.payloadList = []		# List of payloads in this flight
		self.mapMade = False
		
		self.currentBalloon = BalloonUpdate('', 0, 0, 0, 0, '', 0, 0, 0)
		self.tabs.setCurrentIndex(0)

		# Graph Setup
		self.figure = Figure()
		self.canvas = FigureCanvas(self.figure)
		layout = QtGui.QVBoxLayout()
		layout.addWidget(self.canvas)
		self.graphWidget.setLayout(layout)

		# Graphing Arrays
		self.receivedTime = np.array([])
		self.receivedLat = np.array([])
		self.receivedLon = np.array([])
		self.receivedAlt = np.array([])
		self.losLog = np.array([])
		self.elevationLog = np.array([])
		self.bearingLog = np.array([])

		# Determine Serial Connections
		self.searchComPorts()

	def iridiumNoConnection(self):
		self.useIridium = False
		self.autoIridium.setChecked(False)
		if(not self.autoAPRS.isChecked() and not self.autoRFD.isChecked()):
			self.autoDisabled.setChecked(True)
		self.createWarning("Unable to Connect to Iridium Database")
		self.iridiumStarted = False


	def closeEvent(self, event):
		# At the close of the main window, write each payload's information to a file
		for each in self.payloadList:
			payloadInstance = "Logs/"+each.getName() + '-'+str(datetime.today().strftime("%m-%d-%Y %H-%M-%S")+'.txt')
			f = open(payloadInstance, 'w')
			for one in each.getMessages():
				f.write('Message' + ','+str(one.getTimestamp())+','+str(one.getMessage()) + '\n')
			for one in each.getGPSUpdates():
				f.write("GPS" + ','+str(one.getTimestamp())+','+str(one.getMessage()) + '\n')
			f.close()

		event.accept()
		
	def setAutotrack(self):
		""" Toggles autotracking """

		if self.autotrackOnline:
			self.autotrackOnline = False

			# Update a nice and pretty status indicator in red
			self.status.setText("Offline")
			self.changeTextColor(self.status,"red")
			self.trackerLaunch.setText("Launch Antenna Tracker")
			
		else:
			self.autotrackOnline = True
			self.tabs.setCurrentIndex(1)
			self.antennaOnline(self.currentBalloon)
			if not self.servosAttached:
				self.createWarning('No servos attached')

	def updateBalloonLocation(self, update):
		""" Updates the tracker with the latest balloon location """
		
		# Log the balloon location no matter what
		self.logData("balloonLocation", update.getTrackingMethod()+','+str(update.getTime())+','+str(update.getLat())+','+str(update.getLon())+','+str(update.getAlt())+','+str(update.getBear())+','+str(update.getEle())+','+str(update.getLOS()))

		if update.getTrackingMethod() == 'RFD':
			if not self.useRFD:
				return
		if update.getTrackingMethod() == 'Iridium':
			if not self.useIridium:
				return
		if update.getTrackingMethod() == 'APRS':
			if not self.useAPRS:
				return
		
		# Make sure it's a good location
		if ((update.getLat() == 0.0) or (update.getLon() == 0.0) or (update.getAlt() == 0.0)):		# Don't consider updates with bad info to be new updates
			return
		
		# Makes sure it's the newest location
		if update.getSeconds() < self.currentBalloon.getSeconds():
			return
			# Confirm that update matches a selected tracking method
			# if self.currentBalloon.getTrackingMethod() == 'RFD':
				# if (not self.useIridium or not self.useAPRS) and self.useRFD:
					# return
					
			# if self.currentBalloon.getTrackingMethod() == 'Iridium':
				# if (not self.useRFD or not self.useAPRS) and self.useIridium:
					# return
					
			# if self.currentBalloon.getTrackingMethod() == 'APRS':
				# if (not self.useIridium or not self.useRFD) and self.useAPRS:
					# return
			

		# If you haven't returned by now, update the graphing arrays
		try:
			self.updateGraphingArrays(update)
		except:
			print("Error updating graphing arrays with "+update.getTrackingMethod()+" Data")

		self.antennaOnline(update)		# Move the tracker if tracking
		self.refresh(update)			# Update the tables
		self.currentBalloon = update
		if self.internetAccess and self.mapMade:		# Update the map
			self.mapView.setHtml(getMapHtml(update.getLat(), update.getLon(), googleMapsApiKey))
	
	def updateIncoming(self, row, column, value):
		""" Update the Incoming GPS Data grid with the newest values """
		self.incomingDataTable.setItem(column, row, QtGui.QTableWidgetItem(str(value)))
		
	def updateGround(self, row, column, value):
		""" Update the Ground Station Data grid with the newest values """
		self.groundDataTable.setItem(column, row, QtGui.QTableWidgetItem(str(value)))
		
	def refresh(self, update):
		""" Refreshs the info grids and plots with the newest values """
		# Update the info grid with the newest balloon information
		self.updateIncoming(0, 0, update.getTime())
		self.updateIncoming(0, 1, update.getLat())
		self.updateIncoming(0, 2, update.getLon())
		self.updateIncoming(0, 3, round(update.getAlt(), 2))
		self.updateIncoming(0, 4, round(update.getEle(), 2))
		self.updateIncoming(0, 5, round(update.getBear(), 2))
		self.updateIncoming(0, 6, round(update.getLOS(), 2))
		self.updateIncoming(0, 7, round(update.getMagDec(), 2))
		self.updateIncoming(0, 8, update.getTrackingMethod())
			
		# Ground Station Data Table (usually doesn't change, but I guess it might)
		self.updateGround(0, 0, self.groundLat)
		self.updateGround(0, 1, self.groundLon)
		self.updateGround(0, 2, self.groundAlt)
		self.updateGround(0, 3, self.centerBear)

		# Antenna current "intended" position
		self.updateGround(0, 4, self.panOffset)
		self.updateGround(0, 5, self.tiltOffset)
		self.updateGround(0, 6, self.antennaBear)
		self.updateGround(0, 7, self.antennaEle)
		
		# Update the Graphs in the Tracker Tab
		if self.graphReal.isChecked():						# Check to see if you have the graph checkbox selected
			if len(self.receivedAlt) > 0:

				# creates the 4 subplots 
				altPlot = self.figure.add_subplot(221)
				losPlot = self.figure.add_subplot(222)
				elePlot = self.figure.add_subplot(223)
				bearPlot = self.figure.add_subplot(224)

				# discards the old graph
				altPlot.hold(False)
				losPlot.hold(False)
				elePlot.hold(False)
				bearPlot.hold(False)
				
				# plot data
				altPlot.plot(self.receivedTime-self.receivedTime[0],self.receivedAlt, 'r-')
				altPlot.set_ylabel('Altitude (ft)')
				losPlot.plot(self.receivedTime-self.receivedTime[0],self.losLog,'g-')
				losPlot.set_ylabel('Line-of-Sight (km)')
				elePlot.plot(self.receivedTime-self.receivedTime[0],self.elevationLog, 'b-')
				elePlot.set_ylabel('Elevation Angle')
				bearPlot.plot(self.receivedTime-self.receivedTime[0],self.bearingLog,'y-')
				bearPlot.set_ylabel('Bearing Angle')

				# refresh canvas
				self.canvas.draw()

	def manualRefresh(self):
		""" Updates the ground station data table """
		# Ground Station Data Table (usually doesn't change, but I guess it might)
		self.updateGround(0, 0, self.groundLat)
		self.updateGround(0, 1, self.groundLon)
		self.updateGround(0, 2, self.groundAlt)
		self.updateGround(0, 3, self.centerBear)

		# Antenna current "intended" position
		self.updateGround(0, 4, self.panOffset)
		self.updateGround(0, 5, self.tiltOffset)
		self.updateGround(0, 6, self.antennaBear)
		self.updateGround(0, 7, self.antennaEle)
					
	def getSettings(self):
		""" Go through the settings tab and update class and global variables with the new settings """
		
		# Determine whether or not to save the Data for this flight
		if self.saveDataCheckbox.isChecked():
			if not self.saveData:
				self.saveData = True
				timestamp = str(datetime.today().strftime("%m-%d-%Y %H-%M-%S"))

				# Create the log files
				self.rfdLog = "Logs/"+timestamp + ' ' + "RFDLOG.txt"
				f = open(self.rfdLog, 'w')
				f.close()
				self.stillImageLog = "Logs/"+timestamp + ' ' + "STILLIMAGELOG.txt"
				f = open(self.stillImageLog, 'w')
				f.close()
				self.balloonLocationLog = "Logs/"+timestamp + ' ' + "BALLOONLOCATIONLOG.txt"
				f = open(self.balloonLocationLog, 'w')
				f.close()
				self.pointingLog = "Logs/"+timestamp + ' ' + "POINTINGLOG.txt"
				f = open(self.pointingLog, 'w')
				f.close()
		elif not self.saveDataCheckbox.isChecked():
			self.saveData = False
			
		# Determine if there's internet Access for the maps
		if self.internetCheckBox.isChecked():
			self.internetAccess = True
			
			# Set up the Map View
			if not self.mapMade:
				self.mapView = WebView()
				self.mapView.setHtml(getMapHtml(45, -93, googleMapsApiKey))
				self.mapViewGridLayout.addWidget(self.mapView)
			self.mapMade = True
		else:
			self.internetAccess = False
		
		# Check to see what COM ports are in use, and assign them their values from the entry boxes
		self.servosAttached = self.servoAttached.isChecked()
		self.RFDAttached = self.rfdAttached.isChecked()
		self.ardAttached = self.arduinoAttached.isChecked()
		self.APRSAttached = self.aprsAttached.isChecked()

		if self.servoAttached.isChecked():
			if not self.servosStarted:
				if not self.servoCOM.text() == "":
					servoCOM = str(self.servoCOM.text())
					self.servos = SerialDevice(servoCOM, 9600, 0.5)
					self.servoController = ServoController(self.servos.getDevice())
					self.servoController.setServoAccel(1, 1)
					self.servoController.setServoSpeed(3, 1)
					self.servosStarted = True

		if self.rfdAttached.isChecked():
			if not self.rfdStarted:
				if not self.rfdCOM.text() == "":
					rfdCOM = str(self.rfdCOM.text())
					self.RFD = SerialDevice(rfdCOM, 38400, 2)

					# Prepare the RFD Controls and the Still Image System
					self.rfdListen = RfdListen(self, self.RFD.getDevice())
					self.rfdCommand = RfdCommand(self, self.RFD.getDevice())
					self.stillImageSystem = StillImageSystem(self, self.RFD.getDevice())
					
					# Move them to the side threads
					self.rfdListen.moveToThread(self.rfdListenThread)
					self.rfdCommand.moveToThread(self.rfdCommandThread)
					self.stillImageSystem.moveToThread(self.stillImageThread)

					# Set up slots
					self.rfdListen.listenStart.connect(self.rfdListen.listen)
					self.rfdListen.listenInterrupt.connect(lambda: self.rfdListen.setInterrupt(True))
					self.rfdListen.shareIdentifier.connect(self.rfdListen.setIdentifier)
					self.rfdCommand.commandStart.connect(self.rfdCommand.command)
					self.rfdCommand.commandInterrupt.connect(lambda: self.rfdCommand.setInterrupt(True))
					self.rfdCommand.foundIdentifier.connect(self.rfdCommand.setAcknowledged)
					self.rfdCommand.piruntimeStart.connect(self.rfdCommand.getPiRuntimeData)
					self.rfdCommand.statusStart.connect(self.rfdCommand.getDeviceStatus)
					
					# Connect the command and listen together
					self.rfdListen.setCommand(self.rfdCommand)
					self.rfdCommand.setListen(self.rfdListen)
					
					self.stillImageSystem.mostRecentImageStart.connect(self.stillImageSystem.getMostRecentImage)
					self.stillImageSystem.imageDataStart.connect(self.stillImageSystem.getImageDataTxt)
					self.stillImageSystem.requestedImageStart.connect(self.stillImageSystem.getRequestedImage)
					self.stillImageSystem.getSettingsStart.connect(self.stillImageSystem.getPicSettings)
					self.stillImageSystem.sendSettingsStart.connect(self.stillImageSystem.sendNewPicSettings)
					self.stillImageSystem.vFlipStart.connect(self.stillImageSystem.picVerticalFlip)
					self.stillImageSystem.hFlipStart.connect(self.stillImageSystem.picHorizontalFlip)
					self.stillImageSystem.timeSyncStart.connect(self.stillImageSystem.time_sync)
					self.stillImageSystem.stillInterrupt.connect(lambda: self.stillImageSystem.setInterrupt(True))
					
					self.rfdStarted = True

		if self.arduinoAttached.isChecked():
			if not self.arduinoStarted:
				if not self.arduinoCOM.text() == "":
					arduinoCOM = str(self.arduinoCOM.text())
					self.arduino = SerialDevice(arduinoCOM, 115200, 5)
					self.arduinoStarted = True

		if self.aprsAttached.isChecked():
			if self.aprsCallsign.text() == "":				# Get the APRS callsign too, default to placeholder
				self.callsign = str(self.aprsCallsign.placeholderText())
			else:
				self.callsign = self.aprsCallsign.text()
			if not self.aprsCOM.text() == "":
				aprsCOM = str(self.aprsCOM.text())
				self.APRS = SerialDevice(aprsCOM, 9600, 5)
				
		# Get the IMEI for the iridium modem, default to placeholder
		if self.iridiumIMEI.text() == '':
			self.IMEI = str(self.iridiumIMEI.placeholderText())
		else:
			self.IMEI = str(self.iridiumIMEI.text())
		
		# Get the center bearing
		if self.getLocal.isChecked():
			self.useArduino = True
			self.manualLocal = False
			if not self.centerBearSet:			# If the center bearing hasn't been set before, use the arduino to set it
				self.calibrateIMU()
		else:
			self.manualLocal = True
			self.useArduino = False
			if self.bearingNorth.isChecked():			# North Radio Button
				self.centerBear = 0
			elif self.bearingEast.isChecked():			# East Radio Button
				self.centerBear = 90
			elif self.bearingSouth.isChecked():		# South Radio Button
				self.centerBear = 180
			elif self.bearingWest.isChecked():			# West Radio Button
				self.centerBear = 270
			else:
				self.centerBear = 0
				print "Error with manual bearing setup"
			# Get the ground station location from the entry boxes, default to placeholder
			self.groundLat = self.manualLat.text()
			self.groundLon = self.manualLon.text()
			self.groundAlt = self.manualAlt.text()
			if self.groundLat == "":
				self.groundLat = self.manualLat.placeholderText()
			if self.groundLon == "":
				self.groundLon = self.manualLon.placeholderText()
			if self.groundAlt == "":
				self.groundAlt = self.manualAlt.placeholderText()
			self.groundLat = float(self.groundLat)
			self.groundLon = float(self.groundLon)
			self.groundAlt = float(self.groundAlt)

		# Determine which types of tracking are selected
		self.useIridium = self.autoIridium.isChecked()
		self.useAPRS = self.autoAPRS.isChecked()
		self.useRFD = self.autoRFD.isChecked()
		self.useDisabled = self.autoDisabled.isChecked()

		if self.useDisabled:
			self.useIridium = False
			self.useAPRS = False
			self.useRFD = False

		# Start up each type of tracking selected
		if self.useRFD:
			if not self.RFDAttached:
				self.createWarning('No RFD Attached')
				self.autoRFD.setChecked(False)
				self.useRFD = False 
			else:
				self.rfdListenStart()

		if self.useAPRS and not self.aprsStarted:
			if self.APRSAttached:  # Don't start it up again if it's already going
				self.getAPRS = GetAPRS(self, self.APRS.getDevice())
				self.getAPRS.moveToThread(self.aprsThread)
				self.getAPRS.start.connect(self.getAPRS.run)
				self.getAPRS.setInterrupt.connect(self.getAPRS.interrupt)
				self.getAPRS.start.emit()
				self.aprsStarted = True

			else:
				self.createWarning('No APRS Attached')
				self.autoAPRS.setChecked(False)
				self.useAPRS = False
				self.aprsStarted = False

		elif not self.useAPRS and self.aprsStarted:
			print("APRS Interrupted")
			self.getAPRS.setInterrupt.emit()
			self.aprsStarted = False

		if self.useIridium and not self.iridiumStarted:					# Don't start it up again if it's already going
			if self.internetAccess:
				self.getIridium = GetIridium(self, self.dbHost, self.dbUser, self.dbPass, self.dbName, self.IMEI)
				self.getIridium.moveToThread(self.iridiumThread)
				self.getIridium.start.connect(self.getIridium.run)
				self.getIridium.setInterrupt.connect(self.getIridium.interrupt)
				self.getIridium.start.emit()
				self.iridiumStarted = True

			else:
				self.createWarning('Iridium Tracking will not work without Internet Access')
				self.autoIridium.setChecked(False)
				self.useIridium = False
				self.iridiumStarted = False

		elif not self.useIridium and self.iridiumStarted:
			print("Iridium Interrupted")
			self.getIridium.setInterrupt.emit()
			self.iridiumStarted = False

		if self.autoIridium.isChecked() or self.autoAPRS.isChecked() or self.autoRFD.isChecked():
			self.manualRefresh()
		else:
			self.autoDisabled.setChecked(True)	
			self.useDisabled = True		
			self.manualRefresh()

	def createWarning(self, text):
		""" Creates a warning pop up window that can be dismissed by clicking the button """
		self.warning = QWidget()
		self.warningLabel = QLabel()
		self.warningLabel.setText(text)
		self.warningButton = QPushButton()
		self.warningButton.setText('OK')
		self.warningButton.clicked.connect(lambda: self.deleteWindow(self.warning))
		self.warningLayout = QVBoxLayout()
		self.warningLayout.addWidget(self.warningLabel)
		self.warningLayout.addWidget(self.warningButton)
		self.warning.setLayout(self.warningLayout)
		self.warning.show()

	def deleteWindow(self, window):
		""" Eliminates the window """
		window.deleteLater()
		
	def antennaOnline(self, update):
		""" Reaim the antennae while in autotrack mode """

		if self.autotrackOnline:
			self.status.setText("Online")
			self.changeTextColor(self.status, "green")		# Update a nice and pretty status indicator in green
			self.trackerLaunch.setText("Disable Antenna Tracker")
			if self.servosAttached:
				self.moveToTarget(update.getBear(), update.getEle())		# Move Antenna to correct position

		else:
			# Graphing Arrays - wipe them
			self.receivedTime = []
			self.receivedLat = []
			self.receivedLon = []
			self.receivedAlt = []
			self.losLog = []
			self.elevationLog = []
			self.bearingLog = []
			# Update a nice and pretty status indicator in red
			self.status.setText("Offline")
			self.changeTextColor(self.status, "red")
	
	def manualEntryUpdate(self):
		""" Takes the values from the manual coordinate entry boxes and updates the tracker """

		if not self.autotrackOnline:		# Only allow manual updates of the tracker if autotracking is disabled
			try:
				lat = float(self.ManualEntryLatitude.text())
				lon = float(self.ManualEntryLongitude.text())
				alt = float(self.ManualEntryAltitude.text())
				distance = haversine(self.groundLat, self.groundLon, lat, lon)
				bear = bearing(self.groundLat, self.groundLon, lat, lon)
				ele = elevationAngle(alt, self.groundAlt, distance)

				self.moveToTarget(bear, ele)		# Move the tracker
				self.manualRefresh()		# Update the ground station table
				print("Reaimed by Manual Coordinate Entry")

			except:
				print("Error with Manual Coordinate Entry, make sure Latitude, Longitude, and Altitude are entered")

	def manualAngleEntryUpdate(self):
		""" Takes the values from the manual angle entry boxes and updates the tracker """
		if not self.autotrackOnline:		# Only allow manual updates of the tracker if autotracking is disabled
			try:
				bear = float(self.manualEntryBearing.text())
				# Get the bearing between 0 and 360
				while bear < 0:
					bear += 360
				while bear > 360:
					bear -= 360
				print(bear)
				
				ele = float(self.manualEntryElevation.text())
				# Get the elevation angle between 0 and 360
				while ele < 0:
					ele += 360
				while ele > 360:
					ele -= 360
				print(ele)

				self.moveToTarget(bear,ele)
				self.manualRefresh()
				print("Reaimed by Manual Angle Entry")

			except Exception, e:
				print(str(e))
				print("Error with Manual Angle Entry, make sure Bearing and Elevation Angle are entered")
	
	def sliderControl(self, arg):
		""" Control the sliders when you hit the button, or stop it if you hit the button again """
		
		# When the start/stop button is clicked, toggle the state of the sliders
		if arg == "click":
			if not self.autotrackOnline:   # Only let this work if you're not in autotrack mode
				if self.inSliderMode:				# If you're in slider mode, set the boolean to false, change the text back and get out
					self.inSliderMode = False
					self.sliderButton.setText("START")
					self.sliderStatus.setText("OFF")
					self.changeTextColor(self.sliderStatus, "red")
					return
				elif not self.inSliderMode:		# if not in slider mode, change the boolean, text and text color
					print(self.inSliderMode)
					self.inSliderMode = True
					print(self.inSliderMode)
					self.sliderButton.setText("STOP")
					self.sliderStatus.setText("ON")
					self.changeTextColor(self.sliderStatus, "green")
					
		# When a slider position is changed, move the position of the servos
		if arg == "slide":
			if self.inSliderMode:			# Only move if you're in slider mode
				self.moveToTarget(self.panServoSlider.value(), self.tiltServoSlider.value())
				self.manualRefresh()			# Refresh the data tables
					
	def trimControl(self, arg):
		""" Updates the trim values when the trim buttons are clicked, and move the tracking accordingly """
		
		if arg == 'up':
			self.tiltOffset += 1
			print("Tilt Trim: "+str(self.tiltOffset))
		elif arg == 'down':
			self.tiltOffset -= 1
			print("Tilt Trim: "+str(self.tiltOffset))
		elif arg == 'left':
			self.panOffset -= 1
			print("Pan Trim: "+str(self.panOffset))
		elif arg == 'right':
			self.panOffset += 1
			print("Pan Trim: "+str(self.panOffset))
		elif arg == 'reset':
			self.tiltOffset = 0
			self.panOffset = 0
			print("Tilt Trim: "+str(self.tiltOffset))
			print("Pan Trim: "+str(self.panOffset))

		self.moveToTarget(self.antennaBear, self.antennaEle)			# Move the tracker
		self.manualRefresh()								# Update the ground station table
			
	def updateStillImageValues(self, values):
		""" Updates the still image system slider positions to match the values """
		self.picWidthSlider.setValue(values[0])
		self.picHeightSlider.setValue(values[1])
		self.picSharpSlider.setValue(values[2])
		self.picBrightSlider.setValue(values[3])
		self.picContrastSlider.setValue(values[4])
		self.picSaturationSlider.setValue(values[5])
		self.picISOSlider.setValue(values[6])
			
	def updatePicSliderValues(self):
		""" Updates the values displayed for the still image picture control sliders """
		self.picCurrentWidthValue.setText(str(self.picWidthSlider.value()))
		self.picCurrentHeightValue.setText(str(self.picHeightSlider.value()))
		self.picCurrentSharpnessValue.setText(str(self.picSharpSlider.value()))
		self.picCurrentBrightnessValue.setText(str(self.picBrightSlider.value()))
		self.picCurrentContrastValue.setText(str(self.picContrastSlider.value()))
		self.picCurrentSaturationValue.setText(str(self.picSaturationSlider.value()))
		self.picCurrentISOValue.setText(str(self.picISOSlider.value()))

	def stillImageSystemFinished(self):
		""" Resume the RFD listen if you were doing it before """
		
		self.stillImageStop()
		if self.stillImageStall:
			self.stillImageStall = False
			print('start')
			self.rfdListenStart()
			
	def stillImageStart(self):
		self.stillImageOnline = True
		self.stillImageOnlineLabel.setText("ON")
		self.changeTextColor(self.stillImageOnlineLabel, "green")
		self.logData('stillImage', 'toggle'+','+"Still Image System Turned On")
		
	def stillImageStop(self):
		self.stillImageOnline = False
		self.stillImageOnlineLabel.setText("OFF")
		self.changeTextColor(self.stillImageOnlineLabel, "red")
		self.logData("stillImage", 'toggle'+','+"Still Image System Turned Off")
		
	def stillImageButtonPress(self,arg):
		""" Starts the function associate to the button pressed in the worker thread """

		if arg == 'mostRecent':
			self.stillImageStart()
			if self.rfdListenOnline:
				self.stillImageStall = True
				self.rfdListenStop()
			self.stillImageSystem.mostRecentImageStart.emit(self.requestedImageName.text())
			
		if arg == 'selectImage':
			self.stillImageStart()
			if self.stillImageOnline:

				# Build the image selection window
				self.picSelectionWindow = QWidget()
				self.picSelectionWindow.setWindowTitle("Image Selection")
				self.listbox = QListWidget(self)
				self.picSelectionLabel = QLabel()
				self.picSelectionLabel.setText("Select the Picture to Receive")
				self.picSelectionButton = QPushButton()
				self.picSelectionButton.setText("Select")
				self.picSelectLayout = QVBoxLayout()
				self.picSelectLayout.addWidget(self.picSelectionLabel)
				self.picSelectLayout.addWidget(self.listbox)
				self.picSelectLayout.addWidget(self.picSelectionButton)
				self.picSelectionWindow.setLayout(self.picSelectLayout)
				self.picSelectionWindow.show()
				# Move to the function if they click select
				self.picSelectionButton.clicked.connect(lambda: self.checkRequestedImage(self.listbox.currentItem()))

			if self.rfdListenOnline:
				self.stillImageStall = True
				self.rfdListenStop()

			self.stillImageSystem.imageDataStart.emit()
			
		if arg == 'getPicSettings':
			self.stillImageStart()
			if self.rfdListenOnline:
				self.stillImageStall = True
				self.rfdListenStop()
			self.stillImageSystem.getSettingsStart.emit()
			
		if arg == 'sendNewSettings':
			self.stillImageStart()
			# Update the global values based on current slider position
			self.picWidth = int(self.picWidthSlider.value())
			self.picHeight = int(self.picHeightSlider.value())
			self.picSharpness = int(self.picSharpSlider.value())
			self.picBrightness = int(self.picBrightSlider.value())
			self.picContrast = int(self.picContrastSlider.value())
			self.picSaturation = int(self.picSaturationSlider.value())
			self.picISO = int(self.picISOSlider.value())
			picSettings = [self.picWidth,self.picHeight,self.picSharpness,self.picBrightness,self.picContrast,self.picSaturation,self.picISO]

			if self.rfdListenOnline:
				self.stillImageStall = True
				self.rfdListenStop()
			self.stillImageSystem.sendSettingsStart.emit(picSettings)
			
		if arg == 'HFlip':
			self.stillImageStart()
			if self.rfdListenOnline:
				self.stillImageStall = True
				self.rfdListenStop()
			self.stillImageSystem.hFlipStart.emit()
			
		if arg == 'VFlip':
			self.stillImageStart()
			if self.rfdListenOnline:
				self.stillImageStall = True
				self.rfdListenStop()
			self.stillImageSystem.vFlipStart.emit()
			
		if arg == 'timeSync':
			self.stillImageStart()
			if self.rfdListenOnline:
				self.stillImageStall = True
				self.rfdListenStop()
			self.stillImageSystem.timeSyncStart.emit()


	def updateListbox(self, line):
		self.listbox.addItem(line)

	def updatePicture(self, displayPath):
		""" Updates the still image system picture display to the picture associated with the path """

		print("Updating Picture")
		pm = QPixmap(str(displayPath))		# Create a pixmap from the default image
		scaledPm = pm.scaled(self.picLabel.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
		self.picLabel.setPixmap(scaledPm)			# Set the label to the map
		self.picLabel.show()				# Show the image
		
		self.logData('stillImage','newPic'+','+displayPath)

	def updatePictureProgress(self, progress, maxProgress):
		""" Updates the still image system photo progress bar based on the value and max value passed in as arguments """
		self.photoProgressBar.setMaximum(maxProgress)
		self.photoProgressBar.setValue(progress)

	def checkRequestedImage(self, pic):
		""" Still Image System: Make sure the user doesn't accidentally get a high res image """

		data = pic.text()
		if data[10] != 'b':		# High Res images are marked with a b

			# Create the window to ask for confirmation, with text and buttons
			self.confirmationCheckWindow = QWidget()
			self.confirmationLabel = QLabel()
			self.confirmationLabel.setText("WARNING! You have selected a high resolution image! Are you sure you want to download?")
			self.confirmationYesButton = QPushButton()
			self.confirmationNoButton = QPushButton()
			self.confirmationYesButton.setText("Yes")
			self.confirmationNoButton.setText("No")
			self.confirmationHLayout = QHBoxLayout()
			self.confirmationVLayout = QVBoxLayout()
			self.confirmationHLayout.addWidget(self.confirmationYesButton)
			self.confirmationHLayout.addWidget(self.confirmationNoButton)
			self.confirmationVLayout.addWidget(self.confirmationLabel)
			self.confirmationVLayout.addLayout(self.confirmationHLayout)
			self.confirmationCheckWindow.setLayout(self.confirmationVLayout)
			self.confirmationCheckWindow.show()

			# Connect the buttons to the functions
			self.confirmationYesButton.clicked.connect(lambda: self.getRequestedImageHelper(data))
			self.confirmationNoButton.clicked.connect(lambda: self.deleteWindow(self.confirmationCheckWindow))
			self.confirmationNoButton.clicked.connect(lambda: self.deleteWindow(self.picSelectionWindow))			

		else:
			self.getRequestedImageHelper(str(data))		# Go ahead and download the picture
			self.picSelectionWindow.deleteLater()

	def getRequestedImageHelper(self, data):
		""" Starts gettings the requested image in the rfd thread """

		# Get rid of the window's if they're still around
		try:
			self.deleteWindow(self.confirmationCheckWindow)
		except Exception, e:
			print(str(e))

		self.stillImageSystem.requestedImageStart.emit(data)

	def picDefaultSettings(self):
		""" Still Image System: Sets the camera variables to the default values """
			
		# Default Picture Settings
		width = 650
		height = 450
		sharpness = 0			# Default  =0; range = (-100 to 100)
		brightness = 50			# Default = 50; range = (0 to 100)
		contrast = 0			# Default = 0; range = (-100 to 100)
		saturation = 0			# Default = 0; range = (-100 to 100)
		iso = 400				# Unknown Default; range = (100 to 800)

		# Print/write to the browser what you're doing
		print "Default width:", width
		self.updateStillBrowser("Default Width: " + str(width))
		print "Default height:", height
		self.updateStillBrowser("Default Height: " + str(height))
		print "Default sharpness:", sharpness
		self.updateStillBrowser("Default Sharpness: " + str(sharpness))
		print "Default brightness:", brightness
		self.updateStillBrowser("Default Brightness: " + str(brightness))
		print "Default contrast:", contrast
		self.updateStillBrowser("Default Contrast: " + str(contrast))
		print "Default saturation:", saturation
		self.updateStillBrowser("Default Saturation: " + str(saturation))
		print "Default ISO:", iso
		self.updateStillBrowser("Default ISO: " + str(iso)+'\n')
		sys.stdout.flush()			# Clear the buffer
		
		# Change the slider values
		self.picWidthSlider.setValue(width)
		self.picHeightSlider.setValue(height)
		self.picSharpSlider.setValue(sharpness)
		self.picBrightSlider.setValue(brightness)
		self.picContrastSlider.setValue(contrast)
		self.picSaturationSlider.setValue(saturation)
		self.picISOSlider.setValue(iso)
		
		# Update the Values
		self.picWidth = width
		self.picHeight = height
		self.picSharpness = sharpness
		self.picBrightness = brightness
		self.picContrast = contrast
		self.picSaturation = saturation
		self.picISO = iso
		
		return
		
	def resizePicture(self, event):
		pm = QPixmap(self.displayPhotoPath)		# Create a pixmap from the default image
		scaledPm = pm.scaled(self.picLabel.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
		self.picLabel.setPixmap(scaledPm)			# Set the label to the map
		self.picLabel.show()				# Show the image
		
	def rfdListenButtonPress(self):
		""" Receives the press of the listen button, and handles it """

		if not self.rfdListenOnline:		# If listening isn't on, turn it on
			self.rfdListenStart()
				
		else:
			self.rfdListenStop()
			
	def rfdListenStart(self):
		""" Start the RFD Listen """
		if self.stillImageOnline:
			print("Still Image System cannot be Online")
			self.updateRFDBrowser("Still Image System cannot be Online")
			self.rfdListenOnline = False
			return

		if self.RFDAttached:		# Only try to do things if the RFD is attached
			self.rfdListenOnline = True
			self.rfdListenButton.setText("Stop Listening")		# Update the button text and label color
			self.rfdListenOnlineLabel.setText("ON")
			self.changeTextColor(self.rfdListenOnlineLabel, "green")

			self.logData("RFD","toggle"+','+"RFD Listen Online")

			# Starts the rfdListen function in the side thread so that it doesn't interrupt the main loop
			self.rfdListen.listenStart.emit()

		else:
			self.rfdListenOnline = False
			self.updateRFDBrowser("No RFD Radio attached")
			
	def rfdListenStop(self):
	
		self.rfdListenOnline = False 

		# Turn off the RFD listen, and change the button and label text and color
		self.rfdListen.listenInterrupt.emit()
		self.rfdListenButton.setText("Listen")
		self.rfdListenOnlineLabel.setText("OFF")
		self.changeTextColor(self.rfdListenOnlineLabel,"red")

		self.logData("RFD", 'toggle'+','+"RFD Listen Offline")
			
	def rfdCommandsButtonPress(self):
		""" Toggles the state of the RFD Commands """
		
		# If the commands aren't online, turn them online, and change the text/color of the label and button
		if not self.rfdCommandsOnline:
			if self.stillImageOnline:		# Don't let this work if the still image system is using the RFD 900
				print("Still Image System cannot be Online")
				self.updateRFDBrowser("Still Image System cannot be Online")
				return
			if self.RFDAttached:		# Only try to do things if the RFD is attached	
				self.rfdCommandsOnline = True

				self.logData("RFD",'toggle'+','+'RFD Commands Online')	# Log the toggle
				self.rfdCommandButton.setText("STOP")		# Change the button and label to opposite state
				self.rfdCommandsOnlineLabel.setText("ON")
				self.changeTextColor(self.rfdCommandsOnlineLabel,"green")
					
				# Acquire the identifier and command
				identifier = str(self.rfdIDEntry.text())
				command = str(self.rfdCommandEntry.text())
				if identifier == '' or command == '':		# Don't send null strings
					print("Null strings not allowed")
					self.updateRFDBrowser("Null strings not allowed")
					self.rfdCommandsOnline = False
					self.rfdListenOnline = False
					self.rfdCommandButton.setText("START")
					self.rfdCommandsOnlineLabel.setText("OFF")
					self.changeTextColor(self.rfdCommandsOnlineLabel,"red")
					return
				else:
					# Start up the RFD command function (and the listen if it isn't on already)
					if not self.rfdListenOnline:
						self.rfdListenStart()
					self.rfdCommand.commandStart.emit(identifier,command)

			else:		# If no RFD, let the user know and return
				print("No RFD Radio attached to this Computer")
				self.updateRFDBrowser("No RFD Radio attached to this Computer")
				return
		else:
			# Turn off the RFD Commands, and change the button and label text and color
			self.rfdCommand.commandInterrupt.emit()
			self.rfdCommandsOnline = False

			self.logData("RFD",'toggle'+','+"RFD Commands Offline")
			self.rfdCommandButton.setText("START")
			self.rfdCommandsOnlineLabel.setText("OFF")
			self.changeTextColor(self.rfdCommandsOnlineLabel, "red")

	def rfdCommandsDone(self):
		self.rfdCommandsOnline = False
		self.logData("RFD", 'toggle'+','+"RFD Commands Offline")
		self.rfdCommandButton.setText("START")
		self.rfdCommandsOnlineLabel.setText("OFF")
		self.changeTextColor(self.rfdCommandsOnlineLabel, "red")
		
	def getPiRuntimeDataButtonPress(self):
		""" Check to see if the system is in a state where it can receive the pi Runtime Data """
		
		if self.stillImageOnline:
			print("Still Image System cannot be Online")
			self.updateRFDBrowser("Still Image System cannot be Online")
			return

		if not self.RFDAttached:
			print("No RFD Attached")
			self.updateRFDBrowser("No RFD Attached")
			return

		self.rfdListenStop()
		self.rfdCommand.piruntimeStart.emit()
	
	def piruntimeDone(self):
		self.rfdListenStart()

	def requestDeviceStatus(self):
		""" Check to see if the system is in a state where it can receive the command relay device status """
		
		if self.stillImageOnline:
			print("Still Image System cannot be Online")
			self.updateRFDBrowser("Still Image System cannot be Online")
			return

		if not self.RFDAttached:
			print("No RFD Attached")
			self.updateRFDBrowser("No RFD Attached")
			return
			
		self.rfdCommand.statusStart.emit()

	def updateRFDBrowser(self, text):
		self.rfdReceiveBrowser.append(text)
		self.logData("RFD", "newText"+','+text)

	def updateStillBrowser(self, text):
		self.stillImageTextBrowser.append(text)
		self.logData("stillImage", "newText"+','+text)
						
	def updatePayloads(self, received):
		"""
		Updates the payloads by creating new ones when necessary, and adding messages 
		to the ones known. Updates the browsers in the payloads tabs as well
		"""
		
		# Go through each payload in the payload list, and see if this message is from a known payload
		knownPayload = False
		for each in self.payloadList:
			if each.getName() == str(received.split(';')[0]):
				each.addMessage(str(received.split(';')[1][:-2]))
				knownPayload = True
		
		if not knownPayload:
			if len(received.split(';')) == 2:		# If there is a new identifier, make a new payload and add the message to it
				print("Made new Payload: " + str(received.split(';')[0]))
				temp = self.tabs.currentIndex()
				self.tabs.setCurrentIndex(4)		# Change the current tab index to the payloads tab (to make the focus right)
				self.createNewPayload(str(received.split(';')[0]), str(received.split(';')[1][:-2]))		# Make the new payload
				self.tabs.setCurrentIndex(temp)		# Switch back to the tab you were on before it was made
		
		# Update the text browsers and maps in the payloads tab for each payload
		for each in self.payloadList:
			for line in each.getNewMessages():
				each.getMessageBrowser().append(line.getTimestamp() + " || " + line.getMessage())
			for line in each.getNewGPSUpdates():
				each.getGPSBrowser().append(line.getTimestamp() + " || " + line.getMessage())
			if each.hasMap() and each.inNewLocation():
				each.updateMap()
		
	def changeTextColor(self, obj, color):
		""" Changes the color of a text label to either red or green """
		
		if color == "red":		# Makes the label red
			palette = QtGui.QPalette()
			brush = QtGui.QBrush(QtGui.QColor(243, 0, 0))
			brush.setStyle(QtCore.Qt.SolidPattern)
			palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.WindowText, brush)
			brush = QtGui.QBrush(QtGui.QColor(243, 0, 0))
			brush.setStyle(QtCore.Qt.SolidPattern)
			palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.WindowText, brush)
			brush = QtGui.QBrush(QtGui.QColor(120, 120, 120))
			brush.setStyle(QtCore.Qt.SolidPattern)
			palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.WindowText, brush)
			obj.setPalette(palette)
		if color == "green":		# Makes the label green
			palette = QtGui.QPalette()
			brush = QtGui.QBrush(QtGui.QColor(21, 255, 5))
			brush.setStyle(QtCore.Qt.SolidPattern)
			palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.WindowText, brush)
			brush = QtGui.QBrush(QtGui.QColor(21, 255, 5))
			brush.setStyle(QtCore.Qt.SolidPattern)
			palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.WindowText, brush)
			brush = QtGui.QBrush(QtGui.QColor(120, 120, 120))
			brush.setStyle(QtCore.Qt.SolidPattern)
			palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.WindowText, brush)
			obj.setPalette(palette)
			
	def createNewPayload(self, name, msg):
		""" Make a new payload, add the message received to it, and create the proper display windows in the payloads tab """

		print("Create Payload")
		print(name, msg)
		
		if len(self.payloadList) == 0:
			self.payloadTabs = QtGui.QTabWidget()
			self.payloadTabs.setStyleSheet('QTabBar { font-size: 18pt; font-family: MS Shell Dlg 2; }')
			self.payloadTabGridLayout.addWidget(self.payloadTabs)
		
		# Make the payload label
		self.newPayloadLabel = QtGui.QLabel()
		self.newPayloadLabel.setText(name)
		# Make the payload Messages Label
		self.newPayloadMessagesLabel = QtGui.QLabel()
		self.newPayloadMessagesLabel.setText("Messages")
		self.newPayloadMessagesLabel.setFont(QtGui.QFont('MS Shell Dlg 2', 16))
		# Make the payload GPS Updates Label
		self.newPayloadGPSLabel = QtGui.QLabel()
		self.newPayloadGPSLabel.setText("GPS Updates")
		self.newPayloadGPSLabel.setFont(QtGui.QFont('MS Shell Dlg 2', 16))
		# Make the Messages Browser
		self.newPayloadMessagesBrowser = QtGui.QTextBrowser()
		self.newPayloadMessagesBrowser.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding)
		# Make the GPS Updates Browser
		newPayloadGPSBrowserName = "payloadGPSBrowser"+str(len(self.payloadList)+1)
		self.newPayloadGPSBrowser = QtGui.QTextBrowser()
		self.newPayloadGPSBrowser.setObjectName(newPayloadGPSBrowserName)
		self.newPayloadGPSBrowser.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding)
		# Make the grid layout and add elements to it
		newGridName = "payloadGridLLayout"+str(len(self.payloadList)+1)
		self.newGrid = QtGui.QGridLayout()
		self.newGrid.setObjectName(newGridName)
		self.newGrid.addWidget(self.newPayloadMessagesLabel, 0, 0, 1, 1)
		self.newGrid.addWidget(self.newPayloadGPSLabel, 0, 1, 1, 1)
		self.newGrid.addWidget(self.newPayloadMessagesBrowser, 1, 0, 1, 1)
		
		if self.internetAccess:		# Only make the map if you have internet access
			# Make the QWebView
			newPayloadWebViewName = 'payloadWebView'+str(len(self.payloadList)+1)
			self.newPayloadWebView = WebView()
			self.newPayloadWebView.setObjectName(newPayloadWebViewName)
			self.newPayloadWebView.setSizePolicy(QtGui.QSizePolicy.Ignored, QtGui.QSizePolicy.Expanding)
			# Make a Vertical Layout for the GPS Browser and Webview
			self.newPayloadVertical = QtGui.QVBoxLayout()
			self.newPayloadVertical.addWidget(self.newPayloadGPSBrowser)
			self.newPayloadVertical.addWidget(self.newPayloadWebView)
			self.newGrid.addLayout(self.newPayloadVertical, 1, 1, 1, 1)
			self.newPayloadWebView.setHtml(getMapHtml(self.currentBalloon.getLat(), self.currentBalloon.getLon(), googleMapsApiKey))
			
		else:
			self.newGrid.addWidget(self.newPayloadGPSBrowser, 1, 1, 1, 1)
		
		# Add the new objects to a new tab
		self.tempWidget = QWidget()
		self.tempWidget.setLayout(self.newGrid)
		self.payloadTabs.addTab(self.tempWidget, name)
		
		newPayload = Payload(name, self.newPayloadMessagesBrowser, self.newPayloadGPSBrowser)		# Create the new payload
		if self.internetAccess:		# If there's internet, add the webview
			newPayload.addWebview(self.newPayloadWebView)
			
		newPayload.addMessage(msg)
		self.payloadList.append(newPayload)
		
	def searchComPorts(self):
		""" Sets the Connections based on the Com Ports in use """
		
		ardCheck = False
		serCheck = False
		rfdCheck = False
		aprsCheck = False
		ports = list(serial.tools.list_ports.comports())
		
		# Go through each port, and determine if it matches a known device
		for each in ports:
			print(each)
			eachLst = str(each).split('-')
			# The Arduino shows up as Arduino Uno
			if (eachLst[1].find("Arduino Uno") != -1) or (each.pid == 67):
				arduinoCOM = eachLst[0].strip()
				self.arduinoCOM.setText(arduinoCOM)
				self.arduinoAttached.setChecked(True)
				self.arduinoAttached.setChecked(True)
				self.bearingNorth.setChecked(False)
				ardCheck = True
				
			try:		# Mini Maestro shows up as Pololu Micro Maestro 6, but with 2 ports. We want the command port
				if eachLst[1].find("Pololu Micro Maestro 6") and eachLst[2].find("Servo Controller Command Port") != -1:
					servoCOM = eachLst[0].strip()
					self.servoCOM.setText(servoCOM)
					self.servoAttached.setChecked(True)
					serCheck = True

			except:		# Because not every port has 2 '-' characters, the split function may not work
				if (each.vid == 8187 and each.pid == 137) and each.location is None:
					servoCOM = eachLst[0].strip()
					self.servoCOM.setText(servoCOM)
					self.servoAttached.setChecked(True)
					serCheck = True

			# RFD 900 has vid 1027 and pid 24577
			if each.vid == 1027 and each.pid == 24577:
				rfdCOM = each[0].strip()
				self.rfdCOM.setText(rfdCOM)
				self.rfdAttached.setChecked(True)
				rfdCheck = True

			# The USB to Serial cable used with the APRS receiver identifies itself as Prolific USB-to-Serial Comm Port
			if (eachLst[1].find("Prolific") != -1) or (each.vid == 1659 and each.pid == 8963):
				aprsCOM = eachLst[0].strip()
				self.aprsCOM.setText(aprsCOM)
				self.aprsAttached.setChecked(True)
				aprsCheck = True
				
		# After checking all of the ports, you can see if a device has been disconnected
		if not ardCheck:
			self.arduinoAttached.setChecked(False)
			self.bearingNorth.setChecked(True)
			self.arduinoCOM.setText('')
			self.arduinoAttached.setChecked(False)
		if not serCheck:
			self.servoCOM.setText('')
			self.servoAttached.setChecked(False)
		if not rfdCheck:
			self.rfdCOM.setText('')
			self.rfdAttached.setChecked(False)
		if not aprsCheck:
			self.aprsCOM.setText('')
			self.aprsAttached.setChecked(False)
			
	def disabledChecked(self):
		""" Makes sure that only the disabled autotrack option is checked """

		if self.autoDisabled.isChecked():
			self.autotrackBlock = True
			self.autoIridium.setChecked(False)
			self.autoAPRS.setChecked(False)
			self.autoRFD.setChecked(False)
		self.autotrackBlock = False

	def autotrackChecked(self):
		""" Makes sure that disabled isn't checked if there is an autotrack option checked """

		if self.autoIridium.isChecked() or self.autoAPRS.isChecked() or self.autoRFD.isChecked():
			if not self.autotrackBlock:
				self.autoDisabled.setChecked(False)

	def calibrateIMU(self):
		""" Display the calibration values for the IMU in a visible window,
		and allow the user to select when the calibration is ready
		"""
		
		if self.ardAttached:
			if not self.useArduino:
				self.createWarning('Need to select Get Local for Center Bearing')
				print("Need to select Get Local for Center Bearing")
				return

			try:
				s2 = self.arduino.getDevice()
			except:
				print("Error opening the Arduino serial port")
				return

			try:
				# Make the Display Window for the Calibration
				self.calibrationWindow = QWidget()
				self.calibrationWindow.setWindowTitle("IMU Calibration")
				self.vLayout = QtGui.QVBoxLayout()
				self.calBrowser = QtGui.QTextBrowser()
				self.calButton = QtGui.QPushButton()
				self.calLabel = QtGui.QLabel()
				self.calLabel.setText("Press Ready when you are done with the calibration")
				self.calButton.setText("Ready")
				self.calButton.clicked.connect(lambda: self.getCenterBearing(s2))
				self.vLayout.addWidget(self.calLabel)
				self.vLayout.addWidget(self.calBrowser)
				self.vLayout.addWidget(self.calButton)
				self.calibrationWindow.setLayout(self.vLayout)
				self.calibrationWindow.show()
			except:
				print("Error creating the calibration window")
				return

			self.calibrationReady = False
			while not self.calibrationReady:		# Continuously loop until the IMU is calibrated to satisfaction
				temp_arduino = "0"
				s2.flushInput()		# Clear the buffer so it can get new info
				t.sleep(0.05)
				while temp_arduino[0] != '~':		# The arduino string is comma separated, and starts with ~
					temp_arduino = s2.readline()
					temp_arduino = temp_arduino.split(',')
					displayStr = 'System: ' + temp_arduino[7] + '; ' + 'Gyro: ' + temp_arduino[8] + '; ' + 'Accel: '+temp_arduino[9] + '; ' + 'Mag: '+temp_arduino[10]
					print(displayStr)
					self.calBrowser.append(displayStr)
				QCoreApplication.processEvents()
		else:
			self.createWarning('No Arduino Attached')
			print("No Arduino Attached")

	def getCenterBearing(self, s2):
		""" Acquire a center bearing and a GPS location from the calibration arduino """

		self.calibrationWindow.deleteLater()
		self.calBrowser.deleteLater()
		self.calLabel.deleteLater()
		self.vLayout.deleteLater()
		self.calButton.deleteLater()
		self.calibrationReady = True
		temp_arduino = "0"
		s2.flushInput()		# Clear the buffer so it can read new info
		while temp_arduino[0] != '~':
			temp_arduino = s2.readline()
			temp_arduino = temp_arduino.split(',')
		tempLat = temp_arduino[1]		# Get ground station latitude
		tempLon = temp_arduino[2]		# Get ground station longitude
		tempAlt = temp_arduino[3]		# Get ground station altitude
		tempoffsetDegrees = temp_arduino[4]		# Get the offset for the center bearing
		tempLat = tempLat.split(".")
		self.groundLat = float(tempLat[0])+float(tempLat[1])/10000000 		# Convert the lat to decimal degrees as a float
		tempLon = tempLon.split(".")
		self.groundLon = float(tempLon[0])-float(tempLon[1])/10000000		# Convert the lon to decimal degrees as a float
		tempAlt = tempAlt.split(".")
		self.groundAlt = int(tempAlt[0])										# Get the altitude to the floor(foot)
		self.centerBear = float(tempoffsetDegrees)
		declination = float(geomag.declination(dlat=self.groundLat, dlon=self.groundLon, h=self.groundAlt))
		self.centerBear = (self.centerBear+declination)
		if self.centerBear > 360:
			self.centerBear -= 360
		elif self.centerBear < 0:
			self.centerBear += 360
		print "Local Latitude: \t", self.groundLat
		print "Local Longitude:\t", self.groundLon
		print "Local Altitude: \t", self.groundAlt
		print "Offset Degrees: \t", self.centerBear
		print "Declination:	\t", declination
		print "Offset + Dec:   \t", self.centerBear
		print "-------------------------------------------------------"

		self.antennaBear = self.centerBear
		self.centerBearSet = True		# Lets the program know that the center bearing has been set before
		self.manualRefresh()

	def updateGraphingArrays(self, location):
		if len(self.receivedTime) == 0:
			self.receivedTime = np.append(self.receivedTime, location.getSeconds())
			self.receivedLon = np.append(self.receivedLon, location.getLon())
			self.receivedLat = np.append(self.receivedLat, location.getLat())
			self.receivedAlt = np.append(self.receivedAlt, location.getAlt())
			self.bearingLog = np.append(self.bearingLog, location.getBear())
			self.elevationLog = np.append(self.elevationLog, location.getEle())
			self.losLog = np.append(self.losLog, location.getLOS())
		elif self.receivedTime[len(self.receivedTime) - 1] < location.getSeconds():
			self.receivedTime = np.append(self.receivedTime, location.getSeconds())
			self.receivedLon = np.append(self.receivedLon, location.getLon())
			self.receivedLat = np.append(self.receivedLat, location.getLat())
			self.receivedAlt = np.append(self.receivedAlt, location.getAlt())
			self.bearingLog = np.append(self.bearingLog, location.getBear())
			self.elevationLog = np.append(self.elevationLog, location.getEle())
			self.losLog = np.append(self.losLog, location.getLOS())

	def logData(self, type, msg):
		""" Logs the message in the correct file designated in the type argument """
		if self.saveData:
			try:
				if type == "RFD":
					f = open(self.rfdLog, 'a')
				elif type == "stillImage":
					f = open(self.stillImageLog, 'a')
				elif type == "balloonLocation":
					f = open(self.balloonLocationLog, 'a')
				elif type == "pointing":
					f = open(self.pointingLog, 'a')
				f.write(str(datetime.today().strftime("%m/%d/%Y %H:%M:%S"))+','+msg+'\n')
				f.close()
			except:
				print("Error logging data: "+type+','+msg)

		else:
			return

	def pointToMostRecentBalloon(self):
		""" Aims the tracker at the balloon, even if the antenna tracker is offline """

		if self.servosAttached:
			self.moveToTarget(self.currentBalloon.getBear(), self.currentBalloon.getEle())
			print("Tracker aimed at most recent balloon location")
		else:
			print "Error: Settings set to no Servo Connection"

	def moveToCenterPos(self):
		""" Send servos to their center pos (should be horizontal and straight ahead if zeroed) """

		if self.servosAttached:
			try:
				self.servoController.moveTiltServo(127)
				self.servoController.movePanServo(127)
			except:
				print("Error moving servos to center position")
			
			# Set the antenna bearing and elevation to the center position
			self.antennaBear = self.centerBear
			self.antennaEle = 0
			self.manualRefresh()

		else:
			print "Error: Settings set to no Servo Connection"

	def moveToTarget(self, bearing, elevation):
		""" Moves servos based on a bearing and elevation angle """
		
		temp = 0
		# Uses the center bearing, and makes sure you don't do unnecessary spinning when you're close to 0/360
		if (bearing>180) and (self.centerBear == 0):
			self.centerBear = 360
		elif ((self.centerBear - bearing) > 180) and (self.centerBear >= 270):
			bearing += 360
		elif ((self.centerBear - bearing) > 180) and (self.centerBear <= 180):
			temp = self.centerBear
			self.centerBear = 360 + temp

		print ("\tBearing: %.0f" %(bearing+self.panOffset))
		print ("\tElevation Angle: %.0f"%(elevation+self.tiltOffset))

		# With new digital servos, can use map method as described here: http://arduino.cc/en/reference/map
		# Get the correct numerical value for the servo position by adjusting based on offset, max and min
		panTo = ((bearing - (self.centerBear - 168)) * (self.servoController.servoMax - self.servoController.servoMin) / ((self.centerBear + 168) - (self.centerBear - 168)) + self.servoController.servoMin) + (255*self.panOffset/360)
		if panTo > 254:
			panTo = 254
		if panTo < 0:
			panTo = 0
		print "\tServo Degrees:"
		if self.servosAttached:
			self.servoController.movePanServo(math.trunc(panTo))

		# Get the correct numerical value for the servo position by adjusting based on offset, max and min
		tiltTo = (((0-elevation) - self.servoController.tiltAngleMin) * (self.servoController.servoMax - self.servoController.servoMin) / (self.servoController.tiltAngleMax - self.servoController.tiltAngleMin) + self.servoController.servoMin) + (255*(-self.tiltOffset)/360)
		print(tiltTo)
		if tiltTo > 254:
			tiltTo = 254		# Don't go over the max
		if tiltTo < 0:
			tiltTo = 0			# Don't go under the min
		if self.servosAttached:		# Move the servos to the new locations if they're attacheed
			self.servoController.moveTiltServo(math.trunc(tiltTo))
		if temp != 0:
				self.centerBear = temp
			
		# Write the new pointing location to the log file
		self.logData("pointing", str(bearing)+','+str(elevation))

		# Update pointing values
		self.antennaBear = bearing
		self.antennaEle = elevation
		self.manualRefresh()
	
if __name__ == "__main__":
	app = QtGui.QApplication.instance()		# checks if QApplication already exists
	if not app:								# create QApplication if it doesnt exist 
		app = QtGui.QApplication(sys.argv)
		
	# Let's .jpg be shown (http://www.qtcentre.org/threads/49119-JPG-not-working-when-calling-setPixmap()-on-QLabel)
	path = r"C:\Users\Ground Station\Anaconda2\Lib\site-packages\PySide\plugins"
	app.addLibraryPath(path)

	with open('api_key') as f:
		googleMapsApiKey = f.readline().strip()
	
	mGui = MainWindow()						# Launch the main window
	mGui.showMaximized()					# Shows the main window maximized
	sys.stdout = Unbuffered(sys.stdout)		# Sets up an unbuffered stream
	app.exec_()								# Starts the application
