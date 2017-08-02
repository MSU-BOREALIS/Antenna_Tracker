from PyQt4 import *
from PyQt4 import QtCore
from PyQt4.QtCore import *
import serial
import time
import datetime
import sys
import base64
import hashlib


class StillImageSystem(QtCore.QObject):
    """ A class for controlling the still image system """

    # Signals
    mostRecentImageStart = pyqtSignal(str)
    imageDataStart = pyqtSignal()
    requestedImageStart = pyqtSignal(str)
    getSettingsStart = pyqtSignal()
    sendSettingsStart = pyqtSignal(list)
    vFlipStart = pyqtSignal()
    hFlipStart = pyqtSignal()
    timeSyncStart = pyqtSignal()
    stillInterrupt = pyqtSignal()

    def __init__(self, MainWindow, RFD):
        super(StillImageSystem, self).__init__()
        self.rfdSer = RFD
        self.interrupt = False
        self.mainWindow = MainWindow

        # Picture Qualities
        self.picWidth = 650
        self.picHeight = 450
        self.picSharpness = 0
        self.picBrightness = 50
        self.picContrast = 0
        self.picSaturation = 0
        self.picISO = 400

        # Variable to determine spacing of checksum. Ex. wordlength = 1000 will
        # send one thousand bits before calculating and verifying checksum
        self.wordlength = 7000
        self.extension = ".jpg"
        # The starting display photo is the logo of the MnSGC
        self.displayPhotoPath = "Images/MnSGC_Logo_highRes.png"

        self.mainWindow.stillNewText.connect(
            self.mainWindow.updateStillBrowser)
        self.mainWindow.listboxUpdate.connect(self.mainWindow.updateListbox)
        self.mainWindow.stillNewProgress.connect(
            self.mainWindow.updatePictureProgress)
        self.mainWindow.newPicture.connect(self.mainWindow.updatePicture)
        self.mainWindow.requestConfirmation.connect(
            self.mainWindow.checkRequestedImage)
        self.mainWindow.newPicSliderValues.connect(
            self.mainWindow.updateStillImageValues)
        self.mainWindow.stillSystemFinished.connect(
            self.mainWindow.stillImageSystemFinished)

    def getMostRecentImage(self, requestedImageName):
        """ Still Image System: Get the Most Recent Image through the RFD 900 """
        print('entered')

        ### Write 1 until you get the acknowledge back ###
        self.rfdSer.write('1!')
        timeCheck = time.time() + 1
        killTime = time.time() + 10
        while self.rfdSer.read() != 'A':
            if timeCheck < time.time():			# Make sure you don't print out a huge stream if you get the wrong response
                print "Waiting for Acknowledge"
                self.mainWindow.stillNewText.emit("Waiting for Acknowledge")
                timeCheck = time.time() + 1
            sys.stdout.flush()
            # self.rfdSer.write('1!')

        ### Make the file name by reading the radio ###
        sendfilename = ""
        temp = 0
        while(temp <= 14):
            sendfilename += str(self.rfdSer.read())
            temp += 1

        # Get the image path name from the entry box, or create it if there's
        # nothing entered ###
        imagepath = requestedImageName
        if (imagepath == ""):
            try:
                if sendfilename[0] == "i":
                    imagepath = sendfilename
                else:
                    imagepath = "image_%s%s" % (
                        str(datetime.datetime.today().strftime("%Y%m%d_T%H%M%S")), self.extension)
            except:
                imagepath = "image_%s%s" % (
                    str(datetime.datetime.today().strftime("%Y%m%d_T%H%M%S")), self.extension)
        else:
            imagepath = imagepath + self.extension
        print "Image will be saved as:", imagepath
        self.mainWindow.stillNewText.emit(
            "Image will be saved as: " + imagepath)

        ### Receive the Image ###
        timecheck = time.time()
        sys.stdout.flush()
        self.receive_image(str(imagepath), self.wordlength)			# Get the picture
        print "Receive Time =", (time.time() - timecheck)
        self.mainWindow.stillNewText.emit(
            "Receive Time = " + str((time.time() - timecheck)))

        ### Clean Up and Exit ###
        self.mainWindow.stillNewProgress.emit(
            0, 1)		# Reset the progress bar to empty
        sys.stdout.flush()							# Clear the buffer

        self.mainWindow.stillSystemFinished.emit()			# Emit the finish signal

        return

    def getImageDataTxt(self):
        """ Still Image System: Requests imagedata.txt, for the purpose of selecting a specific image to download """

        ### Send the Pi 2 until the acknowledge is received ###
        self.rfdSer.write('2!')
        timeCheck = time.time() + 1
        while self.rfdSer.read() != 'A':
            if timeCheck < time.time():				# Make sure you don't print out a huge stream if the wrong thing is received
                print "Waiting for Acknowledge"
                self.mainWindow.stillNewText.emit("Waiting for Acknowledge")
                timeCheck = time.time() + 1
            sys.stdout.flush()
            # self.rfdSer.write('IMAGE;2!')

        try:
            f = open('imagedata' + ".txt", "w")
            print "opened image"
        except:
            print "Error with Opening File"
            self.mainWindow.stillNewText.emit("Error with Opening File")
            sys.stdout.flush()

            self.mainWindow.stillSystemFinished.emit()

            return

        # Read each line that received from the RFD, and write them to the file
        # ###
        timecheck = time.time()
        temp = self.rfdSer.readline()
        while temp != 'X\n':
            f.write(temp)
            try:
                self.mainWindow.listboxUpdate.emit(temp)
            except:
                print "Error Adding Items"
                self.mainWindow.stillNewText.emit("Error Adding Items")
                break
            temp = self.rfdSer.readline()
        f.close()
        sys.stdout.flush()
        self.mainWindow.stillSystemFinished.emit()		# Emit the finished signal

        return

    def getRequestedImage(self, data):
        """ Still Image System: Retrieves the image specified in the argument, deletes the confirmation window if needed """

        ### Continuously write 3 until the acknowledge is received ###
        self.rfdSer.write('3!')
        timeCheck = time.time() + 1
        killTime = time.time() + 10
        while self.rfdSer.read() != 'A' and time.time() < killTime:
            if timeCheck < time.time():			# Make sure you don't emit a huge stream of messages if the wrong this is received
                print "Waiting for Acknowledge"
                self.mainWindow.stillNewText.emit("Waiting for Acknowledge")
                timeCheck = time.time() + 1
            sys.stdout.flush()
            # self.rfdSer.write('IMAGE;3!')
         # self.sync(self.rfdSer)
        # # Syncronize the data streams of the ground station and the Pi before
        # starting
        imagepath = data[0:15]
        self.rfdSer.write('B,')
        # Tell the pi which picture you want to download
        self.rfdSer.write(str(data))
        timecheck = time.time()
        print "Image will be saved as:", imagepath
        self.mainWindow.stillNewText.emit(
            "Image will be saved as: " + str(imagepath))
        sys.stdout.flush()
        # Receive the image
        self.receive_image(str(imagepath), self.wordlength)
        print "Receive Time =", (time.time() - timecheck)
        self.mainWindow.stillNewText.emit(
            "Receive Time = " + str((time.time() - timecheck)))
        self.mainWindow.stillNewProgress.emit(0, 1)			# Reset the progress bar
        sys.stdout.flush()
        self.mainWindow.stillSystemFinished.emit()		# Emit the finished signal

        return

    def getPicSettings(self):
        """ Still Image System: Retrieve Current Camera Settings """

        print "Retrieving Camera Settings"
        self.mainWindow.stillNewText.emit("Retrieving Camera Settings")
        killtime = time.time() + 10  			# A timeout for the loop so you don't get stuck

        ### Send the Pi 4 until the acknowledge is received ###
        self.rfdSer.write('4!')
        timeCheck = time.time()
        while (self.rfdSer.read() != 'A') & (time.time() < killtime):
            if time.time() < timeCheck:					# Make sure you don't print out a huge stream if you get the wrong response
                print "Waiting for Acknowledge"
                self.mainWindow.stillNewText.emit("Waiting for Acknowledge")
                timeCheck = time.time() + 1
            # self.rfdSer.write('IMAGE;4!')

        if time.time() > killtime:
            self.mainWindow.stillNewText.emit('No Acknowledge Received')
            sys.stdout.flush()
            return

        termtime = time.time() + 10
        done = False
        while not done:
            settings = self.rfdSer.readline()
            print settings
            if not settings == '':
                settings = settings.replace('\n', '')
                print settings
                settingsLst = settings.split(',')
                print settingsLst
                fail = True
                if len(settingsLst) == 7:
                    fail = False
                    for each in settingsLst:
                        temp = each.replace('-', '')
                        print(temp)
                        if not temp.isdigit():
                            fail = True
                if not fail:
                    try:
                        done = True
                        print settingsLst
                        self.picWidth = int(settingsLst[0])
                        self.picHeight = int(settingsLst[1])
                        self.picSharpness = int(settingsLst[2])
                        self.picBrightness = int(settingsLst[3])
                        self.picContrast = int(settingsLst[4])
                        self.picSaturation = int(settingsLst[5])
                        self.picISO = int(settingsLst[6])
                        self.mainWindow.stillNewText.emit(
                            "Width = " + str(self.picWidth))
                        self.mainWindow.stillNewText.emit(
                            "Height = " + str(self.picHeight))
                        self.mainWindow.stillNewText.emit(
                            "Sharpness = " + str(self.picSharpness))
                        self.mainWindow.stillNewText.emit(
                            "Brightness = " + str(self.picBrightness))
                        self.mainWindow.stillNewText.emit(
                            "Contrast = " + str(self.picContrast))
                        self.mainWindow.stillNewText.emit(
                            "Saturation = " + str(self.picSaturation))
                        self.mainWindow.stillNewText.emit(
                            "ISO = " + str(self.picISO) + '\n')
                        self.mainWindow.newPicSliderValues.emit(
                            [self.picWidth, self.picHeight, self.picSharpness, self.picBrightness, self.picContrast, self.picSaturation, self.picISO])
                    except:
                        self.mainWindow.stillNewText.emit(
                            'Error retrieving Camera Settings')
            if time.time() > termtime:
                #done = True
                self.mainWindow.stillNewText.emit('Failed to Receive Settings')

        sys.stdout.flush()
        self.mainWindow.stillSystemFinished.emit()		# Emit the finished signal

        return

    def sendNewPicSettings(self, settings):
        """ Still Image System: Send New Camera Settings to the Pi """

        # Update the instance variables
        self.picWidth = int(settings[0])
        self.picHeight = int(settings[1])
        self.picSharpness = int(settings[2])
        self.picBrightness = int(settings[3])
        self.picContrast = int(settings[4])
        self.picSaturation = int(settings[5])
        self.picISO = int(settings[6])

        # Continue sending 5 until the acknowledge is received from the Pi ###
        self.rfdSer.write('5!')
        acknowledge = self.rfdSer.read()
        timeCheck = time.time() + 1
        termtime = time.time() + 10
        while acknowledge != 'A' and time.time() < termtime:
            acknowledge = self.rfdSer.read()
            print(acknowledge)
            if timeCheck < time.time():
                print "Waiting for Acknowledge"
                self.mainWindow.stillNewText.emit("Waiting for Acknowledge")
                timeCheck = time.time() + 1
            # self.rfdSer.write('IMAGE;5!')
            timecheck = time.time()

        if time.time() > termtime:
            self.mainWindow.stillNewText.emit(
                'No Acknowledge Received, Settings not Updated')
            return

        termtime = time.time() + 10
        settingsStr = str(self.picWidth) + ',' + str(self.picHeight) + ',' + str(self.picSharpness) + ',' + str(
            self.picBrightness) + ',' + str(self.picContrast) + ',' + str(self.picSaturation) + ',' + str(self.picISO)
        while self.rfdSer.read() != 'B' and time.time() < termtime:
            if timeCheck < time.time():
                print "Waiting for Acknowledge"
                self.mainWindow.stillNewText.emit("Waiting for Acknowledge")
                timeCheck = time.time() + 1

            self.rfdSer.write('A/' + settingsStr + '\n')
            self.rfdSer.flushOutput()

        if time.time() > termtime:
            self.mainWindow.stillNewText.emit(
                'No Acknowledge Received on Settings Update\n')
        else:
            self.mainWindow.stillNewText.emit('Settings Updated\n')

        sys.stdout.flush()			# Clear the buffer

        self.mainWindow.stillSystemFinished.emit()		# Emit the finished signal
        return

    def picVerticalFlip(self):
        """ Still Image System: Flips the image vertically """

        # Send the pi 0 until the acknowledge is received, or until too much
        # time has passed ###
        self.rfdSer.write('0!')
        termtime = time.time() + 10
        timeCheck = time.time() + 1
        while self.rfdSer.read() != 'A':
            # self.rfdSer.write('IMAGE;0!')
            # time.sleep(1)
            if timeCheck < time.time():
                print("Waiting for Acknowledge")
                self.mainWindow.stillNewText.emit("Waiting for Acknowledge")
                timeCheck = time.time() + 1
            # self.rfdSer.write('IMAGE;0!')
            if termtime < time.time():
                print("No Acknowldeg Received, Connection Error")
                self.mainWindow.stillNewText.emit(
                    "No Acknowledge Received, Connect Error")
                sys.stdout.flush()

                self.mainWindow.stillSystemFinished.emit()		# Emit the finished signal
                return

        print("Camera Vertically Flipped")
        self.mainWindow.stillNewText.emit("Camera Vertically Flipped")
        sys.stdout.flush()
        self.mainWindow.stillSystemFinished.emit()		# Emit the finished signal

    def picHorizontalFlip(self):
        """ Still Image System: Flips the image Horizontally """

        # Send the pi 9 until the acknowledge is received, or until too much
        # time has passed ###
        self.rfdSer.write('9!')
        termtime = time.time() + 10
        timeCheck = time.time() + 1
        while self.rfdSer.read() != 'A':
            if timeCheck < time.time():
                print("Waiting for Acknowledge")
                self.mainWindow.stillNewText.emit("Waiting for Acknowledge")
                timeCheck = time.time() + 1
            # self.rfdSer.write('IMAGE;9!')
            if termtime < time.time():
                print("No Acknowldeg Received, Connection Error")
                self.mainWindow.stillNewText.emit(
                    "No Acknowledge Received, Connect Error")
                sys.stdout.flush()

                self.mainWindow.stillSystemFinished.emit()		# Emit the finished signal
                return

        print("Camera Horizontally Flipped")
        self.mainWindow.stillNewText.emit("Camera Horizontally Flipped")
        sys.stdout.flush()
        self.mainWindow.stillSystemFinished.emit()		# Emit the finished signal

    def time_sync(self):
        """ Still Image System: Syncronizes the Pi and ground station so that the connection test can be run """

        # Send the Pi 8 until the acknowledge is received, or until the too
        # much time has passed ###
        self.rfdSer.write('8!')
        termtime = time.time() + 20
        timeCheck = time.time() + 1
        while self.rfdSer.read() != 'A':
            if timeCheck < time.time():
                print "Waiting for Acknowledge"
                self.mainWindow.stillNewText.emit("Waiting for Acknowledge")
                timeCheck = time.time() + 1
            # self.rfdSer.write('8!')
            if termtime < time.time():  # If too much time has passed, let the user know and return
                print "No Acknowledge Received, Connection Error"
                self.mainWindow.stillNewText.emit(
                    'No Acknowledge Received, Connection Error\n')
                sys.stdout.flush()

                self.mainWindow.stillSystemFinished.emit() 		# Emit the finished signal
                return

        ### Display the time on the Pi and the local time ###
        localtime = str(
            datetime.datetime.today().strftime("%m/%d/%Y %H:%M:%S"))
        rasptime = str(self.rfdSer.readline())
        print "##################################\nRaspb Time = %s\nLocal Time = %s\n##################################" % (rasptime, localtime)
        self.mainWindow.stillNewText.emit(
            "##################################\nRaspb Time = %s\nLocal Time = %s\n##################################" % (rasptime, localtime) + '\n')
        # sys.stdin.flush()

        # Run the connection test
        self.connectiontest(10)
        sys.stdout.flush()
        self.mainWindow.stillSystemFinished.emit() 		# Emit the finished signal
        return

    def receive_image(self, savepath, wordlength):
        """ Receive an Image through the RFD 900 """
        # Notifies User we have entered the receiveimage() module
        print "Confirmed photo request"
        self.mainWindow.stillNewText.emit("Confirmed photo request")
        sys.stdout.flush()

        ### Module Specific Variables ###
        # Initializes the checksum timeout (timeout value is not set here)
        trycnt = 0
        failcount = 0
        totalcnt = 0
        finalstring = ""		# Initializes the data string so that the += function can be used
        done = False			# Initializes the end condition

        ### Setup the Progress Bar ###
        stillProgress = 0
        try:
            # The first thing you get is the total picture size so you can make
            # the progress bar
            time.sleep(1)
            photoSize = self.rfdSer.readline()
            print("Total Picture Size: ", photoSize)
            self.mainWindow.stillNewText.emit(
                "Total Picture Size: " + photoSize)
            stillPhotoMax = int(photoSize)
            self.mainWindow.stillNewProgress.emit(stillProgress, stillPhotoMax)
        except:
            print("Error retrieving picture size")
            self.mainWindow.stillNewText.emit("Error retrieving picture size")
            stillPhotoMax = 1

        ### Retreive Data Loop (Will end when on timeout) ###
        while not done:
            print "Current Receive Position: ", str(len(finalstring))
            self.mainWindow.stillNewText.emit(
                "Current Received Position: " + str(len(finalstring)))
            # Asks first for checksum. Checksum is asked for first so that if
            # data is less than wordlength, it won't error out the checksum
            # data
            checktheirs = self.rfdSer.read(32)
            # Retreives characters, who's total string length is predetermined
            # by variable wordlength
            word = self.rfdSer.read(wordlength)
            # Retreives a checksum based on the received data string
            checkours = self.gen_checksum(word)

            # CHECKSUM
            if checkours != checktheirs:
                if trycnt < 5:		# This line sets the maximum number of checksum resends. Ex. trycnt = 5 will attempt to rereceive data 5 times before erroring out											  #I've found that the main cause of checksum errors is a bit drop or add desync, this adds a 2 second delay and resyncs both systems
                    self.rfdSer.write('N')
                    trycnt += 1
                    failcount += 1
                    print "try number:", str(trycnt)
                    self.mainWindow.stillNewText.emit(
                        "try number: " + str(trycnt))
                    print "\tresend last"		# This line is mostly used for troubleshooting, allows user to view that both devices are at the same position when a checksum error occurs
                    self.mainWindow.stillNewText.emit("\tresent last")
                    print "\tpos @", str(len(finalstring))
                    self.mainWindow.stillNewText.emit(
                        "\tpos @ " + str(len(finalstring)))
                    print "\twordlength", str(wordlength)
                    self.mainWindow.stillNewText.emit(
                        "\twordlength " + str(wordlength))
                    sys.stdout.flush()
                    if wordlength > 1000:
                        wordlength -= 1000
                    self.sync()		# This corrects for bit deficits or excesses ######  THIS IS A MUST FOR DATA TRANSMISSION WITH THE RFD900s!!!! #####
                else:
                    # Kind of a worst case, checksum trycnt is reached and so
                    # we save the image and end the receive, a partial image
                    # will render if enough data
                    self.rfdSer.write('N')
                    finalstring += word
                    done = True
                    break
            else:							# If everything goes well, reset the try counter, and add the word to the accumulating final wor
                trycnt = 0
                self.rfdSer.write('Y')
                finalstring += str(word)
                stillProgress += wordlength
                self.mainWindow.stillNewProgress.emit(
                    stillProgress, stillPhotoMax)
            # The words always come in increments of some thousand, so if it's
            # not evenly divisible, you're probably at the end
            if len(finalstring) % 1000 != 0:
                done = True
                break
        # Save the image as the given filename in the Images folder
        try:
            self.b64_to_image(finalstring, "Images/" +
                              str(savepath))			# Decode the image
            self.displayPhotoPath = "Images/" + str(savepath)
            # Send the signal with the new image location to the main GUI
            self.mainWindow.newPicture.emit(self.displayPhotoPath)
        except:
            print "Error with filename, saved as newimage" + self.extension
            self.mainWindow.stillNewText.emit(
                "Error with filename, saved as newimage" + self.extension)
            self.mainWindow.stillNewText.emit("Test633")
            sys.stdout.flush()
            # Save image as newimage.jpg due to a naming error in the Images
            # folder
            self.b64_to_image(finalstring, "Images/" +
                              "newimage" + self.extension)

        ### Clean Up ###
        self.wordlength = 7000			# Reset the wordlength to the original
        print "Image Saved"
        self.mainWindow.stillNewText.emit("Image Saved")
        self.mainWindow.stillNewText.emit(
            "Number of Packets Lost = " + str(failcount))
        sys.stdout.flush()

    def sync(self):
        """ Ensures both sender and receiver are at that the same point in their data streams """

        # Prepare to sync by resetting variables
        print "Attempting to Sync - This should take approx. 2 sec"
        self.mainWindow.stillNewText.emit(
            "Attempting to Sync - This should take approx. 2 sec")
        sync = ""
        addsync0 = ""
        addsync1 = ""
        addsync2 = ""
        addsync3 = ""

        # Program is held until no data is being sent (timeout) or until the
        # pattern 's' 'y' 'n' 'c' is found ###
        while sync != "sync":
            addsync0 = self.rfdSer.read()
            addsync0 = str(addsync0)
            if addsync0 == '':
                break
            sync = addsync3 + addsync2 + addsync1 + addsync0
            addsync3 = addsync2
            addsync2 = addsync1
            addsync1 = addsync0
            sync = ""
        # Notifies sender that the receiving end is now synced
        self.rfdSer.write('S')
        print "System Match"
        self.mainWindow.stillNewText.emit("System Match")
        self.rfdSer.flushInput()			# Clear the buffers to be ready
        self.rfdSer.flushOutput()
        sys.stdout.flush()
        return

    def connectiontest(self, numping):
        """ Determines the ping time between the Pi and the computer """

        # Send the Pi A until the acknowledge is received, or too much time has
        # passed ###
        self.rfdSer.write('6!')
        termtime = time.time() + 20
        timeCheck = time.time() + 1
        while self.rfdSer.read() != 'A':
            if timeCheck < time.time():
                print "Waiting for Acknowledge"
                self.mainWindow.stillNewText.emit("Waiting for Acknowledge")
                timeCheck = time.time() + 1
            # self.rfdSer.write('6!')
            if termtime < time.time():  # If too much time passed, let the user know and return
                print "No Acknowledge Received, Connection Error"
                self.mainWindow.stillNewText.emit(
                    "No Acknowledge Received, Connection Error")
                sys.stdout.flush()
                return
        avg = 0

        # Using the specifified number of pings, give the Pi 10 seconds per
        # ping to respond correctly, and record the times ###
        self.rfdSer.write('~')
        temp = ""
        for x in range(1, numping):
            sendtime = time.time()
            receivetime = 0
            termtime = sendtime + 10
            # Loop until you get a P back, or too much time has passed
            while (temp != '~') & (time.time() < termtime):
                self.rfdSer.write('~')
                temp = self.rfdSer.read()
                receivetime = time.time()
                if receivetime == 0:  # If too much time has passed and no valid response, print the error, write D, and return
                    print "Connection Error, No return ping within 10 seconds"
                    self.mainWindow.stillNewText.emit(
                        "Connection Error, No return ping within 10 seconds")
                    self.rfdSer.write('D')
                    sys.stdout.flush()
                    return
            else:  # Otherwise reset the temp variable, and accumulate the avg
                temp = ""
                avg += receivetime - sendtime
                #print (avg/x)
        self.rfdSer.write('D')

        ### Determine and print the average response time ###
        avg = avg / numping
        print "Ping Response Time = " + str(avg)[0:4] + " seconds"
        self.mainWindow.stillNewText.emit(
            "Ping Response Time = " + str(avg)[0:4] + " seconds\n")
        sys.stdout.flush()			# Clear the buffer

        return

    def image_to_b64(self, path):
        """ Converts an image to a base64 encoded String (ASCII characters) """

        with open(path, "rb") as imageFile:
            return base64.b64encode(imageFile.read())

    def b64_to_image(self, data, savepath):
        """ Converts a base64 encoded string of ASCII characters back to an image, the save path dictates image format """
        fl = open(savepath, "wb")
        fl.write(data.decode('base64'))
        fl.close()

    def gen_checksum(self, data):
        """ Generates a 32 character hash up to 10000 char length String(for checksum). If string is too long I've notice length irregularities in checksum """
        return hashlib.md5(data).hexdigest()

    def setInterrupt(self, arg):
        self.interrupt = arg
