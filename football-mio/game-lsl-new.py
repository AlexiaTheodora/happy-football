import pygame
import sys
import multiprocessing
from pygame.locals import *
from pynput.keyboard import Controller


import multiprocessing
#from pickable import PickleableSurface
#from pickle import loads,dumps
import csv

import time
from pylsl import StreamInfo, StreamOutlet, StreamInlet, resolve_stream
import pandas as pd

import numpy as np
from pylsl import StreamInlet, resolve_stream, StreamOutlet, StreamInfo
import scipy
from scipy.signal import butter, lfilter
import unicodedata
import csv
import time
import datetime
import warnings
import matplotlib.pyplot as plt
from datetime import date
'''
from mioconn.src.myodriver import MyoDriver
from mioconn.src.config import Config
import serial
import getopt
import sys
import time
import pygame
import time
from pylsl import StreamInfo, StreamOutlet, StreamInlet, resolve_stream
'''
pygame.init()

# Constants
emg_ch = 7  # 34:APL-R, 35:APL-L, 36:ED-R, 37:ED-L, 38:FD-R, 39:FD-L
emg_ch_right = 3
emg_ch_left = 4

fs = 200
win_len = 1
filt_low = 4
filt_high = 10
filt_order = 1

MAC_WIDTH = 1280
MAC_HEIGHT = 800
WIDTH, HEIGHT = MAC_WIDTH, MAC_HEIGHT
FONT = pygame.font.Font('freesansbold.ttf', 32)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
X = WIDTH / 2 - 30
Y = HEIGHT * 3 / 4

BALL_IMAGE = pygame.image.load("assets/ball.png")
BALL_RED_IMAGE = pygame.image.load("assets/ball_red.png")
GATE_R_IMAGE = pygame.image.load("assets/gate_r.png")
GATE_L_IMAGE = pygame.image.load("assets/gate_l.png")
SPEED = 10

# defaults threshholds
THLU = 500
THLL = 200
THRU = 500
THRL = 200

force_upper_limit = False

event_game_start = ['41']
event_game_stop = ['42']
event_move_left_start = ['11']
event_move_left_stop = ['12']
event_move_right_start = ['21']
event_move_right_stop = ['22']

info = StreamInfo('EMG', type='Markers', channel_count=1, channel_format='string', source_id='')
outlet = StreamOutlet(info)

streams = resolve_stream('type', 'Markers')
inlet = StreamInlet(streams[0])

FILE = open('motions.txt', 'a')
ACTIVATE_FILE = False  # change to true when you want to log the event markers
ACTIVATE_ONE_SCRIPT_ONLY = False
today = date.today()


def start_lsl_stream():
    """
    Starts listening to EEG lsl stream. Will get "stuck" if no stream is found.
    :param type: string - type of stream type (e.g. 'EEG' or 'marker')
    :return: lsl_inlet; pysls.StreamInlet object
    """

    '''
    if len(streams) > 1:
        warnings.warn('Number of EEG streams is > 0, picking the first one.')
    lsl_inlet = StreamInlet(streams[0])
    lsl_inlet.pull_sample()  # need to pull first sample to get buffer started for some reason
    print("Stream started.")
    '''
    '''
    it works much slower
    if streams_emg1:
        inlet1 = StreamInlet(streams_emg1[0])
    if streams_emg2:
        inlet2 = StreamInlet(streams_emg2[0])
    '''

    streams = resolve_stream()
    # changed from old code which gad as arguments type and 'type'
    '''
    if len(streams) > 1:
        warnings.warn('Number of EEG streams is > 0, picking the first one.')
    lsl_inlet = StreamInlet(streams[0])
    lsl_inlet.pull_sample()  # need to pull first sample to get buffer started for some reason
    print("Stream started.")
    '''
    inlet1 = StreamInlet(streams[0])
    inlet2 = StreamInlet(streams[1])
    return inlet1, inlet2


def butter_bandpass(lowcut, highcut, fs, order):
    b, a = butter(order, [lowcut, highcut], fs=fs, btype='band', output="ba")
    return b, a

def pull_from_buffer(lsl_inlet, max_tries=10):
    """
    Pull data from the provided lsl inlet and return it as an array.
    :param lsl_inlet: lsl inlet object
    :param max_tries: int; number of empty chunks after which an error is thrown.
    :return: np.ndarray of shape (n_samples, n_channels)
    """
    # Makes it possible to run experiment without eeg data for testing by setting lsl_inlet to None
    

    pull_at_once = 200
    samps_pulled = 200
    n_tries = 0

    samples = []
    while pull_at_once == samps_pulled:
        data_lsl, _ = lsl_inlet.pull_chunk(max_samples=pull_at_once)
        arr = np.array(data_lsl)
        if len(arr) > 0:
            samples.append(arr)
            samps_pulled = len(arr)
        else:
            n_tries += 1
            time.sleep(0.7)
            if n_tries == max_tries:
                raise ValueError("Stream does not seem to provide any data.")
    # print('samples',samples)
    return np.vstack(samples)


