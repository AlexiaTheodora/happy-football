import multiprocessing

from .src.myodriver import MyoDriver
from .src.config import Config
import serial
import getopt
import sys
import time
import pygame
import time
from pylsl import StreamInfo, StreamOutlet, StreamInlet, resolve_stream
from pythonosc import osc_server

w, h = 800, 600

last_vals = None  # Initialize last_vals as None
last_vals2 = None  # Initialize last_vals as None
CONNECTED = False


def plot(scr, vals1, vals2):
    global last_vals
    global last_vals2

    DRAW_LINES = True
    D = 5

    if last_vals is None:
        last_vals = vals1
        return
    if last_vals2 is None:
        last_vals2 = vals2
        return

    scr.scroll(-D)
    scr.fill((0, 0, 0), (w - D, 0, w, h))

    for i, (u, v) in enumerate(zip(last_vals, vals1)):
        if DRAW_LINES:
            # Draw lines for the first set of values (vals1)
            pygame.draw.line(scr, (0, 255, 0),
                             (w - D, int(h / 9 * (i + 1 - u))),
                             (w, int(h / 9 * (i + 1 - v))))
            pygame.draw.line(scr, (255, 255, 255),
                             (w - D, int(h / 9 * (i + 1))),
                             (w, int(h / 9 * (i + 1))))
    for i, (u, v) in enumerate(zip(last_vals2, vals2)):
        if DRAW_LINES:
            # Draw lines for the second set of values (vals2)
            pygame.draw.line(scr, (255, 0, 0),
                             (w - D, int(h / 9 * (i + 1 - u))),
                             (w, int(h / 9 * (i + 1 - v))))
            pygame.draw.line(scr, (255, 255, 255),
                             (w - D, int(h / 9 * (i + 1))),
                             (w, int(h / 9 * (i + 1))))

    pygame.display.flip()
    last_vals = vals1
    last_vals2 = vals2


def main(argv):
    global CONNECTED
    # comment scr and plot when you do not want for them to run in parallel
    scr = pygame.display.set_mode((w, h))

    config = Config()

    # Get options and arguments
    try:
        opts, args = getopt.getopt(argv, 'hsn:a:p:v', ['help', 'shutdown', 'nmyo', 'address', 'port', 'verbose'])
    except getopt.GetoptError:
        sys.exit(2)
    turnoff = False
    for opt, arg in opts:
        if opt in ('-h', '--help'):
            print_usage()
            sys.exit()
        elif opt in ('-s', '--shutdown'):
            turnoff = True
        elif opt in ("-n", "--nmyo"):
            config.MYO_AMOUNT = int(arg)
        elif opt in ("-a", "--address"):
            config.OSC_ADDRESS = arg
        elif opt in ("-p", "--port"):
            config.OSC_PORT = arg
        elif opt in ("-v", "--verbose"):
            config.VERBOSE = True

    # Run
    myo_driver = None
    seconds = 10
    try:

        info_emg1 = StreamInfo(type='EMG', name='EMG_Stream1', channel_count=8, nominal_srate=200, channel_format='float32', source_id='')
        outlet_emg1 = StreamOutlet(info_emg1)

        info_emg2 = StreamInfo(type='EMG', name='EMG_Stream2',channel_count=8, nominal_srate=200, channel_format='float32', source_id='')
        outlet_emg2 = StreamOutlet(info_emg2)


        info_imu1 = StreamInfo(name = 'IMU_Stream1', type='IMU', channel_count=5,nominal_srate=200, channel_format='float32', source_id='')
        outlet_imu1 = StreamOutlet(info_imu1)

        info_imu2 = StreamInfo(name = 'IMU_Stream2', type='IMU', channel_count=5, nominal_srate=200, channel_format='float32', source_id='')
        outlet_imu2 = StreamOutlet(info_imu2)

        # Init
        myo_driver = MyoDriver(config)

        # Connect
        myo_driver.run()


        if turnoff:
            # Turn off
            myo_driver.deep_sleep_all()
            return

        if Config.GET_MYO_INFO:
            # Get info
            myo_driver.get_info()

        print("Ready for data.")
        CONNECTED = True
        print()


        #server = osc_server.ThreadingOSCUDPServer((config.OSC_ADDRESS, config.OSC_PORT), myo_driver.data_handler.builder)
        #server.serve_forever()
        while True:
            pygame.event.pump()
            myo_driver.receive()

            while not (myo_driver.data_handler.myo_imu_data.empty()):
                data_both_samples = myo_driver.data_handler.myo_imu_data.get()

                emg1 = []
                emg2 = []

                imu1 = []
                imu2 = []

                if(data_both_samples.get('emg')):
                    if (data_both_samples.get('emg').get("1")):
                        emg2 = list(data_both_samples.get('emg').get("1"))
                    if(data_both_samples.get('emg').get("0")):
                        emg1 = list(data_both_samples.get('emg').get("0"))

                if (data_both_samples.get('imu')):
                    if (data_both_samples.get('imu').get("1")):
                        imu2 =  list(data_both_samples.get('imu').get("1"))

                    if (data_both_samples.get('imu').get("0")):
                        imu1 =  list(data_both_samples.get('imu').get("0"))

                #emg2 = list(myo_driver.data_handler.myo_data1.get(block=False))
                #emg2 = []
                # plot the data in a new window

                #plot(scr, [e / 500. for e in emg1], [e1 / 500. for e1 in emg2])
                # plot(scr, [e / 500. for e in emg1])
                # do not use time sleep when plotting
                #print("left: {}, right {}".format(emg1, emg2))

                if emg1 != []:
                    outlet_emg1.push_sample(emg1)
                if emg2 != []:
                    outlet_emg2.push_sample(emg2)


                if imu1 != []:
                    outlet_imu1.push_sample(imu1)
                if imu2 != []:
                    outlet_imu2.push_sample(imu2)







    except KeyboardInterrupt:
        print("Interrupted.")
        pygame.quit()
        quit()

    except serial.serialutil.SerialException:
        print("ERROR: Couldn't open port. Please close MyoConnect and any program using this serial port.")

    finally:
        print("Disconnecting...")
        if myo_driver is not None:
            if Config.DEEP_SLEEP_AT_KEYBOARD_INTERRUPT:
                myo_driver.deep_sleep_all()
            else:
                myo_driver.disconnect_all()
        print("Disconnected")
        quit()


def print_usage():
    message = """usage: python mio_connect.py [-h | --help] [-s | --shutdown] [-n | --nmyo <amount>] [-a | --address \
<address>] [-p | --port <port_number>] [-v | --verbose]

Options and arguments:
    -h | --help: display this message
    -s | --shutdown: turn off (deep_sleep) the expected amount of myos
    -n | --nmyo <amount>: set the amount of devices to expect
    -a | --address <address>: set OSC address
    -p | --port <port_number>: set OSC port
    -v | --verbose: get verbose output
"""
    print(message)


if __name__ == "__main__":
    main(sys.argv[1:])
