import os

import pygame
import sys
import multiprocessing
from pygame.locals import *
from pynput.keyboard import Controller
from config_game import ConfigGame
import multiprocessing
# from pickable import PickleableSurface
# from pickle import loads,dumps
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
from datetime import datetime
import warnings
import matplotlib.pyplot as plt
from datetime import date

# from mioconn import mio_connect

pygame.init()

# Constants
emg_ch = 7  # 34:APL-R, 35:APL-L, 36:ED-R, 37:ED-L, 38:FD-R, 39:FD-L
emg_ch_right = 3
emg_ch_left = 4

fs = 200
win_len = 5  # can be changed
filt_low = 20
filt_high = 40
filt_order = 4

MAC_WIDTH = 1280
MAC_HEIGHT = 1000
WIDTH, HEIGHT = MAC_WIDTH, MAC_HEIGHT
FONT = pygame.font.Font('freesansbold.ttf', 32)
FONT_THRESHOLD = pygame.font.Font('freesansbold.ttf', 14)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
X = WIDTH / 2 - 30
Y = HEIGHT * 3 / 4

BALL_IMAGE = pygame.image.load("assets/ball.png")
BALL_RED_IMAGE = pygame.image.load("assets/ball_red.png")
GATE_R_IMAGE = pygame.image.load("assets/gate_r.png")
GATE_L_IMAGE = pygame.image.load("assets/gate_l.png")
SPEED = 10  # can be changed

# defaults threshholds
global THLL, THLL, THRU, THRL
THLU = ConfigGame.THLU
THLL = ConfigGame.THLL
THRU = ConfigGame.THRU
THRL = ConfigGame.THRL
MAX_LEFT = ConfigGame.MAX_LEFT
MAX_RIGHT = ConfigGame.MAX_RIGHT

force_upper_limit = False

event_game_start: list = [41]
event_game_stop: list = [42]
event_move_left: list = [1]
event_move_right: list = [2]

info_markers = StreamInfo(name='Event Markers', type='Markers', channel_count=1, channel_format='float32', source_id='')
outlet_markers = StreamOutlet(info_markers)

streams = resolve_stream('type', 'Markers')
inlet = StreamInlet(streams[0])

FILE = open('motions.txt', 'a')
CONFIG_FILE = open('config_game.py', 'a')
#today = date.today()


# todo 1 steam for gyro

def start_lsl_stream(name):
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

    streams = resolve_stream('name', name)
    # changed from old code which gad as arguments type and 'type'
    '''
    if len(streams) > 1:
        warnings.warn('Number of EEG streams is > 0, picking the first one.')
    lsl_inlet = StreamInlet(streams[0])
    lsl_inlet.pull_sample()  # need to pull first sample to get buffer started for some reason
    print("Stream started.")
    '''
    inlet1 = StreamInlet(streams[0])

    return inlet1


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

    pull_at_once = 10000 // 5
    samps_pulled = 10000 // 5
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
    if replace:
        data_lsl = data_lsl[:2000]
    elif data_lsl is None:
        data_lsl = new_data
    else:
        data_lsl = np.vstack([data_lsl, new_data])
    return data_lsl


def send_trigger(trigger):
    outlet_markers.push_sample(trigger)
    if ConfigGame.ACTIVATE_DATA_STORAGE:
        #current_datetime = datetime.now().strftime("%Y-%m-%d %H-")
        FILE.write("{} ---- {}".format(trigger, datetime.datetime.now()))
        FILE.write('\n')


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

    def back_to_default_position(self):
        self.x = WIDTH / 2 - 30
        self.y = HEIGHT * 3 / 4


class GateRight:
    def __init__(self,x):
        self.width = self.height = HEIGHT / 5
        self.x = x
        self.y = HEIGHT * 3 / 4 - self.height / 2
        self.image = pygame.transform.scale(GATE_R_IMAGE, (self.width, self.height))

    def draw(self):
        screen.blit(self.image, (self.x, self.y))