def pull_data(lsl_inlet, data_lsl, replace=True):
    new_data = pull_from_buffer(lsl_inlet)
    if replace or data_lsl is None:
        data_lsl = new_data
    else:
        data_lsl = np.vstack([data_lsl, new_data])
    return data_lsl


def send_trigger(trigger):
    outlet.push_sample(trigger)
    if ACTIVATE_FILE:
        FILE.write("{} ---- {}".format(trigger, datetime.datetime.now()))
        FILE.write('\n')
    time.sleep(0.01)

'''
class MioConnect:
    def __init__(self):
        self.w = 800
        self.h = 600
        self.last_vals = None

    def plot(self, scr, vals1, vals2):

        DRAW_LINES = True
        D = 5

        if self.last_vals is None:
            self.last_vals = vals1
            return

        scr.scroll(-D)
        scr.fill((0, 0, 0), (self.w - D, 0, self.w, self.h))

        for i, (u, v) in enumerate(zip(self.last_vals, vals1)):
            if DRAW_LINES:
                # Draw lines for the first set of values (vals1)
                pygame.draw.line(scr, (0, 255, 0),
                                 (self.w - D, int(self.h / 9 * (i + 1 - u))),
                                 (self.w, int(self.h / 9 * (i + 1 - v))))
                pygame.draw.line(scr, (255, 255, 255),
                                 (self.w - D, int(self.h / 9 * (i + 1))),
                                 (self.w, int(self.h / 9 * (i + 1))))

                # Draw lines for the second set of values (vals2)
                pygame.draw.line(scr, (255, 0, 0),
                                 (self.w - D, int(self.h / 9 * (i + 1 - vals2[i]))),
                                 (self.w, int(self.h / 9 * (i + 1 - vals2[i]))))
                pygame.draw.line(scr, (255, 0, 255),
                                 (self.w - D, int(self.h / 9 * (i + 1))),
                                 (self.w, int(self.h / 9 * (i + 1))))
        pygame.display.flip()
        self.last_vals = vals1

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

    def main(self, argv):

        # comment scr and plot when you do not want for them to run in parallel
        scr = pygame.display.set_mode((self.w, self.h))

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

        myo_driver = None
        seconds = 10
        try:

            info_emg1 = StreamInfo('EMG_Stream1', 'EMG', 8, 1000, 'float32', 'EMG1_ID')
            outlet_emg1 = StreamOutlet(info_emg1)

            info_emg2 = StreamInfo('EMG_Stream2', 'EMG', 8, 1000, 'float32', 'EMG2_ID')
            outlet_emg2 = StreamOutlet(info_emg2)

            myo_driver = MyoDriver(config)
            myo_driver.run()

            if turnoff:
                myo_driver.deep_sleep_all()
                return

            if Config.GET_MYO_INFO:
                myo_driver.get_info()

            print("Ready for data.")
            print()

            while True:
                pygame.event.pump()
                myo_driver.receive()

                while not (myo_driver.data_handler.myo_data0.empty()) and not (
                        myo_driver.data_handler.myo_data1.empty()):
                    emg1 = list(myo_driver.data_handler.myo_data0.get())
                    emg2 = list(myo_driver.data_handler.myo_data1.get())
                    # plot(scr, [e / 500. for e in emg1], [e1 / 500. for e1 in emg2])
                    outlet_emg1.push_sample(emg1)
                    outlet_emg2.push_sample(emg2)


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

    def start(self):
        self.main(sys.argv[1:])
'''

class Ball:
    def __init__(self):
        self.width = self.height = HEIGHT / 13
        self.x = WIDTH / 2 - 30
        self.y = HEIGHT * 3 / 4
        self.dx = 0  # Change in x position (initialize to 0)
        self.move_count = 0
        self.image = pygame.transform.scale(BALL_IMAGE, (self.width, self.height))
        # self.screen = screen

    def move_left(self):
        self.dx = -SPEED
        self.move_count += 1
        self.x -= SPEED
        self.update()

    def move_right(self):
        self.dx = SPEED
        self.move_count += 1
        self.x += SPEED
        self.update()

    def stop(self):
        self.dx = 0

    def update(self):
        screen.blit(self.image, (self.x, self.y))

    def change_to_red(self):
        self.image = pygame.transform.scale(BALL_RED_IMAGE, (self.width, self.height))

    def change_to_normal(self):
        self.image = pygame.transform.scale(BALL_IMAGE, (self.width, self.height))


