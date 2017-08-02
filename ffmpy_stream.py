import ffmpy
import psutil
import threading
from time import sleep


# you will need to type in your RTMP key here
# this is your induvisual key that each group has.
RTMPKEY = 'put your key in these quotes'

# once you type in your key all you have to do is run this python script by typing in:
#      python ffmpy_stream.py
# this will start up the python script and will try to connect to the payload to stream if it can.


def continuousStream(Flag):

    ff = ffmpy.FFmpeg(

        # first argument is the input
        # second argument is the flags that are associated with the input
        # in this case -stimeout 5000000 will wait 5s before ending the function if there is no feed.++699566659

        inputs={'rtsp://192.168.1.3:8554/': '-stimeout 3000000 '},
        #	inputs={'trailer_720p.mov': '-re'},

        # in this output statement there are 4 arguments, the first two are a local stream that you can view in vlc
        # using rtp://localhost:4000/ as the network stream in vlc

        # the 3rd and 4th arguments are for streamign to streams website.
        outputs={'rtp://localhost:4000': '-c copy -f rtp_mpegts', 'rtmp://media.stream.live:1935/live/' + \
                 RTMPKEY: '  -r 25 -c copy -loglevel panic -b:v 3M -f flv'}

        # if you want to see the output of ffmpeg take out -loglevel panic
    )

    print("Your current ffmpeg command:")
    print(ff.cmd)
    print()

    # this while loop will run as along as the boolean passed into it is True.
    #
    # if you lose connection to the payload this will automatically retry connecting
    # to the rtsp connection until the video stream is established again.
    while(Flag):

        try:
            print("starting ffmpeg process")

            # process to start a thread
            t = threading.Thread(target=ff.run, args=())
            # run in the background
            t.daemon = True

            t.start()

            ##################################
            # bench testing commands below
            ##################################
            #print("CPU usage currenly")

            # this while loop will run as long as the thread is running
            while(t.is_alive()):
                sleep(0.1)
                # print(psutil.cpu_percent(interval=1))
                # print(threading.enumerate())

            # this command will just wait for the thread to clean up.
            t.join()
            print(
                "ffmpeg has finished, through end of file or timeout, streaming shouldn't reach here")
            print("restarting now")

        except:
            print(
                "Error, unable to maintain thread.  Connection to payload is interrupted.")


if __name__ == "__main__":

    #########################################################
    # this should be changed to whatever your checkbox is.
    #########################################################
    flag = False

    print('running ffmpeg from alternate file, testing threading layering')
    t = threading.Thread(target=continuousStream, args=(flag,))
    t.daemon = True
    t.start()
    t.join()
    print("end of streaming?")
