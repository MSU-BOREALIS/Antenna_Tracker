from PySide2 import *
from PySide2 import QtCore, QtGui
from PySide2.QtCore import *
from PySide2.QtCore import Signal as pyqtSignal
import time
from time import sleep
import threading
import datetime
# Library for using SSH
import paramiko
from paramiko import client
from paramiko.client import *


class VLCStreamer(QtCore.QObject):

    # Received Signals
    start = pyqtSignal()
    kill = pyqtSignal()

    def __init__(self):
        super(VLCStreamer, self).__init__()
        StreamThread = None

    def startVLCStream(self):
        """ Executes the streaming command on the pi and then begins stream """
        try:
            print("Connecting to streaming pi")
            client = SSHClient()
            client.set_missing_host_key_policy(AutoAddPolicy)
            client.connect('192.168.1.69', port=22, username='pi', password='raspberry')
            # If the pi is already streaming, will not start another streaming process
            client.exec_command('if pgrep vlc; then echo "Streaming already started"; else ./vlcTest.sh; fi')
        except Exception as e:
            print("Error sending commands to pi: ", str(e))

        # Delay to allow the streaming to start
        time.sleep(1)

        try:
            # Attempt to start streaming
            print("Starting VLC stream capture")
            timenow = datetime.datetime.now().strftime('%m-%w-%y_%H-%M-%S')
            print('Saving stream to StreamedVideo folder with name: ' + timenow + '.mp4')
            self.saveStreamThread = threading.Thread(target=lambda: os.system('vlc.exe rtsp://' + '192.168.1.69'
                                                                              + ':8080/ --sout=file/mp4:'
                                                                              + 'StreamedVideo\\'  # Folder
                                                                              + timenow + '.mp4'))  # Filename
            self.displayStreamThread = threading.Thread(target=lambda: os.system('vlc.exe rtsp://' + '192.168.1.69' + ':8080/'))

            self.saveStreamThread.start()
            time.sleep(.1)
            self.displayStreamThread.start()
        except Exception as e:
            print("Error beginning VLC Stream: ", str(e))

    def killVLCStream(self):
        """ Sends a command to the pi to kill streaming """
        try:
            print("Connecting to streaming pi")
            client = SSHClient()
            client.set_missing_host_key_policy(AutoAddPolicy)
            client.connect('192.168.1.69', port=22, username='pi', password='raspberry')
            client.exec_command('pkill vlc')
            print("Killed pi's vlc stream")
        except Exception as e:
            print("Error sending commands to pi: ", str(e))
