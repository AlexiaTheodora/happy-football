from multiprocessing import Process, Event, freeze_support
import os
from pynput.keyboard import Controller
import shutil
import numpy as np
from pylsl import StreamInlet, resolve_stream
import scipy
from scipy.signal import butter, lfilter
import unicodedata
from datetime import datetime
import random
import liesl
import configparser
import getopt
import sys
import pygame
from pylsl import StreamInfo, StreamOutlet
import struct
import re
import time
from serial.tools.list_ports import comports
import serial
import math
from pythonosc import udp_client
import multiprocessing

w, h = 800, 600

last_vals = None
last_vals2 = None


pygame.init()
pygame.mixer.init()

# Constants
emg_ch = 7  # 34:APL-R, 35:APL-L, 36:ED-R, 37:ED-L, 38:FD-R, 39:FD-L
emg_ch_right = 3
emg_ch_left = 4

fs = 200
win_len = 5  # can be changed
filt_low = 20
filt_high = 40
filt_order = 4

SCREEN_INFO = pygame.display.Info()
SCREEN_WIDTH = SCREEN_INFO.current_w
SCREEN_HEIGHT = SCREEN_INFO.current_h

MAC_WIDTH = 1280
MAC_HEIGHT = 800
WIDTH, HEIGHT = MAC_WIDTH, MAC_HEIGHT
FONT = pygame.font.Font('freesansbold.ttf', 32)
FONT_THRESHOLD = pygame.font.Font('freesansbold.ttf', 14)
FONT_YES_NO = pygame.font.Font('freesansbold.ttf', 70)

WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
X = WIDTH / 2 - 30
Y = HEIGHT * 3 / 4

config = configparser.ConfigParser()
config.read('config_game.ini')

translate = configparser.ConfigParser()
translate.read('translate_de.ini')

BALL_IMAGE = pygame.image.load("assets/ball.png")
BALL_RED_IMAGE = pygame.image.load("assets/ball_red.png")
GATE_R_IMAGE = pygame.image.load("assets/gate_r.png")
GATE_L_IMAGE = pygame.image.load("assets/gate_l.png")
SPEED = 10  # can be changed

# defaults threshholds
global THLL, THRL, THLU, THRU
THLL = config.getint('Game', 'thll')
THRL = config.getint('Game', 'thrl')
THLU = config.getint('Game', 'thlu')
THRU = config.getint('Game', 'thru')
MAX_LEFT = config.getint('Game', 'MAX_LEFT')
MAX_RIGHT = config.getint('Game', 'MAX_RIGHT')

force_upper_limit = False

global TOKEN_DIRECTION, TOKEN_YES, sound_right_repetitions, sound_left_repetitions
TOKEN_YES = None
TOKEN_DIRECTION = None
sound_right_repetitions = 0
sound_left_repetitions = 0

event_game_start: list = [41]
event_game_stop: list = [42]
event_move_left: list = [1]
event_move_right: list = [2]

info_markers = StreamInfo(name='EventMarkers', type='Markers', channel_count=1, nominal_srate=200,
                          channel_format='float32', source_id='1')
outlet_markers = StreamOutlet(info_markers)
FILE = None


global screen


class Button_Intro:
    def __init__(self, x, y, width, height, text):
        self.rect = pygame.Rect(x, y, width, height)
        self.color = RED
        self.text = FONT.render(text, True, WHITE)
        self.clicked = False

    def draw(self, screen):
        pygame.draw.rect(screen, self.color, self.rect)
        text_rect = self.text.get_rect(center=self.rect.center)
        screen.blit(self.text, text_rect)

    def starting(self,screen):
        pygame.draw.rect(screen, self.color, self.rect)
        starting_text = FONT.render(translate.get('Translate', 'starting'), True, WHITE)
        text_rect = starting_text.get_rect(center=self.rect.center)
        screen.blit(starting_text, text_rect)

########################################## GAME #######################################
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
    if config.getboolean('Game', 'activate_data_storage'):
        FILE.write("{} ---- {}".format(trigger, datetime.now()))
        FILE.write('\n')


def start_lab_recorder(path, name, uid, lr):
    path += "/" + name + ".xdf"
    stream_args = [{"uid": uid}]
    lr.start_recording(path, stream_args)


def stop_lab_recorder(lr):
    lr.stop_recording()


def generate_folder(type):
    global FILE
    today = datetime.now().strftime("%Y-%m-%d")
    path = "artifacts/" + today
    if not os.path.exists(path):
        os.mkdir(path)
    dir_path = path + "/" + today + "_" + type
    if not os.path.exists(dir_path):
        os.mkdir(dir_path)
    # save the config file
    FILE = open(dir_path + '/records.txt', 'a')
    # destination_directory = directory + datetime.now().strftime("%H:%M")
    # os.mkdir(destination_directory)
    return dir_path


def save_rec_file(filename, destination_directory):
    # shutil.move(filename, os.path.join(destination_directory, filename))
    print(f"Recording saved to {os.path.join(destination_directory, filename)}")


def generate_config(template_path, output_path, **kwargs):
    with open(template_path, "r") as file:
        template_content = file.read()

    for key, value in kwargs.items():
        placeholder = f'{{{key}}}'
        template_content = template_content.replace(placeholder, value)

    with open(output_path, "w") as file:
        file.write(template_content)

class Ball:
    def __init__(self):
        self.width = self.height = HEIGHT / 13
        self.x = WIDTH / 2 - 30
        self.y = HEIGHT * 3 / 4 + 50
        self.dx = 0  # Change in x position (initialize to 0)
        self.move_count = 0
        self.image = pygame.transform.scale(BALL_IMAGE, (self.width, self.height))
        self.score_good = 0
        self.score_bad = 0

    def replace(self):
        global TOKEN_YES, TOKEN_DIRECTION, sound_left_repetitions, sound_right_repetitions
        self.x = WIDTH / 2 - 30
        self.y = HEIGHT * 3 / 4
        TOKEN_DIRECTION = random.randint(0, 1)
        TOKEN_YES = random.randint(0, 1)
        sound_left_repetitions = 0
        sound_right_repetitions = 0

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

    def save_thresolds(self):
        FILE.write(str(datetime.now()))
        FILE.write('\n')
        FILE.write(" THLL ---- {}".format(THLL))
        FILE.write('\n')
        FILE.write(" THLU ---- {}".format(THLU))
        FILE.write('\n')
        FILE.write(" THRL ---- {}".format(THRL))
        FILE.write('\n')
        FILE.write(" THRU ---- {}".format(THRU))
        FILE.write('\n')

    def save_scores(self):
        FILE.write('\n')
        FILE.write('\n')
        FILE.write('\n')
        FILE.write(str(datetime.now()))
        FILE.write('\n')
        FILE.write(" Bad Goal ---- {}".format(self.score_bad))
        FILE.write('\n')
        FILE.write(" Good Goal ---- {}".format(self.score_good))
        FILE.write('\n')
        if self.score_good == 0 and self.score_bad == 0:
            FILE.write(" Percentage Good ---- {}%".format(None))
            FILE.write('\n')
            FILE.write(" Percentage Bad ---- {}%".format(None))
            FILE.write('\n')
        else:
            FILE.write(" Percentage Good ---- {}%".format(self.score_good / (self.score_bad + self.score_good) * 100))
            FILE.write('\n')
            FILE.write(" Percentage Bad ---- {}%".format(self.score_bad / (self.score_bad + self.score_good) * 100))
            FILE.write('\n')


class GateRight:
    def __init__(self, x):
        self.width = self.height = HEIGHT / 5
        self.x = x
        self.y = HEIGHT * 3 / 4 - self.height / 2 + 20
        self.image = pygame.transform.scale(GATE_R_IMAGE, (self.width, self.height))

    def draw(self):
        screen.blit(self.image, (self.x, self.y))


class GateLeft:
    def __init__(self, x):
        self.width = self.height = HEIGHT / 5
        self.x = x
        self.y = HEIGHT * 3 / 4 - self.height / 2 + 20
        self.image = pygame.transform.scale(GATE_L_IMAGE, (self.width, self.height))

    def draw(self):
        screen.blit(self.image, (self.x, self.y))


