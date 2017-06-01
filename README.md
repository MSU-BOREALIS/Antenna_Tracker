# Antenna-Tracker-and-RFD-Controls-GUI
By Austin Langford, based on work from MSU-BOREALIS


This software allows you to control the antenna tracker designed by MSU-Borealis using the [Mini Maestro Servo Controller](https://www.pololu.com/product/1354).
It uses an Arduino Uno with a GPS shield and a [BNO055 9-Axis IMU](https://learn.adafruit.com/adafruit-bno055-absolute-orientation-sensor/overview) to calibrate itself.
RFD controls are added as well, allowing communication with a raspberry Pi running code designed by MSU-Borealis and MnSGC.


Uses [Anaconda](https://www.continuum.io/)

### There are 3 autotrack methods available: Iridium, APRS, and RFD.

-**Iridium tracking:** requires internet access so that you can reach the server holding the information controlled by MSU-Borealis.

-**APRS tracking:** set up to handle an [Eagle flight computer](http://www.highaltitudescience.com/products/eagle-flight-computer).

-**RFD tracking:** set up to work with the software on the raspberry pi. The format for the GPS string that needs to be received is as follows: "GPS:hours,minutes,seconds,latitude,longitude,altitude,satellites!"
Currently, this information is provided by an arduino nano with a adafruit GPS Breakout v3 attached to the Pi via USB cable.


## Operation:

-Connect your RFD, mini maestro, and arduino, and run the code through Spyder. Ports should autofill in the connections section. If you do not want to use the arduino/IMU, select the cardinal direction that your tracker is facing.
Select your methods of autotrack, they can all be run simultaneously. Select if you'd like to save data and if you'd like to graph your tracking in the Graphing and Logging section. Also choose whether or not you have internet access

-Hit update settings, and the calibration window will appear. When the gyro, accelerometer, and magnetometer all display a value of 3, place your IMU back onto the tracker, and hit ready to get your location and center bearing.
If you're using the RFD, go into the RFD tab and turn on RFD Listen by clicking the listen button. Press the launch antenna tracker button to begin tracking the most recent received balloon position.

-In order to use the still image system, you need to disable both the RFD commands, and the RFD Listen. 

-Manual controls will require that your autotrack method is set to disabled.