class GateLeft:
    def __init__(self, x):
        self.width = self.height = HEIGHT / 5
        self.x = x
        self.y = HEIGHT * 3 / 4 - self.height / 2
        self.image = pygame.transform.scale(GATE_L_IMAGE, (self.width, self.height))

    def draw(self):
        screen.blit(self.image, (self.x, self.y))


class Button:
    def __init__(self, x, y, width, height, text):
        self.rect = pygame.Rect(x, y, width, height)
        self.color = RED
        self.text = FONT.render(text, True, WHITE)
        self.clicked = False

    def draw(self, screen):
        pygame.draw.rect(screen, self.color, self.rect)
        text_rect = self.text.get_rect(center=self.rect.center)
        screen.blit(self.text, text_rect)


class Bar:
    def __init__(self, image, name, x, y, width, height):
        self.image = image
        self.name = name
        self.width = width
        self.height = height
        self.x = x
        self.y = y
        self.rect = pygame.Rect(x, y, width, height)
        self.color = (255, 255, 255)

    def draw(self):
        '''if level == 1:
            if direction == 'left':
                self.rect = pygame.Rect(self.x + 250, self.y, self.width, self.height)
            if direction == 'right':
                self.rect = pygame.Rect(self.x - 250, self.y, self.width, self.height)
        elif level == 2:
            if direction == 'left':
                self.rect = pygame.Rect(self.x + 150, self.y, self.width, self.height)
            if direction == 'right':
                self.rect = pygame.Rect(self.x - 150, self.y, self.width, self.height)
        elif level == 3:
            if direction == 'left':
                self.rect = pygame.Rect(self.x + 50, self.y, self.width, self.height)
            if direction == 'right':
                self.rect = pygame.Rect(self.x - 50, self.y, self.width, self.height)
        '''
        pygame.draw.rect(screen, self.color, self.rect)

    def clear(self):
        pygame.draw.rect(screen, self.color,pygame.Rect(0,0,0,0))
    def update_x(self,x):
        self.x = x

    def draw_threshold_bar(self, is_threshold_in_range, force):
        global THLU, THLL, THRU, THRL, MAX_LEFT, MAX_RIGHT
        # new solution for the bar threshold
        height_new = 0
        if self.name == 'left':
            MAX_LEFT = int(THLL) + int(THLU)
            height_new = min(self.height * force / int(MAX_LEFT), self.height)
            percentage_lower = 100 * int(THLL) / (int(MAX_LEFT))
            percentage_upper = 100 * int(THLU) / (int(MAX_LEFT))

        elif self.name == 'right':
            MAX_RIGHT = int(THRL) + int(THRU)
            height_new = min(self.height * force / int(MAX_RIGHT), self.height)
            percentage_lower = 100 * int(THRL) / (int(MAX_RIGHT))
            percentage_upper = 100 * int(THRU) / (int(MAX_RIGHT))

        y_new = self.y + self.height - height_new
        threshold_bar = pygame.Rect(self.x, y_new, self.width, height_new)

        if is_threshold_in_range:
            color = GREEN
        else:
            color = RED

        pygame.draw.rect(screen, self.color, self.rect)
        pygame.draw.rect(screen, color, threshold_bar)
        self.draw_threshold_line(percentage_upper, True)
        self.draw_threshold_line(percentage_lower)

    def draw_threshold_line(self, percentage, upper=False):
        y_line = self.height - self.height * percentage / 100
        pygame.draw.line(screen, (0, 0, 0), [self.x, y_line + self.y], [self.x + self.width, y_line + self.y], 2)

        if self.name == 'left':
            if upper:
                text = FONT_THRESHOLD.render(str(THLU), True, WHITE)
                text_rect = text.get_rect()
                text_rect.center = (self.x - 15, y_line + self.y)
                screen.blit(text, text_rect)
            else:
                text = FONT_THRESHOLD.render(str(THLL), True, WHITE)
                text_rect = text.get_rect()
                text_rect.center = (self.x - 15, y_line + self.y)
                screen.blit(text, text_rect)

            text = FONT_THRESHOLD.render(str(MAX_LEFT), True, WHITE)
            text_rect = text.get_rect()
            text_rect.center = (self.x - 15, self.y)
            screen.blit(text, text_rect)


        elif self.name == 'right':
            if upper:
                text = FONT_THRESHOLD.render(str(THRU), True, WHITE)
                text_rect = text.get_rect()
                text_rect.center = (self.x - 15, y_line + self.y)
                screen.blit(text, text_rect)
            else:
                text = FONT_THRESHOLD.render(str(THRL), True, WHITE)
                text_rect = text.get_rect()
                text_rect.center = (self.x - 15, y_line + self.y)
                screen.blit(text, text_rect)

            text = FONT_THRESHOLD.render(str(MAX_RIGHT), True, WHITE)
            text_rect = text.get_rect()
            text_rect.center = (self.x - 15, self.y)
            screen.blit(text, text_rect)


