from Antenna_Tracker_and_RFD_Controls_GUI import SerialDevice


class ServoController:

    def __init__(self, servoController):
        self.moveCommand = 0x84
        self.accelCommand = 0x89
        self.speedCommand = 0x87

        # change the movement speed etc of ubiquity tilt servo
        self.tiltChannel = 0
        self.tiltAccel = 1
        self.tiltSpeed = 1
        self.tiltAngleMin = -180		# -90
        self.tiltAngleMax = 180		 	# 90

        self.rfdtiltChannel = 2
        self.rfdtiltAccel = 1
        self.rfdtiltSpeed = 1
        self.rfdtiltAngleMin = -180		# -90
        self.rfdtiltAngleMax = 180		# 90
        # change the movement speed etc of ubiquity pan servo
        self.panChannel = 1
        self.panAccel = 1
        self.panSpeed = 1

        self.rfdpanChannel = 3
        self.rfdpanAccel = 1
        self.rfdpanSpeed = 1

        # Shouldn't need to change these unless you change to some exotic
        # servos
        self.servoMin = 3600
        self.servoMax = 8400

        # Memory for last position (To account for backlash)
        self.previousPan = 6000
        self.servoController = servoController

        # Set the acceleration and speed of the servos
        self.setServoAccel(self.panAccel, self.tiltAccel)
        self.setServoSpeed(self.panSpeed, self.tiltSpeed)

    def setServos(self, servoController):
        """ Setter method to set the servo serial device """

        self.servoController = servoController.getDevice()

    def setCommands(self, moveCommand, accelCommand, speedCommand):
        """ Setter method to set command hex """

        self.moveCommand = moveCommand
        self.accelCommand = accelCommand
        self.speedCommand = speedCommand

    def setTiltSettings(self, channel, accel, speed, angleMax, angleMin):
        """ Setter method to change tilt settings """

        self.tiltChannel = channel
        self.tiltAccel = accel
        self.tiltSpeed = speed
        self.tiltAngleMin = angleMax
        self.tiltAngleMax = angleMin

        self.setServoAccel(self.panAccel, self.tiltAccel)
        self.setServoSpeed(self.panSpeed, self.tiltSpeed)

    def setPanSettings(self, channel, accel, speed):
        """ Setter method to change pan settings """

        self.panChannel = channel
        self.panAccel = accel
        self.panSpeed = speed

        self.setServoAccel(self.panAccel, self.tiltAccel)
        self.setServoSpeed(self.panSpeed, self.tiltSpeed)

    def setServoLimits(self, maximium, minimum):
        """ Setter method to change servo limits """

        self.servoMin = minimum
        self.servoMax = maximium

    def setServoAccel(self, panAccel, tiltAccel):
        """ Sets the rate at which the servos accelerate """

        try:
            self.tiltAccel = tiltAccel
            self.panAccel = panAccel

            setAccel = [self.accelCommand, self.tiltChannel, self.tiltAccel, 0]
            setAccel = [self.accelCommand,
                        self.rfdtiltChannel, self.tiltAccel, 0]
            self.servoController.write(setAccel)
            setAccel = [self.accelCommand, self.panChannel, self.panAccel, 0]
            setAccel = [self.accelCommand,
                        self.rfdpanChannel, self.panAccel, 0]
            self.servoController.write(setAccel)

        except:
            print("Error, could not set the servo acceleration, check com ports")

    def setServoSpeed(self, panSpeed, tiltSpeed):
        """ Sets the max speed at which the servos rotate """

        try:
            self.tiltSpeed = tiltSpeed
            self.panSpeed = panSpeed

            setSpeed = [self.speedCommand, self.tiltChannel, self.tiltSpeed, 0]
            setSpeed = [self.speedCommand,
                        self.rfdtiltChannel, self.tiltSpeed, 0]
            self.servoController.write(setSpeed)
            setSpeed = [self.speedCommand, self.panChannel, self.panSpeed, 0]
            setSpeed = [self.speedCommand,
                        self.rfdpanChannel, self.panSpeed, 0]
            self.servoController.write(setSpeed)

        except:
            print("Error, could not set the servo speed, check com ports")

    def moveTiltServo(self, position):
        """ Takes a single argument, moves the tilt servo to the position specified by the argument """
        position = int(position)
        msb = (position >> 7) & 0x7F
        lsb = position & 0x7F

        try:

            '''modify upper and lower tilt angle limits'''

            ### Move the tilt servo ###
            '''
            if position < 71:		  # 80 degrees upper limit
                moveTilt = [self.moveCommand, self.tiltChannel, chr(71)]
                moveRfdTilt = [self.moveCommand, self.rfdtiltChannel, chr(71)]
            elif position > 123:	   # 5 degrees lower limit
                moveTilt = [self.moveCommand, self.tiltChannel, chr(123)]
                moveRfdTilt = [self.moveCommand, self.rfdtiltChannel, chr(123)]
            else:
                moveTilt = [self.moveCommand, self.tiltChannel, chr(position)]
                moveRfdTilt = [self.moveCommand,
                               self.rfdtiltChannel, chr(position)]
            '''
            moveTilt = [self.moveCommand, self.tiltChannel, lsb, msb]
            moveRfdTilt = [self.moveCommand, self.tiltChannel, lsb, msb]
            self.servoController.write(moveTilt)
            self.servoController.write(moveRfdTilt)
            print(moveTilt)
            print "\t\tMove Tilt: ", float(position)

        except Exception, e:
            print(str(e))

    def movePanServo(self, position):
        """ Takes a single argument, moves the pan servo to the position specified by the argument """
        position = int(position)
        msb = (position >> 7) & 0x7F
        lsb = position & 0x7F

        try:
            ### Move the pan servo ###
            #if self.previousPan > position:
            #    position += 1
            #self.previousPan = position

            movePan = [self.moveCommand, self.panChannel, lsb, msb]
            moveRfdPan = [self.moveCommand,
                          self.rfdpanChannel, lsb, msb]
            print(movePan)
            self.servoController.write(movePan)
            self.servoController.write(moveRfdPan)
            print "\t\tMove Pan: ", float(position)
            return

        except Exception, e:
            print(str(e))
