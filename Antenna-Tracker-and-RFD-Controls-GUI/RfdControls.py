import serial
import time
import datetime
from PyQt4 import *
from PyQt4 import QtCore
from PyQt4 import QtGui
from PyQt4.QtCore import *
from BalloonUpdate import *
import threading


class RfdListen(QtCore.QObject):

	# Received Signals
	listenStart = pyqtSignal()
	listenInterrupt = pyqtSignal()
	shareIdentifier = pyqtSignal(str)

	def __init__(self, MainWindow, RFD):
		super(RfdListen, self).__init__()
		self.rfdSer = RFD
		self.mainWindow = MainWindow
		self.interrupt = False
		self.identifier = ''

		# Emitted Signals
		self.mainWindow.rfdListenNewText.connect(self.mainWindow.updateRFDBrowser)
		self.mainWindow.rfdNewLocation.connect(self.mainWindow.updateBalloonLocation)
		self.mainWindow.payloadUpdate.connect(self.mainWindow.updatePayloads)


	def listen(self):
		""" Listens to the RFD serial port until interrupted """
				
		### Loop until interrupted; handle anything received by the RFD ###
		self.rfdSer.flushInput()
		while not self.interrupt:
			QtGui.QApplication.processEvents()
			line = str(self.rfdSer.readline())
			if line[0:3] == "GPS" and len(line[4:].split(','))==7:		# If the line received has the GPS identifier, handle it as a newly received RFD balloon location update
				lineLst = line.split(',')
				lineLst[0] = lineLst[0][4:]
				lineLst[-1] = lineLst[-1][:-1]

				### Interpret the balloon location list ###
				try:
					hours = lineLst[0]		# Fix taken at this time
					minutes = lineLst[1]		# Fix taken at this time
					seconds = lineLst[2]		# Fix taken at this time
					lat = stringToFloat(lineLst[3])		# Latitude in Degrees
					lon = stringToFloat(lineLst[4])		# Longitude in Degrees
					alt = stringToFloat(lineLst[5])		# Altitude in meters (sealevel)
					sat = stringToFloat(lineLst[6][:-1])		# Number of Satellites
				except Exception, e:
					print(str(e))

				### Do some calculations, get some values ###
				alt = alt*3.2808	# Convert Altitude to feet
				gpsTime = hours + ":" +  minutes + ":" + seconds.split(".")[0]
				rfdSeconds = stringToFloat(hours) * 3600 + stringToFloat(minutes)*60 + stringToFloat(seconds)

				### Create a new location object ###
				try:
					newLocation = BalloonUpdate(gpsTime,rfdSeconds,lat,lon,alt,"RFD",self.mainWindow.groundLat,self.mainWindow.groundLon,self.mainWindow.groundAlt)
				except Exception, e:
					print(str(e))
					
				try:
					self.mainWindow.rfdNewLocation.emit(newLocation)				# Notify the main GUI of the new position
				except Exception, e:
					print(str(e))
					
				#self.mainWindow.rfdListenNewText.emit(datetime.datetime.today().strftime('%H:%M:%S') + " || "+line)
				
			if(line.replace('\n','') == self.identifier and self.identifier != ''):
				print('ID Found')
				self.rfdCommand.foundIdentifier.emit(True)
				self.identifier = ''
				
			elif line != '':				# Send the line to the text browser if it's not empty
				self.mainWindow.rfdListenNewText.emit(datetime.datetime.today().strftime('%H:%M:%S') + " || "+line)
				self.mainWindow.payloadUpdate.emit(line)			# Send it to the payload manager

		self.interrupt = False

	def setInterrupt(self,arg):
		self.mainWindow.rfdCommandNewText.emit("Listen Interrupted")
		self.interrupt = arg

	def setIdentifier(self,ID):
		self.identifier = ID
		print("New ID: " + self.identifier)

	def setCommand(self,command):
		self.rfdCommand = command


