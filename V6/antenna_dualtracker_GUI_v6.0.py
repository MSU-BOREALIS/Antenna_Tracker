#################################################################################################################################
#       Antenna Tracker Controller for Trident Antenna Array                                                                    #
#                                                                                                                               #
#       Authors: Dylan Trafford, EE & CpE                                                                                       #
#                Trevor Gahl, CpE                                                                                               #
#       Based on work from Scott Miller, CpE                                                                                    #
#       Software created for use by Montana Space Grant Consortium's BOREALIS program                                           #
#       Purpose: To get data from the mySQL database to steer an antenna array                                                  #
#       Creation Date: June 2015                                                                                                #
#       Last Edit Date: 6/24/2016                                                                                               #
#################################################################################################################################

from ui_trackermain import Ui_MainWindow
import PySide
from PySide import QtCore, QtGui
from PySide.QtCore import *
from PySide.QtGui import QApplication, QMainWindow, QTextEdit, QPushButton, QMessageBox
from PySide.QtGui import *
import sys
import os
import math
import serial
import time
import geomag
import MySQLdb                      # database section, help from: http://www.tutorialspoint.com/python/python_database_access.htm
import pyqtgraph as pg
import numpy as np
from datetime import *
import time
import smtplib
from email.mime.text import *
import matplotlib

from matplotlib.figure import Figure
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas

matplotlib.use('Qt4Agg')
matplotlib.rcParams['backend.qt4']='PySide'

#import matplotlib.pyplot as plt
import ast
    

#NOTE:  System was originally designed to operate using one servo controller and two antenna systems. One system ran Ubiquity
#       and the other system ran RFD 900MHz. This has recently been changed to run both antenna systems using only one tripod.

#Ground station location
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
#previousPan = 127       #Memory for last position (To account for backlash)
# Pololu servo controller commands using Mini SSC Protocol, 
#  see: http://www.pololu.com/docs/0J40/5.c  
# Shouldn't need to change these usually

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

# change the movement speed etc of RFD900 tilt servo
#rfd_tiltChannel = 2
#rfd_tiltRange = 360
#rfd_tiltAccel = 1
#rfd_tiltSpeed = 2
#rfd_tilt_angle_min = -180
#rfd_tilt_angle_max = 180

# change the movement speed etc of RFD900 pan servo
#rfd_panChannel = 3
#rfd_panRange = 360
#rfd_panAccel = 5
#rfd_panSpeed = 5

#Graphing Arrays
receivedTime = np.array([])
receivedLat = np.array([])
receivedLon = np.array([])
receivedAlt = np.array([])
losLog = np.array([])
elevationLog = np.array([])
bearingLog = np.array([])


#SQL Access
    #Open database connection
db_host = "eclipse.rci.montana.edu"
db_user = "antenna"
db_passwd = "tracker"
db_name = "freemanproject"
db = MySQLdb.connect(host="eclipse.rci.montana.edu",user="antenna",passwd="tracker",db="freemanproject")
IMEI = "xxxxxxxxxxxxxxx"     #######   YOU MUST ENTER YOUR IMIE NUMBER HERE   ##########
    #prepare a cursor object using cursor() method
cursor = db.cursor()



