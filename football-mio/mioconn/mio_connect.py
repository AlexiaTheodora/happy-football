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

w, h = 800, 600

last_vals = None
last_vals2 = None



class MioConnect:
    def __init__(self):
        self.CONNECTED = False

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

    def main(self,argv,connected1, connected2):
        global CONNECTED
        # comment scr and plot when you do not want for them to run in parallel
        #pygame.display.set_mode((1, 1))

        config = Config()

        # Get options and arguments
        try:
            opts, args = getopt.getopt(argv, 'hsn:a:p:v', ['help', 'shutdown', 'nmyo', 'address', 'port', 'verbose'])
        except getopt.GetoptError:
            sys.exit(2)
        turnoff = False
        for opt, arg in opts:
            if opt in ('-h', '--help'):
                self.print_usage()
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
            #pygame.display.quit()

            info_emg1 = StreamInfo(type='EMG', name='EMG_Stream_Left', channel_count=8, nominal_srate=200, channel_format='float32', source_id='')
            outlet_emg1 = StreamOutlet(info_emg1)

            info_emg2 = StreamInfo(type='EMG', name='EMG_Stream_Right',channel_count=8, nominal_srate=200, channel_format='float32', source_id='')
            outlet_emg2 = StreamOutlet(info_emg2)

            info_imu_acc1 = StreamInfo(type='Event Markers', name='IMU_Stream_Accelerometere_1', channel_count=1, channel_format='float32', source_id='')
            outlet_imu_acc1 = StreamOutlet(info_imu_acc1)

            info_imu_acc2 = StreamInfo(type='Event Markers', name='IMU_Stream_Accelerometere_2', channel_count=1, channel_format='float32', source_id='')
            outlet_imu_acc2 = StreamOutlet(info_imu_acc2)

            info_imu_roll1 = StreamInfo(type='Event Markers', name='IMU_Stream_Roll_1', channel_count=1, channel_format='float32', source_id='')
            outlet_imu_roll1 = StreamOutlet(info_imu_roll1)

            info_imu_roll2 = StreamInfo(type='Event Markers', name='IMU_Stream_Roll_2', channel_count=1, channel_format='float32', source_id='')
            outlet_imu_roll2 = StreamOutlet(info_imu_roll2)

            info_imu_pitch1 = StreamInfo(type='Event Markers', name='IMU_Stream_Pitch_1', channel_count=1, channel_format='float32', source_id='')
            outlet_imu_pitch1 = StreamOutlet(info_imu_pitch1)

            info_imu_pitch2 = StreamInfo(type='Event Markers', name='IMU_Stream_Pitch_2', channel_count=1, channel_format='float32', source_id='')
            outlet_imu_pitch2 = StreamOutlet(info_imu_pitch2)

            info_imu_yaw1 = StreamInfo(type='Event Markers', name='IMU_Stream_Yaw_1', channel_count=1, channel_format='float32', source_id='')
            outlet_imu_yaw1 = StreamOutlet(info_imu_yaw1)

            info_imu_yaw2 = StreamInfo(type='Event Markers', name='IMU_Stream_Yaw_2', channel_count=1, channel_format='float32', source_id='')
            outlet_imu_yaw2 = StreamOutlet(info_imu_yaw2)

            info_imu_gyro1 = StreamInfo(type='Event Markers', name='IMU_Stream_Gyro_1', channel_count=1, channel_format='float32', source_id='')
            outlet_imu_gyro1 = StreamOutlet(info_imu_gyro1)

            info_imu_gyro2 = StreamInfo(type='Event Markers', name='IMU_Stream_Gyro_2', channel_count=1, channel_format='float32', source_id='')
            outlet_imu_gyro2 = StreamOutlet(info_imu_gyro2)

            # Init
            myo_driver = MyoDriver(config)

            # Connect
            myo_driver.run(connected1, connected2)

            if turnoff:
                # Turn off
                myo_driver.deep_sleep_all()
                return

            if Config.GET_MYO_INFO:
                # Get info
                myo_driver.get_info()

            print("Ready for data.")
            print()

            while True:
                pygame.event.pump()
                myo_driver.receive()

                while not (myo_driver.data_handler.myo_imu_data.empty()):

                    data_both_samples = myo_driver.data_handler.myo_imu_data.get()

                    emg1 = []
                    emg2 = []

                    imu_acc1  = []
                    imu_acc2  = []
                    imu_yaw1  = []
                    imu_yaw2 = []
                    imu_roll1 = []
                    imu_roll2 = []
                    imu_pitch1 = []
                    imu_pitch2 = []
                    imu_gyro1 = []
                    imu_gyro2 = []

                    if (data_both_samples.get('emg')):
                        if (data_both_samples.get('emg').get("1")):
                            emg2 = list(data_both_samples.get('emg').get("1"))
                        if (data_both_samples.get('emg').get("0")):
                            emg1 = list(data_both_samples.get('emg').get("0"))

                    if (data_both_samples.get('imu')):
                        if (data_both_samples.get('imu').get("1")):
                            vec = data_both_samples.get('imu').get("1")
                            imu_acc2.append(vec[3])
                            imu_yaw2.append(vec[1])
                            imu_roll2.append(vec[0])
                            imu_pitch2.append(vec[2])
                            imu_gyro2.append(vec[4])

                        if (data_both_samples.get('imu').get("0")):
                            vec = data_both_samples.get('imu').get("0")
                            imu_acc1.append(vec[3])
                            imu_yaw1.append(vec[1])
                            imu_roll1.append(vec[0])
                            imu_pitch1.append(vec[2])
                            imu_gyro1.append(vec[4])


                    # emg2 = list(myo_driver.data_handler.myo_data1.get(block=False))
                    # emg2 = []
                    # plot the data in a new window

                    # plot(scr, [e / 500. for e in emg1], [e1 / 500. for e1 in emg2])
                    # plot(scr, [e / 500. for e in emg1])
                    # do not use time sleep when plotting
                    # print("left: {}, right {}".format(emg1, emg2))

                    if emg1 != []:
                        outlet_emg1.push_sample(emg1)
                    if emg2 != []:
                        outlet_emg2.push_sample(emg2)

                    if imu_acc1 != []:
                        outlet_imu_acc1.push_sample(imu_acc1)
                    if imu_yaw1 != []:
                        outlet_imu_yaw1.push_sample(imu_yaw1)
                    if imu_roll1 != []:
                        outlet_imu_roll1.push_sample(imu_roll1)
                    if imu_pitch1 != []:
                        outlet_imu_pitch1.push_sample(imu_pitch1)
                    if imu_gyro1 != []:
                        outlet_imu_gyro1.push_sample(imu_gyro1)

                    if imu_acc2 != []:
                        outlet_imu_acc2.push_sample(imu_acc2)
                    if imu_yaw2 != []:
                        outlet_imu_yaw2.push_sample(imu_yaw2)
                    if imu_roll2 != []:
                        outlet_imu_roll2.push_sample(imu_roll2)
                    if imu_pitch2 != []:
                        outlet_imu_pitch2.push_sample(imu_pitch2)
                    if imu_gyro2 != []:
                        outlet_imu_gyro2.push_sample(imu_gyro2)







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
            outlet_emg1.__del__()
            outlet_emg2.__del__()

            outlet_imu_acc1.__del__()
            outlet_imu_acc2.__del__()
            outlet_imu_yaw1.__del__()
            outlet_imu_yaw2.__del__()
            outlet_imu_roll1.__del__()
            outlet_imu_roll2.__del__()
            outlet_imu_pitch1.__del__()
            outlet_imu_pitch2.__del__()
            outlet_imu_gyro1.__del__()
            outlet_imu_gyro2.__del__()

            print("Disconnected")
            quit()


    def print_usage(self):
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


# decomment the folowing line only when you are running the mio_connect and game scripts separately
'''
if __name__ == "__main__":
    mio_connect = MioConnect()
    mio_connect.main(sys.argv[1:])
'''