class RfdCommand(QtCore.QObject):

	# Signals
	commandStart = pyqtSignal(str,str)
	commandInterrupt = pyqtSignal()
	piruntimeStart = pyqtSignal()
	statusStart = pyqtSignal()
	foundIdentifier = pyqtSignal(bool)

	def __init__(self,MainWindow,RFD):
		super(RfdCommand, self).__init__()
		self.rfdSer = RFD
		self.mainWindow = MainWindow
		self.acknowledged = False
		self.interrupt = False

		# Connections
		self.mainWindow.rfdCommandNewText.connect(self.mainWindow.updateRFDBrowser)
		self.mainWindow.commandFinished.connect(self.mainWindow.rfdCommandsDone)
		self.mainWindow.piruntimeFinished.connect(self.mainWindow.piruntimeDone)


	def command(self,identifier,command):
		""" Handles the RFD Commands """

		self.identifier = str(identifier)
		self.command = str(command)
		toSend = self.identifier + "?" + self.command	+ "!"	# Connect the identifier and the command with a ? separating for parsing, and an ! at the end

		self.rfdListen.shareIdentifier.emit(self.identifier)		# Send out the identifier so the listen function can get it
		
		print(datetime.datetime.today().strftime('%H:%M:%S'))
		self.mainWindow.rfdCommandNewText.emit('\n' + datetime.datetime.today().strftime('%H:%M:%S'))		# Print out when the message began to send

		### Until the acknowledge is received, or the stop button is pressed, keep sending the message ###
		self.setAcknowledged(False)
		self.setInterrupt(False)
		self.mainWindow.rfdCommandNewText.emit("Sending " + toSend)		# Add the message to the browser
		while not self.acknowledged:
			QtGui.QApplication.processEvents()
			self.rfdSer.write(toSend)
			if self.interrupt:		# If the stop button is pressed, interrupt the sending
				self.mainWindow.rfdCommandNewText.emit("Command Interrupted")
				self.setAcknowledged(True)
			time.sleep(0.05)

		if self.interrupt:
			self.setInterrupt(False)

		else:
			print("Acknowledged at: " + datetime.datetime.today().strftime('%H:%M:%S'))
			self.mainWindow.rfdCommandNewText.emit("Acknowledged at: " + datetime.datetime.today().strftime('%H:%M:%S'))		# Print out the time of acknowledge to see how long it took to get the message through
			self.setAcknowledged(False)

		self.mainWindow.commandFinished.emit()

	def getPiRuntimeData(self):
		""" Retrieve the runtime data from the Pi """
			
		### Send the pi 7 until the acknowledge is received, or until too much time has passed ###
		termtime = time.time() + 10
		timeCheck = time.time() + 1
		self.rfdSer.write('IMAGE;7!')
		while self.rfdSer.read() != 'A':
			if(timeCheck < time.time()):
				print("Waiting for Acknowledge")
				self.mainWindow.rfdCommandNewText.emit("Waiting for Acknowledge")
				timeCheck = time.time() + 1
			self.rfdSer.write('IMAGE;7!')
			if(termtime < time.time()):
				print("No Acknowldeg Received, Connection Error")
				self.mainWindow.rfdCommandNewText.emit("No Acknowledge Received, Connect Error")
				self.mainWindow.piruntimeFinished.emit()
				return
		
		### Receive piruntimedata.txt ###
		timecheck = time.time()
		try:
			f = open("piruntimedata.txt","w")
		except:
			print "Error opening file"
			self.mainWindow.rfdCommandNewText.emit("Error opening file")
			self.mainWindow.piruntimeFinished.emit()
			return
		timecheck = time.time()
		termtime = time.time()+60
		temp = self.rfdSer.readline()
		while (temp != "\r") & (temp != ""):		# Write everything the radio is receiving to the file
			f.write(temp)
			temp = self.rfdSer.read()
			if (termtime < time.time()):
				print "Error receiving piruntimedata.txt"
				self.mainWindow.rfdCommandNewText.emit("Error receiving piruntimedata.txt")
				f.close()
				self.mainWindow.piruntimeFinished.emit()
				return
		f.close()
		
		print "piruntimedata.txt saved to local folder"
		self.mainWindow.rfdCommandNewText.emit("piruntimedata.txt saved")
		print "Receive Time =", (time.time() - timecheck)
		self.mainWindow.rfdCommandNewText.emit("Receive Time ="+str((time.time() - timecheck)))
		
		### Open piruntimedata.txt and print it into the command browser ###
		try:
			f = open('piruntimedata.txt','r')
			for line in f:
				print(line)
				self.mainWindow.rfdCommandNewText.emit(line)
			f.close()
		except:
			print("Error reading piruntimedata.txt")
			self.mainWindow.rfdCommandNewText.emit("Error reading piruntimedata.txt")
			
		self.mainWindow.piruntimeFinished.emit()
		return

	def getDeviceStatus(self):
		""" Retrieve the status of the serial devices connected to the Pi """
		self.rfdSer.write('IMAGE;-!')

	def setAcknowledged(self,arg):
		self.acknowledged = arg

	def setInterrupt(self,arg):
		self.interrupt = arg

	def setListen(self,listen):
		self.rfdListen = listen
		
		
def stringToFloat(arg):
	if(arg == '0'):
		return float(0)
	else:
		return float(arg)

