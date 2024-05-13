"""
Default values for the script. Can be overridden by system args.
"""
from .public.myohw import *


class Config:

    MYO_AMOUNT = 2  # Default amount of myos to expect
    EMG_MODE = EmgMode.myohw_emg_mode_send_emg  # EMG mode
    IMU_MODE = ImuMode.myohw_imu_mode_send_all  # IMU mode
    CLASSIFIER_MODE = ClassifierMode.myohw_classifier_mode_enabled  # Classifier mode


    DEEP_SLEEP_AT_KEYBOARD_INTERRUPT = False  # Turn off connected devices after keyboard interrupt

    PRINT_EMG = False  # Console print EMG data
    PRINT_IMU = False  # Console print IMU data

    VERBOSE = False  # Verbose console
    GET_MYO_INFO = True  # Get and display myo info at sync

    MESSAGE_DELAY = 0.1  # Added delay before every message sent to the myo

    OSC_ADDRESS = 'localhost'  # Address for OSC
    OSC_PORT = 3000  # Port for OSC

    RETRY_CONNECTION_AFTER = 2  # Reconnection timeout in seconds
    MAX_RETRIES = 2  # Max amount of retries after unexpected disconnect

    # optional:
    MAC_ADDR_MYO_1 ='e8-26-3b-f2-38-16'
    MAC_ADDR_MYO_2 ='ec-07-35-d9-7a-c6'
    MAC_ADDR_MYO_3 ='ea-de-bf-42-2f-30'


# always left - MAC_ADDR_MYO_1
# always right - MAC_ADDR_MYO_2

#ea-de-bf-42-2f-30 - Armband 3
#0
#Myo ready 0 b'0/B\xbf\xde\xea'

#e8-26-3b-f2-38-16 - Armband 1
#1
#Myo ready 1 b'\x168\xf2;&\xe8'

#ec-07-35-d9-7a-c6 - Armband 2