class GateRight:
    def __init__(self):
        self.width = self.height = HEIGHT / 5
        self.x = WIDTH - 60 - self.width
        self.y = HEIGHT * 3 / 4 - self.height / 2
        self.image = pygame.transform.scale(GATE_R_IMAGE, (self.width, self.height))

    def draw(self):
        screen.blit(self.image, (self.x, self.y))


class GateLeft:
    def __init__(self):
        self.width = self.height = HEIGHT / 5
        self.x = self.width / 2
        self.y = HEIGHT * 3 / 4 - self.height / 2
        self.image = pygame.transform.scale(GATE_L_IMAGE, (self.width, self.height))

    def draw(self):
        screen.blit(self.image, (self.x, self.y))


class Button:
    def __init__(self, x, y, width, height, text):
        self.rect = pygame.Rect(x, y, width, height)
        self.color = RED
        self.text = FONT.render('START', True, WHITE)
        self.clicked = False

    def draw(self, screen):
        pygame.draw.rect(screen, self.color, self.rect)
        text_rect = self.text.get_rect(center=self.rect.center)
        screen.blit(self.text, text_rect)


class GameState:
    def __init__(self, screen, start_button, keyboard):
        self.screen = screen

        self.ball = Ball()
        self.gate_left = GateLeft()
        self.gate_right = GateRight()
        self.intro_done = False
        self.play_done = False
        self.start_button = start_button
        self.keyboard = keyboard
        self.myo_data = []

        self.a = 0
        self.b = 0

    def intro(self):
        # Load and display the introductory image
        intro_image = pygame.image.load("assets/pag1.png")
        intro_rect = intro_image.get_rect()
        intro_rect.center = (WIDTH // 2, HEIGHT // 2)

        text = FONT.render('Justus spielt', True, WHITE)
        text_rect = text.get_rect()
        text_rect.center = (X + 30, Y - 250)

        # start_img = pygame.image.load("assets/start.png")
        # start_img = pygame.transform.scale(start_img,(200,200))
        # start_img_rect = start_img.get_rect()

        self.screen.blit(intro_image, intro_rect)
        self.screen.blit(text, text_rect)
        self.start_button.draw(self.screen)
        # self.screen.blit(start_img,start_img)

        while not self.start_button.clicked:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    send_trigger(event_game_stop)
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.start_button.rect.collidepoint(event.pos):
                        self.start_button.clicked = True
                        self.intro_done = True

            pygame.display.flip()
        self.play()

    def get_emg(self, lsl_inlet, data_lsl, emg, win_len):
        # print(np.shape(data_lsl))
        data_lsl = pull_data(lsl_inlet=lsl_inlet, data_lsl=data_lsl, replace=False)
        # print('lsl_inlet',lsl_inlet.info())
        # emg = data_lsl[:, emg_ch] # select emg channel
        avg = 0
        for row in data_lsl:
            avg = 0
            for i in row:
                avg += i
            emg.append(avg);

        # print('emg',len(emg))
        # print('data_lsl',len(data_lsl))
        win_samp = win_len * fs  # define win len (depending on fs)
        # print('win_samp',win_samp)
        emg_chunk = 0
        if len(emg) > win_samp:  # wait until data win is long enough
            emg_win = emg[-win_samp:-1]  # pull data from time point 0 to -win_size
            emg_filt = lfilter(self.b, self.a, emg_win)  # applying the filter (no need to change)
            emg_env = np.abs(scipy.signal.hilbert(emg_filt))  # calculating envelope
            # emg_smooth = scipy.signal.savgol_filter(emg_env, window_length=300, polyorder=3) # optional: smooth the signal (avoid data jumps)
            '''
            # for testing
            plt.plot(emg_filt,label='bp_filt')
            plt.plot(emg_env,label='envelope')
            #plt.plot(emg_smooth,label='smooth')
            plt.grid()
            plt.legend()
            plt.show()
            '''

            chunk_size = 4  # start: 20 # change to 4 eventually later - 200HZ sampling rate
            emg_chunk = np.mean(np.power(emg_env[-chunk_size:-1], 2))
            # offset = 100
            # emg_chunk = emg_chunk - offset
            # if emg_chunk < 0: emg_chunk = 0
            # print('emg_chunk',emg_chunk)
        return emg_chunk, data_lsl

    def play(self):

        # maybe create a new class for this

        inlet_emg1 = None
        inlet_emg2 = None
        # !!! change to the time emg!!!!
        send_trigger(event_game_start)

        inlet1, inlet2 = start_lsl_stream()
        data_lsl = None
        self.b, self.a = butter_bandpass(filt_low, filt_high, fs, filt_order)

        '''
        streams_emg1 = resolve_stream('type', 'EMG')
        streams_emg2 = resolve_stream('type', 'EMG')

        if streams_emg1:
            inlet_emg1 = StreamInlet(streams_emg1[0])

        if streams_emg2:
            inlet_emg2 = StreamInlet(streams_emg2[0])
        '''

        text = FONT.render('Welcome to the best game ever', True, WHITE)
        text_rect = text.get_rect()
        text_rect.center = (X + 30, Y - 250)
        self.screen.blit(text, text_rect)

        controls = Controls(pygame.Rect(0, 0, WIDTH / 2, 40))
        controls2 = Controls(pygame.Rect(WIDTH / 2, 0, WIDTH, 40))

        user_text = ''
        user_text2 = ''

        thrs_right = [THRL, THRU]  # this will be changed with the user input thrs - default values can be these ones
        thrs_left = [THLL, THLU]  # this will be changed with the user input thrs - default values can be these ones

        # thrs_right = [200, 5000]
        # thrs_left = [200, 5000]

        continued_left = False
        continued_right = False

        while not self.play_done:
            background = pygame.image.load("assets/football.jpeg")
            background = pygame.transform.scale(background, (WIDTH, HEIGHT))
            background.get_rect().center = (WIDTH // 2, HEIGHT // 2)
            self.screen.blit(background, (0, 0))
            self.gate_left.draw()
            self.gate_right.draw()
            arrow_key_pressed = None

            controls.draw((0, 0, 0), 'Th LU:')
            controls2.draw((0, 0, 0), 'Th RU:')

            # ======================================================================
            force_right = 0
            force_left = 0
            emg1 = []
            emg2 = []
            force_right, data_lsl = self.get_emg(lsl_inlet=inlet1, data_lsl=data_lsl, emg=emg1,
                                                 win_len=win_len)

            force_left, data_lsl = self.get_emg(lsl_inlet=inlet2, data_lsl=data_lsl, emg=emg2,
                                                win_len=win_len)

            # print('Left: ' + str(int(force_left)) + '     Right: ' + str(int(force_right)))

            if force_right > thrs_right[1] or force_left > thrs_left[1]:
                force_upper_limit = True
                self.ball.change_to_red()
            else:
                force_upper_limit = False
                self.ball.change_to_normal()

            if force_left > thrs_left[0] and force_left < thrs_left[1] and force_right < thrs_right[0]:
                print("stanga")
                if continued_right:
                    send_trigger(event_move_right_stop)
                    continued_right = False

                if not continued_left:
                    send_trigger(event_move_left_start)
                    continued_left = True
                self.ball.move_left()
                self.ball.update()
                if self.ball.x <= self.gate_left.x + 20:
                    self.play_done = True
                    continued_left = False

            if force_right > thrs_right[0] and force_right < thrs_right[1] and force_left < thrs_left[0]:
                print("dreapta")
                if continued_left:
                    send_trigger(event_move_left_stop)
                    continued_left = False
                if not continued_right:
                    send_trigger(event_move_right_start)
                    continued_right = True
                self.ball.move_right()
                self.ball.update()
                if self.ball.x >= self.gate_right.x - 20:
                    self.play_done = True
                    continued_right = False

            print("left: {}, right {}".format(force_left, force_right))

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.play_done = True
                    send_trigger(event_game_stop)
                    pygame.quit()
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if controls.rect.collidepoint(event.pos):
                        controls.active = True
                        controls2.active = False
                        # controls.getUserInput(event)
                        controls2.save_user_input(user_text2, THRU)
                    elif controls2.rect.collidepoint(event.pos):
                        controls2.active = True
                        controls.active = False
                        # controls2.getUserInput(event)
                        controls.save_user_input(user_text, THLU)

                if event.type == pygame.KEYDOWN:
                    if controls.active == True:
                        if event.key == pygame.K_BACKSPACE:
                            user_text = user_text[:-1]
                        else:
                            try:
                                if unicodedata.digit(event.unicode) >= 0 and unicodedata.digit(event.unicode) <= 9:
                                    user_text += event.unicode
                                    if len(user_text) > 5:
                                        user_text = user_text[:-1]
                            except:
                                continue

                        if event.key == pygame.K_KP_ENTER:
                            controls.save_user_input(user_text, THLU)

                    elif controls2.active == True:
                        if event.key == pygame.K_BACKSPACE:
                            user_text2 = user_text2[:-1]
                        else:
                            try:
                                if unicodedata.digit(event.unicode) >= 0 and unicodedata.digit(event.unicode) <= 9:
                                    user_text2 += event.unicode
                                    if len(user_text2) > 5:
                                        user_text2 = user_text2[:-1]
                            except:
                                continue
                        if event.key == pygame.K_KP_ENTER:
                            controls2.save_user_input(user_text2, THRU)

            controls.draw_new_text(user_text, 100)
            controls2.draw_new_text(user_text2, 100)

            keys = pygame.key.get_pressed()
            if keys[pygame.K_q]:
                send_trigger(event_game_stop)
                pygame.quit()

            #sample, timestamp = inlet.pull_sample()
            #time.sleep(0.01)
            #print(sample[0], timestamp)

            if arrow_key_pressed:
                text = FONT.render(f"Arrow key pressed: {arrow_key_pressed}", True, (0, 0, 0))
                self.screen.blit(text, (10, 10))

            self.screen.blit(self.ball.image, (self.ball.x, self.ball.y))
            self.screen.blit(text, text_rect)
            pygame.display.flip()

    def congrats(self):
        background = pygame.image.load("assets/congrats.png")
        background = pygame.transform.scale(background, (WIDTH, HEIGHT))
        congrats_text = FONT.render('Congrats!', True, WHITE)
        text_rect = congrats_text.get_rect()
        text_rect.center = (X + 30, X - 250)
        screen.blit(background, (0, 0))
        self.screen.blit(congrats_text, text_rect)
        pygame.display.flip()


class Controls:
    def __init__(self, rectangular: pygame.Rect):
        self.activate = False
        self.user_text = ''
        self.rect = rectangular
        # self.rect2 = pygame.Rect(200, 200, WIDTH, 40)
        self.active = False

    def activateControls(self):
        user_text = ''
        for event in pygame.event.get():
            if event.type == pygame.MOUSEBUTTONDOWN:
                if self.input_rect.collidepoint(event.pos):
                    self.activate = True
                else:
                    self.activate = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_BACKSPACE:
                    user_text = user_text[:-1]
                else:
                    user_text += event.unicode
        self.user_text = user_text

    def show(self):
        input_rect = pygame.Rect(200, 200, 140, 32)
        text_surface = FONT.render(self.user_text, True, (255, 255, 255))
        screen.blit(text_surface, (input_rect.x + 5, input_rect.y + 5))
        input_rect.w = max(100, text_surface.get_width() + 10)
        pygame.display.flip()

    def draw(self, color, text):
        # color_active = pygame.Color('lightskyblue3')
        text_surface = FONT.render(text, True, (0, 255, 0))
        pygame.draw.rect(screen, color, self.rect)
        screen.blit(text_surface, (self.rect.x + 5, self.rect.y + 5))

    def draw_new_text(self, text, additional_space):
        text_surface = FONT.render(text, True, (0, 255, 0))
        screen.blit(text_surface, (self.rect.x + additional_space, self.rect.y + 5))
        # text_rect = self.text.get_rect(center=self.rect.center)
        # screen.blit(self.user_text, self.rect)

    def save_user_input(self, text, threshold):
        self.user_text = text
        threshold = text
        print(threshold)

    def getUserInput(self, event):

        if event.type == pygame.KEYDOWN:
            print("uite")
            if self.active == True:
                print("uite")
                if event.key == pygame.K_BACKSPACE:
                    self.user_text = self.user_text[:-1]
                else:
                    try:
                        if unicodedata.digit(event.unicode) >= 0 and unicodedata.digit(event.unicode) <= 9:
                            self.user_text += event.unicode
                            if len(self.user_text) > 3:
                                self.user_text = self.user_text[:-1]
                    finally:
                        pass

        self.draw_new_text(self.user_text, 100)


if __name__ == "__main__":
    keyboard = Controller()

    # pygame.Surface = PickleableSurface
    # pygame.surface.Surface = PickleableSurface
    # surf = pygame.Surface((WIDTH,HEIGHT), pygame.SRCALPHA|pygame.HWSURFACE)
    # screen = pygame.display.set_mode((WIDTH, HEIGHT))
    # dump = dumps(surf)
    # loaded = loads(dump)

    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption('Lexi\'s Football Game!!')

    start_button = Button(X - 50, Y, 175, 90, "Start")
    game_state = GameState(screen, start_button, keyboard)

    game_state.intro()
    FILE.close()

# old code for processing the lsl streams in the game-lsl.py