class MainWindow(QMainWindow,Ui_MainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        self.setupUi(self)
        #Button Function Link Setup
        self.updateSettings.clicked.connect(self.getSettings)
        self.antennaCenter.clicked.connect(moveToCenterPos)
        self.motionTest.clicked.connect(panBothServos)
        self.trackerLaunch.clicked.connect(self.setAutotrack)
        self.PointButton.clicked.connect(self.pointToTarget)
        #self.tempOverride.clicked.connect(self.setOverride)
#        self.cutdownCmd.clicked.connect(self.cutdownEmail)
#        self.abortCmd.clicked.connect(self.abortEmail)
        #This allows for updating tables as a thread type funciton via refresh
        self.refreshtimer = QtCore.QTimer()
        self.refreshtimer.timeout.connect(self.refresh)
        self.refreshtimer.start(5000)
        #Get Data Timer
        self.datatimer = QtCore.QTimer()
        self.datatimer.timeout.connect(getData)
        self.datatimer.start(5000)
        #Antenna Movement Enable
        self.antennatimer = QtCore.QTimer()
        self.antennatimer.timeout.connect(self.antennaOnline)
        self.antennatimer.start(5000)
        #Manual Control Slider
        self.hSlider.valueChanged.connect(self.valueChange)
        self.vSlider.valueChanged.connect(self.valueChange)

        
##        #Animation Timer
##        self.anitimer = QtCore.QTimer()
##        self.anitimer.timeout.connect(self.trackerAnimation)
##        self.anitimer.start(500)
##        #Email Timer
##        self.email = QtCore.QTimer()
##        self.email.timeout.connect(self.dummy)
##        self.email.start(1000)
        
        self.tl = QtCore.QTimeLine(1000)
        self.tl2 = QtCore.QTimeLine(1000)
        self.tl.setFrameRange(0, 100)
        self.tl2.setFrameRange(0, 100)
        self.a = QtGui.QGraphicsItemAnimation()
        self.b = QtGui.QGraphicsItemAnimation()
        self.c = QtGui.QGraphicsItemAnimation()
        self.d = QtGui.QGraphicsItemAnimation()
        self.e = QtGui.QGraphicsItemAnimation()
        
        self.scene = QtGui.QGraphicsScene(self)

        self.balloon = QtGui.QGraphicsEllipseItem(-40,-50,40,50)
        self.balloon.setBrush(QColor(Qt.white))
        self.payload = QtGui.QGraphicsRectItem(-10,-10,10,10)
        self.payload.setBrush(QColor(Qt.darkRed))

        self.payloadString1 = QtGui.QGraphicsRectItem(-10,-5,10,10)
        
        self.antenna = QtGui.QGraphicsEllipseItem(-70,-70,70,70)

        self.balLoc = QtGui.QGraphicsTextItem("Balloon Loc")
        self.antLoc = QtGui.QGraphicsTextItem("Antenna Loc")
        
        self.origin = QtGui.QGraphicsEllipseItem(-2,-2,2,2)
        
        #self.installEventFilter(self)
        
        #Graphing
        
        #self.figure = plt.figure()
        self.figure = Figure()        
        self.canvas = FigureCanvas(self.figure)
        
        layout = QtGui.QVBoxLayout()
        
        layout.addWidget(self.canvas)
        
        self.widget.setLayout(layout)
        
##        self.plotAlt.plot(receivedTime,receivedAlt,pen = 'r',title = "Altitude (ft)")
##        self.plotAlt.showGrid(x=True,y = True,alpha = 1)
##
##        self.plotLOS.plot(receivedTime,losLog,pen = 'g',title = "Line-of-Sight (km)")
##        self.plotLOS.showGrid(x=True,y = True,alpha = 1)
##
##        self.plotElevation.plot(receivedTime,elevationLog,pen = 'y',title = "Elevation")
##        self.plotElevation.showGrid(x=True,y = True,alpha = 1)
##
##        self.plotBear.plot(receivedTime,bearingLog,pen = 'b',title = "Bearing")
##        self.plotBear.showGrid(x=True,y = True,alpha = 1)
##        
    def valueChange(self):
        global antennaEle, antennaBear
        global panOffset, tiltOffset, centerBear, trackTiltOffset, trackBearOffset
        panOffset = self.hSlider.value()
        trackBearOffset = self.hSlider.value()
        tiltOffset = 0 - self.vSlider.value()
        trackTiltOffset = self.vSlider.value()
        moveToTarget(antennaBear,antennaEle)
        self.refresh()

            
##    def eventFilter(self,widget,event):         #This sets up a keyboard event listener that allows arrow key controls of the dish after clicking on the animation frame in the second tab.
##        global antennaEle, antennaBear
##        global panOffset, tiltOffset, centerBear, trackTiltOffset, trackBearOffset
##        if(event.type() == QtCore.QEvent.KeyPress):
##            key = event.key()
##            if key == QtCore.Qt.Key_Up:
##                tiltOffset -= moveIncrement
##                trackTiltOffset -= moveIncrement
##                moveToTarget(antennaBear, antennaEle)
##            elif key == QtCore.Qt.Key_Down:
##                tiltOffset += moveIncrement
##                trackTiltOffset += moveIncrement
##                moveToTarget(antennaBear, antennaEle)
##            elif key == QtCore.Qt.Key_Left:
##                centerBear += moveIncrement
##                trackBearOffset += moveIncrement
##                moveToTarget(antennaBear, antennaEle)
##            elif key == QtCore.Qt.Key_Right:
##                centerBear -= moveIncrement
##                trackBearOffset -= moveIncrement
##                moveToTarget(antennaBear, antennaEle)
##            self.refresh()
##            return True
##        return QtGui.QWidget.eventFilter(self,widget,event)
        
    def pointToTarget(self):
        global groundAlt, groundLat, groungLon
        if(self.pointAlt.text() == ""):
            pointtoAlt = float(self.pointAlt.placeholderText())
        else:
            pointtoAlt = float(ast.literal_eval(self.pointAlt.text()))
            
        if(self.pointLat.text() == ""):
            pointtoLat = float(self.pointLat.placeholderText())
        else:
            pointtoLat = float(ast.literal_eval(self.pointLat.text()))
            
        if(self.pointLong.text() == ""):
            pointtoLon = float(self.pointLong.placeholderText())
        else:
            pointtoLon = float(ast.literal_eval(self.pointLong.text()))
        deltaAlt = float(pointtoAlt) - groundAlt
        distanceToTarget = haversine( groundLat,  groundLon, pointtoLat, pointtoLon)
        bearingToTarget = bearing(groundLat,  groundLon, pointtoLat, pointtoLon)   
        elevationAngle = math.degrees(math.atan2(deltaAlt,distanceToTarget))
        moveToTarget(bearingToTarget,elevationAngle)
        '''
    def trackerAnimation(self):
        self.scene.addItem(self.balloon)
        self.scene.addItem(self.antenna)
        self.scene.addItem(self.balLoc)
        self.scene.addItem(self.antLoc)
        self.scene.addItem(self.payload)
        self.scene.addItem(self.origin)
        
        self.a.setItem(self.balloon)
        self.a.setTimeLine(self.tl)
        self.b.setItem(self.antenna)
        self.b.setTimeLine(self.tl2)
        self.c.setItem(self.balLoc)
        self.c.setTimeLine(self.tl)
        self.d.setItem(self.antLoc)
        self.d.setTimeLine(self.tl2)
        self.e.setItem(self.payload)
        self.e.setTimeLine(self.tl)
        
        
        self.trackerAni.setScene(self.scene)
        if useRFD:
            self.a.setPosAt(1,QtCore.QPointF(0,-10))
        else:
            #balloonEle = 500 - (iridiumEle*(500/90.00))
            #pointEle = 500 - (antennaEle*(500/90.00))
            #balloonBear = (iridiumBear-centerBear)*(500/180.00)
            #pointBear = (antennaBear-centerBear)*(500/180.00)
            #print pointEle
            #print pointBear
            
            self.a.setPosAt(1,QtCore.QPointF(float(iridiumBear),-float(iridiumEle)))
            self.b.setPosAt(1,QtCore.QPointF(float(antennaBear)+15,-(float(antennaEle)-10)))
            self.c.setPosAt(1,QtCore.QPointF(float(iridiumBear),-(float(iridiumEle)-30)))
            self.d.setPosAt(1,QtCore.QPointF(float(antennaBear),-(float(antennaEle)+100)))     
            self.e.setPosAt(1,QtCore.QPointF(float(iridiumBear)-15,-float(iridiumEle)+12))
            
            self.balLoc.setPlainText("Balloon\nBear:{:.1f}\nEle:{:.1f}".format(iridiumBear,iridiumEle))
            self.antLoc.setPlainText("Antenna\nBear:{:.1f}\nEle:{:.1f}".format(antennaBear,antennaEle))
        self.tl.start()
        self.tl2.start()
        '''

    def setAutotrack(self):
        global autotrackOnline
        if autotrackOnline:
            autotrackOnline = False
        else:
            autotrackOnline = True
            global receivedTime, receivedLat, receivedLon, receivedAlt, bearingLog, elevationLog, losLog
            receivedTime = np.array([])
            receivedLat = np.array([])
            receivedLon = np.array([])
            receivedAlt = np.array([])
            losLog = np.array([])
            elevationLog = np.array([])
            bearingLog = np.array([])
            self.tabs.setCurrentIndex(1)

    def setOverride(self):
        global manualOverride
        if manualOverride:
            manualOverride = False
        else:
            manualOverride = True
        
        #Updates the Incoming GPS Data field in the gui with most recent iridium packet
    def updateIncoming(self,row,column,value):
        self.incomingData.setItem(column,row,QtGui.QTableWidgetItem(str(value)))
        

        #Updates the Ground Station Data field in the gui with the current ground station data
    def updateGround(self,row,column,value):
        self.groundData.setItem(column,row,QtGui.QTableWidgetItem(str(value)))
        
    def refresh(self):
        global recievedTime, losLog, bearingLog, elevationLog
        if(useRFD):
            self.updateIncoming(0,0,rfdTime)
            self.updateIncoming(0,1,rfdLat)
            self.updateIncoming(0,2,rfdLon)
            self.updateIncoming(0,3,round(rfdAlt,2))
            self.updateIncoming(0,4,round(rfdEle,2))
            self.updateIncoming(0,5,round(rfdBear,2))
            self.updateIncoming(0,6,round(rfdLOS,2))
            self.updateIncoming(0,7,round(float(geomag.declination(dlat = rfdLat,dlon = rfdLon, h = rfdAlt))),2)
        else :
            #Incoming Data Table
            self.updateIncoming(0,0,iridiumTime)
            self.updateIncoming(0,1,iridiumLat)
            self.updateIncoming(0,2,iridiumLon)
            self.updateIncoming(0,3,round(iridiumAlt,2))
            self.updateIncoming(0,4,round(iridiumEle,2))
            self.updateIncoming(0,5,round(iridiumBear,2))
            self.updateIncoming(0,6,round(iridiumLOS,2))
            self.updateIncoming(0,7,round(geomag.declination(dlat = iridiumLat,dlon = iridiumLon, h = iridiumAlt),2))
            
        #Ground Station Data Table (unlikely to change but what the heck)
        self.updateGround(0,0,groundLat)
        self.updateGround(0,1,groundLon)
        self.updateGround(0,2,groundAlt)
        self.updateGround(0,3,centerBear)
        #Antenna current "intended" position
        self.updateGround(0,4,trackBearOffset)
        self.updateGround(0,5,trackTiltOffset)
        self.updateGround(0,6,antennaBear)
        self.updateGround(0,7,antennaEle)
        if settingsUpdated:
            testarray = np.array([0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23])
            testdata = np.array([0,1,2,3,4,5,6,7,0,1,2,3,4,5,6,7,0,1,2,3,4,5,6,7])
            if len(receivedAlt) > 0:

                # create an axis
                ALTPLOT = self.figure.add_subplot(221)
                LOSPLOT = self.figure.add_subplot(222)
                ELEPLOT = self.figure.add_subplot(223)
                BEARPLOT = self.figure.add_subplot(224)

                # discards the old graph
                ALTPLOT.hold(False)
                LOSPLOT.hold(False)
                ELEPLOT.hold(False)
                BEARPLOT.hold(False)
                
                # plot data
                ALTPLOT.plot(receivedTime-receivedTime[0],receivedAlt, 'r-')
                ALTPLOT.set_ylabel('Altitude (ft)')
                LOSPLOT.plot(receivedTime-receivedTime[0],losLog,'g-')
                LOSPLOT.set_ylabel('Line-of-Sight (km)')
                ELEPLOT.plot(receivedTime-receivedTime[0],elevationLog, 'b-')
                ELEPLOT.set_ylabel('Elevation Angle')
                BEARPLOT.plot(receivedTime-receivedTime[0],bearingLog,'y-')
                BEARPLOT.set_ylabel('Bearing Angle')

                # refresh canvas
                self.canvas.draw()
            
    def getSettings(self):
        global servoAttached, rfdAttached, arduinoAttached,manualOverride
        global settingsUpdated, useIridium, useRFD, usePrediction, useSim, useHybrid
        global centerBear, getLocal, manualLocal, manualOverride, calibrationGoal
        global groundLat, groundLon, groundAlt
        global servoCOM, rfdCOM, arduinoCOM
        global simDate, simStartAlt
        global s
        global receivedTime, receivedLat, receivedLon, receivedAlt, bearingLog, elevationLog, losLog
        settingsUpdated = True
        useIridium = self.autoIridium.isChecked()
        useRFD = self.autoRFD.isChecked()
        usePrediction = self.autoIridiumPredict.isChecked()
        useSim = self.autoSimulation.isChecked()
        if useSim:
            receivedTime = np.array([])
            receivedLat = np.array([])
            receivedLon = np.array([])
            receivedAlt = np.array([])
            losLog = np.array([])
            elevationLog = np.array([])
            bearingLog = np.array([])
        useHybrid = self.autoHybrid.isChecked()
        servoAttached = self.servoAttached.isChecked()
        rfdAttached = self.rfdAttached.isChecked()
        arduinoAttached = self.arduinoAttached.isChecked()
        #manualOverride = self.manualOverride.isChecked()
        if(self.servoAttached.isChecked()):
            if(self.servoCOM.text() == ""):
                servoCOM = self.servoCOM.placeholderText()
            else:
                servoCOM = self.servoCOM.text()
            s = serial.Serial(str(servoCOM), baudrate = servoBaud, timeout = servoTimeout)
            setServoAccel()
            setServoSpeed()
            s.close()
        if(self.rfdAttached.isChecked()):
            if(self.rfdCOM.text() == ""):
                rfdCOM = self.rfdCOM.placeholderText()
            else:
                rfdCOM = self.rfdCOM.text()
        if(self.arduinoAttached.isChecked()):
            if(self.arduinoCOM.text() == ""):
                arduinoCOM = self.arduinoCOM.placeholderText()
            else:
                arduinoCOM = self.arduinoCOM.text()
        if(self.calibrationGoalVal.text() == ""):
            calibrationGoal = self.calibrationGoalVal.placeholderText()
        else:
            calibrationGoal = int(ast.literal_eval(self.calibrationGoalVal.text()))
        #manualOverride = self.manualOverride.isChecked()
        if (self.simDate.text() == ""):
            simDate = self.simDate.placeholderText()
        else:
            simDate = self.simDate.text()
        if (self.simAlt.text() == ""):
            simStartAlt = self.simAlt.placeholderText()
        else:
            simStartAlt = self.simAlt.text()
        
        if(self.getLocal.isChecked()):
            getLocal = True
            manualLocal = False
            arduinoGround()
        else:
            manualLocal = True
            getLocal = False
            if(self.bearingNorth.isChecked()):
                centerBear = 0
            elif(self.bearingEast.isChecked()):
                centerBear = 90
            elif(self.bearingSouth.isChecked()):
                centerBear = 180
            elif(self.bearingWest.isChecked()):
                centerBear = 270
            else:
                centerBear = 0
                print "Error with manual bearing setup"
            groundLat = self.manualLat.text()
            groundLon = self.manualLon.text()
            groundAlt = self.manualAlt.text()
            if (groundLat == ""):
                groundLat = self.manualLat.placeholderText()
            if (groundLon == ""):
                groundLon = self.manualLon.placeholderText()
            if (groundAlt == ""):
                groundAlt = self.manualAlt.placeholderText()
            groundLat = float(groundLat)
            groundLon = float(groundLon)
            groundAlt = float(groundAlt)
            
            #Graphing and Data Logging
            if(self.graphSQL.isChecked()):
                receivedTime = np.array([])
                receivedLat = np.array([])
                receivedLon = np.array([])
                receivedAlt = np.array([])
                losLog = np.array([])
                elevationLog = np.array([])
                bearingLog = np.array([])
                retrieveDate = time.strftime("%Y-%m-%d")
                while(getSQLArray(retrieveDate)):
                    pass
        
    def antennaOnline(self):
        global autotrackOnline
        global useIridium, useRFD, usePrediction, useSim, useHybrid
        global receivedTime, receivedLat, receivedLon, receivedAlt, bearingLog, elevationLog, losLog
        if autotrackOnline:
            #Update a nice and pretty status indicator in green
            self.status.setText("Online")
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
            self.status.setPalette(palette)
            #Move Antenna to correct position based on settings
            if manualOverride:
                moveToTarget(antennaBear, antennaEle) 
            else:
                if useIridium or useSim:
                    moveToTarget(iridiumBear, iridiumEle)
                if useRFD:
                    moveToTarget(rfdBear, rfdEle)
        else:

            #Graphing Arrays - wipe them
            receivedTime = []
            receivedLat = []
            receivedLon = []
            receivedAlt = []
            losLog = []
            elevationLog = []
            bearingLog = []
            #Update a nice and pretty status indicator in red
            self.status.setText("Offline")
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
            self.status.setPalette(palette)
'''
#    def cutdownEmail(self):             #Not functional (was a nice thought but all emails are blocked as spam when sent)
#        self.abortStatus = False
#        self.tminus = 10
#        self.sendingLabel.setText("Sending...")
#        self.sendCmd.setText("Cutdown")
#        while((self.tminus >= 0)and (self.abortStatus == False)):
#            self.countdown.display(self.tminus)
#            self.tminus = self.tminus - 1
#            time.sleep(1)
#            QCoreApplication.processEvents()
#        if self.abortStatus == True:
#            self.sendingLabel.setText("Aborted")
#            print "Aborting Email"
#        else:
#            print "Sending Email"
#            # Create a text/plain message
#            msg = MIMEText("Test")
#            # me == the sender's email address
#            # you == the recipient's email address
#            msg['Subject'] = "300234060252680"              #ID number
#            msg['From'] = "dylantrafford@trackergui.com"
#            msg['To'] = "data@sbd.iridium.com"
#
#            # Send the message via our own SMTP server, but don't include the
#            # envelope header.
#            emails = smtplib.SMTP('localhost')
#            emails.sendmail(me, [you], msg.as_string())
#            emails.quit()
#            self.sendingLabel.setText("Sent")
#    
#    def abortEmail(self):
#        self.abortStatus = True
#
#    def dummy(self):
#        pass   
'''
def getData():              #Where to get GPS data from, if not a simulation, default to iridium
        if useSim:
            getSimulation()
        else:
            getIridium()        

def arduinoGround():        #Gather data from arduino mounted on ground station
        global groundAlt,groundLat,groundLon,centerBear,antennaBear,calibrationGoal
        if arduinoAttached:
                s2 =serial.Serial(str(arduinoCOM), baudrate = arduinoBaud, timeout = arduinoTimeout)
                time.sleep(5)                
                temp_arduino = "0";
                calibration = 0;
                x = 64;
                y = 70;
                bad = 0
                while (calibration < int(calibrationGoal)):
                    temp_arduino = "0"
                    s2.flushInput()
                    time.sleep(0.05)
                    while(temp_arduino[0] != '~'):
                        temp_arduino = s2.readline()
                        print temp_arduino
                        temp_arduino = temp_arduino.split(',')
                    try:
                        #+int(temp_arduino[5])
                        calibration = int(temp_arduino[8])+int(temp_arduino[7])+int(temp_arduino[6])
                    finally:
                        print "Calibration: ",calibration, " // Goal of ", int(calibrationGoal) 
                        if (x > 191):
                            x = 64;
                            time.sleep(3)
                        else:
                            x += 10;
                        if (y < 70):
                            y = 127;
                        else:
                            y -= 3;
                        movePanServo(x)
                        moveTiltServo(y)
                moveToCenterPos()
                time.sleep(10)
                temp_arduino = "0"
                s2.flushInput()

                while(temp_arduino[0] != '~'):
                    temp_arduino = s2.readline();
                    print temp_arduino
                    temp_arduino = temp_arduino.split(',');
                print "Requesting Latitude"
                tempLat = temp_arduino[1]
                print tempLat
                print "Requesting Longitude"
                tempLon = temp_arduino[2]
                print tempLon
                print "Requesting Altitude"
                tempAlt = temp_arduino[3]
                tempoffsetDegrees = "0.00"
                print tempAlt
                print "Requesting Orientation"
                tempoffsetDegrees = temp_arduino[4]
                print tempoffsetDegrees
                tempLat = tempLat.split(".")
                groundLat = float(tempLat[0])+float(tempLat[1])/10000000 
                tempLon = tempLon.split(".")
                groundLon = float(tempLon[0])-float(tempLon[1])/10000000
                tempAlt = tempAlt.split(".")
                groundAlt = int(tempAlt[0])
                #tempoffsetDegrees = tempoffsetDegrees.split(".")
                centerBear = float(tempoffsetDegrees)
                declination = float(geomag.declination(dlat = groundLat,dlon = groundLon, h = groundAlt))
                s2.close()
        else:
            print "Error: Arduino set in Settings as not connected"
        print "Local Latitude: \t",groundLat
        print "Local Longitude:\t",groundLon
        print "Local Altitude: \t",groundAlt
        print "Offset Degrees: \t",centerBear
        print "Declination:    \t",declination
        centerBear = (centerBear+declination)
        if centerBear > 360:
            centerBear = centerBear - 360
        elif centerBear < 0:
            centerBear = centerBear + 360
        print "Offset + Dec:   \t",(centerBear)
        print "-------------------------------------------------------"
        antennaBear = (centerBear)
            
def moveToCenterPos():              #Send servos to their center pos (should be horizontal and straight ahead if zeroed)
    global s
    print "Starting serial communication with",servoCOM
    if servoAttached:
        moveTiltServo(127)
        movePanServo(127)
        print "Move to Center Command Sent via", servoCOM
    else:
        print "Error: Settings set to no Servo Connection"
   
def panBothServos():                        #Moves servos through range of motion tests
    global s
    print "Starting serial communication with",servoCOM
    if servoAttached:
        for i in range(127,0,-1):
            moveTiltServo(i)
            movePanServo(i)
            time.sleep(0.05)
            i+=1
        time.sleep(1)

        for i in range(0,254,1):
            moveTiltServo(i)
            movePanServo(i)
            time.sleep(0.05)
            i+=1
        time.sleep(1)
        print "Motion Test Finished"
    else:
        print "Error: Settings set to no Servo Connection"
    
def moveToTarget(bearing,elevation):        #moves servos based on a bearing and elevation angle
        
        global centerBear,antennaBear,antennaEle
        temp = 0
        if((bearing>180) and (centerBear == 0)):
                centerBear = 360
        elif (((centerBear - bearing) > 180) and (centerBear >= 270)):
                bearing = bearing + 360
        elif (((centerBear - bearing) > 180) and (centerBear <=180)):
                temp = centerBear
                centerBear = 360 + temp
        print ("\tBearing: %.0f" %bearing)
        print ("\tElevation Angle: %.0f"%elevation)
        #panTo = (((offsetDegrees-bearing+panOffset)*255)/panRange)+127.5
        # With new digital servos, can use map method as described here: http://arduino.cc/en/reference/map
        panTo = ((bearing - (centerBear - 168)) * (servo_max - servo_min) / ((centerBear + 168) - (centerBear - 168)) + servo_min) + (255*panOffset/360)
        if panTo > 254: panTo = 254
        if panTo < 0: panTo = 0
        print "\tServo Degrees:"
        if servoAttached:
            movePanServo(math.trunc(panTo)) 
        #tiltTo = (255*(96-elevation))/90
        #tiltTo = (255*(tiltRange-elevation+tiltOffset))/90
        #If Error in Antenna Mount i.e. put antenna on backwards fix with changing 0-elevation to elevation (must change tilt stops too
        tiltTo = (((0-elevation) - tilt_angle_min) * (servo_max - servo_min) / (tilt_angle_max - tilt_angle_min) + servo_min) + tiltOffset
        if tiltTo > 254: tiltTo = 254
        if tiltTo < 0: tiltTo = 0
        if servoAttached:
            moveTiltServo(math.trunc(tiltTo))
        if (temp!= 0):
                centerBear = temp
        if servoAttached:
            s.close()
        antennaBear = bearing
        antennaEle = elevation
                        
def setServoAccel():
        #Ubiquity Setup
        setAccel = [accelCommand,tiltChannel,tiltAccel,0]
        s.write(setAccel)
        setAccel = [accelCommand,panChannel,panAccel,0]
        s.write(setAccel)
        '''
        #RFD setup
#        setAccel = [accelCommand,rfd_tiltChannel,rfd_tiltAccel,0]
#        s.write(setAccel)
#        setAccel = [accelCommand,rfd_panChannel,rfd_panAccel,0]
#        s.write(setAccel)
        '''
def setServoSpeed():
        #Ubiquity Setup
        setSpeed = [speedCommand,tiltChannel,tiltSpeed,0]
        s.write(setSpeed)
        setSpeed = [speedCommand,panChannel,panSpeed,0]
        s.write(setSpeed)
        '''
        #RFD setup
#        setSpeed = [speedCommand,rfd_tiltChannel,rfd_tiltSpeed,0]
#        s.write(setSpeed)
#        setSpeed = [speedCommand,rfd_panChannel,rfd_panSpeed,0]
#        s.write(setSpeed)
        '''
def moveTiltServo(position):
        global antennaEle
        if servoAttached:
            s = serial.Serial(str(servoCOM), baudrate = servoBaud, timeout = servoTimeout)
            #move tilt
            if(position < 70):          #80 degrees upper limit
                    moveTilt = [moveCommand,tiltChannel,chr(70)]
            elif(position > 123):       #5 degrees lower limit
                    moveTilt = [moveCommand,tiltChannel,chr(123)]
            else:
                    moveTilt = [moveCommand,tiltChannel,chr(position)]
            s.write(moveTilt)
            #RFD (for use with a second antenna tracker)
#            moveTilt = [moveCommand,rfd_tiltChannel,chr(position)]
            s.close()
            mGui.updateGround(0,5,((position - 127)*90/127.00))
            #antennaEle = (position - 127)*90/127.00
            mGui.refresh()
        else:
            print "Error: Settings indicate no servo connection"
        print "\t\tMove Tilt: ", float(position)

def movePanServo(position):
        global antennaBear
        if servoAttached:
            s = serial.Serial(str(servoCOM), baudrate = servoBaud, timeout = servoTimeout)
            '''
            if previousPan > position:
                position += 1
            previousPan = position
            '''
            #move Ubiquity
            movePan = [moveCommand,panChannel,chr(255-position)]
            s.write(movePan)
            #move RFD
#            movePan = [moveCommand,rfd_panChannel,chr(255-position)]
            s.write(movePan)
            print "\t\tMove Pan: ", float(position)
            s.close()
            mGui.updateGround(0,4,centerBear +((position - 127)*90/127.00))
            #antennaBear = centerBear +((position - 127)*90/127.00)
            mGui.refresh()
        else:
            print "Error: Settings indicate no servo connection"
        
# great circle bearing, see: http://www.movable-type.co.uk/scripts/latlong.html 
def bearing(trackerLat, trackerLon, remoteLat, remoteLon):
        dLat = math.radians(remoteLat-trackerLat)       # delta latitude in radians
        dLon = math.radians(remoteLon-trackerLon)       # delta longitude in radians
        
        y = math.sin(dLon)*math.cos(math.radians(remoteLat))
        x = math.cos(math.radians(trackerLat))*math.sin(math.radians(remoteLat))-math.sin(math.radians(trackerLat))*math.cos(math.radians(remoteLat))*math.cos(dLat)
        tempBearing = math.degrees(math.atan2(y,x))     # returns the bearing from true north
        if (tempBearing < 0):
                tempBearing = tempBearing + 360
        return tempBearing
    

    ##############################
    ## Returns Data in Nautical ##
    ##############################

# haversine formula, see: http://www.movable-type.co.uk/scripts/latlong.html    
def haversine(trackerLat, trackerLon, remoteLat, remoteLon):
        R = 6371        # radius of earth in Km

        dLat = math.radians(remoteLat-trackerLat)       # delta latitude in radians
        dLon = math.radians(remoteLon-trackerLon)       # delta longitude in radians
        ####################################
        a = math.sin(dLat/2)*math.sin(dLat/2)+math.cos(math.radians(trackerLat))*math.cos(math.radians(remoteLat))*math.sin(dLon/2)*math.sin(dLon/2)
        #############################
        c = 2*math.atan2(math.sqrt(a),math.sqrt(1-a))
        
        d = R*c
        
        return d*3280.839895 # multiply distance in Km by 3280 for feet
  
def getIridium():
    global receivedTime, receivedLat, receivedLon, receivedAlt, bearingLog, elevationLog, losLog
    global db_host, db_user, db_passwd, db_name
    # execute SQL query using execute() method.
    #try:

    #SQL Access to access iridium packet information
    db_local = MySQLdb.connect(host=db_host,user=db_user,passwd=db_passwd,db=db_name)
    #prepare a cursor object using cursor() method
    cursor = db_local.cursor()
    #sql = "select gps_fltDate,gps_time,gps_lat,gps_long,gps_alt from gps where pri_key = (select max(pri_key) from gps) and gps_IMEI = "+IMEI
    sql = "select gps_fltDate,gps_time,gps_lat,gps_long,gps_alt from gps where gps_IMEI = '"+IMEI+"' order by pri_key DESC"   
    #sql = "select gps_fltDate,gps_time,gps_lat,gps_long,gps_alt from gps order by pri_key DESC"   
    #sql = "select gps_fltDate,gps_time,gps_lat,gps_long,gps_alt from gps where gps_fltDate = '2015-01-17' order by gps_time"
    
    #print "Fetching from Iridium: \n\t " + sql + "\n"
    cursor.execute(sql)
    # Fetch a single row using fetchone() method.
    try:
        results = cursor.fetchone()
        remoteTime = results[1].split(":")
        remoteHours = int(remoteTime[0])
        remoteMinutes = int(remoteTime[1])
        remoteSeconds = int(remoteTime[2])
        remoteTime = results[1]
        remoteSeconds = remoteSeconds + (60*remoteMinutes) + (3600*remoteHours)
        remoteLat = float(results[2])                   #http://stackoverflow.com/questions/379906/parse-string-to-float-or-int
        remoteLon = float(results[3])
        remoteAlt = float(results[4]) * 3.280839895  #(meters to feet conversion)
    except:
        print "ERROR PARSING DATA FROM DATABASE: Cannot parse data or data may not exist, please double check your IMEI number at the top of the code"
        cursor.close()
        return
    #print "-----------------------------------------------"
    #print "\tGPS_TIME: \t\t",results[1]
    #print ("Local alt: %.0f" %groundAlt)
    #print ("Remote alt: %.0f" %remoteAlt)
    #print ("Remote Lat: %.7f" %remoteLat)
    #print ("Remote Lon: %.7f" %remoteLon)
    deltaAlt = remoteAlt-groundAlt   
    #print ("Delta alt: %.0f" %deltaAlt)
    distanceToTarget = haversine( groundLat,  groundLon, remoteLat, remoteLon)        
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
        #print "First Catch"
        receivedTime = np.append(receivedTime,remoteSeconds)
        receivedLon = np.append(receivedLon,iridiumLon)
        receivedLat = np.append(receivedLat,iridiumLat)
        receivedAlt = np.append(receivedAlt,iridiumAlt)
        bearingLog = np.append(bearingLog,iridiumBear)
        elevationLog = np.append(elevationLog,iridiumEle)
        losLog = np.append(losLog,iridiumLOS)
    elif(receivedTime[len(receivedTime) - 1] < remoteSeconds):
        #print "Second Catch"
        receivedTime = np.append(receivedTime,remoteSeconds)
        receivedLon = np.append(receivedLon,iridiumLon)
        receivedLat = np.append(receivedLat,iridiumLat)
        receivedAlt = np.append(receivedAlt,iridiumAlt)
        bearingLog = np.append(bearingLog,iridiumBear)
        elevationLog = np.append(elevationLog,iridiumEle)
        losLog = np.append(losLog,iridiumLOS)
    #except:
    #    print ("Error: unable to fetch data")
    cursor.close()
    db_local.close()
    
    #############################
    ## Runs Tracker Simulation ##
    #############################


def getSimulation():
    global db, cursor
    global receivedTime, receivedLat, receivedLon, receivedAlt, bearingLog, elevationLog, losLog
    try:
        #sql = "select gps_fltDate,gps_time,gps_lat,gps_long,gps_alt from gps where gps_fltDate = '{}' order by pri_key".format(simDate)
        sql = "select gps_fltDate,gps_time,gps_lat,gps_long,gps_alt from gps where gps_fltDate = '{}' and gps_alt >= {} order by pri_key".format(simDate,simStartAlt)
        #sql = "select gps_fltDate,gps_time,gps_lat,gps_long,gps_alt from gps where gps_fltDate = '2015-01-17' order by gps_time"
        cursor.execute(sql)
        # Fetch a single row using fetchone() method.
        remoteSeconds = 0
        try:
            while(remoteSeconds <= receivedTime[len(receivedTime)-1]):
                results = cursor.fetchone()
                remoteTime = results[1].split(":")
                remoteHours = int(remoteTime[0])
                remoteMinutes = int(remoteTime[1])
                remoteSeconds = int(remoteTime[2])
                #print remoteHours, remoteMinutes, remoteSeconds
                remoteTime = results[1]
                remoteSeconds = remoteSeconds + (60*remoteMinutes) + (3600*remoteHours)
                #print remoteSeconds
                
        except:
            results = cursor.fetchone()
            remoteTime = results[1].split(":")
            remoteHours = int(remoteTime[0])
            remoteMinutes = int(remoteTime[1])
            remoteSeconds = int(remoteTime[2])
            remoteTime = results[1]
            remoteSeconds = remoteSeconds + (60*remoteMinutes) + (3600*remoteHours)
            
        remoteLat = float(results[2])                   #http://stackoverflow.com/questions/379906/parse-string-to-float-or-int
        remoteLon = float(results[3])
        remoteAlt = float(results[4]) * 3.280839895  #(meters to feet conversion)
        print "-----------------------------------------------"
        print "\tGPS_TIME: \t\t",results[1]
        print ("Local alt: %.0f" %groundAlt)
        print ("Remote alt: %.0f" %remoteAlt)
        print ("Remote Lat: %.7f" %remoteLat)
        print ("Remote Lon: %.7f" %remoteLon)
        deltaAlt = remoteAlt-groundAlt   
        print ("Delta alt: %.0f" %deltaAlt)
        distanceToTarget = haversine( groundLat,  groundLon, remoteLat, remoteLon)        
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

        receivedTime = np.append(receivedTime,remoteSeconds)
        receivedLon = np.append(receivedLon,iridiumLon)
        receivedLat = np.append(receivedLat,iridiumLat)
        receivedAlt = np.append(receivedAlt,iridiumAlt)
        bearingLog = np.append(bearingLog,iridiumBear)
        elevationLog = np.append(elevationLog,iridiumEle)
        losLog = np.append(losLog,iridiumLOS)
    except:
        print ("Error: unable to fetch data")
        
def getSQLArray(retrieveDate):
    global db, cursor
    global receivedTime, receivedLat, receivedLon, receivedAlt, bearingLog, elevationLog, losLog
    # execute SQL query using execute() method.
    try:
        sql = sql = "select gps_fltDate,gps_time,gps_lat,gps_long,gps_alt from gps where gps_fltDate = '{}' order by pri_key".format(retrieveDate)
        #sql = "select gps_fltDate,gps_time,gps_lat,gps_long,gps_alt from gps where gps_fltDate = '2015-01-17' order by gps_time"
        cursor.execute(sql)
        # Fetch a single row using fetchone() method.
        while(True):
            results = cursor.fetchone()
            if results == None:
                return False
            remoteTime = results[1].split(":")
            remoteHours = int(remoteTime[0])
            remoteMinutes = int(remoteTime[1])
            remoteSeconds = int(remoteTime[2])
            remoteTime = results[1]
            remoteSeconds = remoteSeconds + (60*remoteMinutes) + (3600*remoteHours)
            remoteLat = float(results[2])                   #http://stackoverflow.com/questions/379906/parse-string-to-float-or-int
            remoteLon = float(results[3])
            remoteAlt = float(results[4]) * 3.280839895  #(meters to feet conversion)
            deltaAlt = remoteAlt-groundAlt   
            distanceToTarget = haversine( groundLat,  groundLon, remoteLat, remoteLon)        
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
        return True
    except:
        print ("Error: unable to fetch data")
    
if __name__ == "__main__":
    app = QApplication(sys.argv)
    mGui = MainWindow()
    mGui.show()
    app.exec_()
    cursor.close()
    db.close()      #disconnect from SQL Server

else:
    print "Error Booting Gui"
    while(1):
        pass