class Button:
    def __init__(self, x, y, width, height, text):
        self.rect = pygame.Rect(x, y, width, height)
        self.color = RED
        self.text = FONT.render(text, True, WHITE)
        if text == 'Zurueck':
            self.text = pygame.font.Font('freesansbold.ttf', 25).render(text, True, WHITE)
        self.clicked = False

    def draw(self, screen):
        pygame.draw.rect(screen, self.color, self.rect)
        text_rect = self.text.get_rect(center=self.rect.center)
        screen.blit(self.text, text_rect)

    def starting(self,screen):
        pygame.draw.rect(screen, self.color, self.rect)
        starting_text = FONT.render(translate.get('Translate', 'starting'), True, WHITE)
        text_rect = starting_text.get_rect(center=self.rect.center)
        screen.blit(starting_text, text_rect)


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
        pygame.draw.rect(screen, self.color, self.rect)

    def clear(self):
        pygame.draw.rect(screen, self.color, pygame.Rect(0, 0, 0, 0))

    def update_x(self, x):
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
        self.start_button = Button(X - 275, Y, 200, 90, translate.get('Translate', 'start.game'))
        self.training_button = Button(X - 50, Y, 175, 90, translate.get('Translate', 'train'))
        self.yes_no_button = Button(X + 150, Y, 175, 90, translate.get('Translate', 'yes.no'))
        self.back_button = Button(X + 555, Y + 125, 100, 50, translate.get('Translate', 'back'))
        self.keyboard = keyboard
        self.myo_data = []
        self.type = ''
        self.process = liesl.Recorder()
        self.source_directory = None
        self.file_records = None

        self.a = 0
        self.b = 0

    def countdown(self):
        seconds = 5
        end_time = time.time() + seconds
        while seconds:
            remaining_time = int(end_time - time.time())
            text = FONT.render(f'You can start in {str(remaining_time)}', True, WHITE)
            text_rect = text.get_rect()
            text_rect.center = (X + 30, Y - 250)
            pygame.draw.rect(screen, (0, 0, 0), text_rect)
            self.screen.blit(text, text_rect)
            pygame.display.flip()
            if remaining_time <= 0:
                break
            time.sleep(1)
            pygame.draw.rect(screen, (0, 0, 0), text_rect)

    def intro(self, back=False):
        if back:
            pygame.display.flip()
            self.start_button.clicked = False
            self.training_button.clicked = False
            self.yes_no_button.clicked = False

        # Load and display the introductory image
        intro_image = pygame.image.load("assets/pag1.png")
        intro_image = pygame.transform.scale(intro_image, (WIDTH, HEIGHT))
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
                    stop_lab_recorder(self.process)
                    # save_rec_file(outlet_markers.get_info().name(), self.source_directory)
                    outlet_markers.__del__()
                    shutil.copy("config_game.ini", self.source_directory)
                    FILE.close()
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.start_button.rect.collidepoint(event.pos):
                        self.start_button.clicked = True
                        self.intro_done = True
                        self.start_button.starting(self.screen)
                    if self.training_button.rect.collidepoint(event.pos):
                        self.training_button.clicked = True
                        self.intro_done = True
                        self.training_button.starting(self.screen)
                    if self.yes_no_button.rect.collidepoint(event.pos):
                        self.yes_no_button.clicked = True
                        self.intro_done = True
                        self.yes_no_button.starting(self.screen)

            pygame.display.flip()

        if self.start_button.clicked:
            self.source_directory = generate_folder("Game")
            self.start_play()

        if self.training_button.clicked:
            # self.start_play(training=True)
            self.source_directory = generate_folder("Training")
            self.training = Training(self.screen, self)
            self.training.intro_training_function(False)
        if self.yes_no_button.clicked:
            self.source_directory = generate_folder("Yes_No")
            self.start_play(yes_no=True)

    def get_emg(self, lsl_inlet, data_lsl, emg, win_len, timeout):

        if timeout < time.time():
            timeout = time.time() + 20
            # print(lsl_inlet.info().name(), emg)
            data_lsl = pull_data(lsl_inlet=lsl_inlet, data_lsl=data_lsl, replace=True)
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

    def start_play(self, training_mode=False, yes_no=False):
        self.back_button.clicked = False

        countdown_done = False
        send_trigger(event_game_start)

        inlet1 = start_lsl_stream('EMG-Left')
        inlet2 = start_lsl_stream('EMG-Right')
        imu_inlet1 = start_lsl_stream('IMU-Left')
        imu_inlet2 = start_lsl_stream('IMU-Right')
        inlet_markers = start_lsl_stream('EventMarkers')

        start_lab_recorder(self.source_directory, inlet1.info().name(), inlet1.info().uid(), self.process)
        start_lab_recorder(self.source_directory, inlet2.info().name(), inlet2.info().uid(), self.process)
        start_lab_recorder(self.source_directory, imu_inlet1.info().name(), imu_inlet1.info().uid(), self.process)
        start_lab_recorder(self.source_directory, imu_inlet2.info().name(), imu_inlet2.info().uid(), self.process)
        # todo too manz stream info error???
        start_lab_recorder(self.source_directory, inlet_markers.info().name(), inlet_markers.info().uid(), self.process)

        data_lsl_right = None
        data_lsl_left = None
        self.b, self.a = butter_bandpass(filt_low, filt_high, fs, filt_order)

        controls = Controls(pygame.Rect(0, 40, WIDTH / 2, 40))
        controls2 = Controls(pygame.Rect(WIDTH / 2, 40, WIDTH, 40))
        controls3 = Controls(pygame.Rect(0, 80, WIDTH / 2, 40))
        controls4 = Controls(pygame.Rect(WIDTH / 2, 80, WIDTH, 40))

        user_text = str(THLU)
        user_text2 = str(THRU)
        user_text3 = str(THLL)
        user_text4 = str(THRL)

        timeout1 = time.time() + 20
        timeout2 = time.time() + 20

        global TOKEN_YES, TOKEN_DIRECTION, sound_left_repetitions,sound_right_repetitions
        TOKEN_YES = random.randint(0, 1)
        TOKEN_DIRECTION = random.randint(0, 1)

        arrow_left_image = pygame.image.load("assets/blue-left-arrow.png")
        arrow_left_image = pygame.transform.scale(arrow_left_image, (HEIGHT / 10, HEIGHT / 10))

        arrow_right_image = pygame.image.load("assets/blue-right-arrow.png")
        arrow_right_image = pygame.transform.scale(arrow_right_image, (HEIGHT / 10, HEIGHT / 10))

        pygame.mixer.init()
        sound_left = pygame.mixer.Sound("assets/goal_left_justus.wav")
        sound_left.set_volume(0.6)

        sound_right = pygame.mixer.Sound("assets/goal_right_justus.wav")
        sound_right.set_volume(0.6)


        while not self.play_done:

            background = pygame.image.load("assets/football.jpeg")
            background = pygame.transform.scale(background, (WIDTH, HEIGHT))
            background.get_rect().center = (WIDTH // 2, HEIGHT // 2)
            self.screen.blit(background, (0, 0))
            self.back_button.draw(self.screen)

            arrow_key_pressed = None

            if not countdown_done:
                # self.countdown()
                countdown_done = True

            if yes_no:
                self.type = 'Yes_No'
                text = FONT.render(translate.get('Translate', 'yes.no.mode'), True, WHITE)
                text_rect = text.get_rect()
                text_rect.center = (X + 30, Y - 250)
                self.screen.blit(text, text_rect)

                self.gate_left = GateLeft(HEIGHT / 10)
                self.gate_right = GateRight(WIDTH - 60 - HEIGHT / 5)
                self.bar_left = Bar(screen, 'left', self.gate_left.x + 50, 140, HEIGHT / 14, HEIGHT / 3)
                self.bar_right = Bar(screen, 'right', self.gate_right.x + 30, 140, HEIGHT / 14, HEIGHT / 3)

                text_yes = FONT_YES_NO.render(translate.get('Translate', 'yes'), True, GREEN)
                text_yes_rect = text_yes.get_rect()

                smile_image = pygame.image.load("assets/smile.png")
                smile_image = pygame.transform.scale(smile_image, (60, 60))

                sad_image = pygame.image.load("assets/sad.png")
                sad_image = pygame.transform.scale(sad_image, (60, 60))

                text_no = FONT_YES_NO.render(translate.get('Translate', 'no'), True, RED)
                text_no_rect = text_no.get_rect()

                if TOKEN_YES == 0:
                    text_yes_rect.center = (self.gate_left.x + 50, self.gate_left.y - 40)
                    text_no_rect.center = (self.gate_right.x + 50, self.gate_right.y - 40)
                    self.screen.blit(smile_image, (self.gate_left.x + 100, self.gate_left.y - 80))
                    self.screen.blit(sad_image, (self.gate_right.x + 130, self.gate_right.y - 80))

                else:
                    text_yes_rect.center = (self.gate_right.x + 50, self.gate_right.y - 40)
                    text_no_rect.center = (self.gate_left.x + 50, self.gate_left.y - 40)
                    self.screen.blit(sad_image, (self.gate_left.x + 130, self.gate_left.y - 80))
                    self.screen.blit(smile_image, (self.gate_right.x + 100, self.gate_right.y - 80))

                self.screen.blit(text_yes, text_yes_rect)
                self.screen.blit(text_no, text_no_rect)

                self.gate_left.draw()
                self.gate_right.draw()
                self.bar_left.draw()
                self.bar_right.draw()
                controls.draw((0, 0, 0), translate.get('Translate', 'thlu'))
                controls2.draw((0, 0, 0), translate.get('Translate', 'thru'))
                controls3.draw((0, 0, 0), translate.get('Translate', 'thll'))
                controls4.draw((0, 0, 0), translate.get('Translate', 'thrl'))

            elif training_mode:
                self.type = 'Training'
                text = FONT.render(translate.get('Translate', 'training.mode'), True, WHITE)
                text_rect = text.get_rect()
                text_rect.center = (X + 30, Y - 250)
                self.screen.blit(text, text_rect)

                if self.training.left_1.clicked:
                    self.gate_left = GateLeft(HEIGHT / 10 + 250)
                    self.bar_left = Bar(screen, 'left', self.gate_left.x + 50, 140, HEIGHT / 14, HEIGHT / 3)
                    self.gate_left.draw()
                    self.bar_left.draw()
                    self.gate_right = None
                    self.bar_right = None
                    controls.draw((0, 0, 0), translate.get('Translate', 'thlu'))
                    controls3.draw((0, 0, 0), translate.get('Translate', 'thll'))
                elif self.training.left_2.clicked:
                    self.gate_left = GateLeft(HEIGHT / 10 + 150)
                    self.bar_left = Bar(screen, 'left', self.gate_left.x + 50, 140, HEIGHT / 14, HEIGHT / 3)
                    self.gate_left.draw()
                    self.bar_left.draw()
                    self.gate_right = None
                    self.bar_right = None
                    controls.draw((0, 0, 0), translate.get('Translate', 'thlu'))
                    controls3.draw((0, 0, 0), translate.get('Translate', 'thll'))
                elif self.training.left_3.clicked:
                    self.gate_left = GateLeft(HEIGHT / 10 + 50)
                    self.bar_left = Bar(screen, 'left', self.gate_left.x + 50, 140, HEIGHT / 14, HEIGHT / 3)
                    self.gate_left.draw()
                    self.bar_left.draw()
                    self.gate_right = None
                    self.bar_right = None
                    controls.draw((0, 0, 0), translate.get('Translate', 'thlu'))
                    controls3.draw((0, 0, 0), translate.get('Translate', 'thll'))
                elif self.training.right_1.clicked:
                    self.gate_right = GateRight(WIDTH - 60 - HEIGHT / 10 - 50)
                    self.bar_right = Bar(screen, 'right', self.gate_right.x + 30, 140, HEIGHT / 14, HEIGHT / 3)
                    self.gate_right.draw()
                    self.bar_right.draw()
                    self.gate_left = None
                    self.bar_left = None
                    controls2.draw((0, 0, 0), translate.get('Translate', 'thru'))
                    controls4.draw((0, 0, 0), translate.get('Translate', 'thrl'))
                elif self.training.right_2.clicked:
                    self.gate_right = GateRight(WIDTH - 60 - HEIGHT / 10 - 150)
                    self.bar_right = Bar(screen, 'right', self.gate_right.x + 30, 140, HEIGHT / 14, HEIGHT / 3)
                    self.gate_right.draw()
                    self.bar_right.draw()
                    self.gate_left = None
                    self.bar_left = None
                    controls2.draw((0, 0, 0), translate.get('Translate', 'thru'))
                    controls4.draw((0, 0, 0), translate.get('Translate', 'thrl'))
                elif self.training.right_3.clicked:
                    self.gate_right = GateRight(WIDTH - 60 - HEIGHT / 10 - 250)
                    self.bar_right = Bar(screen, 'right', self.gate_right.x + 30, 140, HEIGHT / 14, HEIGHT / 3)
                    self.gate_right.draw()
                    self.bar_right.draw()
                    self.gate_left = None
                    self.bar_left = None
                    controls2.draw((0, 0, 0), translate.get('Translate', 'thru'))
                    controls4.draw((0, 0, 0), translate.get('Translate', 'thrl'))

            else:
                self.type = 'Game'
                text = FONT.render(translate.get('Translate', 'game.mode'), True, WHITE)
                text_rect = text.get_rect()
                text_rect.center = (X + 30, Y - 500)
                self.screen.blit(text, text_rect)
                text_good = translate.get('Translate', 'good.goals')
                text_bad = translate.get('Translate', 'bad.goals')

                text = pygame.font.Font('freesansbold.ttf', 25).render(
                    f'{text_good}: {self.ball.score_good}', True,
                    WHITE)
                text_rect = text.get_rect()
                text_rect.center = (X + 30, Y - 250)
                self.screen.blit(text, text_rect)

                text = pygame.font.Font('freesansbold.ttf', 25).render(
                    f'{text_bad}: {self.ball.score_bad}', True, WHITE)
                text_rect = text.get_rect()
                text_rect.center = (X + 30, Y - 300)
                self.screen.blit(text, text_rect)

                self.gate_left = GateLeft(HEIGHT / 10)
                self.gate_right = GateRight(WIDTH - 60 - HEIGHT / 5)
                self.bar_left = Bar(screen, 'left', self.gate_left.x + 50, 140, HEIGHT / 14, HEIGHT / 3)
                self.bar_right = Bar(screen, 'right', self.gate_right.x + 30, 140, HEIGHT / 14, HEIGHT / 3)
                self.gate_left.draw()
                self.gate_right.draw()
                self.bar_left.draw()
                self.bar_right.draw()

                if TOKEN_DIRECTION == 0:
                    self.screen.blit(arrow_left_image, (X, Y - 400))
                    if sound_left_repetitions == 0:
                        sound_left.play()
                        sound_left_repetitions = 1

                else:
                    self.screen.blit(arrow_right_image, (X, Y - 400))
                    if sound_right_repetitions == 0:
                        sound_right.play()
                        sound_right_repetitions = 1

                controls.draw((0, 0, 0), translate.get('Translate', 'thlu'))
                controls2.draw((0, 0, 0), translate.get('Translate', 'thru'))
                controls3.draw((0, 0, 0), translate.get('Translate', 'thll'))
                controls4.draw((0, 0, 0), translate.get('Translate', 'thrl'))

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

            if force_right > int(THRU) and self.bar_right is not None:
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

            if force_left > int(THLL) and force_left < int(THLU) and force_right < int(
                    THRL) and self.bar_left is not None:
                print("stanga")
                send_trigger(event_move_left)
                self.bar_left.draw_threshold_bar(True, force_left)
                self.ball.move_left()

                if self.ball.x <= self.gate_left.x + 20:
                    if self.type == 'Game':
                        if TOKEN_DIRECTION == 0:
                            self.congrats()
                            self.ball.score_good += 1
                        else:
                            self.ball.score_bad += 1
                    elif self.type == 'Training':
                        self.congrats()
                    self.ball.replace()

            if force_right > int(THRL) and force_right < int(THRU) and force_left < int(
                    THLL) and self.bar_right is not None:
                print("dreapta")
                send_trigger(event_move_right)
                self.bar_right.draw_threshold_bar(True, force_right)
                self.ball.move_right()
                if self.ball.x >= self.gate_right.x - 20:
                    if self.type == 'Game':
                        if TOKEN_DIRECTION == 1:
                            self.congrats()
                            self.ball.score_good += 1
                        else:
                            self.ball.score_bad += 1
                    elif self.type == 'Training':
                        self.congrats()
                    self.ball.replace()

            if force_right > int(THRL) and force_right < int(THRU) and force_left < int(THLU) and force_left > int(
                    THLL) and self.bar_left is not None and self.bar_right is not None:
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
                    stop_lab_recorder(self.process)
                    outlet_markers.__del__()
                    if self.type == 'Game':
                        self.ball.save_scores()
                    shutil.copy("config_game.ini", self.source_directory)
                    self.ball.save_thresolds()
                    FILE.close()
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
                        shutil.copy("config_game.ini", self.source_directory)

                if event.type == pygame.KEYDOWN:
                    if controls.active == True:

                        if event.key == pygame.K_RETURN:
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
                stop_lab_recorder(self.process)
                self.ball.save_scores()
                self.ball.save_thresolds()
                shutil.copy("config_game.ini", self.source_directory)
                FILE.close()
                outlet_markers.__del__()
                pygame.quit()

            sample, timestamp = inlet_markers.pull_chunk(max_samples=1)
            # print(sample, timestamp)

            if arrow_key_pressed:
                text = FONT.render(f"Arrow key pressed: {arrow_key_pressed}", True, (0, 0, 0))
                self.screen.blit(text, (10, 10))

            self.screen.blit(self.ball.image, (self.ball.x, self.ball.y))
            self.screen.blit(text, text_rect)
            pygame.time.Clock().tick(30)

            if self.back_button.clicked:
                self.ball.replace()
                self.ball.save_scores()
                self.ball.save_thresolds()
                self.ball.score_bad = 0
                self.ball.score_good = 0
                self.intro(back=True)
            pygame.display.flip()

    def congrats(self):
        pygame.mixer.init()
        sound = pygame.mixer.Sound("assets/congrats.wav")
        sound.set_volume(0.6)
        background = pygame.image.load("assets/congrats.png")
        background = pygame.transform.scale(background, (WIDTH, HEIGHT))
        congrats_text = FONT.render(translate.get('Translate', 'congrats'), True, WHITE)
        text_rect = congrats_text.get_rect()
        text_rect.center = (X + 30, X - 250)
        sound.play()
        screen.blit(background, (0, 0))
        self.screen.blit(congrats_text, text_rect)
        pygame.display.flip()
        start_time = time.time()
        running = True
        while running:
            seconds = time.time() - start_time
            if seconds > 3:
                running = False


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
            config.set('Game', 'thlu', str(THLU))
        elif threshold == 'THRU':
            THRU = text
            config.set('Game', 'thru', str(THRU))
        elif threshold == 'THLL':
            THLL = text
            config.set('Game', 'thll', str(THLL))
        elif threshold == 'THRL':
            THRL = text
            config.set('Game', 'thrl', str(THRL))
        with open('config_game.ini', 'w') as configfile:
            config.write(configfile)

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
        self.left_1 = Button(X - 275, Y - 135, 210, 85, translate.get('Translate', 'left.level.1'))
        self.left_2 = Button(X - 275, Y - 45, 210, 85, translate.get('Translate', 'left.level.2'))
        self.left_3 = Button(X - 275, Y + 45, 210, 85, translate.get('Translate', 'left.level.3'))
        self.right_1 = Button(X + 100, Y - 135, 230, 85, translate.get('Translate', 'right.level.1'))
        self.right_2 = Button(X + 100, Y - 45, 230, 85, translate.get('Translate', 'right.level.2'))
        self.right_3 = Button(X + 100, Y + 45, 230, 85, translate.get('Translate', 'right.level.3'))
        self.ball = game_state.ball
        self.intro_training = False
        self.process = None

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
        intro_image = pygame.transform.scale(intro_image, (WIDTH, HEIGHT))
        intro_rect = intro_image.get_rect()
        intro_rect.center = (WIDTH // 2, HEIGHT // 2)

        text = FONT.render(translate.get('Translate', 'training.mode'), True, WHITE)
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
                    stop_lab_recorder(self.process)
                    self.ball.save_scores()
                    self.ball.save_thresolds()
                    FILE.close()
                    outlet_markers.__del__()
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.left_1.rect.collidepoint(event.pos):
                        self.left_1.clicked = True
                        self.intro_training = True
                        self.left_1.starting(self.screen)
                    if self.left_2.rect.collidepoint(event.pos):
                        self.left_2.clicked = True
                        self.intro_training = True
                        self.left_2.starting(self.screen)
                    if self.left_3.rect.collidepoint(event.pos):
                        self.left_3.clicked = True
                        self.intro_training = True
                        self.left_3.starting(self.screen)
                    if self.right_1.rect.collidepoint(event.pos):
                        self.right_1.clicked = True
                        self.intro_training = True
                        self.right_1.starting(self.screen)
                    if self.right_2.rect.collidepoint(event.pos):
                        self.right_2.clicked = True
                        self.intro_training = True
                        self.right_2.starting(self.screen)
                    if self.right_3.rect.collidepoint(event.pos):
                        self.right_3.clicked = True
                        self.intro_training = True
                        self.right_3.starting(self.screen)

            pygame.display.flip()

        self.game_state.start_play(training_mode=True, yes_no=False)

def main_game():
    global screen
    keyboard = Controller()

    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption('Football Game!!')

    game_state = GameState(screen, keyboard)

    # mio_connect.main(sys.argv[1:])

    game_state.intro()

################ MIO CONNECT ########################################
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

        def main(self, argv, connected1, connected2):
            global CONNECTED
            # comment scr and plot when you do not want for them to run in parallel
            # pygame.display.set_mode((1, 1))

            config = Config()

            # Get options and arguments
            try:
                opts, args = getopt.getopt(argv, 'hsn:a:p:v',
                                           ['help', 'shutdown', 'nmyo', 'address', 'port', 'verbose'])
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
                # pygame.display.quit()

                info_emg1 = StreamInfo(type='EMG', name='EMG-Left', channel_count=8, nominal_srate=200,
                                       channel_format='float32', source_id='11')
                outlet_emg1 = StreamOutlet(info_emg1)

                info_emg2 = StreamInfo(type='EMG', name='EMG-Right', channel_count=8, nominal_srate=200,
                                       channel_format='float32', source_id='12')
                outlet_emg2 = StreamOutlet(info_emg2)

                info_imu1 = StreamInfo(name='IMU-Left', type='IMU', channel_count=5, nominal_srate=200,
                                       channel_format='float32', source_id='13')
                outlet_imu1 = StreamOutlet(info_imu1)

                info_imu2 = StreamInfo(name='IMU-Right', type='IMU', channel_count=5, nominal_srate=200,
                                       channel_format='float32', source_id='14')
                outlet_imu2 = StreamOutlet(info_imu2)

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

                        imu1 = []
                        imu2 = []

                        if (data_both_samples.get('emg')):
                            if (data_both_samples.get('emg').get("1")):
                                emg2 = list(data_both_samples.get('emg').get("1"))
                            if (data_both_samples.get('emg').get("0")):
                                emg1 = list(data_both_samples.get('emg').get("0"))

                        if (data_both_samples.get('imu')):
                            if (data_both_samples.get('imu').get("1")):
                                imu2 = list(data_both_samples.get('imu').get("1"))

                            if (data_both_samples.get('imu').get("0")):
                                imu1 = list(data_both_samples.get('imu').get("0"))

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
                outlet_emg1.__del__()
                outlet_emg2.__del__()
                outlet_imu1.__del__()
                outlet_imu2.__del__()

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

class MyoDriver:
    """
    Responsible for myo connections and messages.
    """

    def __init__(self, config):

        self.config = config
        print("OSC Address: " + str(self.config.OSC_ADDRESS))
        print("OSC Port: " + str(self.config.OSC_PORT))
        print()

        self.data_handler = DataHandler(self.config)
        self.bluetooth = Bluetooth(self.config.MESSAGE_DELAY)
        #self.screen = pygame.display.set_mode((400, 300))


        self.myos = []
        self.myo_data1 = []
        # self.myo_data2 = []

        self.myo_to_connect = None
        self.scanning = False

        # Add handlers for expected events
        self.set_handlers()

    def run(self,connected1, connected2):
        """
        Main. Disconnects possible connections and starts as many connections as needed.
        """
        self.disconnect_all()
        '''
        while len(self.myos) < self.config.MYO_AMOUNT:
            print(
                "*** Connecting myo " + str(len(self.myos) + 1) + " out of " + str(self.config.MYO_AMOUNT) + " ***")
            print()
        '''
        self.add_myo_connection(connected1, connected2)
        self.add_myo_connection(connected1, connected2)
        self.receive()

    def receive(self):
        self.bluetooth.receive()

    ##############################################################################
    #                                  CONNECT                                   #
    ##############################################################################

    def add_myo_connection(self,connected1,connected2):
        """
        Procedure for connection with the Myo Armband. Scans, connects, disables sleep and starts EMG stream.
        """
        # Discover
        self._print_status("Scanning")
        self.bluetooth.gap_discover()

        # Await myo detection and create Myo object.
        self.scanning = True
        while self.myo_to_connect is None:
            self.bluetooth.receive()

        # End gap
        self.bluetooth.end_gap()

        # Add handlers
        self.bluetooth.add_connection_status_handler(self.create_connection_status_handle(self.myo_to_connect, connected1, connected2))
        self.bluetooth.add_disconnected_handler(self.create_disconnect_handle(self.myo_to_connect))

        # Direct connection. Reconnect implements the retry procedure.
        self.myos.append(self.myo_to_connect)
        self.connect_and_retry(self.myo_to_connect, self.config.RETRY_CONNECTION_AFTER, self.config.MAX_RETRIES)
        self.myo_to_connect = None

    def connect_and_retry(self, myo, timeout=None, max_retries=None):
        """
        Procedure for a reconnection.
        :param myo: Myo object to connect. Should have its address set
        :param timeout: Time to wait for response
        :param max_retries: Max retries before exiting the program
        :return: True if connection was successful, false otherwise.
        """
        retries = 0
        # The subroutine will await the response until timeout is met
        while not self.direct_connect(myo, timeout) and not myo.connected:
            retries += 1
            if max_retries is not None and retries > max_retries:
                print("Max retries reached. Exiting")
                sys.exit(1)
            print()
            print("Reconnection failed for connection " + str(myo.connection_id) + ". Retry " + str(retries) + "...")
        myo.set_connected(True)
        return True

    def direct_connect(self, myo_to_connect, timeout=None):
        """
        Procedure for a direct connection with the device.
        :param myo_to_connect: Myo object to connect. Should have its address set
        :param timeout: Time to wait for response
        :return: True if connection was successful, false otherwise.
        """
        t0 = time.time()
        # Direct connection
        # print(myo_to_connect.mac_address)
        self._print_status("Connecting to", myo_to_connect.address)
        self.bluetooth.direct_connect(myo_to_connect.address)

        # Await response
        while myo_to_connect.connection_id is None or not myo_to_connect.connected:
            # print(myo_to_connect.connection_id)
            #print(myo_to_connect.mac_address)

            if timeout is not None and timeout + t0 < time.time():
                return False
            '''
            if myo_to_connect.connection_id == 0 and myo_to_connect.mac_address == Config.MAC_ADDR_MYO_1:
                self.receive()
            if myo_to_connect.connection_id == 1 and myo_to_connect.mac_address == Config.MAC_ADDR_MYO_2:
                self.receive()
            '''
            self.receive()

        # Notify successful connection with self.print_status and vibration
        self._print_status("Connection successful. Setting up...")
        self._print_status()
        self.bluetooth.send_vibration_medium(myo_to_connect.connection_id)

        # Disable sleep
        self.bluetooth.disable_sleep(myo_to_connect.connection_id)

        # Enable data and subscribe
        self.bluetooth.enable_data(myo_to_connect.connection_id, self.config)

        print("Myo ready", myo_to_connect.connection_id, myo_to_connect.address)
        print()
        return True

    ##############################################################################
    #                                  HANDLERS                                  #
    ##############################################################################

    def handle_discover(self, _, payload):
        """
        Handler for ble_evt_gap_scan_response event.
        """
        if self.scanning and not self.myo_to_connect:
            self._print_status("Device found", payload['sender'])
            if payload['data'].endswith(bytes(Final.myo_id)):
                if not self._has_paired_with(payload['sender']):
                    self.myo_to_connect = Myo(payload['sender'])
                    self._print_status("Myo found", self.myo_to_connect.address)
                    self._print_status()
                    self.scanning = False

    def _has_paired_with(self, address):
        """
        Checks if given address has already been recorded in a Myo initialization.
        :param address: address to check
        :return: True if already paired, False otherwise.
        """
        for m in self.myos:
            if m.address == address:
                return True
        return False

    def handle_connect(self, _, payload):
        """
        Handler for ble_rsp_gap_connect_direct event.
        """
        if not payload['result'] == 0:
            if payload['result'] == 385:
                print("ERROR: Device in Wrong State")
            else:
                print(payload)
        else:
            self._print_status("Connection successful")

    def create_disconnect_handle(self, myo):
        def handle_disconnect(_, payload):
            """
            Handler for ble_evt_connection_status event.
            """
            if myo.connection_id == payload['connection'] or (
                    myo.mac_address == Config.MAC_ADDR_MYO_1 and payload['connection'] == 1) or (
                    myo.mac_address == Config.MAC_ADDR_MYO_2 and payload[
                'connection'] == 0) or myo.mac_address != Config.MAC_ADDR_MYO_2 or \
                    myo.mac_address != Config.MAC_ADDR_MYO_1 or (myo.mac_address == Config.MAC_ADDR_MYO_1 and not payload['connection']) \
                    or (myo.mac_address == Config.MAC_ADDR_MYO_2 and not payload['connection'])\
                    or myo.mac_adress == Config.MAC_ADDR_MYO_3:
                print("Connection " + str(payload['connection']) + " lost.")
                myo.set_connected(False)
                if payload['reason'] == 574:
                    print("Disconnected. Reason: Connection Failed to be Established.")
                if payload['reason'] == 534:
                    print("Disconnected. Reason: Connection Terminated by Local Host.")
                if payload['reason'] == 520:
                    print("Disconnected. Reason: Connection Timeout.")
                else:
                    print("Disconnected:", payload)
                # Won't return until the connection is established successfully
                print("Reconnecting...")
                self.connect_and_retry(myo, self.config.RETRY_CONNECTION_AFTER, self.config.MAX_RETRIES)

        return handle_disconnect

    def create_connection_status_handle(self, myo,connected1, connected2):
        def handle_connection_status(_, payload):
            """
            Handler for ble_evt_connection_status event.
            """
            if payload['address'] == myo.address and payload['flags'] == 5:
                self._print_status("Connection status: ", payload)
                myo.set_connected(True)
                # print(payload['connection'])
                if (myo.mac_address == Config.MAC_ADDR_MYO_1 and payload['connection'] == 0) or (
                        myo.mac_address == Config.MAC_ADDR_MYO_2 and payload['connection'] == 1):
                    myo.set_id(payload['connection'])
                    if myo.mac_address == Config.MAC_ADDR_MYO_1:
                        #pygame.draw.rect(self.screen, (255,0,0), pygame.Rect(0,0,0,0))
                        #text_surface = FONT.render('Myo left connected', True, (255, 255, 255))
                        #text_rect = self.text.get_rect(center=self.rect.center)
                        #self.screen.blit(self.text, text_rect)
                        #pygame.display.flip()
                        print("left")
                        connected1.set()
                    elif myo.mac_address == Config.MAC_ADDR_MYO_2:
                        connected2.set()
                        print("right")

                self._print_status("Connected with id", myo.connection_id)

        return handle_connection_status

    def handle_attribute_value(self, e, payload):
        """
        Handler for EMG events, expected as a ble_evt_attclient_attribute_value event with handle 43, 46, 49 or 52.
        """
        emg_handles = [
            ServiceHandles.EmgData0Characteristic,
            ServiceHandles.EmgData1Characteristic,
            ServiceHandles.EmgData2Characteristic,
            ServiceHandles.EmgData3Characteristic
        ]
        imu_handles = [
            ServiceHandles.IMUDataCharacteristic
        ]
        myo_info_handles = [
            ServiceHandles.DeviceName,
            ServiceHandles.FirmwareVersionCharacteristic,
            ServiceHandles.BatteryCharacteristic
        ]

        # Delegate EMG
        if payload['atthandle'] in emg_handles:
            self.data_handler.handle_emg(payload)

        # Delegate IMU
        elif payload['atthandle'] in imu_handles:
            self.data_handler.handle_imu(payload)

        # TODO: Delegate classifier

        # Delegate myo info
        elif payload['atthandle'] in myo_info_handles:
            for myo in self.myos:
                myo.handle_attribute_value(payload)

        # Print otherwise
        else:
            self._print_status(e, payload)

    def set_handlers(self):
        """
        Set handlers for relevant events.
        """
        self.bluetooth.add_scan_response_handler(self.handle_discover)
        self.bluetooth.add_connect_response_handler(self.handle_connect)
        self.bluetooth.add_attribute_value_handler(self.handle_attribute_value)

    ##############################################################################
    #                                    MYO                                     #
    ##############################################################################

    def get_info(self):
        """
        Send read attribute messages and await answer.
        """
        if len(self.myos):
            self._print_status("Getting myo info")
            self._print_status()
            for myo in self.myos:
                self.bluetooth.read_device_name(myo.connection_id)
                self.bluetooth.read_firmware_version(myo.connection_id)
                self.bluetooth.read_battery_level(myo.connection_id)
            while not self._myos_ready():
                self.receive()
            print("Myo list:")
            for myo in self.myos:
                print(" - " + str(myo))
            print()

    def disconnect_all(self):
        """
        Stop possible scanning and close all connections.
        """
        self.bluetooth.disconnect_all()

    def deep_sleep_all(self):
        """
        Send deep sleep (turn off) signal to every connected myo.
        """
        print("Turning off devices...")
        for m in self.myos:
            self.bluetooth.deep_sleep(m.connection_id)
        print("Disconnected.")

    ##############################################################################
    #                                   UTILS                                    #
    ##############################################################################

    def _myos_ready(self):
        """
        :return: True if every myo has its data set, False otherwise.
        """
        for m in self.myos:
            if not m.ready():
                return False
        return True

    def _print_status(self, *args):
        """
        Printer function for VERBOSE support.
        """
        if self.config.VERBOSE:
            print(*args)

class Myo():
    """
    Wrapper for a Myo, its name, address, firmware and most importantly, connection id.
    """

    def __init__(self, address):
        self.address = address  ### MAC-address in reversed byte format; e.g.: b'\xc6z\xd95\x07\xec'

        ###  convert each byte of the address to its hexadecimal representation.
        ### The '02x' format specifier ensures that each hexadecimal representation is zero-padded to have at least two characters:
        hex_list = [format(byte, '02x') for byte in address]
        ### join the double-characters with hyphens '-' in reverse order [::-1]
        self.mac_address = '-'.join(hex_list[::-1])  ### MAC-address in usual format, e.g.: ec-07-35-d9-7a-c6

        self.connection_id = None
        self.device_name = None
        self.firmware_version = None
        self.battery_level = None
        self.connected = False
        self.emg_handlers = []

    def add_emg_handler(self, h):
        self.emg_handlers.append(h)

    def set_id(self, connection_id):
        """
        Set connection id, required for every write/read attribute message.
        """
        self.connection_id = connection_id
        return self

    def set_connected(self, connected):
        self.connected = connected

    def handle_attribute_value(self, payload):
        """
        When attribute values are not EMG/IMU related, are a Myo attribute being read.
        """
        if self.connection_id == payload['connection']:
            if payload['atthandle'] == ServiceHandles.DeviceName:
                self.device_name = payload['value'].decode()
                # print("Device name", payload['value'].decode())
            elif payload['atthandle'] == ServiceHandles.FirmwareVersionCharacteristic:
                self.firmware_version = payload['value']
                # print("Firmware version", payload['value'])
                if not payload['value'] == b'\x01\x00\x05\x00\xb2\x07\x02\x00':
                    print("MYO WITH UNEXPECTED FIRMWARE, MAY NOT BEHAVE PROPERLY.", payload['value'])
            elif payload['atthandle'] == ServiceHandles.BatteryCharacteristic:
                self.battery_level = payload['value']
            else:
                print("UNEXPECTED ATTRIBUTE VALUE: ", payload)

    def ready(self):
        """
        :return:True if every field is valid, False otherwise.
        """
        return self.address is not None and \
            self.connection_id is not None and \
            self.device_name is not None and \
            self.firmware_version is not None and \
            self.battery_level is not None

    def __str__(self):
        return "Myo: " + str(self.device_name) + ", " + \
            "Battery level: " + str(*struct.unpack('b', self.battery_level)) + "/100, " + \
            "Connection: " + str(self.connection_id) + ", " + \
            "Address: " + str(self.address) + ", " + \
            "Firmware: " + str(self.firmware_version)

    #### miohw.py ###
class Final:

    myo_id = [0x42, 0x48, 0x12, 0x4A,
              0x7F, 0x2C, 0x48, 0x47,
              0xB9, 0xDE, 0x04, 0xA9,
              0x01, 0x00, 0x06, 0xD5]

    direct_connection_tail = (0, 6, 6, 64, 0)

    subscribe_payload = [0x01, 0x00]


class Services:
    ControlService = 0x0001  # Myo info service
    MyoInfoCharacteristic = 0x0101  # Serial number for this Myo and various parameters which are specific to this
    # firmware. Read - only attribute.
    FirmwareVersionCharacteristic = 0x0201  # Current firmware  characteristic.
    CommandCharacteristic = 0x0401  # Issue commands to the Myo.Write - only characteristic.

    ImuDataService = 0x0002  # IMU service
    IMUDataCharacteristic = 0x0402
    MotionEventCharacteristic = 0x0502

    ClassifierService = 0x0003  # Classifier event service.
    ClassifierEventCharacteristic = 0x0103  # Classifier event data.Indicate - only characteristic.

    EmgDataService = 0x0005  # Raw EMG data service.
    EmgData0Characteristic = 0x0105  # Raw EMG data.Notify - only characteristic.
    EmgData1Characteristic = 0x0205  # Raw EMG data.Notify - only characteristic.
    EmgData2Characteristic = 0x0305  # Raw EMG data.Notify - only characteristic.
    EmgData3Characteristic = 0x0405  # Raw EMG data.Notify - only characteristic.


class ServiceHandles:
    """
    Thanks to https://github.com/brokenpylons/MyoLinux/blob/master/src/myoapi_p.h
    """
    # ControlService
    MyoInfoCharacteristic = 0x0
    DeviceName = 0x3
    BatteryCharacteristic = 0x11
    BatteryDescriptor = 0x12
    FirmwareVersionCharacteristic = 0x17
    CommandCharacteristic = 0x19

    # ImuDataService
    IMUDataCharacteristic = 0x1c
    IMUDataDescriptor = 0x1d
    # MotionEventCharacteristic

    # ClassifierService
    ClassifierEventCharacteristic = 0x0023

    EmgData0Characteristic = 0x2b
    EmgData1Characteristic = 0x2e
    EmgData2Characteristic = 0x31
    EmgData3Characteristic = 0x34

    EmgData0Descriptor = 0x2c
    EmgData1Descriptor = 0x2f
    EmgData2Descriptor = 0x32
    EmgData3Descriptor = 0x35


class StandardServices:
    BatteryService = 0x180f  # Battery service
    BatteryLevelCharacteristic = 0x2a19  # Current battery level information. Read/notify characteristic.
    DeviceName = 0x2a00  # Device name data. Read/write characteristic.


class Pose:
    myohw_pose_rest = 0x0000
    myohw_pose_fist = 0x0001
    myohw_pose_wave_in = 0x0002
    myohw_pose_wave_out = 0x0003
    myohw_pose_fingers_spread = 0x0004
    myohw_pose_double_tap = 0x0005
    myohw_pose_unknown = 0xffff


class MyoCommand:
    # payload size = 3: EmgMode ImuMode ClassifierMode
    myohw_command_set_mode = 0x01  # Set EMG and IMU modes.

    # payload size = 1: VibrationType
    myohw_command_vibrate = 0x03  # Vibrate.

    # payload size = 0
    myohw_command_deep_sleep = 0x04  # Put Myo into deep sleep.

    # payload size = 18: [duration strength]*
    myohw_command_vibrate2 = 0x07  # Extended vibrate.

    # payload size = 1: SleepMode
    myohw_command_set_sleep_mode = 0x09  # Set sleep mode.

    # payload size = 1: UnlockType
    myohw_command_unlock = 0x0a  # Unlock Myo.

    # payload size = 1: UserActionType
    myohw_command_user_action = 0x0b  # Notify user that an action has been recognized or confirmed


class EmgMode:
    myohw_emg_mode_none = 0x00  # Do not send EMG data.
    myohw_emg_mode_send_emg = 0x02  # Send filtered EMG data.
    myohw_emg_mode_send_emg_raw = 0x03  # Send raw (unfiltered) EMG data.


class ImuMode:
    myohw_imu_mode_none = 0x00  # Do not send IMU data or events.
    myohw_imu_mode_send_data = 0x01  # Send IMU data streams (accelerometer gyroscope and orientation).
    myohw_imu_mode_send_events = 0x02  # Send motion events detected by the IMU (e.g. taps).
    myohw_imu_mode_send_all = 0x03  # Send both IMU data streams and motion events.
    myohw_imu_mode_send_raw = 0x04  # Send raw IMU data streams.


class ClassifierMode:
    myohw_classifier_mode_disabled = 0x00  # Disable and reset the internal state of the onboard classifier.
    myohw_classifier_mode_enabled = 0x01  # Send classifier events (poses and arm events).


class VibrationType:
    myohw_vibration_none = 0x00  # Do not vibrate.
    myohw_vibration_short = 0x01  # Vibrate for a short amount of time.
    myohw_vibration_medium = 0x02  # Vibrate for a medium amount of time.
    myohw_vibration_long = 0x03  # Vibrate for a long amount of time.


class SleepMode:
    myohw_sleep_mode_normal = 0  # Normal sleep mode; Myo will sleep after a period of inactivity.
    myohw_sleep_mode_never_sleep = 1  # Never go to sleep.


class UnlockType:
    myohw_unlock_lock = 0x00  # Re-lock immediately.
    myohw_unlock_timed = 0x01  # Unlock now and re-lock after a fixed timeout.
    myohw_unlock_hold = 0x02  # Unlock now and remain unlocked until a lock command is received.


class UserActionType:
    myohw_user_action_single = 0  # User did a single discrete action such as pausing a video.

    #####bluetooth.py
class Bluetooth:
    """
    Responsible for serial comm and message encapsulation.
    New commands can be added using myohw.py and following provided commands.
    """
    def __init__(self, message_delay):
        self.lib = BGLib()
        self.message_delay = message_delay
        self.serial = serial.Serial(port=self._detect_port(), baudrate=9600, dsrdtr=1)

    @staticmethod
    def _detect_port():
        """
        Detect COM port.
        :return: COM port with the expected ID
        """
        print("Detecting available ports")
        for p in comports():
            if re.search(r'PID=2458:0*1', p[2]):
                print('Port detected: ', p[0])
                print()
                return p[0]
        return None

##############################################################################
#                                  PROTOCOL                                  #
##############################################################################

    def receive(self):
        """
        Check for received evens and handle them.
        """
        self.lib.check_activity(self.serial)

    def send(self, msg):
        """
        Send given message through serial. A small delay is required for the Myo to process them correctly
        :param msg: packed message to send
        """
        time.sleep(self.message_delay)
        self.lib.send_command(self.serial, msg)

    def write_att(self, connection, atthandle, data):
        """
        Wrapper for code readability.
        """
        self.send(self.lib.ble_cmd_attclient_attribute_write(connection, atthandle, data))

    def read_att(self, connection, atthandle):
        """
        Wrapper for code readability.
        """
        self.send(self.lib.ble_cmd_attclient_read_by_handle(connection, atthandle))

    def disconnect_all(self):
        """
        Stop possible scanning and close all connections.
        """
        self.send(self.lib.ble_cmd_gap_end_procedure())
        self.send(self.lib.ble_cmd_connection_disconnect(0))
        self.send(self.lib.ble_cmd_connection_disconnect(1))
        self.send(self.lib.ble_cmd_connection_disconnect(2))


##############################################################################
#                                  COMMANDS                                  #
##############################################################################

    def gap_discover(self):
        self.send(self.lib.ble_cmd_gap_discover(1))

    def end_gap(self):
        self.send(self.lib.ble_cmd_gap_end_procedure())

    def direct_connect(self, myo_address):
        self.send(self.lib.ble_cmd_gap_connect_direct(myo_address, *Final.direct_connection_tail))

    def send_vibration(self, connection, vibration_type):
        self.write_att(connection,
                       ServiceHandles.CommandCharacteristic,
                       [MyoCommand.myohw_command_vibrate,
                        0x01,
                        vibration_type])

    def send_vibration_short(self, connection):
        self.write_att(connection,
                       ServiceHandles.CommandCharacteristic,
                       [MyoCommand.myohw_command_vibrate,
                        0x01,
                        VibrationType.myohw_vibration_short])

    def send_vibration_medium(self, connection):
        self.send_vibration(connection, VibrationType.myohw_vibration_medium)

    def send_vibration_long(self, connection):
        self.send_vibration(connection, VibrationType.myohw_vibration_long)

    def disable_sleep(self, connection):
        self.write_att(connection,
                       ServiceHandles.CommandCharacteristic,
                       [MyoCommand.myohw_command_set_sleep_mode,
                        0x01,
                        SleepMode.myohw_sleep_mode_never_sleep])

    def read_device_name(self, connection):
        self.read_att(connection, ServiceHandles.DeviceName)

    def read_firmware_version(self, connection):
        self.read_att(connection, ServiceHandles.FirmwareVersionCharacteristic)

    def read_battery_level(self, connection):
        self.read_att(connection, ServiceHandles.BatteryCharacteristic)

    def deep_sleep(self, connection):
        self.write_att(connection,
                       ServiceHandles.CommandCharacteristic,
                       [MyoCommand.myohw_command_deep_sleep])

    def enable_data(self, connection, config):
        # TODO: Subscribe to classifier events.

        # Start EMG
        self.write_att(connection,
                       ServiceHandles.CommandCharacteristic,
                       [MyoCommand.myohw_command_set_mode,
                        0x03,
                        config.EMG_MODE,
                        config.IMU_MODE,
                        config.CLASSIFIER_MODE])

        # Subscribe for IMU
        self.write_att(connection,
                       ServiceHandles.IMUDataDescriptor,
                       Final.subscribe_payload)

        # Subscribe for EMG
        self.write_att(connection,
                       ServiceHandles.EmgData0Descriptor,
                       Final.subscribe_payload)
        self.write_att(connection,
                       ServiceHandles.EmgData1Descriptor,
                       Final.subscribe_payload)
        self.write_att(connection,
                       ServiceHandles.EmgData2Descriptor,
                       Final.subscribe_payload)
        self.write_att(connection,
                       ServiceHandles.EmgData3Descriptor,
                       Final.subscribe_payload)


##############################################################################
#                                  HANDLERS                                  #
##############################################################################

    def add_scan_response_handler(self, handler):
        self.lib.ble_evt_gap_scan_response.add(handler)

    def add_connect_response_handler(self, handler):
        self.lib.ble_rsp_gap_connect_direct.add(handler)

    def add_attribute_value_handler(self, handler):
        self.lib.ble_evt_attclient_attribute_value.add(handler)

    def add_disconnected_handler(self, handler):
        self.lib.ble_evt_connection_disconnected.add(handler)

    def add_connection_status_handler(self, handler):
        self.lib.ble_evt_connection_status.add(handler)

    ####bglib..py
__author__ = "Jeff Rowberg"
__license__ = "MIT"
__version__ = "2013-05-04"
__email__ = "jeff@rowberg.net"


# thanks to Masaaki Shibata for Python event handler code
# http://www.emptypage.jp/notes/pyevent.en.html

class BGAPIEvent(object):

    def __init__(self, doc=None):
        self.__doc__ = doc

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return BGAPIEventHandler(self, obj)

    def __set__(self, obj, value):
        pass


class BGAPIEventHandler(object):

    def __init__(self, event, obj):

        self.event = event
        self.obj = obj

    def _getfunctionlist(self):

        """(internal use) """

        try:
            eventhandler = self.obj.__eventhandler__
        except AttributeError:
            eventhandler = self.obj.__eventhandler__ = {}
        return eventhandler.setdefault(self.event, [])

    def add(self, func):

        """Add new event handler function.

        Event handler function must be defined like func(sender, earg).
        You can add handler also by using '+=' operator.
        """

        self._getfunctionlist().append(func)
        return self

    def remove(self, func):

        """Remove existing event handler function.

        You can remove handler also by using '-=' operator.
        """

        self._getfunctionlist().remove(func)
        return self

    def fire(self, earg=None):

        """Fire event and call all handler functions

        You can call EventHandler object itself like e(earg) instead of
        e.fire(earg).
        """

        for func in self._getfunctionlist():
            func(self.obj, earg)

    __iadd__ = add
    __isub__ = remove
    __call__ = fire


class BGLib(object):

    def ble_cmd_system_reset(self, boot_in_dfu):
        return struct.pack('<4BB', 0, 1, 0, 0, boot_in_dfu)
    def ble_cmd_system_hello(self):
        return struct.pack('<4B', 0, 0, 0, 1)
    def ble_cmd_system_address_get(self):
        return struct.pack('<4B', 0, 0, 0, 2)
    def ble_cmd_system_reg_write(self, address, value):
        return struct.pack('<4BHB', 0, 3, 0, 3, address, value)
    def ble_cmd_system_reg_read(self, address):
        return struct.pack('<4BH', 0, 2, 0, 4, address)
    def ble_cmd_system_get_counters(self):
        return struct.pack('<4B', 0, 0, 0, 5)
    def ble_cmd_system_get_connections(self):
        return struct.pack('<4B', 0, 0, 0, 6)
    def ble_cmd_system_read_memory(self, address, length):
        return struct.pack('<4BIB', 0, 5, 0, 7, address, length)
    def ble_cmd_system_get_info(self):
        return struct.pack('<4B', 0, 0, 0, 8)
    def ble_cmd_system_endpoint_tx(self, endpoint, data):
        return struct.pack('<4BBB' + str(len(data)) + 's', 0, 2 + len(data), 0, 9, endpoint, len(data), bytes(i for i in data))
    def ble_cmd_system_whitelist_append(self, address, address_type):
        return struct.pack('<4B6sB', 0, 7, 0, 10, bytes(i for i in address), address_type)
    def ble_cmd_system_whitelist_remove(self, address, address_type):
        return struct.pack('<4B6sB', 0, 7, 0, 11, bytes(i for i in address), address_type)
    def ble_cmd_system_whitelist_clear(self):
        return struct.pack('<4B', 0, 0, 0, 12)
    def ble_cmd_system_endpoint_rx(self, endpoint, size):
        return struct.pack('<4BBB', 0, 2, 0, 13, endpoint, size)
    def ble_cmd_system_endpoint_set_watermarks(self, endpoint, rx, tx):
        return struct.pack('<4BBBB', 0, 3, 0, 14, endpoint, rx, tx)
    def ble_cmd_flash_ps_defrag(self):
        return struct.pack('<4B', 0, 0, 1, 0)
    def ble_cmd_flash_ps_dump(self):
        return struct.pack('<4B', 0, 0, 1, 1)
    def ble_cmd_flash_ps_erase_all(self):
        return struct.pack('<4B', 0, 0, 1, 2)
    def ble_cmd_flash_ps_save(self, key, value):
        return struct.pack('<4BHB' + str(len(value)) + 's', 0, 3 + len(value), 1, 3, key, len(value), bytes(i for i in value))
    def ble_cmd_flash_ps_load(self, key):
        return struct.pack('<4BH', 0, 2, 1, 4, key)
    def ble_cmd_flash_ps_erase(self, key):
        return struct.pack('<4BH', 0, 2, 1, 5, key)
    def ble_cmd_flash_erase_page(self, page):
        return struct.pack('<4BB', 0, 1, 1, 6, page)
    def ble_cmd_flash_write_words(self, address, words):
        return struct.pack('<4BHB' + str(len(words)) + 's', 0, 3 + len(words), 1, 7, address, len(words), bytes(i for i in words))
    def ble_cmd_attributes_write(self, handle, offset, value):
        return struct.pack('<4BHBB' + str(len(value)) + 's', 0, 4 + len(value), 2, 0, handle, offset, len(value), bytes(i for i in value))
    def ble_cmd_attributes_read(self, handle, offset):
        return struct.pack('<4BHH', 0, 4, 2, 1, handle, offset)
    def ble_cmd_attributes_read_type(self, handle):
        return struct.pack('<4BH', 0, 2, 2, 2, handle)
    def ble_cmd_attributes_user_read_response(self, connection, att_error, value):
        return struct.pack('<4BBBB' + str(len(value)) + 's', 0, 3 + len(value), 2, 3, connection, att_error, len(value), bytes(i for i in value))
    def ble_cmd_attributes_user_write_response(self, connection, att_error):
        return struct.pack('<4BBB', 0, 2, 2, 4, connection, att_error)
    def ble_cmd_connection_disconnect(self, connection):
        return struct.pack('<4BB', 0, 1, 3, 0, connection)
    def ble_cmd_connection_get_rssi(self, connection):
        return struct.pack('<4BB', 0, 1, 3, 1, connection)
    def ble_cmd_connection_update(self, connection, interval_min, interval_max, latency, timeout):
        return struct.pack('<4BBHHHH', 0, 9, 3, 2, connection, interval_min, interval_max, latency, timeout)
    def ble_cmd_connection_version_update(self, connection):
        return struct.pack('<4BB', 0, 1, 3, 3, connection)
    def ble_cmd_connection_channel_map_get(self, connection):
        return struct.pack('<4BB', 0, 1, 3, 4, connection)
    def ble_cmd_connection_channel_map_set(self, connection, map):
        return struct.pack('<4BBB' + str(len(map)) + 's', 0, 2 + len(map), 3, 5, connection, len(map), bytes(i for i in map))
    def ble_cmd_connection_features_get(self, connection):
        return struct.pack('<4BB', 0, 1, 3, 6, connection)
    def ble_cmd_connection_get_status(self, connection):
        return struct.pack('<4BB', 0, 1, 3, 7, connection)
    def ble_cmd_connection_raw_tx(self, connection, data):
        return struct.pack('<4BBB' + str(len(data)) + 's', 0, 2 + len(data), 3, 8, connection, len(data), bytes(i for i in data))
    def ble_cmd_attclient_find_by_type_value(self, connection, start, end, uuid, value):
        return struct.pack('<4BBHHHB' + str(len(value)) + 's', 0, 8 + len(value), 4, 0, connection, start, end, uuid, len(value), bytes(i for i in value))
    def ble_cmd_attclient_read_by_group_type(self, connection, start, end, uuid):
        return struct.pack('<4BBHHB' + str(len(uuid)) + 's', 0, 6 + len(uuid), 4, 1, connection, start, end, len(uuid), bytes(i for i in uuid))
    def ble_cmd_attclient_read_by_type(self, connection, start, end, uuid):
        return struct.pack('<4BBHHB' + str(len(uuid)) + 's', 0, 6 + len(uuid), 4, 2, connection, start, end, len(uuid), bytes(i for i in uuid))
    def ble_cmd_attclient_find_information(self, connection, start, end):
        return struct.pack('<4BBHH', 0, 5, 4, 3, connection, start, end)
    def ble_cmd_attclient_read_by_handle(self, connection, chrhandle):
        return struct.pack('<4BBH', 0, 3, 4, 4, connection, chrhandle)
    def ble_cmd_attclient_attribute_write(self, connection, atthandle, data):
        return struct.pack('<4BBHB' + str(len(data)) + 's', 0, 4 + len(data), 4, 5, connection, atthandle, len(data), bytes(i for i in data))
    def ble_cmd_attclient_write_command(self, connection, atthandle, data):
        return struct.pack('<4BBHB' + str(len(data)) + 's', 0, 4 + len(data), 4, 6, connection, atthandle, len(data), bytes(i for i in data))
    def ble_cmd_attclient_indicate_confirm(self, connection):
        return struct.pack('<4BB', 0, 1, 4, 7, connection)
    def ble_cmd_attclient_read_long(self, connection, chrhandle):
        return struct.pack('<4BBH', 0, 3, 4, 8, connection, chrhandle)
    def ble_cmd_attclient_prepare_write(self, connection, atthandle, offset, data):
        return struct.pack('<4BBHHB' + str(len(data)) + 's', 0, 6 + len(data), 4, 9, connection, atthandle, offset, len(data), bytes(i for i in data))
    def ble_cmd_attclient_execute_write(self, connection, commit):
        return struct.pack('<4BBB', 0, 2, 4, 10, connection, commit)
    def ble_cmd_attclient_read_multiple(self, connection, handles):
        return struct.pack('<4BBB' + str(len(handles)) + 's', 0, 2 + len(handles), 4, 11, connection, len(handles), bytes(i for i in handles))
    def ble_cmd_sm_encrypt_start(self, handle, bonding):
        return struct.pack('<4BBB', 0, 2, 5, 0, handle, bonding)
    def ble_cmd_sm_set_bondable_mode(self, bondable):
        return struct.pack('<4BB', 0, 1, 5, 1, bondable)
    def ble_cmd_sm_delete_bonding(self, handle):
        return struct.pack('<4BB', 0, 1, 5, 2, handle)
    def ble_cmd_sm_set_parameters(self, mitm, min_key_size, io_capabilities):
        return struct.pack('<4BBBB', 0, 3, 5, 3, mitm, min_key_size, io_capabilities)
    def ble_cmd_sm_passkey_entry(self, handle, passkey):
        return struct.pack('<4BBI', 0, 5, 5, 4, handle, passkey)
    def ble_cmd_sm_get_bonds(self):
        return struct.pack('<4B', 0, 0, 5, 5)
    def ble_cmd_sm_set_oob_data(self, oob):
        return struct.pack('<4BB' + str(len(oob)) + 's', 0, 1 + len(oob), 5, 6, len(oob), bytes(i for i in oob))
    def ble_cmd_gap_set_privacy_flags(self, peripheral_privacy, central_privacy):
        return struct.pack('<4BBB', 0, 2, 6, 0, peripheral_privacy, central_privacy)
    def ble_cmd_gap_set_mode(self, discover, connect):
        return struct.pack('<4BBB', 0, 2, 6, 1, discover, connect)
    def ble_cmd_gap_discover(self, mode):
        return struct.pack('<4BB', 0, 1, 6, 2, mode)
    def ble_cmd_gap_connect_direct(self, address, addr_type, conn_interval_min, conn_interval_max, timeout, latency):
        return struct.pack('<4B6sBHHHH', 0, 15, 6, 3, bytes(i for i in address), addr_type, conn_interval_min, conn_interval_max, timeout, latency)
    def ble_cmd_gap_end_procedure(self):
        return struct.pack('<4B', 0, 0, 6, 4)
    def ble_cmd_gap_connect_selective(self, conn_interval_min, conn_interval_max, timeout, latency):
        return struct.pack('<4BHHHH', 0, 8, 6, 5, conn_interval_min, conn_interval_max, timeout, latency)
    def ble_cmd_gap_set_filtering(self, scan_policy, adv_policy, scan_duplicate_filtering):
        return struct.pack('<4BBBB', 0, 3, 6, 6, scan_policy, adv_policy, scan_duplicate_filtering)
    def ble_cmd_gap_set_scan_parameters(self, scan_interval, scan_window, active):
        return struct.pack('<4BHHB', 0, 5, 6, 7, scan_interval, scan_window, active)
    def ble_cmd_gap_set_adv_parameters(self, adv_interval_min, adv_interval_max, adv_channels):
        return struct.pack('<4BHHB', 0, 5, 6, 8, adv_interval_min, adv_interval_max, adv_channels)
    def ble_cmd_gap_set_adv_data(self, set_scanrsp, adv_data):
        return struct.pack('<4BBB' + str(len(adv_data)) + 's', 0, 2 + len(adv_data), 6, 9, set_scanrsp, len(adv_data), bytes(i for i in adv_data))
    def ble_cmd_gap_set_directed_connectable_mode(self, address, addr_type):
        return struct.pack('<4B6sB', 0, 7, 6, 10, bytes(i for i in address), addr_type)
    def ble_cmd_hardware_io_port_config_irq(self, port, enable_bits, falling_edge):
        return struct.pack('<4BBBB', 0, 3, 7, 0, port, enable_bits, falling_edge)
    def ble_cmd_hardware_set_soft_timer(self, time, handle, single_shot):
        return struct.pack('<4BIBB', 0, 6, 7, 1, time, handle, single_shot)
    def ble_cmd_hardware_adc_read(self, input, decimation, reference_selection):
        return struct.pack('<4BBBB', 0, 3, 7, 2, input, decimation, reference_selection)
    def ble_cmd_hardware_io_port_config_direction(self, port, direction):
        return struct.pack('<4BBB', 0, 2, 7, 3, port, direction)
    def ble_cmd_hardware_io_port_config_function(self, port, function):
        return struct.pack('<4BBB', 0, 2, 7, 4, port, function)
    def ble_cmd_hardware_io_port_config_pull(self, port, tristate_mask, pull_up):
        return struct.pack('<4BBBB', 0, 3, 7, 5, port, tristate_mask, pull_up)
    def ble_cmd_hardware_io_port_write(self, port, mask, data):
        return struct.pack('<4BBBB', 0, 3, 7, 6, port, mask, data)
    def ble_cmd_hardware_io_port_read(self, port, mask):
        return struct.pack('<4BBB', 0, 2, 7, 7, port, mask)
    def ble_cmd_hardware_spi_config(self, channel, polarity, phase, bit_order, baud_e, baud_m):
        return struct.pack('<4BBBBBBB', 0, 6, 7, 8, channel, polarity, phase, bit_order, baud_e, baud_m)
    def ble_cmd_hardware_spi_transfer(self, channel, data):
        return struct.pack('<4BBB' + str(len(data)) + 's', 0, 2 + len(data), 7, 9, channel, len(data), bytes(i for i in data))
    def ble_cmd_hardware_i2c_read(self, address, stop, length):
        return struct.pack('<4BBBB', 0, 3, 7, 10, address, stop, length)
    def ble_cmd_hardware_i2c_write(self, address, stop, data):
        return struct.pack('<4BBBB' + str(len(data)) + 's', 0, 3 + len(data), 7, 11, address, stop, len(data), bytes(i for i in data))
    def ble_cmd_hardware_set_txpower(self, power):
        return struct.pack('<4BB', 0, 1, 7, 12, power)
    def ble_cmd_hardware_timer_comparator(self, timer, channel, mode, comparator_value):
        return struct.pack('<4BBBBH', 0, 5, 7, 13, timer, channel, mode, comparator_value)
    def ble_cmd_test_phy_tx(self, channel, length, type):
        return struct.pack('<4BBBB', 0, 3, 8, 0, channel, length, type)
    def ble_cmd_test_phy_rx(self, channel):
        return struct.pack('<4BB', 0, 1, 8, 1, channel)
    def ble_cmd_test_phy_end(self):
        return struct.pack('<4B', 0, 0, 8, 2)
    def ble_cmd_test_phy_reset(self):
        return struct.pack('<4B', 0, 0, 8, 3)
    def ble_cmd_test_get_channel_map(self):
        return struct.pack('<4B', 0, 0, 8, 4)
    def ble_cmd_test_debug(self, input):
        return struct.pack('<4BB' + str(len(input)) + 's', 0, 1 + len(input), 8, 5, len(input), bytes(i for i in input))

    ble_rsp_system_reset = BGAPIEvent()
    ble_rsp_system_hello = BGAPIEvent()
    ble_rsp_system_address_get = BGAPIEvent()
    ble_rsp_system_reg_write = BGAPIEvent()
    ble_rsp_system_reg_read = BGAPIEvent()
    ble_rsp_system_get_counters = BGAPIEvent()
    ble_rsp_system_get_connections = BGAPIEvent()
    ble_rsp_system_read_memory = BGAPIEvent()
    ble_rsp_system_get_info = BGAPIEvent()
    ble_rsp_system_endpoint_tx = BGAPIEvent()
    ble_rsp_system_whitelist_append = BGAPIEvent()
    ble_rsp_system_whitelist_remove = BGAPIEvent()
    ble_rsp_system_whitelist_clear = BGAPIEvent()
    ble_rsp_system_endpoint_rx = BGAPIEvent()
    ble_rsp_system_endpoint_set_watermarks = BGAPIEvent()
    ble_rsp_flash_ps_defrag = BGAPIEvent()
    ble_rsp_flash_ps_dump = BGAPIEvent()
    ble_rsp_flash_ps_erase_all = BGAPIEvent()
    ble_rsp_flash_ps_save = BGAPIEvent()
    ble_rsp_flash_ps_load = BGAPIEvent()
    ble_rsp_flash_ps_erase = BGAPIEvent()
    ble_rsp_flash_erase_page = BGAPIEvent()
    ble_rsp_flash_write_words = BGAPIEvent()
    ble_rsp_attributes_write = BGAPIEvent()
    ble_rsp_attributes_read = BGAPIEvent()
    ble_rsp_attributes_read_type = BGAPIEvent()
    ble_rsp_attributes_user_read_response = BGAPIEvent()
    ble_rsp_attributes_user_write_response = BGAPIEvent()
    ble_rsp_connection_disconnect = BGAPIEvent()
    ble_rsp_connection_get_rssi = BGAPIEvent()
    ble_rsp_connection_update = BGAPIEvent()
    ble_rsp_connection_version_update = BGAPIEvent()
    ble_rsp_connection_channel_map_get = BGAPIEvent()
    ble_rsp_connection_channel_map_set = BGAPIEvent()
    ble_rsp_connection_features_get = BGAPIEvent()
    ble_rsp_connection_get_status = BGAPIEvent()
    ble_rsp_connection_raw_tx = BGAPIEvent()
    ble_rsp_attclient_find_by_type_value = BGAPIEvent()
    ble_rsp_attclient_read_by_group_type = BGAPIEvent()
    ble_rsp_attclient_read_by_type = BGAPIEvent()
    ble_rsp_attclient_find_information = BGAPIEvent()
    ble_rsp_attclient_read_by_handle = BGAPIEvent()
    ble_rsp_attclient_attribute_write = BGAPIEvent()
    ble_rsp_attclient_write_command = BGAPIEvent()
    ble_rsp_attclient_indicate_confirm = BGAPIEvent()
    ble_rsp_attclient_read_long = BGAPIEvent()
    ble_rsp_attclient_prepare_write = BGAPIEvent()
    ble_rsp_attclient_execute_write = BGAPIEvent()
    ble_rsp_attclient_read_multiple = BGAPIEvent()
    ble_rsp_sm_encrypt_start = BGAPIEvent()
    ble_rsp_sm_set_bondable_mode = BGAPIEvent()
    ble_rsp_sm_delete_bonding = BGAPIEvent()
    ble_rsp_sm_set_parameters = BGAPIEvent()
    ble_rsp_sm_passkey_entry = BGAPIEvent()
    ble_rsp_sm_get_bonds = BGAPIEvent()
    ble_rsp_sm_set_oob_data = BGAPIEvent()
    ble_rsp_gap_set_privacy_flags = BGAPIEvent()
    ble_rsp_gap_set_mode = BGAPIEvent()
    ble_rsp_gap_discover = BGAPIEvent()
    ble_rsp_gap_connect_direct = BGAPIEvent()
    ble_rsp_gap_end_procedure = BGAPIEvent()
    ble_rsp_gap_connect_selective = BGAPIEvent()
    ble_rsp_gap_set_filtering = BGAPIEvent()
    ble_rsp_gap_set_scan_parameters = BGAPIEvent()
    ble_rsp_gap_set_adv_parameters = BGAPIEvent()
    ble_rsp_gap_set_adv_data = BGAPIEvent()
    ble_rsp_gap_set_directed_connectable_mode = BGAPIEvent()
    ble_rsp_hardware_io_port_config_irq = BGAPIEvent()
    ble_rsp_hardware_set_soft_timer = BGAPIEvent()
    ble_rsp_hardware_adc_read = BGAPIEvent()
    ble_rsp_hardware_io_port_config_direction = BGAPIEvent()
    ble_rsp_hardware_io_port_config_function = BGAPIEvent()
    ble_rsp_hardware_io_port_config_pull = BGAPIEvent()
    ble_rsp_hardware_io_port_write = BGAPIEvent()
    ble_rsp_hardware_io_port_read = BGAPIEvent()
    ble_rsp_hardware_spi_config = BGAPIEvent()
    ble_rsp_hardware_spi_transfer = BGAPIEvent()
    ble_rsp_hardware_i2c_read = BGAPIEvent()
    ble_rsp_hardware_i2c_write = BGAPIEvent()
    ble_rsp_hardware_set_txpower = BGAPIEvent()
    ble_rsp_hardware_timer_comparator = BGAPIEvent()
    ble_rsp_test_phy_tx = BGAPIEvent()
    ble_rsp_test_phy_rx = BGAPIEvent()
    ble_rsp_test_phy_end = BGAPIEvent()
    ble_rsp_test_phy_reset = BGAPIEvent()
    ble_rsp_test_get_channel_map = BGAPIEvent()
    ble_rsp_test_debug = BGAPIEvent()

    ble_evt_system_boot = BGAPIEvent()
    ble_evt_system_debug = BGAPIEvent()
    ble_evt_system_endpoint_watermark_rx = BGAPIEvent()
    ble_evt_system_endpoint_watermark_tx = BGAPIEvent()
    ble_evt_system_script_failure = BGAPIEvent()
    ble_evt_system_no_license_key = BGAPIEvent()
    ble_evt_flash_ps_key = BGAPIEvent()
    ble_evt_attributes_value = BGAPIEvent()
    ble_evt_attributes_user_read_request = BGAPIEvent()
    ble_evt_attributes_status = BGAPIEvent()
    ble_evt_connection_status = BGAPIEvent()
    ble_evt_connection_version_ind = BGAPIEvent()
    ble_evt_connection_feature_ind = BGAPIEvent()
    ble_evt_connection_raw_rx = BGAPIEvent()
    ble_evt_connection_disconnected = BGAPIEvent()
    ble_evt_attclient_indicated = BGAPIEvent()
    ble_evt_attclient_procedure_completed = BGAPIEvent()
    ble_evt_attclient_group_found = BGAPIEvent()
    ble_evt_attclient_attribute_found = BGAPIEvent()
    ble_evt_attclient_find_information_found = BGAPIEvent()
    ble_evt_attclient_attribute_value = BGAPIEvent()
    ble_evt_attclient_read_multiple_response = BGAPIEvent()
    ble_evt_sm_smp_data = BGAPIEvent()
    ble_evt_sm_bonding_fail = BGAPIEvent()
    ble_evt_sm_passkey_display = BGAPIEvent()
    ble_evt_sm_passkey_request = BGAPIEvent()
    ble_evt_sm_bond_status = BGAPIEvent()
    ble_evt_gap_scan_response = BGAPIEvent()
    ble_evt_gap_mode_changed = BGAPIEvent()
    ble_evt_hardware_io_port_status = BGAPIEvent()
    ble_evt_hardware_soft_timer = BGAPIEvent()
    ble_evt_hardware_adc_result = BGAPIEvent()

    def wifi_cmd_dfu_reset(self, dfu):
        return struct.pack('<4BB', 0, 1, 0, 0, dfu)
    def wifi_cmd_dfu_flash_set_address(self, address):
        return struct.pack('<4BI', 0, 4, 0, 1, address)
    def wifi_cmd_dfu_flash_upload(self):
        return struct.pack('<4BB' + str(len(data)) + 's', 0, 1 + len(data), 0, 2, data, len(data), bytes(i for i in data))
    def wifi_cmd_dfu_flash_upload_finish(self):
        return struct.pack('<4B', 0, 0, 0, 3)
    def wifi_cmd_system_sync(self):
        return struct.pack('<4B', 0, 0, 1, 0)
    def wifi_cmd_system_reset(self, dfu):
        return struct.pack('<4BB', 0, 1, 1, 1, dfu)
    def wifi_cmd_system_hello(self):
        return struct.pack('<4B', 0, 0, 1, 2)
    def wifi_cmd_system_set_max_power_saving_state(self, state):
        return struct.pack('<4BB', 0, 1, 1, 3, state)
    def wifi_cmd_config_get_mac(self, hw_interface):
        return struct.pack('<4BB', 0, 1, 2, 0, hw_interface)
    def wifi_cmd_config_set_mac(self, hw_interface):
        return struct.pack('<4BB', 0, 1, 2, 1, hw_interface, mac)
    def wifi_cmd_sme_wifi_on(self):
        return struct.pack('<4B', 0, 0, 3, 0)
    def wifi_cmd_sme_wifi_off(self):
        return struct.pack('<4B', 0, 0, 3, 1)
    def wifi_cmd_sme_power_on(self, enable):
        return struct.pack('<4BB', 0, 1, 3, 2, enable)
    def wifi_cmd_sme_start_scan(self, hw_interface):
        return struct.pack('<4BBB' + str(len(chList)) + 's', 0, 2 + len(chList), 3, 3, hw_interface, chList, len(chList), bytes(i for i in chList))
    def wifi_cmd_sme_stop_scan(self):
        return struct.pack('<4B', 0, 0, 3, 4)
    def wifi_cmd_sme_set_password(self):
        return struct.pack('<4BB' + str(len(password)) + 's', 0, 1 + len(password), 3, 5, password, len(password), bytes(i for i in password))
    def wifi_cmd_sme_connect_bssid(self):
        return struct.pack('<4B', 0, 0, 3, 6, bssid)
    def wifi_cmd_sme_connect_ssid(self):
        return struct.pack('<4BB' + str(len(ssid)) + 's', 0, 1 + len(ssid), 3, 7, ssid, len(ssid), bytes(i for i in ssid))
    def wifi_cmd_sme_disconnect(self):
        return struct.pack('<4B', 0, 0, 3, 8)
    def wifi_cmd_sme_set_scan_channels(self, hw_interface):
        return struct.pack('<4BBB' + str(len(chList)) + 's', 0, 2 + len(chList), 3, 9, hw_interface, chList, len(chList), bytes(i for i in chList))
    def wifi_cmd_tcpip_start_tcp_server(self, port, default_destination):
        return struct.pack('<4BHb', 0, 3, 4, 0, port, default_destination)
    def wifi_cmd_tcpip_tcp_connect(self, port, routing):
        return struct.pack('<4BHb', 0, 3, 4, 1, address, port, routing)
    def wifi_cmd_tcpip_start_udp_server(self, port, default_destination):
        return struct.pack('<4BHb', 0, 3, 4, 2, port, default_destination)
    def wifi_cmd_tcpip_udp_connect(self, port, routing):
        return struct.pack('<4BHb', 0, 3, 4, 3, address, port, routing)
    def wifi_cmd_tcpip_configure(self, use_dhcp):
        return struct.pack('<4BB', 0, 1, 4, 4, address, netmask, gateway, use_dhcp)
    def wifi_cmd_tcpip_dns_configure(self, index):
        return struct.pack('<4BB', 0, 1, 4, 5, index, address)
    def wifi_cmd_tcpip_dns_gethostbyname(self):
        return struct.pack('<4BB' + str(len(name)) + 's', 0, 1 + len(name), 4, 6, name, len(name), bytes(i for i in name))
    def wifi_cmd_endpoint_send(self, endpoint):
        return struct.pack('<4BBB' + str(len(data)) + 's', 0, 2 + len(data), 5, 0, endpoint, data, len(data), bytes(i for i in data))
    def wifi_cmd_endpoint_set_streaming(self, endpoint, streaming):
        return struct.pack('<4BBB', 0, 2, 5, 1, endpoint, streaming)
    def wifi_cmd_endpoint_set_active(self, endpoint, active):
        return struct.pack('<4BBB', 0, 2, 5, 2, endpoint, active)
    def wifi_cmd_endpoint_set_streaming_destination(self, endpoint, streaming_destination):
        return struct.pack('<4BBb', 0, 2, 5, 3, endpoint, streaming_destination)
    def wifi_cmd_endpoint_close(self, endpoint):
        return struct.pack('<4BB', 0, 1, 5, 4, endpoint)
    def wifi_cmd_hardware_set_soft_timer(self, time, handle, single_shot):
        return struct.pack('<4BIBB', 0, 6, 6, 0, time, handle, single_shot)
    def wifi_cmd_hardware_external_interrupt_config(self, enable, polarity):
        return struct.pack('<4BBB', 0, 2, 6, 1, enable, polarity)
    def wifi_cmd_hardware_change_notification_config(self, enable):
        return struct.pack('<4BI', 0, 4, 6, 2, enable)
    def wifi_cmd_hardware_change_notification_pullup(self, pullup):
        return struct.pack('<4BI', 0, 4, 6, 3, pullup)
    def wifi_cmd_hardware_io_port_config_direction(self, port, mask, direction):
        return struct.pack('<4BBHH', 0, 5, 6, 4, port, mask, direction)
    def wifi_cmd_hardware_io_port_config_open_drain(self, port, mask, open_drain):
        return struct.pack('<4BBHH', 0, 5, 6, 5, port, mask, open_drain)
    def wifi_cmd_hardware_io_port_write(self, port, mask, data):
        return struct.pack('<4BBHH', 0, 5, 6, 6, port, mask, data)
    def wifi_cmd_hardware_io_port_read(self, port, mask):
        return struct.pack('<4BBH', 0, 3, 6, 7, port, mask)
    def wifi_cmd_hardware_output_compare(self, index, bit32, timer, mode, compare_value):
        return struct.pack('<4BBBBBI', 0, 8, 6, 8, index, bit32, timer, mode, compare_value)
    def wifi_cmd_hardware_adc_read(self, input):
        return struct.pack('<4BB', 0, 1, 6, 9, input)
    def wifi_cmd_flash_ps_defrag(self):
        return struct.pack('<4B', 0, 0, 7, 0)
    def wifi_cmd_flash_ps_dump(self):
        return struct.pack('<4B', 0, 0, 7, 1)
    def wifi_cmd_flash_ps_erase_all(self):
        return struct.pack('<4B', 0, 0, 7, 2)
    def wifi_cmd_flash_ps_save(self, key):
        return struct.pack('<4BHB' + str(len(value)) + 's', 0, 3 + len(value), 7, 3, key, value, len(value), bytes(i for i in value))
    def wifi_cmd_flash_ps_load(self, key):
        return struct.pack('<4BH', 0, 2, 7, 4, key)
    def wifi_cmd_flash_ps_erase(self, key):
        return struct.pack('<4BH', 0, 2, 7, 5, key)
    def wifi_cmd_i2c_start_read(self, endpoint, slave_address, length):
        return struct.pack('<4BBHB', 0, 4, 8, 0, endpoint, slave_address, length)
    def wifi_cmd_i2c_start_write(self, endpoint, slave_address):
        return struct.pack('<4BBH', 0, 3, 8, 1, endpoint, slave_address)
    def wifi_cmd_i2c_stop(self, endpoint):
        return struct.pack('<4BB', 0, 1, 8, 2, endpoint)

    wifi_rsp_dfu_reset = BGAPIEvent()
    wifi_rsp_dfu_flash_set_address = BGAPIEvent()
    wifi_rsp_dfu_flash_upload = BGAPIEvent()
    wifi_rsp_dfu_flash_upload_finish = BGAPIEvent()
    wifi_rsp_system_sync = BGAPIEvent()
    wifi_rsp_system_reset = BGAPIEvent()
    wifi_rsp_system_hello = BGAPIEvent()
    wifi_rsp_system_set_max_power_saving_state = BGAPIEvent()
    wifi_rsp_config_get_mac = BGAPIEvent()
    wifi_rsp_config_set_mac = BGAPIEvent()
    wifi_rsp_sme_wifi_on = BGAPIEvent()
    wifi_rsp_sme_wifi_off = BGAPIEvent()
    wifi_rsp_sme_power_on = BGAPIEvent()
    wifi_rsp_sme_start_scan = BGAPIEvent()
    wifi_rsp_sme_stop_scan = BGAPIEvent()
    wifi_rsp_sme_set_password = BGAPIEvent()
    wifi_rsp_sme_connect_bssid = BGAPIEvent()
    wifi_rsp_sme_connect_ssid = BGAPIEvent()
    wifi_rsp_sme_disconnect = BGAPIEvent()
    wifi_rsp_sme_set_scan_channels = BGAPIEvent()
    wifi_rsp_tcpip_start_tcp_server = BGAPIEvent()
    wifi_rsp_tcpip_tcp_connect = BGAPIEvent()
    wifi_rsp_tcpip_start_udp_server = BGAPIEvent()
    wifi_rsp_tcpip_udp_connect = BGAPIEvent()
    wifi_rsp_tcpip_configure = BGAPIEvent()
    wifi_rsp_tcpip_dns_configure = BGAPIEvent()
    wifi_rsp_tcpip_dns_gethostbyname = BGAPIEvent()
    wifi_rsp_endpoint_send = BGAPIEvent()
    wifi_rsp_endpoint_set_streaming = BGAPIEvent()
    wifi_rsp_endpoint_set_active = BGAPIEvent()
    wifi_rsp_endpoint_set_streaming_destination = BGAPIEvent()
    wifi_rsp_endpoint_close = BGAPIEvent()
    wifi_rsp_hardware_set_soft_timer = BGAPIEvent()
    wifi_rsp_hardware_external_interrupt_config = BGAPIEvent()
    wifi_rsp_hardware_change_notification_config = BGAPIEvent()
    wifi_rsp_hardware_change_notification_pullup = BGAPIEvent()
    wifi_rsp_hardware_io_port_config_direction = BGAPIEvent()
    wifi_rsp_hardware_io_port_config_open_drain = BGAPIEvent()
    wifi_rsp_hardware_io_port_write = BGAPIEvent()
    wifi_rsp_hardware_io_port_read = BGAPIEvent()
    wifi_rsp_hardware_output_compare = BGAPIEvent()
    wifi_rsp_hardware_adc_read = BGAPIEvent()
    wifi_rsp_flash_ps_defrag = BGAPIEvent()
    wifi_rsp_flash_ps_dump = BGAPIEvent()
    wifi_rsp_flash_ps_erase_all = BGAPIEvent()
    wifi_rsp_flash_ps_save = BGAPIEvent()
    wifi_rsp_flash_ps_load = BGAPIEvent()
    wifi_rsp_flash_ps_erase = BGAPIEvent()
    wifi_rsp_i2c_start_read = BGAPIEvent()
    wifi_rsp_i2c_start_write = BGAPIEvent()
    wifi_rsp_i2c_stop = BGAPIEvent()

    wifi_evt_dfu_boot = BGAPIEvent()
    wifi_evt_system_boot = BGAPIEvent()
    wifi_evt_system_state = BGAPIEvent()
    wifi_evt_system_sw_exception = BGAPIEvent()
    wifi_evt_system_power_saving_state = BGAPIEvent()
    wifi_evt_config_mac_address = BGAPIEvent()
    wifi_evt_sme_wifi_is_on = BGAPIEvent()
    wifi_evt_sme_wifi_is_off = BGAPIEvent()
    wifi_evt_sme_scan_result = BGAPIEvent()
    wifi_evt_sme_scan_result_drop = BGAPIEvent()
    wifi_evt_sme_scanned = BGAPIEvent()
    wifi_evt_sme_connected = BGAPIEvent()
    wifi_evt_sme_disconnected = BGAPIEvent()
    wifi_evt_sme_interface_status = BGAPIEvent()
    wifi_evt_sme_connect_failed = BGAPIEvent()
    wifi_evt_sme_connect_retry = BGAPIEvent()
    wifi_evt_tcpip_configuration = BGAPIEvent()
    wifi_evt_tcpip_dns_configuration = BGAPIEvent()
    wifi_evt_tcpip_endpoint_status = BGAPIEvent()
    wifi_evt_tcpip_dns_gethostbyname_result = BGAPIEvent()
    wifi_evt_endpoint_syntax_error = BGAPIEvent()
    wifi_evt_endpoint_data = BGAPIEvent()
    wifi_evt_endpoint_status = BGAPIEvent()
    wifi_evt_endpoint_closing = BGAPIEvent()
    wifi_evt_hardware_soft_timer = BGAPIEvent()
    wifi_evt_hardware_change_notification = BGAPIEvent()
    wifi_evt_hardware_external_interrupt = BGAPIEvent()
    wifi_evt_flash_ps_key = BGAPIEvent()

    on_busy = BGAPIEvent()
    on_idle = BGAPIEvent()
    on_timeout = BGAPIEvent()
    on_before_tx_command = BGAPIEvent()
    on_tx_command_complete = BGAPIEvent()

    bgapi_rx_buffer = b""
    bgapi_rx_expected_length = 0
    busy = False
    packet_mode = False
    debug = False

    def send_command(self, ser, packet):
        if self.packet_mode: packet = chr(len(packet) & 0xFF) + packet
        if self.debug: print('=>[ ' + ' '.join(['%02X' % b for b in packet]) + ' ]')
        self.on_before_tx_command()
        self.busy = True
        self.on_busy()
        ser.write(packet)
        self.on_tx_command_complete()

    def check_activity(self, ser, timeout=0):
        if timeout > 0:
            ser.timeout = timeout
            while 1:
                x = ser.read()
                if len(x) > 0:
                    self.parse(x)
                else: # timeout
                    self.busy = False
                    self.on_idle()
                    self.on_timeout()
                if not self.busy: # finished
                    break
        else:
            while ser.inWaiting(): self.parse(ser.read())
        return self.busy

    def parse(self, barray):
        b=barray[0]
        if len(self.bgapi_rx_buffer) == 0 and (b == 0x00 or b == 0x80 or b == 0x08 or b == 0x88):
            self.bgapi_rx_buffer+=bytes([b])
        elif len(self.bgapi_rx_buffer) == 1:
            self.bgapi_rx_buffer+=bytes([b])
            self.bgapi_rx_expected_length = 4 + (self.bgapi_rx_buffer[0] & 0x07) + self.bgapi_rx_buffer[1]
        elif len(self.bgapi_rx_buffer) > 1:
            self.bgapi_rx_buffer+=bytes([b])

        """
        BGAPI packet structure (as of 2012-11-07):
            Byte 0:
                  [7] - 1 bit, Message Type (MT)         0 = Command/Response, 1 = Event
                [6:3] - 4 bits, Technology Type (TT)     0000 = Bluetooth 4.0 single mode, 0001 = Wi-Fi
                [2:0] - 3 bits, Length High (LH)         Payload length (high bits)
            Byte 1:     8 bits, Length Low (LL)          Payload length (low bits)
            Byte 2:     8 bits, Class ID (CID)           Command class ID
            Byte 3:     8 bits, Command ID (CMD)         Command ID
            Bytes 4-n:  0 - 2048 Bytes, Payload (PL)     Up to 2048 bytes of payload
        """

        #print'%02X: %d, %d' % (b, len(self.bgapi_rx_buffer), self.bgapi_rx_expected_length)
        if self.bgapi_rx_expected_length > 0 and len(self.bgapi_rx_buffer) == self.bgapi_rx_expected_length:
            if self.debug: print('<=[ ' + ' '.join(['%02X' % b for b in self.bgapi_rx_buffer ]) + ' ]')
            packet_type, payload_length, packet_class, packet_command = self.bgapi_rx_buffer[:4]
            self.bgapi_rx_payload = self.bgapi_rx_buffer[4:]
            self.bgapi_rx_buffer = b""
            if packet_type & 0x88 == 0x00:
                # 0x00 = BLE response packet
                if packet_class == 0:
                    if packet_command == 0: # ble_rsp_system_reset
                        self.ble_rsp_system_reset({  })
                        self.busy = False
                        self.on_idle()
                    elif packet_command == 1: # ble_rsp_system_hello
                        self.ble_rsp_system_hello({  })
                    elif packet_command == 2: # ble_rsp_system_address_get
                        address = struct.unpack('<6s', self.bgapi_rx_payload[:6])[0]
                        address = address
                        self.ble_rsp_system_address_get({ 'address': address })
                    elif packet_command == 3: # ble_rsp_system_reg_write
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.ble_rsp_system_reg_write({ 'result': result })
                    elif packet_command == 4: # ble_rsp_system_reg_read
                        address, value = struct.unpack('<HB', self.bgapi_rx_payload[:3])
                        self.ble_rsp_system_reg_read({ 'address': address, 'value': value })
                    elif packet_command == 5: # ble_rsp_system_get_counters
                        txok, txretry, rxok, rxfail, mbuf = struct.unpack('<BBBBB', self.bgapi_rx_payload[:5])
                        self.ble_rsp_system_get_counters({ 'txok': txok, 'txretry': txretry, 'rxok': rxok, 'rxfail': rxfail, 'mbuf': mbuf })
                    elif packet_command == 6: # ble_rsp_system_get_connections
                        maxconn = struct.unpack('<B', self.bgapi_rx_payload[:1])[0]
                        self.ble_rsp_system_get_connections({ 'maxconn': maxconn })
                    elif packet_command == 7: # ble_rsp_system_read_memory
                        address, data_len = struct.unpack('<IB', self.bgapi_rx_payload[:5])
                        data_data = self.bgapi_rx_payload[5:]
                        self.ble_rsp_system_read_memory({ 'address': address, 'data': data_data })
                    elif packet_command == 8: # ble_rsp_system_get_info
                        major, minor, patch, build, ll_version, protocol_version, hw = struct.unpack('<HHHHHBB', self.bgapi_rx_payload[:12])
                        self.ble_rsp_system_get_info({ 'major': major, 'minor': minor, 'patch': patch, 'build': build, 'll_version': ll_version, 'protocol_version': protocol_version, 'hw': hw })
                    elif packet_command == 9: # ble_rsp_system_endpoint_tx
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.ble_rsp_system_endpoint_tx({ 'result': result })
                    elif packet_command == 10: # ble_rsp_system_whitelist_append
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.ble_rsp_system_whitelist_append({ 'result': result })
                    elif packet_command == 11: # ble_rsp_system_whitelist_remove
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.ble_rsp_system_whitelist_remove({ 'result': result })
                    elif packet_command == 12: # ble_rsp_system_whitelist_clear
                        self.ble_rsp_system_whitelist_clear({  })
                    elif packet_command == 13: # ble_rsp_system_endpoint_rx
                        result, data_len = struct.unpack('<HB', self.bgapi_rx_payload[:3])
                        data_data = self.bgapi_rx_payload[3:]
                        self.ble_rsp_system_endpoint_rx({ 'result': result, 'data': data_data })
                    elif packet_command == 14: # ble_rsp_system_endpoint_set_watermarks
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.ble_rsp_system_endpoint_set_watermarks({ 'result': result })
                elif packet_class == 1:
                    if packet_command == 0: # ble_rsp_flash_ps_defrag
                        self.ble_rsp_flash_ps_defrag({  })
                    elif packet_command == 1: # ble_rsp_flash_ps_dump
                        self.ble_rsp_flash_ps_dump({  })
                    elif packet_command == 2: # ble_rsp_flash_ps_erase_all
                        self.ble_rsp_flash_ps_erase_all({  })
                    elif packet_command == 3: # ble_rsp_flash_ps_save
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.ble_rsp_flash_ps_save({ 'result': result })
                    elif packet_command == 4: # ble_rsp_flash_ps_load
                        result, value_len = struct.unpack('<HB', self.bgapi_rx_payload[:3])
                        value_data = self.bgapi_rx_payload[3:]
                        self.ble_rsp_flash_ps_load({ 'result': result, 'value': value_data })
                    elif packet_command == 5: # ble_rsp_flash_ps_erase
                        self.ble_rsp_flash_ps_erase({  })
                    elif packet_command == 6: # ble_rsp_flash_erase_page
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.ble_rsp_flash_erase_page({ 'result': result })
                    elif packet_command == 7: # ble_rsp_flash_write_words
                        self.ble_rsp_flash_write_words({  })
                elif packet_class == 2:
                    if packet_command == 0: # ble_rsp_attributes_write
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.ble_rsp_attributes_write({ 'result': result })
                    elif packet_command == 1: # ble_rsp_attributes_read
                        handle, offset, result, value_len = struct.unpack('<HHHB', self.bgapi_rx_payload[:7])
                        value_data = self.bgapi_rx_payload[7:]
                        self.ble_rsp_attributes_read({ 'handle': handle, 'offset': offset, 'result': result, 'value': value_data })
                    elif packet_command == 2: # ble_rsp_attributes_read_type
                        handle, result, value_len = struct.unpack('<HHB', self.bgapi_rx_payload[:5])
                        value_data = self.bgapi_rx_payload[5:]
                        self.ble_rsp_attributes_read_type({ 'handle': handle, 'result': result, 'value': value_data })
                    elif packet_command == 3: # ble_rsp_attributes_user_read_response
                        self.ble_rsp_attributes_user_read_response({  })
                    elif packet_command == 4: # ble_rsp_attributes_user_write_response
                        self.ble_rsp_attributes_user_write_response({  })
                elif packet_class == 3:
                    if packet_command == 0: # ble_rsp_connection_disconnect
                        connection, result = struct.unpack('<BH', self.bgapi_rx_payload[:3])
                        self.ble_rsp_connection_disconnect({ 'connection': connection, 'result': result })
                    elif packet_command == 1: # ble_rsp_connection_get_rssi
                        connection, rssi = struct.unpack('<Bb', self.bgapi_rx_payload[:2])
                        self.ble_rsp_connection_get_rssi({ 'connection': connection, 'rssi': rssi })
                    elif packet_command == 2: # ble_rsp_connection_update
                        connection, result = struct.unpack('<BH', self.bgapi_rx_payload[:3])
                        self.ble_rsp_connection_update({ 'connection': connection, 'result': result })
                    elif packet_command == 3: # ble_rsp_connection_version_update
                        connection, result = struct.unpack('<BH', self.bgapi_rx_payload[:3])
                        self.ble_rsp_connection_version_update({ 'connection': connection, 'result': result })
                    elif packet_command == 4: # ble_rsp_connection_channel_map_get
                        connection, map_len = struct.unpack('<BB', self.bgapi_rx_payload[:2])
                        map_data = self.bgapi_rx_payload[2:]
                        self.ble_rsp_connection_channel_map_get({ 'connection': connection, 'map': map_data })
                    elif packet_command == 5: # ble_rsp_connection_channel_map_set
                        connection, result = struct.unpack('<BH', self.bgapi_rx_payload[:3])
                        self.ble_rsp_connection_channel_map_set({ 'connection': connection, 'result': result })
                    elif packet_command == 6: # ble_rsp_connection_features_get
                        connection, result = struct.unpack('<BH', self.bgapi_rx_payload[:3])
                        self.ble_rsp_connection_features_get({ 'connection': connection, 'result': result })
                    elif packet_command == 7: # ble_rsp_connection_get_status
                        connection = struct.unpack('<B', self.bgapi_rx_payload[:1])[0]
                        self.ble_rsp_connection_get_status({ 'connection': connection })
                    elif packet_command == 8: # ble_rsp_connection_raw_tx
                        connection = struct.unpack('<B', self.bgapi_rx_payload[:1])[0]
                        self.ble_rsp_connection_raw_tx({ 'connection': connection })
                elif packet_class == 4:
                    if packet_command == 0: # ble_rsp_attclient_find_by_type_value
                        connection, result = struct.unpack('<BH', self.bgapi_rx_payload[:3])
                        self.ble_rsp_attclient_find_by_type_value({ 'connection': connection, 'result': result })
                    elif packet_command == 1: # ble_rsp_attclient_read_by_group_type
                        connection, result = struct.unpack('<BH', self.bgapi_rx_payload[:3])
                        self.ble_rsp_attclient_read_by_group_type({ 'connection': connection, 'result': result })
                    elif packet_command == 2: # ble_rsp_attclient_read_by_type
                        connection, result = struct.unpack('<BH', self.bgapi_rx_payload[:3])
                        self.ble_rsp_attclient_read_by_type({ 'connection': connection, 'result': result })
                    elif packet_command == 3: # ble_rsp_attclient_find_information
                        connection, result = struct.unpack('<BH', self.bgapi_rx_payload[:3])
                        self.ble_rsp_attclient_find_information({ 'connection': connection, 'result': result })
                    elif packet_command == 4: # ble_rsp_attclient_read_by_handle
                        connection, result = struct.unpack('<BH', self.bgapi_rx_payload[:3])
                        self.ble_rsp_attclient_read_by_handle({ 'connection': connection, 'result': result })
                    elif packet_command == 5: # ble_rsp_attclient_attribute_write
                        connection, result = struct.unpack('<BH', self.bgapi_rx_payload[:3])
                        self.ble_rsp_attclient_attribute_write({ 'connection': connection, 'result': result })
                    elif packet_command == 6: # ble_rsp_attclient_write_command
                        connection, result = struct.unpack('<BH', self.bgapi_rx_payload[:3])
                        self.ble_rsp_attclient_write_command({ 'connection': connection, 'result': result })
                    elif packet_command == 7: # ble_rsp_attclient_indicate_confirm
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.ble_rsp_attclient_indicate_confirm({ 'result': result })
                    elif packet_command == 8: # ble_rsp_attclient_read_long
                        connection, result = struct.unpack('<BH', self.bgapi_rx_payload[:3])
                        self.ble_rsp_attclient_read_long({ 'connection': connection, 'result': result })
                    elif packet_command == 9: # ble_rsp_attclient_prepare_write
                        connection, result = struct.unpack('<BH', self.bgapi_rx_payload[:3])
                        self.ble_rsp_attclient_prepare_write({ 'connection': connection, 'result': result })
                    elif packet_command == 10: # ble_rsp_attclient_execute_write
                        connection, result = struct.unpack('<BH', self.bgapi_rx_payload[:3])
                        self.ble_rsp_attclient_execute_write({ 'connection': connection, 'result': result })
                    elif packet_command == 11: # ble_rsp_attclient_read_multiple
                        connection, result = struct.unpack('<BH', self.bgapi_rx_payload[:3])
                        self.ble_rsp_attclient_read_multiple({ 'connection': connection, 'result': result })
                elif packet_class == 5:
                    if packet_command == 0: # ble_rsp_sm_encrypt_start
                        handle, result = struct.unpack('<BH', self.bgapi_rx_payload[:3])
                        self.ble_rsp_sm_encrypt_start({ 'handle': handle, 'result': result })
                    elif packet_command == 1: # ble_rsp_sm_set_bondable_mode
                        self.ble_rsp_sm_set_bondable_mode({  })
                    elif packet_command == 2: # ble_rsp_sm_delete_bonding
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.ble_rsp_sm_delete_bonding({ 'result': result })
                    elif packet_command == 3: # ble_rsp_sm_set_parameters
                        self.ble_rsp_sm_set_parameters({  })
                    elif packet_command == 4: # ble_rsp_sm_passkey_entry
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.ble_rsp_sm_passkey_entry({ 'result': result })
                    elif packet_command == 5: # ble_rsp_sm_get_bonds
                        bonds = struct.unpack('<B', self.bgapi_rx_payload[:1])[0]
                        self.ble_rsp_sm_get_bonds({ 'bonds': bonds })
                    elif packet_command == 6: # ble_rsp_sm_set_oob_data
                        self.ble_rsp_sm_set_oob_data({  })
                elif packet_class == 6:
                    if packet_command == 0: # ble_rsp_gap_set_privacy_flags
                        self.ble_rsp_gap_set_privacy_flags({  })
                    elif packet_command == 1: # ble_rsp_gap_set_mode
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.ble_rsp_gap_set_mode({ 'result': result })
                    elif packet_command == 2: # ble_rsp_gap_discover
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.ble_rsp_gap_discover({ 'result': result })
                    elif packet_command == 3: # ble_rsp_gap_connect_direct
                        result, connection_handle = struct.unpack('<HB', self.bgapi_rx_payload[:3])
                        self.ble_rsp_gap_connect_direct({ 'result': result, 'connection_handle': connection_handle })
                    elif packet_command == 4: # ble_rsp_gap_end_procedure
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.ble_rsp_gap_end_procedure({ 'result': result })
                    elif packet_command == 5: # ble_rsp_gap_connect_selective
                        result, connection_handle = struct.unpack('<HB', self.bgapi_rx_payload[:3])
                        self.ble_rsp_gap_connect_selective({ 'result': result, 'connection_handle': connection_handle })
                    elif packet_command == 6: # ble_rsp_gap_set_filtering
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.ble_rsp_gap_set_filtering({ 'result': result })
                    elif packet_command == 7: # ble_rsp_gap_set_scan_parameters
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.ble_rsp_gap_set_scan_parameters({ 'result': result })
                    elif packet_command == 8: # ble_rsp_gap_set_adv_parameters
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.ble_rsp_gap_set_adv_parameters({ 'result': result })
                    elif packet_command == 9: # ble_rsp_gap_set_adv_data
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.ble_rsp_gap_set_adv_data({ 'result': result })
                    elif packet_command == 10: # ble_rsp_gap_set_directed_connectable_mode
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.ble_rsp_gap_set_directed_connectable_mode({ 'result': result })
                elif packet_class == 7:
                    if packet_command == 0: # ble_rsp_hardware_io_port_config_irq
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.ble_rsp_hardware_io_port_config_irq({ 'result': result })
                    elif packet_command == 1: # ble_rsp_hardware_set_soft_timer
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.ble_rsp_hardware_set_soft_timer({ 'result': result })
                    elif packet_command == 2: # ble_rsp_hardware_adc_read
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.ble_rsp_hardware_adc_read({ 'result': result })
                    elif packet_command == 3: # ble_rsp_hardware_io_port_config_direction
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.ble_rsp_hardware_io_port_config_direction({ 'result': result })
                    elif packet_command == 4: # ble_rsp_hardware_io_port_config_function
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.ble_rsp_hardware_io_port_config_function({ 'result': result })
                    elif packet_command == 5: # ble_rsp_hardware_io_port_config_pull
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.ble_rsp_hardware_io_port_config_pull({ 'result': result })
                    elif packet_command == 6: # ble_rsp_hardware_io_port_write
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.ble_rsp_hardware_io_port_write({ 'result': result })
                    elif packet_command == 7: # ble_rsp_hardware_io_port_read
                        result, port, data = struct.unpack('<HBB', self.bgapi_rx_payload[:4])
                        self.ble_rsp_hardware_io_port_read({ 'result': result, 'port': port, 'data': data })
                    elif packet_command == 8: # ble_rsp_hardware_spi_config
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.ble_rsp_hardware_spi_config({ 'result': result })
                    elif packet_command == 9: # ble_rsp_hardware_spi_transfer
                        result, channel, data_len = struct.unpack('<HBB', self.bgapi_rx_payload[:4])
                        data_data = self.bgapi_rx_payload[4:]
                        self.ble_rsp_hardware_spi_transfer({ 'result': result, 'channel': channel, 'data': data_data })
                    elif packet_command == 10: # ble_rsp_hardware_i2c_read
                        result, data_len = struct.unpack('<HB', self.bgapi_rx_payload[:3])
                        data_data = self.bgapi_rx_payload[3:]
                        self.ble_rsp_hardware_i2c_read({ 'result': result, 'data': data_data })
                    elif packet_command == 11: # ble_rsp_hardware_i2c_write
                        written = struct.unpack('<B', self.bgapi_rx_payload[:1])[0]
                        self.ble_rsp_hardware_i2c_write({ 'written': written })
                    elif packet_command == 12: # ble_rsp_hardware_set_txpower
                        self.ble_rsp_hardware_set_txpower({  })
                    elif packet_command == 13: # ble_rsp_hardware_timer_comparator
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.ble_rsp_hardware_timer_comparator({ 'result': result })
                elif packet_class == 8:
                    if packet_command == 0: # ble_rsp_test_phy_tx
                        self.ble_rsp_test_phy_tx({  })
                    elif packet_command == 1: # ble_rsp_test_phy_rx
                        self.ble_rsp_test_phy_rx({  })
                    elif packet_command == 2: # ble_rsp_test_phy_end
                        counter = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.ble_rsp_test_phy_end({ 'counter': counter })
                    elif packet_command == 3: # ble_rsp_test_phy_reset
                        self.ble_rsp_test_phy_reset({  })
                    elif packet_command == 4: # ble_rsp_test_get_channel_map
                        channel_map_len = struct.unpack('<B', self.bgapi_rx_payload[:1])[0]
                        channel_map_data = self.bgapi_rx_payload[1:]
                        self.ble_rsp_test_get_channel_map({ 'channel_map': channel_map_data })
                    elif packet_command == 5: # ble_rsp_test_debug
                        output_len = struct.unpack('<B', self.bgapi_rx_payload[:1])[0]
                        output_data = self.bgapi_rx_payload[1:]
                        self.ble_rsp_test_debug({ 'output': output_data })
                self.busy = False
                self.on_idle()
            elif packet_type & 0x88 == 0x80:
                # 0x80 = BLE event packet
                if packet_class == 0:
                    if packet_command == 0: # ble_evt_system_boot
                        major, minor, patch, build, ll_version, protocol_version, hw = struct.unpack('<HHHHHBB', self.bgapi_rx_payload[:12])
                        self.ble_evt_system_boot({ 'major': major, 'minor': minor, 'patch': patch, 'build': build, 'll_version': ll_version, 'protocol_version': protocol_version, 'hw': hw })
                        self.busy = False
                        self.on_idle()
                    elif packet_command == 1: # ble_evt_system_debug
                        data_len = struct.unpack('<B', self.bgapi_rx_payload[:1])[0]
                        data_data = self.bgapi_rx_payload[1:]
                        self.ble_evt_system_debug({ 'data': data_data })
                    elif packet_command == 2: # ble_evt_system_endpoint_watermark_rx
                        endpoint, data = struct.unpack('<BB', self.bgapi_rx_payload[:2])
                        self.ble_evt_system_endpoint_watermark_rx({ 'endpoint': endpoint, 'data': data })
                    elif packet_command == 3: # ble_evt_system_endpoint_watermark_tx
                        endpoint, data = struct.unpack('<BB', self.bgapi_rx_payload[:2])
                        self.ble_evt_system_endpoint_watermark_tx({ 'endpoint': endpoint, 'data': data })
                    elif packet_command == 4: # ble_evt_system_script_failure
                        address, reason = struct.unpack('<HH', self.bgapi_rx_payload[:4])
                        self.ble_evt_system_script_failure({ 'address': address, 'reason': reason })
                    elif packet_command == 5: # ble_evt_system_no_license_key
                        self.ble_evt_system_no_license_key({  })
                elif packet_class == 1:
                    if packet_command == 0: # ble_evt_flash_ps_key
                        key, value_len = struct.unpack('<HB', self.bgapi_rx_payload[:3])
                        value_data = self.bgapi_rx_payload[3:]
                        self.ble_evt_flash_ps_key({ 'key': key, 'value': value_data })
                elif packet_class == 2:
                    if packet_command == 0: # ble_evt_attributes_value
                        connection, reason, handle, offset, value_len = struct.unpack('<BBHHB', self.bgapi_rx_payload[:7])
                        value_data = self.bgapi_rx_payload[7:]
                        self.ble_evt_attributes_value({ 'connection': connection, 'reason': reason, 'handle': handle, 'offset': offset, 'value': value_data })
                    elif packet_command == 1: # ble_evt_attributes_user_read_request
                        connection, handle, offset, maxsize = struct.unpack('<BHHB', self.bgapi_rx_payload[:6])
                        self.ble_evt_attributes_user_read_request({ 'connection': connection, 'handle': handle, 'offset': offset, 'maxsize': maxsize })
                    elif packet_command == 2: # ble_evt_attributes_status
                        handle, flags = struct.unpack('<HB', self.bgapi_rx_payload[:3])
                        self.ble_evt_attributes_status({ 'handle': handle, 'flags': flags })
                elif packet_class == 3:
                    if packet_command == 0: # ble_evt_connection_status
                        connection, flags, address, address_type, conn_interval, timeout, latency, bonding = struct.unpack('<BB6sBHHHB', self.bgapi_rx_payload[:16])
                        address = address
                        self.ble_evt_connection_status({ 'connection': connection, 'flags': flags, 'address': address, 'address_type': address_type, 'conn_interval': conn_interval, 'timeout': timeout, 'latency': latency, 'bonding': bonding })
                    elif packet_command == 1: # ble_evt_connection_version_ind
                        connection, vers_nr, comp_id, sub_vers_nr = struct.unpack('<BBHH', self.bgapi_rx_payload[:6])
                        self.ble_evt_connection_version_ind({ 'connection': connection, 'vers_nr': vers_nr, 'comp_id': comp_id, 'sub_vers_nr': sub_vers_nr })
                    elif packet_command == 2: # ble_evt_connection_feature_ind
                        connection, features_len = struct.unpack('<BB', self.bgapi_rx_payload[:2])
                        features_data = self.bgapi_rx_payload[2:]
                        self.ble_evt_connection_feature_ind({ 'connection': connection, 'features': features_data })
                    elif packet_command == 3: # ble_evt_connection_raw_rx
                        connection, data_len = struct.unpack('<BB', self.bgapi_rx_payload[:2])
                        data_data = self.bgapi_rx_payload[2:]
                        self.ble_evt_connection_raw_rx({ 'connection': connection, 'data': data_data })
                    elif packet_command == 4: # ble_evt_connection_disconnected
                        connection, reason = struct.unpack('<BH', self.bgapi_rx_payload[:3])
                        self.ble_evt_connection_disconnected({ 'connection': connection, 'reason': reason })
                elif packet_class == 4:
                    if packet_command == 0: # ble_evt_attclient_indicated
                        connection, attrhandle = struct.unpack('<BH', self.bgapi_rx_payload[:3])
                        self.ble_evt_attclient_indicated({ 'connection': connection, 'attrhandle': attrhandle })
                    elif packet_command == 1: # ble_evt_attclient_procedure_completed
                        connection, result, chrhandle = struct.unpack('<BHH', self.bgapi_rx_payload[:5])
                        self.ble_evt_attclient_procedure_completed({ 'connection': connection, 'result': result, 'chrhandle': chrhandle })
                    elif packet_command == 2: # ble_evt_attclient_group_found
                        connection, start, end, uuid_len = struct.unpack('<BHHB', self.bgapi_rx_payload[:6])
                        uuid_data = self.bgapi_rx_payload[6:]
                        self.ble_evt_attclient_group_found({ 'connection': connection, 'start': start, 'end': end, 'uuid': uuid_data })
                    elif packet_command == 3: # ble_evt_attclient_attribute_found
                        connection, chrdecl, value, properties, uuid_len = struct.unpack('<BHHBB', self.bgapi_rx_payload[:7])
                        uuid_data = self.bgapi_rx_payload[7:]
                        self.ble_evt_attclient_attribute_found({ 'connection': connection, 'chrdecl': chrdecl, 'value': value, 'properties': properties, 'uuid': uuid_data })
                    elif packet_command == 4: # ble_evt_attclient_find_information_found
                        connection, chrhandle, uuid_len = struct.unpack('<BHB', self.bgapi_rx_payload[:4])
                        uuid_data = self.bgapi_rx_payload[4:]
                        self.ble_evt_attclient_find_information_found({ 'connection': connection, 'chrhandle': chrhandle, 'uuid': uuid_data })
                    elif packet_command == 5: # ble_evt_attclient_attribute_value
                        connection, atthandle, type, value_len = struct.unpack('<BHBB', self.bgapi_rx_payload[:5])
                        value_data = self.bgapi_rx_payload[5:]
                        self.ble_evt_attclient_attribute_value({ 'connection': connection, 'atthandle': atthandle, 'type': type, 'value': value_data })
                    elif packet_command == 6: # ble_evt_attclient_read_multiple_response
                        connection, handles_len = struct.unpack('<BB', self.bgapi_rx_payload[:2])
                        handles_data = self.bgapi_rx_payload[2:]
                        self.ble_evt_attclient_read_multiple_response({ 'connection': connection, 'handles': handles_data })
                elif packet_class == 5:
                    if packet_command == 0: # ble_evt_sm_smp_data
                        handle, packet, data_len = struct.unpack('<BBB', self.bgapi_rx_payload[:3])
                        data_data = self.bgapi_rx_payload[3:]
                        self.ble_evt_sm_smp_data({ 'handle': handle, 'packet': packet, 'data': data_data })
                    elif packet_command == 1: # ble_evt_sm_bonding_fail
                        handle, result = struct.unpack('<BH', self.bgapi_rx_payload[:3])
                        self.ble_evt_sm_bonding_fail({ 'handle': handle, 'result': result })
                    elif packet_command == 2: # ble_evt_sm_passkey_display
                        handle, passkey = struct.unpack('<BI', self.bgapi_rx_payload[:5])
                        self.ble_evt_sm_passkey_display({ 'handle': handle, 'passkey': passkey })
                    elif packet_command == 3: # ble_evt_sm_passkey_request
                        handle = struct.unpack('<B', self.bgapi_rx_payload[:1])[0]
                        self.ble_evt_sm_passkey_request({ 'handle': handle })
                    elif packet_command == 4: # ble_evt_sm_bond_status
                        bond, keysize, mitm, keys = struct.unpack('<BBBB', self.bgapi_rx_payload[:4])
                        self.ble_evt_sm_bond_status({ 'bond': bond, 'keysize': keysize, 'mitm': mitm, 'keys': keys })
                elif packet_class == 6:
                    if packet_command == 0: # ble_evt_gap_scan_response
                        rssi, packet_type, sender, address_type, bond, data_len = struct.unpack('<bB6sBBB', self.bgapi_rx_payload[:11])
                        sender = sender
                        data_data = self.bgapi_rx_payload[11:]
                        self.ble_evt_gap_scan_response({ 'rssi': rssi, 'packet_type': packet_type, 'sender': sender, 'address_type': address_type, 'bond': bond, 'data': data_data })
                    elif packet_command == 1: # ble_evt_gap_mode_changed
                        discover, connect = struct.unpack('<BB', self.bgapi_rx_payload[:2])
                        self.ble_evt_gap_mode_changed({ 'discover': discover, 'connect': connect })
                elif packet_class == 7:
                    if packet_command == 0: # ble_evt_hardware_io_port_status
                        timestamp, port, irq, state = struct.unpack('<IBBB', self.bgapi_rx_payload[:7])
                        self.ble_evt_hardware_io_port_status({ 'timestamp': timestamp, 'port': port, 'irq': irq, 'state': state })
                    elif packet_command == 1: # ble_evt_hardware_soft_timer
                        handle = struct.unpack('<B', self.bgapi_rx_payload[:1])[0]
                        self.ble_evt_hardware_soft_timer({ 'handle': handle })
                    elif packet_command == 2: # ble_evt_hardware_adc_result
                        input, value = struct.unpack('<Bh', self.bgapi_rx_payload[:3])
                        self.ble_evt_hardware_adc_result({ 'input': input, 'value': value })
            elif packet_type & 0x88 == 0x08:
                # 0x08 = wifi response packet
                if packet_class == 0:
                    if packet_command == 0: # wifi_rsp_dfu_reset
                        self.wifi_rsp_dfu_reset({  })
                        self.busy = False
                        self.on_idle()
                    elif packet_command == 1: # wifi_rsp_dfu_flash_set_address
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.wifi_rsp_dfu_flash_set_address({ 'result': result })
                    elif packet_command == 2: # wifi_rsp_dfu_flash_upload
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.wifi_rsp_dfu_flash_upload({ 'result': result })
                    elif packet_command == 3: # wifi_rsp_dfu_flash_upload_finish
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.wifi_rsp_dfu_flash_upload_finish({ 'result': result })
                elif packet_class == 1:
                    if packet_command == 0: # wifi_rsp_system_sync
                        self.wifi_rsp_system_sync({  })
                    elif packet_command == 1: # wifi_rsp_system_reset
                        self.wifi_rsp_system_reset({  })
                    elif packet_command == 2: # wifi_rsp_system_hello
                        self.wifi_rsp_system_hello({  })
                    elif packet_command == 3: # wifi_rsp_system_set_max_power_saving_state
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.wifi_rsp_system_set_max_power_saving_state({ 'result': result })
                elif packet_class == 2:
                    if packet_command == 0: # wifi_rsp_config_get_mac
                        result, hw_interface = struct.unpack('<HB', self.bgapi_rx_payload[:3])
                        self.wifi_rsp_config_get_mac({ 'result': result, 'hw_interface': hw_interface })
                    elif packet_command == 1: # wifi_rsp_config_set_mac
                        result, hw_interface = struct.unpack('<HB', self.bgapi_rx_payload[:3])
                        self.wifi_rsp_config_set_mac({ 'result': result, 'hw_interface': hw_interface })
                elif packet_class == 3:
                    if packet_command == 0: # wifi_rsp_sme_wifi_on
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.wifi_rsp_sme_wifi_on({ 'result': result })
                    elif packet_command == 1: # wifi_rsp_sme_wifi_off
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.wifi_rsp_sme_wifi_off({ 'result': result })
                    elif packet_command == 2: # wifi_rsp_sme_power_on
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.wifi_rsp_sme_power_on({ 'result': result })
                    elif packet_command == 3: # wifi_rsp_sme_start_scan
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.wifi_rsp_sme_start_scan({ 'result': result })
                    elif packet_command == 4: # wifi_rsp_sme_stop_scan
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.wifi_rsp_sme_stop_scan({ 'result': result })
                    elif packet_command == 5: # wifi_rsp_sme_set_password
                        status = struct.unpack('<B', self.bgapi_rx_payload[:1])[0]
                        self.wifi_rsp_sme_set_password({ 'status': status })
                    elif packet_command == 6: # wifi_rsp_sme_connect_bssid
                        result, hw_interface = struct.unpack('<HB', self.bgapi_rx_payload[:3])
                        self.wifi_rsp_sme_connect_bssid({ 'result': result, 'hw_interface': hw_interface })
                    elif packet_command == 7: # wifi_rsp_sme_connect_ssid
                        result, hw_interface = struct.unpack('<HB', self.bgapi_rx_payload[:3])
                        self.wifi_rsp_sme_connect_ssid({ 'result': result, 'hw_interface': hw_interface })
                    elif packet_command == 8: # wifi_rsp_sme_disconnect
                        result, hw_interface = struct.unpack('<HB', self.bgapi_rx_payload[:3])
                        self.wifi_rsp_sme_disconnect({ 'result': result, 'hw_interface': hw_interface })
                    elif packet_command == 9: # wifi_rsp_sme_set_scan_channels
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.wifi_rsp_sme_set_scan_channels({ 'result': result })
                elif packet_class == 4:
                    if packet_command == 0: # wifi_rsp_tcpip_start_tcp_server
                        result, endpoint = struct.unpack('<HB', self.bgapi_rx_payload[:3])
                        self.wifi_rsp_tcpip_start_tcp_server({ 'result': result, 'endpoint': endpoint })
                    elif packet_command == 1: # wifi_rsp_tcpip_tcp_connect
                        result, endpoint = struct.unpack('<HB', self.bgapi_rx_payload[:3])
                        self.wifi_rsp_tcpip_tcp_connect({ 'result': result, 'endpoint': endpoint })
                    elif packet_command == 2: # wifi_rsp_tcpip_start_udp_server
                        result, endpoint = struct.unpack('<HB', self.bgapi_rx_payload[:3])
                        self.wifi_rsp_tcpip_start_udp_server({ 'result': result, 'endpoint': endpoint })
                    elif packet_command == 3: # wifi_rsp_tcpip_udp_connect
                        result, endpoint = struct.unpack('<HB', self.bgapi_rx_payload[:3])
                        self.wifi_rsp_tcpip_udp_connect({ 'result': result, 'endpoint': endpoint })
                    elif packet_command == 4: # wifi_rsp_tcpip_configure
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.wifi_rsp_tcpip_configure({ 'result': result })
                    elif packet_command == 5: # wifi_rsp_tcpip_dns_configure
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.wifi_rsp_tcpip_dns_configure({ 'result': result })
                    elif packet_command == 6: # wifi_rsp_tcpip_dns_gethostbyname
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.wifi_rsp_tcpip_dns_gethostbyname({ 'result': result })
                elif packet_class == 5:
                    if packet_command == 0: # wifi_rsp_endpoint_send
                        result, endpoint = struct.unpack('<HB', self.bgapi_rx_payload[:3])
                        self.wifi_rsp_endpoint_send({ 'result': result, 'endpoint': endpoint })
                    elif packet_command == 1: # wifi_rsp_endpoint_set_streaming
                        result, endpoint = struct.unpack('<HB', self.bgapi_rx_payload[:3])
                        self.wifi_rsp_endpoint_set_streaming({ 'result': result, 'endpoint': endpoint })
                    elif packet_command == 2: # wifi_rsp_endpoint_set_active
                        result, endpoint = struct.unpack('<HB', self.bgapi_rx_payload[:3])
                        self.wifi_rsp_endpoint_set_active({ 'result': result, 'endpoint': endpoint })
                    elif packet_command == 3: # wifi_rsp_endpoint_set_streaming_destination
                        result, endpoint = struct.unpack('<HB', self.bgapi_rx_payload[:3])
                        self.wifi_rsp_endpoint_set_streaming_destination({ 'result': result, 'endpoint': endpoint })
                    elif packet_command == 4: # wifi_rsp_endpoint_close
                        result, endpoint = struct.unpack('<HB', self.bgapi_rx_payload[:3])
                        self.wifi_rsp_endpoint_close({ 'result': result, 'endpoint': endpoint })
                elif packet_class == 6:
                    if packet_command == 0: # wifi_rsp_hardware_set_soft_timer
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.wifi_rsp_hardware_set_soft_timer({ 'result': result })
                    elif packet_command == 1: # wifi_rsp_hardware_external_interrupt_config
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.wifi_rsp_hardware_external_interrupt_config({ 'result': result })
                    elif packet_command == 2: # wifi_rsp_hardware_change_notification_config
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.wifi_rsp_hardware_change_notification_config({ 'result': result })
                    elif packet_command == 3: # wifi_rsp_hardware_change_notification_pullup
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.wifi_rsp_hardware_change_notification_pullup({ 'result': result })
                    elif packet_command == 4: # wifi_rsp_hardware_io_port_config_direction
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.wifi_rsp_hardware_io_port_config_direction({ 'result': result })
                    elif packet_command == 5: # wifi_rsp_hardware_io_port_config_open_drain
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.wifi_rsp_hardware_io_port_config_open_drain({ 'result': result })
                    elif packet_command == 6: # wifi_rsp_hardware_io_port_write
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.wifi_rsp_hardware_io_port_write({ 'result': result })
                    elif packet_command == 7: # wifi_rsp_hardware_io_port_read
                        result, port, data = struct.unpack('<HBH', self.bgapi_rx_payload[:5])
                        self.wifi_rsp_hardware_io_port_read({ 'result': result, 'port': port, 'data': data })
                    elif packet_command == 8: # wifi_rsp_hardware_output_compare
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.wifi_rsp_hardware_output_compare({ 'result': result })
                    elif packet_command == 9: # wifi_rsp_hardware_adc_read
                        result, input, value = struct.unpack('<HBH', self.bgapi_rx_payload[:5])
                        self.wifi_rsp_hardware_adc_read({ 'result': result, 'input': input, 'value': value })
                elif packet_class == 7:
                    if packet_command == 0: # wifi_rsp_flash_ps_defrag
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.wifi_rsp_flash_ps_defrag({ 'result': result })
                    elif packet_command == 1: # wifi_rsp_flash_ps_dump
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.wifi_rsp_flash_ps_dump({ 'result': result })
                    elif packet_command == 2: # wifi_rsp_flash_ps_erase_all
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.wifi_rsp_flash_ps_erase_all({ 'result': result })
                    elif packet_command == 3: # wifi_rsp_flash_ps_save
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.wifi_rsp_flash_ps_save({ 'result': result })
                    elif packet_command == 4: # wifi_rsp_flash_ps_load
                        result, value_len = struct.unpack('<HB', self.bgapi_rx_payload[:3])
                        value_data = self.bgapi_rx_payload[3:]
                        self.wifi_rsp_flash_ps_load({ 'result': result, 'value': value_data })
                    elif packet_command == 5: # wifi_rsp_flash_ps_erase
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.wifi_rsp_flash_ps_erase({ 'result': result })
                elif packet_class == 8:
                    if packet_command == 0: # wifi_rsp_i2c_start_read
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.wifi_rsp_i2c_start_read({ 'result': result })
                    elif packet_command == 1: # wifi_rsp_i2c_start_write
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.wifi_rsp_i2c_start_write({ 'result': result })
                    elif packet_command == 2: # wifi_rsp_i2c_stop
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.wifi_rsp_i2c_stop({ 'result': result })
                self.busy = False
                self.on_idle()
            else:
                # 0x88 = wifi event packet
                if packet_class == 0:
                    if packet_command == 0: # wifi_evt_dfu_boot
                        version = struct.unpack('<I', self.bgapi_rx_payload[:4])[0]
                        self.wifi_evt_dfu_boot({ 'version': version })
                        self.busy = False
                        self.on_idle()
                elif packet_class == 1:
                    if packet_command == 0: # wifi_evt_system_boot
                        major, minor, patch, build, bootloader_version, tcpip_version, hw = struct.unpack('<HHHHHHH', self.bgapi_rx_payload[:14])
                        self.wifi_evt_system_boot({ 'major': major, 'minor': minor, 'patch': patch, 'build': build, 'bootloader_version': bootloader_version, 'tcpip_version': tcpip_version, 'hw': hw })
                    elif packet_command == 1: # wifi_evt_system_state
                        state = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.wifi_evt_system_state({ 'state': state })
                    elif packet_command == 2: # wifi_evt_system_sw_exception
                        address, type = struct.unpack('<IB', self.bgapi_rx_payload[:5])
                        self.wifi_evt_system_sw_exception({ 'address': address, 'type': type })
                    elif packet_command == 3: # wifi_evt_system_power_saving_state
                        state = struct.unpack('<B', self.bgapi_rx_payload[:1])[0]
                        self.wifi_evt_system_power_saving_state({ 'state': state })
                elif packet_class == 2:
                    if packet_command == 0: # wifi_evt_config_mac_address
                        hw_interface = struct.unpack('<B', self.bgapi_rx_payload[:1])[0]
                        self.wifi_evt_config_mac_address({ 'hw_interface': hw_interface })
                elif packet_class == 3:
                    if packet_command == 0: # wifi_evt_sme_wifi_is_on
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.wifi_evt_sme_wifi_is_on({ 'result': result })
                    elif packet_command == 1: # wifi_evt_sme_wifi_is_off
                        result = struct.unpack('<H', self.bgapi_rx_payload[:2])[0]
                        self.wifi_evt_sme_wifi_is_off({ 'result': result })
                    elif packet_command == 2: # wifi_evt_sme_scan_result
                        channel, rssi, snr, secure, ssid_len = struct.unpack('<bhbBB', self.bgapi_rx_payload[:6])
                        ssid_data = self.bgapi_rx_payload[6:]
                        self.wifi_evt_sme_scan_result({ 'channel': channel, 'rssi': rssi, 'snr': snr, 'secure': secure, 'ssid': ssid_data })
                    elif packet_command == 3: # wifi_evt_sme_scan_result_drop
                        self.wifi_evt_sme_scan_result_drop({  })
                    elif packet_command == 4: # wifi_evt_sme_scanned
                        status = struct.unpack('<b', self.bgapi_rx_payload[:1])[0]
                        self.wifi_evt_sme_scanned({ 'status': status })
                    elif packet_command == 5: # wifi_evt_sme_connected
                        status, hw_interface = struct.unpack('<bB', self.bgapi_rx_payload[:2])
                        self.wifi_evt_sme_connected({ 'status': status, 'hw_interface': hw_interface })
                    elif packet_command == 6: # wifi_evt_sme_disconnected
                        reason, hw_interface = struct.unpack('<HB', self.bgapi_rx_payload[:3])
                        self.wifi_evt_sme_disconnected({ 'reason': reason, 'hw_interface': hw_interface })
                    elif packet_command == 7: # wifi_evt_sme_interface_status
                        hw_interface, status = struct.unpack('<BB', self.bgapi_rx_payload[:2])
                        self.wifi_evt_sme_interface_status({ 'hw_interface': hw_interface, 'status': status })
                    elif packet_command == 8: # wifi_evt_sme_connect_failed
                        reason, hw_interface = struct.unpack('<HB', self.bgapi_rx_payload[:3])
                        self.wifi_evt_sme_connect_failed({ 'reason': reason, 'hw_interface': hw_interface })
                    elif packet_command == 9: # wifi_evt_sme_connect_retry
                        hw_interface = struct.unpack('<B', self.bgapi_rx_payload[:1])[0]
                        self.wifi_evt_sme_connect_retry({ 'hw_interface': hw_interface })
                elif packet_class == 4:
                    if packet_command == 0: # wifi_evt_tcpip_configuration
                        use_dhcp = struct.unpack('<B', self.bgapi_rx_payload[:1])[0]
                        self.wifi_evt_tcpip_configuration({ 'use_dhcp': use_dhcp })
                    elif packet_command == 1: # wifi_evt_tcpip_dns_configuration
                        index = struct.unpack('<B', self.bgapi_rx_payload[:1])[0]
                        self.wifi_evt_tcpip_dns_configuration({ 'index': index })
                    elif packet_command == 2: # wifi_evt_tcpip_endpoint_status
                        endpoint, local_port, remote_port = struct.unpack('<BHH', self.bgapi_rx_payload[:5])
                        self.wifi_evt_tcpip_endpoint_status({ 'endpoint': endpoint, 'local_port': local_port, 'remote_port': remote_port })
                    elif packet_command == 3: # wifi_evt_tcpip_dns_gethostbyname_result
                        result, name_len = struct.unpack('<HB', self.bgapi_rx_payload[:3])
                        name_data = self.bgapi_rx_payload[3:]
                        self.wifi_evt_tcpip_dns_gethostbyname_result({ 'result': result, 'name': name_data })
                elif packet_class == 5:
                    if packet_command == 0: # wifi_evt_endpoint_syntax_error
                        endpoint = struct.unpack('<B', self.bgapi_rx_payload[:1])[0]
                        self.wifi_evt_endpoint_syntax_error({ 'endpoint': endpoint })
                    elif packet_command == 1: # wifi_evt_endpoint_data
                        endpoint, data_len = struct.unpack('<BB', self.bgapi_rx_payload[:2])
                        data_data = self.bgapi_rx_payload[2:]
                        self.wifi_evt_endpoint_data({ 'endpoint': endpoint, 'data': data_data })
                    elif packet_command == 2: # wifi_evt_endpoint_status
                        endpoint, type, streaming, destination, active = struct.unpack('<BIBbB', self.bgapi_rx_payload[:8])
                        self.wifi_evt_endpoint_status({ 'endpoint': endpoint, 'type': type, 'streaming': streaming, 'destination': destination, 'active': active })
                    elif packet_command == 3: # wifi_evt_endpoint_closing
                        reason, endpoint = struct.unpack('<HB', self.bgapi_rx_payload[:3])
                        self.wifi_evt_endpoint_closing({ 'reason': reason, 'endpoint': endpoint })
                elif packet_class == 6:
                    if packet_command == 0: # wifi_evt_hardware_soft_timer
                        handle = struct.unpack('<B', self.bgapi_rx_payload[:1])[0]
                        self.wifi_evt_hardware_soft_timer({ 'handle': handle })
                    elif packet_command == 1: # wifi_evt_hardware_change_notification
                        timestamp = struct.unpack('<I', self.bgapi_rx_payload[:4])[0]
                        self.wifi_evt_hardware_change_notification({ 'timestamp': timestamp })
                    elif packet_command == 2: # wifi_evt_hardware_external_interrupt
                        irq, timestamp = struct.unpack('<BI', self.bgapi_rx_payload[:5])
                        self.wifi_evt_hardware_external_interrupt({ 'irq': irq, 'timestamp': timestamp })
                elif packet_class == 7:
                    if packet_command == 0: # wifi_evt_flash_ps_key
                        key, value_len = struct.unpack('<HB', self.bgapi_rx_payload[:3])
                        value_data = self.bgapi_rx_payload[3:]
                        self.wifi_evt_flash_ps_key({ 'key': key, 'value': value_data })


        ###datahandler.py
class DataHandler:
    """
    EMG/IMU/Classifier data handler.
    """

    def __init__(self, config):
        self.osc = udp_client.SimpleUDPClient(config.OSC_ADDRESS, config.OSC_PORT)
        self.printEmg = config.PRINT_EMG
        self.printImu = config.PRINT_IMU
        self.myo_imu_data = multiprocessing.Queue()
        # self.p = multiprocessing.Process(target=self.process, args=(self.myo_data0, self.myo_data1))
        # self.p.start()

    def process(q1, q2):
        return q1.get(), q2.get()

    def handle_emg(self, payload):
        """
        Handle EMG data.
        :param payload: emg data as two samples in a single pack.
        """
        myo_data0 = []
        myo_data1 = []
        if self.printEmg:
            print("EMG", payload['connection'], payload['atthandle'], payload['value'])

        # Send both samples
        self._send_single_emg(payload['connection'], payload['value'][0:8])
        self._send_single_emg(payload['connection'], payload['value'][8:16])

    # print(payload['atthandle'])

    def _send_single_emg(self, conn, data):
        '''
        #print("conn: {}, data {}".format(conn, data_new))

        data_new = []
        builder = udp_client.OscMessageBuilder("/myo/emg")
        builder.add_arg(str(conn), 's')
        for i in struct.unpack('<8b ', data):
            builder.add_arg(i / 127, 'f')  # Normalize
            data_new.append(i)
        if conn == 0:
            self.myo_data0.put_nowait(data_new)
        if conn == 1:
            self.myo_data1.put_nowait(data_new)
            print(data_new)

        self.osc.send(builder.build())
        '''

        # print("conn: {}, data {}".format(conn, data_new))

        data_new = []
        builder = udp_client.OscMessageBuilder("/myo/emg")
        builder.add_arg(str(conn), 's')
        for i in struct.unpack('<8b ', data):
            builder.add_arg(i / 127, 'f')  # Normalize
            data_new.append(i)
        '''
        new_dict = {'emg': {str(conn): data_new}}
        print({str(conn): data_new})
        self.myo_imu_data.put(new_dict)
        '''
        if conn == 0:
            # print("0", data_new)
            dict0 = {'emg': {str(conn): data_new}}
            self.myo_imu_data.put(dict0)
        if conn == 1:
            # self.myo_data1.put(data_new)
            # print("1", data_new)
            dict1 = {'emg': {str(conn): data_new}}
            self.myo_imu_data.put(dict1)
        self.osc.send(builder.build())

    def handle_imu(self, payload):
        """
        Handle IMU data.
        :param payload: imu data in a single byte array.
        """
        if self.printImu:
            print("IMU", payload['connection'], payload['atthandle'], payload['value'])
        # Send orientation
        conn = payload['connection']
        data = payload['value'][0:8]
        builder = udp_client.OscMessageBuilder("/myo/orientation")
        builder.add_arg(str(payload['connection']), 's')
        roll, pitch, yaw = self._euler_angle(*(struct.unpack('hhhh', data)))
        # Normalize to [-1, 1]
        builder.add_arg(roll / math.pi, 'f')
        builder.add_arg(pitch / math.pi, 'f')
        builder.add_arg(yaw / math.pi, 'f')
        self.osc.send(builder.build())

        # Send accelerometer
        data = payload['value'][8:14]
        builder = udp_client.OscMessageBuilder("/myo/accel")
        builder.add_arg(str(payload['connection']), 's')
        accelerometer = self._vector_magnitude(*(struct.unpack('hhh', data)))
        builder.add_arg(accelerometer, 'f')
        self.osc.send(builder.build())

        # Send gyroscope
        data = payload['value'][14:20]
        builder = udp_client.OscMessageBuilder("/myo/gyro")
        builder.add_arg(str(payload['connection']), 's')
        gyro = self._vector_magnitude(*(struct.unpack('hhh', data)))
        builder.add_arg(gyro, 'f')
        self.osc.send(builder.build())

        new_dict = {'imu': {str(conn): [ roll / math.pi, pitch / math.pi,  yaw/math.pi, accelerometer,  gyro ]} }
        #print(new_dict)
        self.myo_imu_data.put(new_dict)

    @staticmethod
    def _euler_angle(w, x, y, z):
        """
        From https://en.wikipedia.org/wiki/Conversion_between_quaternions_and_Euler_angles.
        """
        # roll (x-axis rotation)
        sinr_cosp = +2.0 * (w * x + y * z)
        cosr_cosp = +1.0 - 2.0 * (x * x + y * y)
        roll = math.atan2(sinr_cosp, cosr_cosp)

        # pitch (y-axis rotation)
        sinp = +2.0 * (w * y - z * x)
        if math.fabs(sinp) >= 1:
            pitch = math.copysign(math.pi / 2, sinp)  # use 90 degrees if out of range
        else:
            pitch = math.asin(sinp)

        # yaw (z-axis rotation)
        siny_cosp = +2.0 * (w * z + x * y)
        cosy_cosp = +1.0 - 2.0 * (y * y + z * z)
        yaw = math.atan2(siny_cosp, cosy_cosp)

        return roll, pitch, yaw

    @staticmethod
    def _vector_magnitude(x, y, z):
        return math.sqrt(x * x + y * y + z * z)

    #####config.py
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

    RETRY_CONNECTION_AFTER = 5  # Reconnection timeout in seconds
    MAX_RETRIES = 5  # Max amount of retries after unexpected disconnect

    # optional:
    MAC_ADDR_MYO_1 ='e8-26-3b-f2-38-16'
    MAC_ADDR_MYO_2 ='ea-de-bf-42-2f-30'
    MAC_ADDR_MYO_3 ='ec-07-35-d9-7a-c6'


# always left - MAC_ADDR_MYO_1
# always right - MAC_ADDR_MYO_2

#ea-de-bf-42-2f-30 - Armband 3
#0
#Myo ready 0 b'0/B\xbf\xde\xea'

#e8-26-3b-f2-38-16 - Armband 1
#1
#Myo ready 1 b'\x168\xf2;&\xe8'

#ec-07-35-d9-7a-c6 - Armband 2


    #####

# ================================================================
if __name__ == "__main__":
    freeze_support()
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))

    intro_image = pygame.image.load("assets/pag1.png")
    intro_rect = intro_image.get_rect()
    intro_rect.center = (WIDTH // 2, HEIGHT // 2)

    background = pygame.image.load("assets/football.jpeg")
    background = pygame.transform.scale(background, (WIDTH, HEIGHT))
    background.get_rect().center = (WIDTH // 2, HEIGHT // 2)

    mio_image = pygame.image.load("assets/mio.jpeg")
    mio_image = pygame.transform.scale(mio_image, (300, 250))

    mio_rect_left = mio_image.get_rect()
    mio_rect_right = mio_image.get_rect()
    mio_rect_left.center = (X - 400, Y - 200)
    mio_rect_right.center = (X + 400, Y - 200)

    text = FONT.render(translate.get('Translate', 'football.game'), True, WHITE)
    text_rect = text.get_rect()
    text_rect.center = (X + 30, Y - 250)

    connect_button = Button_Intro(X - 50, Y, 175, 90, translate.get('Translate', 'connect'))
    start_button = Button_Intro(X - 50, Y - 100, 175, 90, translate.get('Translate', 'start.game'))
    play = True

    myo_connected1 = False
    myo_connected2 = False

    mio_connect = MioConnect()

    connected1 = Event()
    connected2 = Event()
    process_mio_connect = Process(target=mio_connect.main, args=('sys.argv[1:]', connected1, connected2))
    process_game = Process(target=main_game)

    while play:
        screen.blit(background, (0, 0))
        screen.blit(mio_image, mio_rect_left)
        screen.blit(mio_image, mio_rect_right)
        screen.blit(text, text_rect)
        connect_button.draw(screen)

        while not connect_button.clicked:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if connect_button.rect.collidepoint(event.pos):
                        connect_button.clicked = True
                        connect_button.starting(screen)
                        process_mio_connect.start()
                        while not myo_connected1 or not myo_connected2:
                            if connected1.wait(5) and not myo_connected1:
                                text = FONT.render(translate.get('Translate', 'myo.left.connected'), True, WHITE)
                                text_rect = text.get_rect()
                                text_rect.center = (X - 400, Y)
                                screen.blit(text, text_rect)
                                pygame.display.flip()
                                myo_connected1 = True

                            if connected2.wait(5) and not myo_connected2:
                                text = FONT.render(translate.get('Translate', 'myo.right.connected'), True, WHITE)
                                text_rect = text.get_rect()
                                text_rect.center = (X + 400, Y)
                                screen.blit(text, text_rect)
                                pygame.display.flip()
                                myo_connected2 = True

                            if not connected1.is_set() and not connected2.is_set():
                                sys.exit()
                            pygame.display.flip()

            pygame.display.flip()

        if myo_connected1 and myo_connected2:
            start_button.draw(screen)
            while not start_button.clicked:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        pygame.quit()
                        sys.exit()
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        if start_button.rect.collidepoint(event.pos):
                            start_button.clicked = True
                            process_game.start()

                pygame.display.flip()
            if start_button.clicked:
                pygame.quit()