'''
    def draw_threshold_line_number(self, threshold, upper_line):
        if upper_line:
            y_line = self.height * 33.33 / 100
        else:
            y_line = self.height * 66.66 / 100
            if threshold == 'THLL':
                number = THLL
                
        text = FONT.render(number, True, WHITE)
        text_rect = text.get_rect()
        text_rect.center = (self.x - 10, y_line + self.y)
        self.screen.blit(text, text_rect)
'''


class GameState:
    def __init__(self, screen, keyboard):
        self.screen = screen

        self.ball = Ball()
        self.gate_left = None
        self.gate_right = None
        self.bar_left = None
        self.bar_right = None
        self.intro_done = False
        self.play_done = False
        self.start_button = Button(X - 275, Y, 200, 90, "Start Game")
        self.training_button = Button(X - 50, Y, 175, 90, "Train")
        self.yes_no_button = Button(X + 150, Y, 175, 90, "Yes/No")
        self.back_button = Button(X + 550, Y + 155, 75, 50, "Back")
        self.keyboard = keyboard
        self.myo_data = []
        self.type = ''

        self.a = 0
        self.b = 0

    def intro(self, back=False):
        if back:
            pygame.display.flip()
            self.start_button.clicked = False
            self.training_button.clicked = False
            self.yes_no_button.clicked = False

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
        self.training_button.draw(self.screen)
        self.yes_no_button.draw(self.screen)
        # self.screen.blit(start_img,start_img)

        while not (self.start_button.clicked or self.training_button.clicked or self.yes_no_button.clicked):
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    send_trigger(event_game_stop)
                    outlet_markers.__del__()
                    today = datetime.now().strftime("%Y-%m-%d")
                    path = "artifacts/" + today
                    if not os.path.exists(path):
                        os.mkdir(path)
                    else:
                        os.mkdir(path + "/" + today + "_" + self.type)
                    print(path + "_" + self.type)
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.start_button.rect.collidepoint(event.pos):
                        self.start_button.clicked = True
                        self.intro_done = True
                    if self.training_button.rect.collidepoint(event.pos):
                        self.training_button.clicked = True
                        self.intro_done = True
                    if self.yes_no_button.rect.collidepoint(event.pos):
                        self.yes_no_button.clicked = True
                        self.intro_done = True

            pygame.display.flip()

        if self.start_button.clicked:
            self.start_play()
        if self.training_button.clicked:
            # self.start_play(training=True)
            self.training = Training(self.screen, self)
            self.training.intro_training_function(False)
        if self.yes_no_button.clicked:
            self.start_play(yes_no=True)

    def get_emg(self, lsl_inlet, data_lsl, emg, win_len, timeout):

        if timeout < time.time():
            timeout = time.time() + 20
            # print(lsl_inlet.info().name(), emg)
            data_lsl = pull_data(lsl_inlet=lsl_inlet, data_lsl=data_lsl, replace=True)
            print("OK")
        else:
            data_lsl = pull_data(lsl_inlet=lsl_inlet, data_lsl=data_lsl, replace=False)

        # emg = data_lsl[:, emg_ch] # select emg channel
        avg = 0
        for row in data_lsl:
            avg = 0
            for i in row:
                avg += abs(i)
            emg.append(avg / 8)
        # print('emg',len(emg))
        # print('data_lsl',len(data_lsl))

        # print(lsl_inlet.info().name(), data_lsl)

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
            chunk_size = 20  # start: 20 # change to 4 eventually later - 200HZ sampling rate # can be changed
            emg_chunk = np.mean(np.power(emg_env[-chunk_size:-1], 2))
            # offset = 100
            # emg_chunk = emg_chunk - offset
            # if emg_chunk < 0: emg_chunk = 0
            # print('emg_chunk',emg_chunk)

        return emg_chunk, data_lsl, timeout

    # todo - check the connection - why is it not connecting properly
    def start_play(self, training_mode=False, yes_no=False):

        self.back_button.clicked = False

        # maybe create a new class for this

        inlet_emg1 = None
        inlet_emg2 = None
        # !!! change to the time emg!!!!
        send_trigger(event_game_start)

        inlet1 = start_lsl_stream('EMG_Stream_Left')
        inlet2 = start_lsl_stream('EMG_Stream_Right')
        # if you need the info from gyro, change the following names accordingly to the names of the streams in mio_connect script
        # imu_inlet1 = start_lsl_stream('IMU_Stream2')
        # imu_inlet2 = start_lsl_stream('IMU_Stream2')

        data_lsl_right = None
        data_lsl_left = None
        self.b, self.a = butter_bandpass(filt_low, filt_high, fs, filt_order)

        controls = Controls(pygame.Rect(0, 80, WIDTH / 2, 40))
        controls2 = Controls(pygame.Rect(WIDTH / 2, 80, WIDTH, 40))
        controls3 = Controls(pygame.Rect(0, 40, WIDTH / 2, 40))
        controls4 = Controls(pygame.Rect(WIDTH / 2, 40, WIDTH, 40))

        user_text = str(THLU)
        user_text2 = str(THRU)
        user_text3 = str(THLL)
        user_text4 = str(THRL)

        timeout1 = time.time() + 20
        timeout2 = time.time() + 20

        while not self.play_done:
            background = pygame.image.load("assets/football.jpeg")
            background = pygame.transform.scale(background, (WIDTH, HEIGHT))
            background.get_rect().center = (WIDTH // 2, HEIGHT // 2)
            self.screen.blit(background, (0, 0))
            self.back_button.draw(self.screen)

            arrow_key_pressed = None

            if yes_no:
                self.type = 'Yes_No'
                text = FONT.render('Yes/No Mode', True, WHITE)
                text_rect = text.get_rect()
                text_rect.center = (X + 30, Y - 250)
                self.screen.blit(text, text_rect)

                self.gate_left = GateLeft(HEIGHT / 10)
                self.gate_right = GateRight(WIDTH - 60 - HEIGHT / 10)
                self.bar_left = Bar(screen, 'left', self.gate_left.x + 50, 140, 70, 420)
                self.bar_right = Bar(screen, 'right', self.gate_right.x + 30, 140, 70, 420)

                text = FONT.render('Yes', True, GREEN)
                text_rect = text.get_rect()
                text_rect.center = (self.gate_left.x + 60, self.gate_left.y + 250)
                self.screen.blit(text, text_rect)
                text = FONT.render('No', True, RED)
                text_rect = text.get_rect()
                text_rect.center = (self.gate_right.x + 60, self.gate_right.y + 250)
                self.screen.blit(text, text_rect)

                self.gate_left.draw()
                self.gate_right.draw()
                self.bar_left.draw()
                self.bar_right.draw()
                controls.draw((0, 0, 0), 'Th LU:')
                controls2.draw((0, 0, 0), 'Th RU:')
                controls3.draw((0, 0, 0), 'Th LL:')
                controls4.draw((0, 0, 0), 'Th RL:')

            elif training_mode:
                self.type = 'Training'
                text = FONT.render('Training Mode', True, WHITE)
                text_rect = text.get_rect()
                text_rect.center = (X + 30, Y - 250)
                self.screen.blit(text, text_rect)

                if self.training.left_1.clicked:
                    self.gate_left = GateLeft(HEIGHT / 10 + 250)
                    self.bar_left = Bar(screen, 'left', self.gate_left.x + 50, 140, 70, 420)
                    self.gate_left.draw()
                    self.bar_left.draw()
                    self.gate_right = None
                    self.bar_right = None
                    controls.draw((0, 0, 0), 'Th LU:')
                    controls3.draw((0, 0, 0), 'Th LL:')
                elif self.training.left_2.clicked:
                    self.gate_left = GateLeft(HEIGHT / 10 + 150)
                    self.bar_left = Bar(screen, 'left', self.gate_left.x + 50, 140, 70, 420)
                    self.gate_left.draw()
                    self.bar_left.draw()
                    self.gate_right = None
                    self.bar_right = None
                    controls.draw((0, 0, 0), 'Th LU:')
                    controls3.draw((0, 0, 0), 'Th LL:')
                elif self.training.left_3.clicked:
                    self.gate_left = GateLeft(HEIGHT / 10 + 50)
                    self.bar_left = Bar(screen, 'left', self.gate_left.x + 50, 140, 70, 420)
                    self.gate_left.draw()
                    self.bar_left.draw()
                    self.gate_right = None
                    self.bar_right = None
                    controls.draw((0, 0, 0), 'Th LU:')
                    controls3.draw((0, 0, 0), 'Th LL:')
                elif self.training.right_1.clicked:
                    self.gate_right = GateRight(WIDTH - 60 - HEIGHT / 10 - 50)
                    self.bar_right = Bar(screen, 'right', self.gate_right.x + 30, 140, 70, 420)
                    self.gate_right.draw()
                    self.bar_right.draw()
                    self.gate_left = None
                    self.bar_left = None
                    controls2.draw((0, 0, 0), 'Th RU:')
                    controls4.draw((0, 0, 0), 'Th RL:')
                elif self.training.right_2.clicked:
                    self.gate_right = GateRight(WIDTH - 60 - HEIGHT / 10 - 150)
                    self.bar_right = Bar(screen, 'right', self.gate_right.x + 30, 140, 70, 420)
                    self.gate_right.draw()
                    self.bar_right.draw()
                    self.gate_left = None
                    self.bar_left = None
                    controls2.draw((0, 0, 0), 'Th RU:')
                    controls4.draw((0, 0, 0), 'Th RL:')
                elif self.training.right_3.clicked:
                    self.gate_right = GateRight(WIDTH - 60 - HEIGHT / 10 - 250)
                    self.bar_right = Bar(screen, 'right', self.gate_right.x + 30, 140, 70, 420)
                    self.gate_right.draw()
                    self.bar_right.draw()
                    self.gate_left = None
                    self.bar_left = None
                    controls2.draw((0, 0, 0), 'Th RU:')
                    controls4.draw((0, 0, 0), 'Th RL:')

            else:
                self.type = 'Game'
                text = FONT.render('Game Mode', True, WHITE)
                text_rect = text.get_rect()
                text_rect.center = (X + 30, Y - 250)
                self.screen.blit(text, text_rect)
                self.gate_left = GateLeft(HEIGHT / 10)
                self.gate_right = GateRight(WIDTH - 60 - HEIGHT / 10)
                self.bar_left = Bar(screen, 'left', self.gate_left.x + 50, 140, 70, 420)
                self.bar_right = Bar(screen, 'right', self.gate_right.x + 30, 140, 70, 420)
                self.gate_left.draw()
                self.gate_right.draw()
                self.bar_left.draw()
                self.bar_right.draw()

                controls.draw((0, 0, 0), 'Th LU:')
                controls2.draw((0, 0, 0), 'Th RU:')
                controls3.draw((0, 0, 0), 'Th LL:')
                controls4.draw((0, 0, 0), 'Th RL:')




            # ======================================================================
            force_right = 0
            force_left = 0
            emg1 = []
            emg2 = []

            force_right, data_lsl_right, timeout2 = self.get_emg(lsl_inlet=inlet2, data_lsl=data_lsl_right, emg=emg2,
                                                                 win_len=win_len, timeout=timeout2)

            force_left, data_lsl_left, timeout1 = self.get_emg(lsl_inlet=inlet1, data_lsl=data_lsl_left, emg=emg1,
                                                               win_len=win_len, timeout=timeout1)

            # old code with imu data
            imu1 = []
            imu2 = []

            # imu1 = imu_inlet1.pull_chunk(max_samples=10)
            # imu2 = imu_inlet2.pull_chunk(max_samples=10)

            if force_right > int(THRU)  and self.bar_right is not None:
                force_upper_limit = True
                self.ball.change_to_red()
                self.bar_right.draw_threshold_bar(False, force_right)

            if force_right < int(THRL) and self.bar_right is not None:
                self.ball.change_to_normal()
                self.bar_right.draw_threshold_bar(False, force_right)

            if force_left > int(THLU) and self.bar_left is not None:
                force_upper_limit = True
                self.ball.change_to_red()
                self.bar_left.draw_threshold_bar(False, force_left)

            if force_left < int(THLL) and self.bar_left is not None:
                self.ball.change_to_normal()
                self.bar_left.draw_threshold_bar(False, force_left)

            self.ball.change_to_normal()

            if force_left > int(THLL) and force_left < int(THLU) and force_right < int(THRL) and self.bar_left is not None:
                print("stanga")
                send_trigger(event_move_left)
                self.bar_left.draw_threshold_bar(True, force_left)
                self.ball.move_left()

                # decomment when you wanna make the game stop
                # if self.ball.x <= self.gate_left.x + 20:
                # self.play_done = True

            if force_right > int(THRL) and force_right < int(THRU) and force_left < int(THLL) and self.bar_right is not None:
                print("dreapta")
                send_trigger(event_move_right)
                self.bar_right.draw_threshold_bar(True, force_right)
                self.ball.move_right()
                # if self.ball.x >= self.gate_right.x - 20:
                # self.play_done = True

            if force_right > int(THRL) and force_right < int(THRU) and force_left < int(THLU) and force_left > int(THLL) and self.bar_left is not None and self.bar_right is not None:
                self.bar_left.draw_threshold_bar(True, force_left)
                self.bar_right.draw_threshold_bar(True, force_right)
                self.ball.stop()
                self.ball.change_to_red()


            print("left: {} ({}/{}/{}),  right {} ({}/{},{}), ".format(int(force_left), THLL, THLU, MAX_LEFT,
                                                                       int(force_right), THRL,
                                                                       THRU, MAX_RIGHT))

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.play_done = True
                    send_trigger(event_game_stop)
                    outlet_markers.__del__()


                    today = datetime.now().strftime("%Y-%m-%d")
                    path = "artifacts/" + today
                    if not os.path.exists(path):
                        os.mkdir(path)
                    else:
                        os.mkdir(path + "/" + today + "_" + self.type)
                    print(path + "_" + self.type)



                    pygame.quit()
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if controls.rect.collidepoint(event.pos):
                        controls.active = True
                        controls2.active = False
                        controls3.active = False
                        controls4.active = False
                        controls2.save_user_input(user_text2, 'THRU')
                        controls3.save_user_input(user_text3, 'THLL')
                        controls4.save_user_input(user_text4, 'THRL')
                    elif controls2.rect.collidepoint(event.pos):
                        controls2.active = True
                        controls.active = False
                        controls3.active = False
                        controls4.active = False
                        controls.save_user_input(user_text, 'THLU')
                        controls3.save_user_input(user_text3, 'THLL')
                        controls4.save_user_input(user_text4, 'THRL')
                    elif controls3.rect.collidepoint(event.pos):
                        controls3.active = True
                        controls.active = False
                        controls2.active = False
                        controls4.active = False
                        controls.save_user_input(user_text, 'THLU')
                        controls2.save_user_input(user_text2, 'THRU')
                        controls4.save_user_input(user_text4, 'THRL')
                    elif controls4.rect.collidepoint(event.pos):
                        controls4.active = True
                        controls.active = False
                        controls2.active = False
                        controls3.active = False
                        controls.save_user_input(user_text, 'THLU')
                        controls2.save_user_input(user_text2, 'THRU')
                        controls3.save_user_input(user_text3, 'THLL')

                    elif self.back_button.rect.collidepoint(event.pos):
                        self.back_button.clicked = True

                if event.type == pygame.KEYDOWN:
                    if controls.active == True:

                        if event.key == pygame.K_RETURN:
                            print(user_text)
                            controls.save_user_input(user_text, 'THLU')

                        elif event.key == pygame.K_BACKSPACE:
                            user_text = user_text[:-1]
                        else:
                            try:
                                if unicodedata.digit(event.unicode) >= 0 and unicodedata.digit(event.unicode) <= 9:
                                    user_text += event.unicode
                                    if len(user_text) > 5:
                                        user_text = user_text[:-1]
                            except:
                                continue

                    elif controls2.active == True:
                        if event.key == pygame.K_RETURN:
                            controls2.save_user_input(user_text2, 'THRU')

                        elif event.key == pygame.K_BACKSPACE:
                            user_text2 = user_text2[:-1]
                        else:
                            try:
                                if unicodedata.digit(event.unicode) >= 0 and unicodedata.digit(event.unicode) <= 9:
                                    user_text2 += event.unicode
                                    if len(user_text2) > 5:
                                        user_text2 = user_text2[:-1]
                            except:
                                continue


                    elif controls3.active == True:
                        if event.key == pygame.K_RETURN:
                            controls3.save_user_input(user_text3, 'THLL')

                        elif event.key == pygame.K_BACKSPACE:
                            user_text3 = user_text3[:-1]
                        else:
                            try:
                                if unicodedata.digit(event.unicode) >= 0 and unicodedata.digit(event.unicode) <= 9:
                                    user_text3 += event.unicode
                                    if len(user_text3) > 5:
                                        user_text3 = user_text3[:-1]
                            except:
                                continue


                    elif controls4.active == True:
                        if event.key == pygame.K_RETURN:
                            controls4.save_user_input(user_text4, 'THRL')
                        elif event.key == pygame.K_BACKSPACE:
                            user_text4 = user_text4[:-1]
                        else:
                            try:
                                if unicodedata.digit(event.unicode) >= 0 and unicodedata.digit(event.unicode) <= 9:
                                    user_text4 += event.unicode
                                    if len(user_text4) > 5:
                                        user_text4 = user_text4[:-1]
                            except:
                                continue



            if self.gate_left is not None:
                controls.draw_new_text(user_text, 115)
                controls3.draw_new_text(user_text3, 115)
            if self.gate_right is not None:
                controls2.draw_new_text(user_text2, 115)
                controls4.draw_new_text(user_text4, 115)

            keys = pygame.key.get_pressed()
            if keys[pygame.K_q]:
                send_trigger(event_game_stop)
                outlet_markers.__del__()
                today = datetime.now().strftime("%Y-%m-%d")
                path = "artifacts/" + today
                if not os.path.exists(path):
                    os.mkdir(path)
                else:
                    os.mkdir(path + "/" + today + "_" + self.type)
                print(path + "_" + self.type)
                pygame.quit()

            sample, timestamp = inlet.pull_chunk(max_samples=1)
            # print(sample, timestamp)

            if arrow_key_pressed:
                text = FONT.render(f"Arrow key pressed: {arrow_key_pressed}", True, (0, 0, 0))
                self.screen.blit(text, (10, 10))

            self.screen.blit(self.ball.image, (self.ball.x, self.ball.y))
            self.screen.blit(text, text_rect)
            pygame.time.Clock().tick(30)

            if self.back_button.clicked:
                self.ball.back_to_default_position()
                self.intro(back=True)
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
        global THRL, THRU, THLL, THLU, MAX_RIGHT, MAX_LEFT
        self.user_text = text
        if threshold == 'THLU':
            THLU = text
        elif threshold == 'THRU':
            THRU = text
        elif threshold == 'THLL':
            THLL = text
        elif threshold == 'THRL':
            THRL = text
        elif threshold == 'MAX_RIGHT':
            MAX_RIGHT = text
        elif threshold == 'MAX_LEFT':
            MAX_LEFT = text

    def getUserInput(self, event):

        if event.type == pygame.KEYDOWN:
            if self.active == True:
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


class Training:
    def __init__(self, screen, game_state: GameState):
        self.game_state = game_state
        self.screen = screen
        self.left_1 = Button(X - 275, Y - 150, 200, 90, "Left: Level 1")
        self.left_2 = Button(X - 275, Y - 50, 200, 90, "Left: Level 2")
        self.left_3 = Button(X - 275, Y + 50, 200, 90, "Left: Level 3 ")
        self.right_1 = Button(X + 150, Y - 150, 220, 90, "Right: Level 1")
        self.right_2 = Button(X + 150, Y - 50, 220, 90, "Right: Level 2")
        self.right_3 = Button(X + 150, Y + 50, 220, 90, "Right: Level 3")
        self.intro_training = False

    def intro_training_function(self, back=False):
        if back:
            pygame.display.flip()
            self.left_1.clicked = False
            self.left_2.clicked = False
            self.left_3.clicked = False
            self.right_1.clicked = False
            self.right_2.clicked = False
            self.right_3.clicked = False

        intro_image = pygame.image.load("assets/pag1.png")
        intro_rect = intro_image.get_rect()
        intro_rect.center = (WIDTH // 2, HEIGHT // 2)

        text = FONT.render('Training Mode', True, WHITE)
        text_rect = text.get_rect()
        text_rect.center = (X + 30, Y - 250)

        self.screen.blit(intro_image, intro_rect)
        self.screen.blit(text, text_rect)
        self.left_1.draw(self.screen)
        self.left_2.draw(self.screen)
        self.left_3.draw(self.screen)
        self.right_1.draw(self.screen)
        self.right_2.draw(self.screen)
        self.right_3.draw(self.screen)

        while not (
                self.left_1.clicked or self.left_2.clicked or self.left_3.clicked or self.right_1.clicked or self.right_2.clicked or self.right_3.clicked):
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    send_trigger(event_game_stop)
                    outlet_markers.__del__()
                    today = datetime.now().strftime("%Y-%m-%d")
                    path = "artifacts/" + today
                    if not os.path.exists(path):
                        os.mkdir(path)
                    else:
                        os.mkdir(path + "/" + today + "_" + self.type)
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.left_1.rect.collidepoint(event.pos):
                        self.left_1.clicked = True
                        self.intro_training = True
                    if self.left_2.rect.collidepoint(event.pos):
                        self.left_2.clicked = True
                        self.intro_training = True
                    if self.left_3.rect.collidepoint(event.pos):
                        self.left_3.clicked = True
                        self.intro_training = True
                    if self.right_1.rect.collidepoint(event.pos):
                        self.right_1.clicked = True
                        self.intro_training = True
                    if self.right_2.rect.collidepoint(event.pos):
                        self.right_2.clicked = True
                        self.intro_training = True
                    if self.right_3.rect.collidepoint(event.pos):
                        self.right_3.clicked = True
                        self.intro_training = True

            pygame.display.flip()

        self.game_state.start_play(training_mode=True, yes_no=False)


def main():
    global screen
    keyboard = Controller()

    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption('Lexi\'s Football Game!!')

    game_state = GameState(screen, keyboard)

    # mio_connect.main(sys.argv[1:])

    game_state.intro()
    FILE.close()


if __name__ == "__main__":
    keyboard = Controller()

    pygame.init()
    # decomment the folowing line only when you are running the mio_connect and game scripts separately
    # screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption('Lexi\'s Football Game!!')

    game_state = GameState(screen, keyboard)
    game_state.intro()
    FILE.close()

# old code for processing the lsl streams in the game-lsl.py
