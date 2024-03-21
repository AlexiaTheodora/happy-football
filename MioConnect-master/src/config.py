"""
Default values for the script. Can be overridden by system args.
"""
from src.public.myohw import *


class Config:

    MYO_AMOUNT = 2  # Default amount of myos to expect
    EMG_MODE = EmgMode.myohw_emg_mode_send_emg  # EMG mode
    IMU_MODE = ImuMode.myohw_imu_mode_none  # IMU mode
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
    MAX_RETRIES = None  # Max amount of retries after unexpected disconnect

    # optional:
    MAC_ADDR_MYO_1 ='e8-26-3b-f2-38-16'
    MAC_ADDR_MYO_2 ='ec-07-35-d9-7a-c6'
