/*
 * Author: Dylan Trafford (EE/CpE), Trevor Gahl (CpE), Gabe Gordon (MSGC MAP Student). Adapted from example code from Adafruit.com
 * Developed for use by MSGC BOREALIS Program
 * Date of Last Edit: 05/10/2016
 * Purpose: To transmit data from a GPS and IMU unit to a computer for ground station positional data.
 * Note: Sends comma seperated data lead by a '~'. When the recieving computer sees a tilda, it knows it is the beginning of the line.
 */

//Included Libraries (some libraries are imported even though they are included in the base packages)
#include <Adafruit_GPS.h>
#include <SoftwareSerial.h>
#include <Wire.h>
#include <SPI.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BNO055.h>
#include <utility/imumaths.h>
#include <avr/sleep.h>
#include <LiquidCrystal.h>

//Defines (string replace constants)
#define BNO055_SAMPLERATE_DELAY_MS (100)                    //Set the delay between reading from the IMU, unused in this version
#define GPSECHO  false                                      //Display GPS data as read from the GPS in the Serial Monitor (dont do for actual use but good for debugging)

//Instance Initializations
Adafruit_BNO055 bno = Adafruit_BNO055(55);                  //Initializes an instance of the BNO055 called bno with an I2C address of 55
LiquidCrystal lcd(10,9,6,5,4,3);
SoftwareSerial mySerial(8, 7);                              //Initializes an instance of SoftwareSerial called mySerial with RX and TX on pins 8 and 7
Adafruit_GPS GPS(&mySerial);                                //Initializes an instance of Adafruit_GPS called GPS using the mySerial instance

//Global Intializations
boolean usingInterrupt = true;                              //Use an interrupt to parce GPS data (preferred to be true)
boolean calibrated = false;
int initial = false;


void setup() {
  // put your setup code here, to run once:
  lcd.begin(16, 2);
  Serial.begin(115200);                                     //Launches a serial connection with a 115200 baud rate
  if(!bno.begin())                                          //Launches the IMU. It returns a true value if it successfully launches. 
  {
    /* There was a problem detecting the BNO055 ... check your connections */
    Serial.print("Ooops, no BNO055 detected ... Check your wiring or I2C ADDR!");
    while(1);
  }
  GPS.begin(9600);                                          //Launches a software serial connection to the GPS at a baud rate of 9600
  delay(500);                                               //Wait for 0.5s
  bno.setExtCrystalUse(true);                                //Use the external clock in the IMU (true for better accuracy)
  bno.setMode(bno.OPERATION_MODE_NDOF);                               
  GPS.sendCommand(PMTK_SET_NMEA_OUTPUT_RMCGGA);             //String formatting on the GPS
  GPS.sendCommand(PMTK_SET_NMEA_UPDATE_1HZ);                //GPS packet dump rate
  GPS.sendCommand(PGCMD_ANTENNA);
  useInterrupt(usingInterrupt);                             //Set to use or not use the interrupt for GPS parcing
  delay(100);                                               //Wait for 0.1s
}

SIGNAL(TIMER0_COMPA_vect) {                                 // Interrupt is called once a millisecond, looks for any new GPS data, and stores it
  char c = GPS.read();
#ifdef UDR0
  if (GPSECHO)
    if (c) UDR0 = c;                                        //UDRO is the register for the hardware serial module
#endif
}

//void(* resetFunc) (void) = 0;                             //declare reset function at address 0. This is for a software reset (unused in current version)

void useInterrupt(boolean v) {                              //turns the interrupt(TIMER0_COMPA_vect) on or off based on the boolean passed to it
  if (v) {
    OCR0A = 0xAF;
    TIMSK0 |= _BV(OCIE0A);
  } else {
    TIMSK0 &= ~_BV(OCIE0A);
    usingInterrupt = false;
  }
}

void loop() {
//  lcd.setCursor(0,1);                                               //Main code, loops continuously
  float x,y,z;
  imu::Vector<3> euler = bno.getVector(Adafruit_BNO055::VECTOR_EULER);
  x = euler.x();                                                      //Creates Euler Vectors for the x, y, and z axis
  y = euler.y();
  z = euler.z();

  sensors_event_t event;                                    //Create a new local event instance.... called event
  
  
  //Get IMU position
  uint8_t system, gyro, accel, mag;                         //Create local variables gyro, accel, mag
  system = gyro = accel = mag = 0;                          //Initialize them to zeros
  
 if(calibrated == false){
  bno.getCalibration(&system, &gyro, &accel, &mag);         //Read the calibration values from the IMU
  bno.getEvent(&event);
//  lcd.setCursor(0,0);   
//  lcd.print("Calibrating...");                                           //Will continually read calibration values until "calibrated" is set to true
//  lcd.setCursor(0,1);
//  lcd.print("S:");
//  lcd.print(system,DEC);
//  lcd.print(" G:");
//  lcd.print(gyro,DEC);
//  lcd.print(" A:");
//  lcd.print(accel,DEC);
//  lcd.print(" M:");
//  lcd.print(mag,DEC); 
  Serial.print("~");
  Serial.print(",");
  Serial.print(GPS.latitudeDegrees,7);
  Serial.print(",");
  Serial.print(GPS.longitudeDegrees,7);
  Serial.print(",");
  Serial.print(GPS.altitude *3.2808);
  Serial.print(",");
  Serial.print(event.orientation.x,2);
  Serial.print(",");
  Serial.print(event.orientation.y,2);
  Serial.print(",");
  Serial.print(event.orientation.z,2);
  Serial.print(",");
  Serial.print(system, DEC);
  Serial.print(",");
  Serial.print(gyro, DEC);
  Serial.print(",");
  Serial.print(accel, DEC);
  Serial.print(",");
  Serial.println(mag, DEC);
//    if(bno.isFullyCalibrated()){
//      calibrated = true;
//    }
//  }

//  else{
//      if(initial == false){
//        delay(7000);
//      }
//        Serial.print("~");                                        //Transmit data over serial leading with a '~' and ending with '\n'
//        Serial.print(",");
//        Serial.print(GPS.latitudeDegrees,7);
//        Serial.print(",");
//        Serial.print(GPS.longitudeDegrees,7);
//        Serial.print(",");
//        Serial.print(GPS.altitude * 3.28084);
//        Serial.print(",");
//        Serial.print(event.orientation.x,2);
//        Serial.print(",");
//        Serial.print(system);
//        Serial.print(",");
//        Serial.print(gyro);
//        Serial.print(",");
//        Serial.print(accel);
//        Serial.print(",");
//        Serial.println(mag);

//        lcd.clear();
//        lcd.setCursor(0,0);                                                 //prints angle values to an LCD screen
//        lcd.print("X:");
//        lcd.setCursor(3,0);
//        lcd.print(x);
//        lcd.setCursor(8,0);
//        lcd.print(" Y:");
//        lcd.setCursor(11,0);
//        lcd.print(y);
//        lcd.setCursor(0,1);
//        lcd.print("Z:");
//        lcd.setCursor(3,1);
//        lcd.print(z);
//        calibrated = true;
//        initial = true;
  }

  delay(500);                                               //Wait for 0.5s
  
    if (!usingInterrupt) {                                    //If interrupt is not being used, the GPS data needs to be checked for parse here.
    char c = GPS.read();
    if (GPSECHO)
      if (c) Serial.print(c);
  }
  if (GPS.newNMEAreceived()) {                              //If data is new, parse it!

    if (!GPS.parse(GPS.lastNMEA()))
      return;
  }
}
