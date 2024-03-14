#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
This experiment was created using PsychoPy3 Experiment Builder (v2023.1.0),
    on June 16, 2023, at 15:26
If you publish work using this script the most relevant publication is:

    Peirce J, Gray JR, Simpson S, MacAskill M, Höchenberger R, Sogo H, Kastman E, Lindeløv JK. (2019)
        PsychoPy2: Experiments in behavior made easy Behav Res 51: 195.
        https://doi.org/10.3758/s13428-018-01193-y

"""

import psychopy

psychopy.useVersion('2023.1.0')

# --- Import packages ---
from psychopy import locale_setup
from psychopy import prefs
from psychopy import plugins
from psychopy import parallel

plugins.activatePlugins()
prefs.hardware['audioLib'] = 'ptb'
prefs.hardware['audioLatencyMode'] = '3'
from psychopy import sound, gui, visual, core, data, event, logging, clock, colors, layout
from psychopy.constants import (NOT_STARTED, STARTED, PLAYING, PAUSED,
                                STOPPED, FINISHED, PRESSED, RELEASED, FOREVER)
import warnings
import time
import matplotlib.pyplot as plt

import numpy as np
from pylsl import StreamInlet, resolve_stream, StreamOutlet, StreamInfo

import numpy as np  # whole numpy lib is available, prepend 'np.'
from numpy import (sin, cos, tan, log, log10, pi, average,
                   sqrt, std, deg2rad, rad2deg, linspace, asarray)
from numpy.random import random, randint, normal, shuffle, choice as randchoice
import os  # handy system and path functions
import sys  # to get file system encoding

from playsound import playsound

from psychopy.hardware import keyboard

import scipy

from scipy.signal import butter, lfilter

# Run 'Before Experiment' code from code_11
import csv
from psychopy.hardware import keyboard

kb = keyboard.Keyboard()
keyFile = open('keys.csv', 'a', newline='')
writeKeys = csv.writer(keyFile)

# =======================================================================================================================
# Game params:
thrs_filename = 'threshold.txt'
thrs_file_left = 'threshold_left.txt'
thrs_file_right = 'threshold_right.txt'

hand_side = "both"  # "right"/"left/both"
if hand_side == "right":
    hand_trig = 61
elif hand_side == "left":
    hand_trig = 62
else:
    hand_trig = 63

thrs_restrict = True

cheers_file = 'congrats.mp3'
ball_control = "emg"  # "grip"/"emg"
ball_pos_inc = 0.01

force_upper_limit = False

# EMG (filter) params:
emg_ch = 34  # 34:APL-R, 35:APL-L, 36:ED-R, 37:ED-L, 38:FD-R, 39:FD-L
emg_ch_right = 38
emg_ch_left = 39

fs = 1000
win_len = 5
filt_low = 20
filt_high = 40
filt_order = 5


# =======================================================================================================================
# Define functions:

def start_lsl_stream(type):
    """
    Starts listening to EEG lsl stream. Will get "stuck" if no stream is found.
    :param type: string - type of stream type (e.g. 'EEG' or 'marker')
    :return: lsl_inlet; pysls.StreamInlet object
    """
    streams = resolve_stream('type', type)
    if len(streams) > 1:
        warnings.warn('Number of EEG streams is > 0, picking the first one.')
    lsl_inlet = StreamInlet(streams[0])
    lsl_inlet.pull_sample()  # need to pull first sample to get buffer started for some reason
    print("Stream started.")
    return lsl_inlet


def pull_from_buffer(lsl_inlet, max_tries=10):
    """
    Pull data from the provided lsl inlet and return it as an array.
    :param lsl_inlet: lsl inlet object
    :param max_tries: int; number of empty chunks after which an error is thrown.
    :return: np.ndarray of shape (n_samples, n_channels)
    """
    # Makes it possible to run experiment without eeg data for testing by setting lsl_inlet to None
    if lsl_inlet is None:
        return

    pull_at_once = 10000
    samps_pulled = 10000
    n_tries = 0

    samples = []
    while samps_pulled == pull_at_once:
        data_lsl, _ = lsl_inlet.pull_chunk(max_samples=pull_at_once)
        arr = np.array(data_lsl)
        if len(arr) > 0:
            samples.append(arr)
            samps_pulled = len(arr)
        else:
            n_tries += 1
            time.sleep(0.01)
            if n_tries == max_tries:
                raise ValueError("Stream does not seem to provide any data.")
    return np.vstack(samples)


def pull_data(lsl_inlet, data_lsl, replace=True):
    new_data = pull_from_buffer(lsl_inlet)
    if replace or data_lsl is None:
        data_lsl = new_data
    else:
        data_lsl = np.vstack([data_lsl, new_data])
    return data_lsl


def set_threshold(file):
    f = open(file, 'r')
    thrs_list = f.readlines()
    try:
        #thrs = int(thrs_list[0])
        thrs = list(map(int, thrs_list[0].split(",")))
    except:
        thrs = []
        print("Could not read from threshold file!")
    # print(str(thrs))
    return thrs


def get_grip_force(lsl_inlet, data_lsl):
    data_grip = pull_data(lsl_inlet=lsl_inlet, data_lsl=data_lsl, replace=True)
    grip_force = np.mean(data_grip[:, 32])
    offset = 70
    grip_force = grip_force - offset
    if grip_force < 0: grip_force = 0
    print(str(int(grip_force)))
    return grip_force


def set_movement_status(grip_force, thrs, hand, status):
    status_hand = 1 if hand == "right" else 0
    if grip_force > thrs[0] and grip_force < thrs[1]:
        status[status_hand] = "down"
    else:
        status[status_hand] = "up"
    return status


def quit_game(lsl_inlet):
    send_trigger(trig=52)
    try:
        lsl_inlet.close_stream()
        print("Stream closed.")
    except:
        print("No LSL stream to close")


def send_trigger(trig):
    parport = parallel.ParallelPort(address=0x0378)  # set to None to run without parport
    parport.setData(trig)
    time.sleep(0.01)
    parport.setData(0)


def butter_bandpass(lowcut, highcut, fs, order):
    b, a = butter(order, [lowcut, highcut], fs=fs, btype='band', output="ba")
    return b, a


def get_emg(lsl_inlet, data_lsl, emg_ch, win_len):
    # print(np.shape(data_lsl))
    data_lsl = pull_data(lsl_inlet=lsl_inlet, data_lsl=data_lsl, replace=False)
    # print(np.shape(data_lsl))
    emg = data_lsl[:, emg_ch] # select emg channel
    win_samp = win_len * fs # define win len (depending on fs)
    emg_chunk = 0
    if len(emg) > win_samp:   # wait until data win is long enough
        emg_win = emg[-win_samp:-1] # pull data from time point 0 to -win_size
        emg_filt = lfilter(b, a, emg_win) # applying the filter (no need to change)
        emg_env = np.abs(scipy.signal.hilbert(emg_filt)) # calculating envelope
        # emg_smooth = scipy.signal.savgol_filter(emg_env, window_length=300, polyorder=3) # optional: smooth the signal (avoid data jumps)
        '''
        # for testing
        plt.plot(emg_filt,label='bp_filt')
        plt.plot(emg_env,label='envelope')
        plt.plot(emg_smooth,label='smooth')
        plt.grid()
        plt.legend()
        plt.show()
        '''
        chunk_size = 20
        emg_chunk = np.mean(np.power(emg_env[-chunk_size:-1], 2))
        # offset = 100
        # emg_chunk = emg_chunk - offset
        # if emg_chunk < 0: emg_chunk = 0
        print(int(emg_chunk))
    return emg_chunk, data_lsl


# =======================================================================================================================
# Start up
lsl_inlet = start_lsl_stream(type='EEG')
data_lsl = None
b, a = butter_bandpass(filt_low, filt_high, fs, filt_order)

# =======================================================================================================================

# Run 'Before Experiment' code from code_3
import csv

startAgainChosen = 15
endChosen = 15

file = open('trial.csv', 'a', newline='')
fieldnames = ['participant', 'session', 'modeChosen', 'level', 'right', 'left']
writer = csv.DictWriter(file, fieldnames=fieldnames)

# Run 'Before Experiment' code from code
xBall = 0
yBall = -0.3
rightClickedGame = 0
leftClickedGame = 0
# Run 'Before Experiment' code from code_5
from psychopy.hardware import keyboard

xBall1 = 0
yBall1 = -0.3
righClicked = 0
leftClicked = 0
# Run 'Before Experiment' code from code_6
xBall2 = 0
yBall2 = -0.3
righClicked = 0
leftClicked = 0
# Run 'Before Experiment' code from code_7
xBall3 = 0
yBall3 = -0.3
righClicked = 0
leftClicked = 0

# Ensure that relative paths start from the same directory as this script
_thisDir = os.path.dirname(os.path.abspath(__file__))
os.chdir(_thisDir)
# Store info about the experiment session
psychopyVersion = '2023.1.0'
expName = 'branching'  # from the Builder filename that created this script
expInfo = {
    'participant': f"{randint(0, 999999):06.0f}",
    'session': '001',
}
# --- Show participant info dialog --
dlg = gui.DlgFromDict(dictionary=expInfo, sortKeys=False, title=expName)
if dlg.OK == False:
    core.quit()  # user pressed cancel
expInfo['date'] = data.getDateStr()  # add a simple timestamp
expInfo['expName'] = expName
expInfo['psychopyVersion'] = psychopyVersion

# Data file name stem = absolute path + name; later add .psyexp, .csv, .log, etc
filename = _thisDir + os.sep + u'data/%s_%s_%s' % (expInfo['participant'], expName, expInfo['date'])

# An ExperimentHandler isn't essential but helps with data saving
thisExp = data.ExperimentHandler(name=expName, version='',
                                 extraInfo=expInfo, runtimeInfo=None,
                                 originPath='C:\\Users\\Phil\\Dropbox\\PhD\\Researchgroup Neuroinformatics\\EMG-BCI\\Football Game\\Football Game\\branching.py',
                                 savePickle=True, saveWideText=True,
                                 dataFileName=filename)
# save a log file for detail verbose info
logFile = logging.LogFile(filename + '.log', level=logging.EXP)
logging.console.setLevel(logging.WARNING)  # this outputs to the screen, not a file

endExpNow = False  # flag for 'escape' or other condition => quit the exp
frameTolerance = 0.001  # how close to onset before 'same' frame

# Start Code - component code to be run after the window creation

# --- Setup the Window ---
win = visual.Window(
    size=[1920, 1080], fullscr=True, screen=0,
    winType='pyglet', allowStencil=False,
    monitor='testMonitor', color=[0, 0, 0], colorSpace='rgb',
    backgroundImage='', backgroundFit='none',
    blendMode='avg', useFBO=True,
    units='height')
win.mouseVisible = True
# store frame rate of monitor if we can measure it
expInfo['frameRate'] = win.getActualFrameRate()
if expInfo['frameRate'] != None:
    frameDur = 1.0 / round(expInfo['frameRate'])
else:
    frameDur = 1.0 / 60.0  # could not measure, so guess
# --- Setup input devices ---
ioConfig = {}
ioSession = ioServer = eyetracker = None

# create a default keyboard (e.g. to check for escape)
defaultKeyboard = keyboard.Keyboard(backend='event')

# --- Initialize components for Routine "releasetrial" ---
image_6 = visual.ImageStim(
    win=win,
    name='image_6',
    image='PsychoPy/pag1.png', mask=None, anchor='center',
    ori=0.0, pos=(0, 0), size=(1.6, 1),
    color=[1, 1, 1], colorSpace='rgb', opacity=None,
    flipHoriz=False, flipVert=False,
    texRes=128.0, interpolate=True, depth=0.0)
key_resp = keyboard.Keyboard()
text_8 = visual.TextStim(win=win, name='text_8',
                         text='Justus spielt Fußball\n',
                         font='Open Sans',
                         pos=(0, 0), height=0.05, wrapWidth=None, ori=0.0,
                         color='white', colorSpace='rgb', opacity=None,
                         languageStyle='LTR',
                         depth=-3.0);

# --- Initialize components for Routine "mode" ---
image_2 = visual.ImageStim(
    win=win,
    name='image_2',
    image='PsychoPy/football.jpeg', mask=None, anchor='center',
    ori=0.0, pos=(0, 0), size=(1.6, 1),
    color=[1, 1, 1], colorSpace='rgb', opacity=None,
    flipHoriz=False, flipVert=False,
    texRes=128.0, interpolate=True, depth=0.0)
modeChoice = visual.TextStim(win=win, name='modeChoice',
                             text="Willkommen im Fußballstadion!\nWas möchtest du heute machen?\n\nTraining - Drücke Taste 'T'\nSpiel - Drücke Taste 'S'\n",
                             font='Open Sans',
                             pos=(0, 0), height=0.05, wrapWidth=None, ori=0.0,
                             color='white', colorSpace='rgb', opacity=None,
                             languageStyle='LTR',
                             depth=-1.0);
mode_resp = keyboard.Keyboard()
# Run 'Begin Experiment' code from code_3
dicti = {'participant': expInfo['participant']}
dicti = {'session': expInfo['session']}
if mode_resp.keys == 't':
    practiceChosen = 1
    gameChosen = 0
    dicti['modeChosen'] = 'practice'
if mode_resp.keys == 's':
    practiceChosen = 0
    gameChosen = 1
    dicti['modeChosen'] = 'game'

# --- Initialize components for Routine "refreshBallPositionGame" ---

# --- Initialize components for Routine "game" ---
football_background = visual.ImageStim(
    win=win,
    name='football_background',
    image='default.png', mask=None, anchor='center',
    ori=0.0, pos=(0, 0), size=(1.6, 1),
    color=[1, 1, 1], colorSpace='rgb', opacity=None,
    flipHoriz=False, flipVert=False,
    texRes=128.0, interpolate=True, depth=-1.0)
gate_l = visual.ImageStim(
    win=win,
    name='gate_l',
    image='PsychoPy/gate_l.png', mask=None, anchor='center',
    ori=0.0, pos=(-0.7, -0.25), size=(0.25, 0.25),
    color=[1, 1, 1], colorSpace='rgb', opacity=None,
    flipHoriz=False, flipVert=False,
    texRes=128.0, interpolate=True, depth=-2.0)
gate_r = visual.ImageStim(
    win=win,
    name='gate_r',
    image='PsychoPy/gate_r.png', mask=None, anchor='center',
    ori=0.0, pos=(0.7, -0.25), size=(0.25, 0.25),
    color=[1, 1, 1], colorSpace='rgb', opacity=None,
    flipHoriz=False, flipVert=False,
    texRes=128.0, interpolate=True, depth=-3.0)
footballTitle = visual.TextStim(win=win, name='footballTitle',
                                text='Das ist das beste Fußballspiel!',
                                font='Open Sans',
                                pos=(0, 0), height=0.05, wrapWidth=None, ori=0.0,
                                color='white', colorSpace='rgb', opacity=None,
                                languageStyle='LTR',
                                depth=-4.0);
ball = visual.ImageStim(
    win=win,
    name='ball',
    image='default.png', mask=None, anchor='center',
    ori=0.0, pos=[0, 0], size=(0.1, 0.1),
    color=[1, 1, 1], colorSpace='rgb', opacity=None,
    flipHoriz=False, flipVert=False,
    texRes=128.0, interpolate=True, depth=-5.0)

ball_red = visual.ImageStim(
    win=win,
    name='ball_red',
    image='PsychoPy/ball_red.png', mask=None, anchor='center',
    ori=0.0, pos=[0, 0], size=(0.1, 0.1),
    color=[1, 1, 1], colorSpace='rgb', opacity=None,
    flipHoriz=False, flipVert=False,
    texRes=128.0, interpolate=True, depth=-5.0)

# --- Initialize components for Routine "gameWon" ---
consent_resp_2 = keyboard.Keyboard()
congrats_background_2 = visual.ImageStim(
    win=win,
    name='congrats_background_2',
    image='default.png', mask=None, anchor='center',
    ori=0.0, pos=(0, 0), size=(1.6, 1),
    color=[1, 1, 1], colorSpace='rgb', opacity=None,
    flipHoriz=False, flipVert=False,
    texRes=128.0, interpolate=True, depth=-2.0)
consentTxt_2 = visual.TextStim(win=win, name='consentTxt_2',
                               text='Tor! \n\nDu hast gewonnen!\n\nGlückwunsch!',
                               font='Open Sans',
                               pos=(0, 0), height=0.1, wrapWidth=None, ori=0.0,
                               color='white', colorSpace='rgb', opacity=None,
                               languageStyle='LTR',
                               depth=-3.0);
sound_1 = sound.Sound('PsychoPy/congrats.mp3', secs=-1, stereo=True, hamming=True,
                      name='sound_1')
sound_1.setVolume(20.0)

# --- Initialize components for Routine "practice" ---
image = visual.ImageStim(
    win=win,
    name='image',
    image='PsychoPy/football.jpeg', mask=None, anchor='center',
    ori=0.0, pos=(0, 0), size=(1.6, 1),
    color=[1, 1, 1], colorSpace='rgb', opacity=None,
    flipHoriz=False, flipVert=False,
    texRes=128.0, interpolate=True, depth=0.0)
text = visual.TextStim(win=win, name='text',
                       text="Das ist der Trainings-Modus!\n\nWähle ein Level:\n\nLevel 1 - Drücke Taste '1'\nLevel 2 - Drücke Taste '2'\nLevel 3 - Drücke Taste '3'",
                       font='Open Sans',
                       pos=(0, 0), height=0.05, wrapWidth=None, ori=0.0,
                       color='white', colorSpace='rgb', opacity=None,
                       languageStyle='LTR',
                       depth=-1.0);
practice_resp = keyboard.Keyboard()

# --- Initialize components for Routine "refreshBallPosition" ---

# --- Initialize components for Routine "level1" ---
image_3 = visual.ImageStim(
    win=win,
    name='image_3',
    image='PsychoPy/football.HEIC', mask=None, anchor='center',
    ori=0.0, pos=(0, 0), size=(1.6, 1),
    color=[1, 1, 1], colorSpace='rgb', opacity=None,
    flipHoriz=False, flipVert=False,
    texRes=128.0, interpolate=True, depth=-1.0)
text_3 = visual.TextStim(win=win, name='text_3',
                         text='Training - Level 1\nDrücke den Druckball in deiner Hand, um den Fußball ins Tor zu schießen!',
                         font='Open Sans',
                         pos=(0, 0), height=0.05, wrapWidth=None, ori=0.0,
                         color='white', colorSpace='rgb', opacity=None,
                         languageStyle='LTR',
                         depth=-2.0);
gate_l_l1 = visual.ImageStim(
    win=win,
    name='gate_l_l1',
    image='PsychoPy/gate_l.png', mask=None, anchor='center',
    ori=0.0, pos=(-0.2, -0.25), size=(0.25, 0.25),
    color=[1, 1, 1], colorSpace='rgb', opacity=None,
    flipHoriz=False, flipVert=False,
    texRes=128.0, interpolate=True, depth=-3.0)
gate_r_l1 = visual.ImageStim(
    win=win,
    name='gate_r_l1',
    image='PsychoPy/gate_r.png', mask=None, anchor='center',
    ori=0.0, pos=(0.2, -0.25), size=(0.25, 0.25),
    color=[1, 1, 1], colorSpace='rgb', opacity=None,
    flipHoriz=False, flipVert=False,
    texRes=128.0, interpolate=True, depth=-4.0)
ball_level1 = visual.ImageStim(
    win=win,
    name='ball_level1',
    image='default.png', mask=None, anchor='center',
    ori=0.0, pos=[0, 0], size=(0.1, 0.1),
    color=[1, 1, 1], colorSpace='rgb', opacity=None,
    flipHoriz=False, flipVert=False,
    texRes=128.0, interpolate=True, depth=-5.0)

# --- Initialize components for Routine "level2" ---
image_4 = visual.ImageStim(
    win=win,
    name='image_4',
    image='PsychoPy/football.HEIC', mask=None, anchor='center',
    ori=0.0, pos=(0, 0), size=(1.6, 1),
    color=[1, 1, 1], colorSpace='rgb', opacity=None,
    flipHoriz=False, flipVert=False,
    texRes=128.0, interpolate=True, depth=-1.0)
text_4 = visual.TextStim(win=win, name='text_4',
                         text='Training - Level 2\nDrücke den Druckball in deiner Hand, um den Fußball ins Tor zu schießen!',
                         font='Open Sans',
                         pos=(0, 0), height=0.05, wrapWidth=None, ori=0.0,
                         color='white', colorSpace='rgb', opacity=None,
                         languageStyle='LTR',
                         depth=-2.0);
gate_r2 = visual.ImageStim(
    win=win,
    name='gate_r2',
    image='PsychoPy/gate_r.png', mask=None, anchor='center',
    ori=0.0, pos=(0.3, -0.25), size=(0.25, 0.25),
    color=[1, 1, 1], colorSpace='rgb', opacity=None,
    flipHoriz=False, flipVert=False,
    texRes=128.0, interpolate=True, depth=-3.0)
gate_l2 = visual.ImageStim(
    win=win,
    name='gate_l2',
    image='PsychoPy/gate_l.png', mask=None, anchor='center',
    ori=0.0, pos=(-0.3, -0.25), size=(0.25, 0.25),
    color=[1, 1, 1], colorSpace='rgb', opacity=None,
    flipHoriz=False, flipVert=False,
    texRes=128.0, interpolate=True, depth=-4.0)
ball_level2 = visual.ImageStim(
    win=win,
    name='ball_level2',
    image='default.png', mask=None, anchor='center',
    ori=0.0, pos=[0, 0], size=(0.1, 0.1),
    color=[1, 1, 1], colorSpace='rgb', opacity=None,
    flipHoriz=False, flipVert=False,
    texRes=128.0, interpolate=True, depth=-5.0)

# --- Initialize components for Routine "level3" ---
image_5 = visual.ImageStim(
    win=win,
    name='image_5',
    image='PsychoPy/football.HEIC', mask=None, anchor='center',
    ori=0.0, pos=(0, 0), size=(1.6, 1),
    color=[1, 1, 1], colorSpace='rgb', opacity=None,
    flipHoriz=False, flipVert=False,
    texRes=128.0, interpolate=True, depth=-1.0)
text_5 = visual.TextStim(win=win, name='text_5',
                         text='Training - Level 3\nDrücke den Druckball in deiner Hand, um den Fußball ins Tor zu schießen!\n',
                         font='Open Sans',
                         pos=(0, 0), height=0.05, wrapWidth=None, ori=0.0,
                         color='white', colorSpace='rgb', opacity=None,
                         languageStyle='LTR',
                         depth=-2.0);
gate_l_3 = visual.ImageStim(
    win=win,
    name='gate_l_3',
    image='PsychoPy/gate_l.png', mask=None, anchor='center',
    ori=0.0, pos=(-0.55, -0.25), size=(0.25, 0.25),
    color=[1, 1, 1], colorSpace='rgb', opacity=None,
    flipHoriz=False, flipVert=False,
    texRes=128.0, interpolate=True, depth=-3.0)
gate_r_3 = visual.ImageStim(
    win=win,
    name='gate_r_3',
    image='PsychoPy/gate_r.png', mask=None, anchor='center',
    ori=0.0, pos=(0.55, -0.25), size=(0.25, 0.25),
    color=[1, 1, 1], colorSpace='rgb', opacity=None,
    flipHoriz=False, flipVert=False,
    texRes=128.0, interpolate=True, depth=-4.0)
ball_level3 = visual.ImageStim(
    win=win,
    name='ball_level3',
    image='default.png', mask=None, anchor='center',
    ori=0.0, pos=[0, 0], size=(0.1, 0.1),
    color=[1, 1, 1], colorSpace='rgb', opacity=None,
    flipHoriz=False, flipVert=False,
    texRes=128.0, interpolate=True, depth=-5.0)

# --- Initialize components for Routine "practice_end" ---
congrats_background = visual.ImageStim(
    win=win,
    name='congrats_background',
    image='default.png', mask=None, anchor='center',
    ori=0.0, pos=(0, 0), size=(1.6, 1),
    color=[1, 1, 1], colorSpace='rgb', opacity=None,
    flipHoriz=False, flipVert=False,
    texRes=128.0, interpolate=True, depth=0.0)
byetext = visual.TextStim(win=win, name='byetext',
                          text='Tor! \n\nDas hast du gut gemacht! \n\nGlückwunsch!',
                          font='Open Sans',
                          pos=(0, 0), height=0.1, wrapWidth=None, ori=0.0,
                          color='white', colorSpace='rgb', opacity=None,
                          languageStyle='LTR',
                          depth=-1.0)
sound_2 = sound.Sound('PsychoPy/congrats.mp3', secs=-1, stereo=True, hamming=True,
                      name='sound_1')
sound_2.setVolume(20.0);

# --- Initialize components for Routine "end_again" ---
image_7 = visual.ImageStim(
    win=win,
    name='image_7',
    image='PsychoPy/pag1.png', mask=None, anchor='center',
    ori=0.0, pos=(0, 0), size=(1.6, 1),
    color=[1, 1, 1], colorSpace='rgb', opacity=None,
    flipHoriz=False, flipVert=False,
    texRes=128.0, interpolate=True, depth=0.0)
text_6 = visual.TextStim(win=win, name='text_6',
                         text="Spiel wiederholen - Drücke Taste 'W'\nSpiel beenden - Drücke Taste 'B'",
                         font='Open Sans',
                         pos=(0, 0), height=0.05, wrapWidth=None, ori=0.0,
                         color='white', colorSpace='rgb', opacity=None,
                         languageStyle='LTR',
                         depth=-1.0);
mode_resp_3 = keyboard.Keyboard()

# --- Initialize components for Routine "end_game" ---
image_8 = visual.ImageStim(
    win=win,
    name='image_8',
    image='PsychoPy/pag1.png', mask=None, anchor='center',
    ori=0.0, pos=(0, 0), size=(1.6, 1),
    color=[1, 1, 1], colorSpace='rgb', opacity=None,
    flipHoriz=False, flipVert=False,
    texRes=128.0, interpolate=True, depth=0.0)
text_7 = visual.TextStim(win=win, name='text_7',
                         text='Danke, dass du mit uns gespielt hast!\nWir hoffen, es hat dir Spaß gemacht!',
                         font='Open Sans',
                         pos=(0, 0), height=0.05, wrapWidth=None, ori=0.0,
                         color='white', colorSpace='rgb', opacity=None,
                         languageStyle='LTR',
                         depth=-1.0);

# Create some handy timers
globalClock = core.Clock()  # to track the time since experiment started
routineTimer = core.Clock()  # to track time remaining of each (possibly non-slip) routine

# --- Prepare to start Routine "releasetrial" ---
continueRoutine = True
# update component parameters for each repeat
key_resp.keys = []
key_resp.rt = []
_key_resp_allKeys = []
# Run 'Begin Routine' code from code_11

keys = kb.getKeys()

for key in keys:
    if key == 'q':
        # --------------------------------------------------------------------------------------------------------------
        quit_game(lsl_inlet=lsl_inlet)
        # --------------------------------------------------------------------------------------------------------------
        core.quit()
    else:
        writeKeys.writerow([key.name, key.duration, key.tDown])
# keep track of which components have finished
releasetrialComponents = [image_6, key_resp, text_8]
for thisComponent in releasetrialComponents:
    thisComponent.tStart = None
    thisComponent.tStop = None
    thisComponent.tStartRefresh = None
    thisComponent.tStopRefresh = None
    if hasattr(thisComponent, 'status'):
        thisComponent.status = NOT_STARTED
# reset timers
t = 0
_timeToFirstFrame = win.getFutureFlipTime(clock="now")
frameN = -1

# --- Run Routine "releasetrial" ---

routineForceEnded = not continueRoutine
while continueRoutine:
    # get current time
    t = routineTimer.getTime()
    tThisFlip = win.getFutureFlipTime(clock=routineTimer)
    tThisFlipGlobal = win.getFutureFlipTime(clock=None)
    frameN = frameN + 1  # number of completed frames (so 0 is the first frame)
    # update/draw components on each frame

    # *image_6* updates

    # if image_6 is starting this frame...
    if image_6.status == NOT_STARTED and tThisFlip >= 0.0 - frameTolerance:
        # keep track of start time/frame for later
        image_6.frameNStart = frameN  # exact frame index
        image_6.tStart = t  # local t and not account for scr refresh
        image_6.tStartRefresh = tThisFlipGlobal  # on global time
        win.timeOnFlip(image_6, 'tStartRefresh')  # time at next scr refresh
        # add timestamp to datafile
        thisExp.timestampOnFlip(win, 'image_6.started')
        # update status
        image_6.status = STARTED
        image_6.setAutoDraw(True)

    # if image_6 is active this frame...
    if image_6.status == STARTED:
        # update params
        pass

    # *key_resp* updates
    waitOnFlip = False

    # if key_resp is starting this frame...
    if key_resp.status == NOT_STARTED and tThisFlip >= 0.0 - frameTolerance:
        # keep track of start time/frame for later
        key_resp.frameNStart = frameN  # exact frame index
        key_resp.tStart = t  # local t and not account for scr refresh
        key_resp.tStartRefresh = tThisFlipGlobal  # on global time
        win.timeOnFlip(key_resp, 'tStartRefresh')  # time at next scr refresh
        # add timestamp to datafile
        thisExp.timestampOnFlip(win, 'key_resp.started')
        # update status
        key_resp.status = STARTED
        # keyboard checking is just starting
        waitOnFlip = True
        win.callOnFlip(key_resp.clock.reset)  # t=0 on next screen flip
        win.callOnFlip(key_resp.clearEvents, eventType='keyboard')  # clear events on next screen flip
    if key_resp.status == STARTED and not waitOnFlip:
        theseKeys = key_resp.getKeys(keyList=['y'], waitRelease=True)
        _key_resp_allKeys.extend(theseKeys)
        if len(_key_resp_allKeys):
            # ----------------------------------------------------------------------------------------------------------
            # Game starts
            send_trigger(trig=51)
            time.sleep(0.1)
            send_trigger(trig=hand_trig)
            # ------------------------------------------------------------------------------
            if ball_control == 'emg':
                data_lsl = pull_data(lsl_inlet=lsl_inlet, data_lsl=data_lsl, replace=False)
            # ----------------------------------------------------------------------------------------------------------
            key_resp.keys = _key_resp_allKeys[-1].name  # just the last key pressed
            key_resp.rt = _key_resp_allKeys[-1].rt
            # a response ends the routine
            continueRoutine = False

    # *text_8* updates

    # if text_8 is starting this frame...
    if text_8.status == NOT_STARTED and tThisFlip >= 0.0 - frameTolerance:
        # keep track of start time/frame for later
        text_8.frameNStart = frameN  # exact frame index
        text_8.tStart = t  # local t and not account for scr refresh
        text_8.tStartRefresh = tThisFlipGlobal  # on global time
        win.timeOnFlip(text_8, 'tStartRefresh')  # time at next scr refresh
        # add timestamp to datafile
        thisExp.timestampOnFlip(win, 'text_8.started')
        # update status
        text_8.status = STARTED
        text_8.setAutoDraw(True)

    # if text_8 is active this frame...
    if text_8.status == STARTED:
        # update params
        pass

    # check for quit (typically the Esc key)
    if endExpNow or defaultKeyboard.getKeys(keyList=["escape"]):
        # --------------------------------------------------------------------------------------------------------------
        quit_game(lsl_inlet=lsl_inlet)
        # --------------------------------------------------------------------------------------------------------------
        core.quit()

    # check if all components have finished
    if not continueRoutine:  # a component has requested a forced-end of Routine
        routineForceEnded = True
        break
    continueRoutine = False  # will revert to True if at least one component still running
    for thisComponent in releasetrialComponents:
        if hasattr(thisComponent, "status") and thisComponent.status != FINISHED:
            continueRoutine = True
            break  # at least one component has not yet finished

    # refresh the screen
    if continueRoutine:  # don't flip if this routine is over or we'll get a blank screen
        win.flip()

# --- Ending Routine "releasetrial" ---
for thisComponent in releasetrialComponents:
    if hasattr(thisComponent, "setAutoDraw"):
        thisComponent.setAutoDraw(False)
# check responses
if key_resp.keys in ['', [], None]:  # No response was made
    key_resp.keys = None
thisExp.addData('key_resp.keys', key_resp.keys)
if key_resp.keys != None:  # we had a response
    thisExp.addData('key_resp.rt', key_resp.rt)
thisExp.nextEntry()
# Run 'End Routine' code from code_11

keys = kb.getKeys()

for key in keys:
    if key == 'q':
        # --------------------------------------------------------------------------------------------------------------
        quit_game(lsl_inlet=lsl_inlet)
        # --------------------------------------------------------------------------------------------------------------
        core.quit()
    else:
        writeKeys.writerow([key.name, key.duration, key.tDown])
# the Routine "releasetrial" was not non-slip safe, so reset the non-slip timer
routineTimer.reset()

# set up handler to look after randomisation of conditions etc
trials_5 = data.TrialHandler(nReps=startAgainChosen, method='random',
                             extraInfo=expInfo, originPath=-1,
                             trialList=[None],
                             seed=None, name='trials_5')
thisExp.addLoop(trials_5)  # add the loop to the experiment
thisTrial_5 = trials_5.trialList[0]  # so we can initialise stimuli with some values
# abbreviate parameter names if possible (e.g. rgb = thisTrial_5.rgb)
if thisTrial_5 != None:
    for paramName in thisTrial_5:
        exec('{} = thisTrial_5[paramName]'.format(paramName))

for thisTrial_5 in trials_5:
    currentLoop = trials_5
    # abbreviate parameter names if possible (e.g. rgb = thisTrial_5.rgb)
    if thisTrial_5 != None:
        for paramName in thisTrial_5:
            exec('{} = thisTrial_5[paramName]'.format(paramName))

    # --- Prepare to start Routine "mode" ---
    continueRoutine = True
    # update component parameters for each repeat
    mode_resp.keys = []
    mode_resp.rt = []
    _mode_resp_allKeys = []
    # Run 'Begin Routine' code from code_3
    if mode_resp.keys == 't':
        practiceChosen = 1
        gameChosen = 0
        dicti['modeChosen'] = 'practice'
    if mode_resp.keys == 's':
        practiceChosen = 0
        gameChosen = 1
        dicti['modeChosen'] = 'game'
    # keep track of which components havew finished
    modeComponents = [image_2, modeChoice, mode_resp]
    for thisComponent in modeComponents:
        thisComponent.tStart = None
        thisComponent.tStop = None
        thisComponent.tStartRefresh = None
        thisComponent.tStopRefresh = None
        if hasattr(thisComponent, 'status'):
            thisComponent.status = NOT_STARTED
    # reset timers
    t = 0
    _timeToFirstFrame = win.getFutureFlipTime(clock="now")
    frameN = -1

    # --- Run Routine "mode" ---
    routineForceEnded = not continueRoutine
    while continueRoutine:
        # get current time
        t = routineTimer.getTime()
        tThisFlip = win.getFutureFlipTime(clock=routineTimer)
        tThisFlipGlobal = win.getFutureFlipTime(clock=None)
        frameN = frameN + 1  # number of completed frames (so 0 is the first frame)
        # update/draw components on each frame

        # *image_2* updates

        # if image_2 is starting this frame...
        if image_2.status == NOT_STARTED and tThisFlip >= 0.0 - frameTolerance:
            # keep track of start time/frame for later
            image_2.frameNStart = frameN  # exact frame index
            image_2.tStart = t  # local t and not account for scr refresh
            image_2.tStartRefresh = tThisFlipGlobal  # on global time
            win.timeOnFlip(image_2, 'tStartRefresh')  # time at next scr refresh
            # add timestamp to datafile
            thisExp.timestampOnFlip(win, 'image_2.started')
            # update status
            image_2.status = STARTED
            image_2.setAutoDraw(True)

        # if image_2 is active this frame...
        if image_2.status == STARTED:
            # update params
            pass

        # *modeChoice* updates

        # if modeChoice is starting this frame...
        if modeChoice.status == NOT_STARTED and tThisFlip >= 0.0 - frameTolerance:
            # keep track of start time/frame for later
            modeChoice.frameNStart = frameN  # exact frame index
            modeChoice.tStart = t  # local t and not account for scr refresh
            modeChoice.tStartRefresh = tThisFlipGlobal  # on global time
            win.timeOnFlip(modeChoice, 'tStartRefresh')  # time at next scr refresh
            # add timestamp to datafile
            thisExp.timestampOnFlip(win, 'modeChoice.started')
            # update status
            modeChoice.status = STARTED
            modeChoice.setAutoDraw(True)

        # if modeChoice is active this frame...
        if modeChoice.status == STARTED:
            # update params
            pass

        # *mode_resp* updates
        waitOnFlip = False

        # if mode_resp is starting this frame...
        if mode_resp.status == NOT_STARTED and tThisFlip >= 0.0 - frameTolerance:
            # keep track of start time/frame for later
            mode_resp.frameNStart = frameN  # exact frame index
            mode_resp.tStart = t  # local t and not account for scr refresh
            mode_resp.tStartRefresh = tThisFlipGlobal  # on global time
            win.timeOnFlip(mode_resp, 'tStartRefresh')  # time at next scr refresh
            # add timestamp to datafile
            thisExp.timestampOnFlip(win, 'mode_resp.started')
            # update status
            mode_resp.status = STARTED
            # keyboard checking is just starting
            waitOnFlip = True
            win.callOnFlip(mode_resp.clock.reset)  # t=0 on next screen flip
            win.callOnFlip(mode_resp.clearEvents, eventType='keyboard')  # clear events on next screen flip
        if mode_resp.status == STARTED and not waitOnFlip:
            theseKeys = mode_resp.getKeys(keyList=['t', 's'], waitRelease=False)
            _mode_resp_allKeys.extend(theseKeys)
            if len(_mode_resp_allKeys):
                mode_resp.keys = _mode_resp_allKeys[-1].name  # just the last key pressed
                mode_resp.rt = _mode_resp_allKeys[-1].rt
                # a response ends the routine
                continueRoutine = False

        # check for quit (typically the Esc key)
        if endExpNow or defaultKeyboard.getKeys(keyList=["escape"]):
            # ----------------------------------------------------------------------------------------------------------
            quit_game(lsl_inlet=lsl_inlet)
            # ----------------------------------------------------------------------------------------------------------
            core.quit()

        # check if all components have finished
        if not continueRoutine:  # a component has requested a forced-end of Routine
            routineForceEnded = True
            break
        continueRoutine = False  # will revert to True if at least one component still running
        for thisComponent in modeComponents:
            if hasattr(thisComponent, "status") and thisComponent.status != FINISHED:
                continueRoutine = True
                break  # at least one component has not yet finished

        # refresh the screen
        if continueRoutine:  # don't flip if this routine is over or we'll get a blank screen
            win.flip()

    # --- Ending Routine "mode" ---
    for thisComponent in modeComponents:
        if hasattr(thisComponent, "setAutoDraw"):
            thisComponent.setAutoDraw(False)
    # check responses
    if mode_resp.keys in ['', [], None]:  # No response was made
        mode_resp.keys = None
    trials_5.addData('mode_resp.keys', mode_resp.keys)
    if mode_resp.keys != None:  # we had a response
        trials_5.addData('mode_resp.rt', mode_resp.rt)
    # Run 'End Routine' code from code_3
    if mode_resp.keys == 't':
        practiceChosen = 1
        gameChosen = 0
        dicti['modeChosen'] = 'practice'
    if mode_resp.keys == 's':
        practiceChosen = 0
        gameChosen = 1
        dicti['modeChosen'] = 'game'
    # the Routine "mode" was not non-slip safe, so reset the non-slip timer
    routineTimer.reset()

    # set up handler to look after randomisation of conditions etc
    showGameLoop = data.TrialHandler(nReps=gameChosen, method='random',
                                     extraInfo=expInfo, originPath=-1,
                                     trialList=[None],
                                     seed=None, name='showGameLoop')
    thisExp.addLoop(showGameLoop)  # add the loop to the experiment
    thisShowGameLoop = showGameLoop.trialList[0]  # so we can initialise stimuli with some values
    # abbreviate parameter names if possible (e.g. rgb = thisShowGameLoop.rgb)
    if thisShowGameLoop != None:
        for paramName in thisShowGameLoop:
            exec('{} = thisShowGameLoop[paramName]'.format(paramName))

    for thisShowGameLoop in showGameLoop:
        currentLoop = showGameLoop
        # abbreviate parameter names if possible (e.g. rgb = thisShowGameLoop.rgb)
        if thisShowGameLoop != None:
            for paramName in thisShowGameLoop:
                exec('{} = thisShowGameLoop[paramName]'.format(paramName))

        # --- Prepare to start Routine "refreshBallPositionGame" ---
        continueRoutine = True
        # update component parameters for each repeat
        # Run 'Begin Routine' code from code_10
        xBall = 0
        yBall = -0.3

        # keep track of which components have finished
        refreshBallPositionGameComponents = []
        for thisComponent in refreshBallPositionGameComponents:
            thisComponent.tStart = None
            thisComponent.tStop = None
            thisComponent.tStartRefresh = None
            thisComponent.tStopRefresh = None
            if hasattr(thisComponent, 'status'):
                thisComponent.status = NOT_STARTED
        # reset timers
        t = 0
        _timeToFirstFrame = win.getFutureFlipTime(clock="now")
        frameN = -1

        # --- Run Routine "refreshBallPositionGame" ---
        routineForceEnded = not continueRoutine
        while continueRoutine:
            # get current time
            t = routineTimer.getTime()
            tThisFlip = win.getFutureFlipTime(clock=routineTimer)
            tThisFlipGlobal = win.getFutureFlipTime(clock=None)
            frameN = frameN + 1  # number of completed frames (so 0 is the first frame)
            # update/draw components on each frame

            # check for quit (typically the Esc key)
            if endExpNow or defaultKeyboard.getKeys(keyList=["escape"]):
                # ------------------------------------------------------------------------------------------------------
                quit_game(lsl_inlet=lsl_inlet)
                # ------------------------------------------------------------------------------------------------------
                core.quit()

            # check if all components have finished
            if not continueRoutine:  # a component has requested a forced-end of Routine
                routineForceEnded = True
                break
            continueRoutine = False  # will revert to True if at least one component still running
            for thisComponent in refreshBallPositionGameComponents:
                if hasattr(thisComponent, "status") and thisComponent.status != FINISHED:
                    continueRoutine = True
                    break  # at least one component has not yet finished

            # refresh the screen
            if continueRoutine:  # don't flip if this routine is over or we'll get a blank screen
                win.flip()

        # --- Ending Routine "refreshBallPositionGame" ---
        for thisComponent in refreshBallPositionGameComponents:
            if hasattr(thisComponent, "setAutoDraw"):
                thisComponent.setAutoDraw(False)
        # Run 'End Routine' code from code_10
        xBall1 = 0
        xBall2 = 0
        xBall3 = 0
        yBall1 = -0.3
        yBall2 = -0.3
        yBall3 = -0.3
        # the Routine "refreshBallPositionGame" was not non-slip safe, so reset the non-slip timer
        routineTimer.reset()

        # set up handler to look after randomisation of conditions etc
        trials_4 = data.TrialHandler(nReps=1000.0, method='random',
                                     extraInfo=expInfo, originPath=-1,
                                     trialList=[None],
                                     seed=None, name='trials_4')
        thisExp.addLoop(trials_4)  # add the loop to the experiment
        thisTrial_4 = trials_4.trialList[0]  # so we can initialise stimuli with some values
        # abbreviate parameter names if possible (e.g. rgb = thisTrial_4.rgb)
        if thisTrial_4 != None:
            for paramName in thisTrial_4:
                exec('{} = thisTrial_4[paramName]'.format(paramName))

        for thisTrial_4 in trials_4:
            currentLoop = trials_4
            # abbreviate parameter names if possible (e.g. rgb = thisTrial_4.rgb)
            if thisTrial_4 != None:
                for paramName in thisTrial_4:
                    exec('{} = thisTrial_4[paramName]'.format(paramName))

            # --- Prepare to start Routine "game" ---
            continueRoutine = True
            # update component parameters for each repeat
            # Run 'Begin Routine' code from code
            mykb = keyboard.Keyboard()
            keysWatched = ['left', 'right']
            status = ['up', 'up']
            football_background.setImage('PsychoPy/football.jpeg')
            ball.setImage('PsychoPy/ball.png')
            # keep track of which components have finished
            gameComponents = [football_background, gate_l, gate_r, footballTitle, ball]
            for thisComponent in gameComponents:
                thisComponent.tStart = None
                thisComponent.tStop = None
                thisComponent.tStartRefresh = None
                thisComponent.tStopRefresh = None
                if hasattr(thisComponent, 'status'):
                    thisComponent.status = NOT_STARTED
            # reset timers
            t = 0
            _timeToFirstFrame = win.getFutureFlipTime(clock="now")
            frameN = -1

            # --- Run Routine "game" ---
            routineForceEnded = not continueRoutine

            # ----------------------------------------------------------------------------------------------------------
            send_trigger(trig=41)
            # ----------------------------------------------------------------------------------------------------------

            while continueRoutine:
                # get current time
                t = routineTimer.getTime()
                tThisFlip = win.getFutureFlipTime(clock=routineTimer)
                tThisFlipGlobal = win.getFutureFlipTime(clock=None)
                frameN = frameN + 1  # number of completed frames (so 0 is the first frame)
                # update/draw components on each frame
                # Run 'Each Frame' code from code

                keys = mykb.getKeys(keysWatched, waitRelease=False, clear=False)

                if len(keys):
                    for i, key in enumerate(keysWatched):
                        if keys[-1].name == key:
                            if keys[-1].duration:
                                status[i] = 'up'
                            else:
                                status[i] = 'down'

                # -------------------------------------------------------------------------------------------------------
                # both hands control
                if hand_side == "both":
                    force_right = 0
                    force_left = 0

                    force_right, data_lsl = get_emg(lsl_inlet=lsl_inlet, data_lsl=data_lsl, emg_ch=emg_ch_right,
                                                   win_len=win_len)
                    force_left, data_lsl = get_emg(lsl_inlet=lsl_inlet, data_lsl=data_lsl, emg_ch=emg_ch_left,
                                                   win_len=win_len)

                    print('Left: ' + str(int(force_left)) + '     Right: ' + str(int(force_right)))

                    thrs_right = set_threshold(file=thrs_file_right)
                    thrs_left = set_threshold(file=thrs_file_left)

                    if force_right > thrs_right[1] or force_left > thrs_left[1]:
                        force_upper_limit = True
                    else:
                        force_upper_limit = False

                    #status = set_movement_status(grip_force=force_right, thrs=thrs_right, hand=1, status=status)
                    #status = set_movement_status(grip_force=force_left, thrs=thrs_left, hand=0, status=status)

                    if thrs_restrict:
                        if force_right > thrs_right[0] and force_right < thrs_right[1] and force_left < thrs_left[0]:
                            status[1] = "down"
                        else:
                            status[1] = "up"

                        if force_left > thrs_left[0] and force_left < thrs_left[1] and force_right < thrs_right[0]:
                            status[0] = "down"
                        else:
                            status[0] = "up"
                    else:
                        if force_right > thrs_right[0] and force_right < thrs_right[1]:
                            status[1] = "down"
                        else:
                            status[1] = "up"

                        if force_left > thrs_left[0] and force_left < thrs_left[1]:
                            status[0] = "down"
                        else:
                            status[0] = "up"

                # ------------------------------------------------------------------------------------------------------
                # single hand control
                else:
                    # Get input: grip force or emg
                    grip_force = 0
                    if ball_control == "grip":
                        grip_force = get_grip_force(lsl_inlet=lsl_inlet, data_lsl=data_lsl)
                    elif ball_control == "emg":
                        grip_force, data_lsl = get_emg(lsl_inlet=lsl_inlet, data_lsl=data_lsl, emg_ch=emg_ch,
                                                       win_len=win_len)
                    else:
                        print("Wrong ball control setting!")
                    # Get input: threshold from txt.file
                    thrs = set_threshold(file=thrs_filename)
                    # Check upper limit
                    if grip_force > thrs[1]:
                        force_upper_limit = True
                    else:
                        force_upper_limit = False
                    # Update movement status
                    status = set_movement_status(grip_force=grip_force, thrs=thrs, hand=hand_side, status=status)


                # ------------------------------------------------------------------------------------------------------

                if status[0] == 'down':
                    xBall -= ball_pos_inc
                    if xBall <= -0.65:
                        trials_4.finished = True
                        continueRoutine = False

                if status[1] == 'down':
                    xBall += ball_pos_inc
                    if xBall >= 0.65:
                        trials_4.finished = True
                        continueRoutine = False

                # *football_background* updates

                # if football_background is starting this frame...
                if football_background.status == NOT_STARTED and tThisFlip >= 0.0 - frameTolerance:
                    # keep track of start time/frame for later
                    football_background.frameNStart = frameN  # exact frame index
                    football_background.tStart = t  # local t and not account for scr refresh
                    football_background.tStartRefresh = tThisFlipGlobal  # on global time
                    win.timeOnFlip(football_background, 'tStartRefresh')  # time at next scr refresh
                    # add timestamp to datafile
                    thisExp.timestampOnFlip(win, 'football_background.started')
                    # update status
                    football_background.status = STARTED
                    football_background.setAutoDraw(True)

                # if football_background is active this frame...
                if football_background.status == STARTED:
                    # update params
                    pass

                # *gate_l* updates

                # if gate_l is starting this frame...
                if gate_l.status == NOT_STARTED and tThisFlip >= 0.0 - frameTolerance:
                    # keep track of start time/frame for later
                    gate_l.frameNStart = frameN  # exact frame index
                    gate_l.tStart = t  # local t and not account for scr refresh
                    gate_l.tStartRefresh = tThisFlipGlobal  # on global time
                    win.timeOnFlip(gate_l, 'tStartRefresh')  # time at next scr refresh
                    # add timestamp to datafile
                    thisExp.timestampOnFlip(win, 'gate_l.started')
                    # update status
                    gate_l.status = STARTED
                    gate_l.setAutoDraw(True)

                # if gate_l is active this frame...
                if gate_l.status == STARTED:
                    # update params
                    pass

                # *gate_r* updates

                # if gate_r is starting this frame...
                if gate_r.status == NOT_STARTED and tThisFlip >= 0.0 - frameTolerance:
                    # keep track of start time/frame for later
                    gate_r.frameNStart = frameN  # exact frame index
                    gate_r.tStart = t  # local t and not account for scr refresh
                    gate_r.tStartRefresh = tThisFlipGlobal  # on global time
                    win.timeOnFlip(gate_r, 'tStartRefresh')  # time at next scr refresh
                    # add timestamp to datafile
                    thisExp.timestampOnFlip(win, 'gate_r.started')
                    # update status
                    gate_r.status = STARTED
                    gate_r.setAutoDraw(True)

                # if gate_r is active this frame...
                if gate_r.status == STARTED:
                    # update params
                    pass

                # *footballTitle* updates

                # if footballTitle is starting this frame...
                if footballTitle.status == NOT_STARTED and tThisFlip >= 0.0 - frameTolerance:
                    # keep track of start time/frame for later
                    footballTitle.frameNStart = frameN  # exact frame index
                    footballTitle.tStart = t  # local t and not account for scr refresh
                    footballTitle.tStartRefresh = tThisFlipGlobal  # on global time
                    win.timeOnFlip(footballTitle, 'tStartRefresh')  # time at next scr refresh
                    # add timestamp to datafile
                    thisExp.timestampOnFlip(win, 'footballTitle.started')
                    # update status
                    footballTitle.status = STARTED
                    footballTitle.setAutoDraw(True)

                # if footballTitle is active this frame...
                if footballTitle.status == STARTED:
                    # update params
                    pass

                # *ball* updates

                # if ball is starting this frame...
                if ball.status == NOT_STARTED and tThisFlip >= 0.0 - frameTolerance:
                    # keep track of start time/frame for later
                    ball.frameNStart = frameN  # exact frame index
                    ball.tStart = t  # local t and not account for scr refresh
                    ball.tStartRefresh = tThisFlipGlobal  # on global time
                    win.timeOnFlip(ball, 'tStartRefresh')  # time at next scr refresh
                    # add timestamp to datafile
                    thisExp.timestampOnFlip(win, 'ball.started')
                    # update status
                    ball.status = STARTED
                    ball.setAutoDraw(True)

                # if ball is active this frame...
                if ball.status == STARTED:
                    if force_upper_limit:
                        ball.setImage('PsychoPy/ball_red.png')
                    else:
                        ball.setImage('PsychoPy/ball.png')
                    # update params
                    ball.setPos((xBall, yBall), log=False)



                # check for quit (typically the Esc key)
                if endExpNow or defaultKeyboard.getKeys(keyList=["escape"]):
                    # --------------------------------------------------------------------------------------------------
                    quit_game(lsl_inlet=lsl_inlet)
                    # --------------------------------------------------------------------------------------------------
                    core.quit()

                # check if all components have finished
                if not continueRoutine:  # a component has requested a forced-end of Routine
                    routineForceEnded = True
                    break
                continueRoutine = False  # will revert to True if at least one component still running
                for thisComponent in gameComponents:
                    if hasattr(thisComponent, "status") and thisComponent.status != FINISHED:
                        continueRoutine = True
                        break  # at least one component has not yet finished

                # refresh the screen
                if continueRoutine:  # don't flip if this routine is over or we'll get a blank screen
                    win.flip()

            # --- Ending Routine "game" ---
            # --------------------------------------------------------------------------------------------------
            if not continueRoutine: send_trigger(trig=42)
            # --------------------------------------------------------------------------------------------------
            for thisComponent in gameComponents:
                if hasattr(thisComponent, "setAutoDraw"):
                    thisComponent.setAutoDraw(False)
            # the Routine "game" was not non-slip safe, so reset the non-slip timer
            routineTimer.reset()
            thisExp.nextEntry()

        # completed 1000.0 repeats of 'trials_4'

        # set up handler to look after randomisation of conditions etc
        trials_3 = data.TrialHandler(nReps=1.0, method='random',
                                     extraInfo=expInfo, originPath=-1,
                                     trialList=[None],
                                     seed=None, name='trials_3')
        thisExp.addLoop(trials_3)  # add the loop to the experiment
        thisTrial_3 = trials_3.trialList[0]  # so we can initialise stimuli with some values
        # abbreviate parameter names if possible (e.g. rgb = thisTrial_3.rgb)
        if thisTrial_3 != None:
            for paramName in thisTrial_3:
                exec('{} = thisTrial_3[paramName]'.format(paramName))

        for thisTrial_3 in trials_3:
            currentLoop = trials_3
            # abbreviate parameter names if possible (e.g. rgb = thisTrial_3.rgb)
            if thisTrial_3 != None:
                for paramName in thisTrial_3:
                    exec('{} = thisTrial_3[paramName]'.format(paramName))

            # --- Prepare to start Routine "gameWon" ---
            continueRoutine = True
            # update component parameters for each repeat
            consent_resp_2.keys = []
            consent_resp_2.rt = []
            _consent_resp_2_allKeys = []
            congrats_background_2.setImage('PsychoPy/congrats.png')
            sound_1.setSound('PsychoPy/congrats.mp3', secs=5, hamming=True)
            sound_1.setVolume(20.0, log=False)
            # keep track of which components have finished
            gameWonComponents = [consent_resp_2, congrats_background_2, consentTxt_2, sound_1]
            for thisComponent in gameWonComponents:
                thisComponent.tStart = None
                thisComponent.tStop = None
                thisComponent.tStartRefresh = None
                thisComponent.tStopRefresh = None
                if hasattr(thisComponent, 'status'):
                    thisComponent.status = NOT_STARTED
            # reset timers
            t = 0
            _timeToFirstFrame = win.getFutureFlipTime(clock="now")
            frameN = -1

            # --- Run Routine "gameWon" ---
            routineForceEnded = not continueRoutine

            while continueRoutine and routineTimer.getTime() < 5.0:
                # get current time
                t = routineTimer.getTime()
                tThisFlip = win.getFutureFlipTime(clock=routineTimer)
                tThisFlipGlobal = win.getFutureFlipTime(clock=None)
                frameN = frameN + 1  # number of completed frames (so 0 is the first frame)
                # update/draw components on each frame

                # *consent_resp_2* updates
                waitOnFlip = False

                # if consent_resp_2 is starting this frame...
                if consent_resp_2.status == NOT_STARTED and tThisFlip >= 0.0 - frameTolerance:
                    # keep track of start time/frame for later
                    consent_resp_2.frameNStart = frameN  # exact frame index
                    consent_resp_2.tStart = t  # local t and not account for scr refresh
                    consent_resp_2.tStartRefresh = tThisFlipGlobal  # on global time
                    win.timeOnFlip(consent_resp_2, 'tStartRefresh')  # time at next scr refresh
                    # add timestamp to datafile
                    thisExp.timestampOnFlip(win, 'consent_resp_2.started')
                    # update status
                    consent_resp_2.status = STARTED
                    # keyboard checking is just starting
                    waitOnFlip = True
                    win.callOnFlip(consent_resp_2.clock.reset)  # t=0 on next screen flip
                    win.callOnFlip(consent_resp_2.clearEvents, eventType='keyboard')  # clear events on next screen flip

                # if consent_resp_2 is stopping this frame...
                if consent_resp_2.status == STARTED:
                    # is it time to stop? (based on global clock, using actual start)
                    if tThisFlipGlobal > consent_resp_2.tStartRefresh + 5 - frameTolerance:
                        # keep track of stop time/frame for later
                        consent_resp_2.tStop = t  # not accounting for scr refresh
                        consent_resp_2.frameNStop = frameN  # exact frame index
                        # add timestamp to datafile
                        thisExp.timestampOnFlip(win, 'consent_resp_2.stopped')
                        # update status
                        consent_resp_2.status = FINISHED
                        consent_resp_2.status = FINISHED
                if consent_resp_2.status == STARTED and not waitOnFlip:
                    theseKeys = consent_resp_2.getKeys(keyList=['left', 'right'], waitRelease=False)
                    _consent_resp_2_allKeys.extend(theseKeys)
                    if len(_consent_resp_2_allKeys):
                        consent_resp_2.keys = _consent_resp_2_allKeys[-1].name  # just the last key pressed
                        consent_resp_2.rt = _consent_resp_2_allKeys[-1].rt
                        # a response ends the routine
                        continueRoutine = False

                # *congrats_background_2* updates

                # if congrats_background_2 is starting this frame...
                if congrats_background_2.status == NOT_STARTED and tThisFlip >= 0.0 - frameTolerance:
                    # keep track of start time/frame for later
                    congrats_background_2.frameNStart = frameN  # exact frame index
                    congrats_background_2.tStart = t  # local t and not account for scr refresh
                    congrats_background_2.tStartRefresh = tThisFlipGlobal  # on global time
                    win.timeOnFlip(congrats_background_2, 'tStartRefresh')  # time at next scr refresh
                    # add timestamp to datafile
                    thisExp.timestampOnFlip(win, 'congrats_background_2.started')
                    # update status
                    congrats_background_2.status = STARTED
                    congrats_background_2.setAutoDraw(True)

                # if congrats_background_2 is active this frame...
                if congrats_background_2.status == STARTED:
                    # update params
                    pass

                # if congrats_background_2 is stopping this frame...
                if congrats_background_2.status == STARTED:
                    # is it time to stop? (based on global clock, using actual start)
                    if tThisFlipGlobal > congrats_background_2.tStartRefresh + 5 - frameTolerance:
                        # keep track of stop time/frame for later
                        congrats_background_2.tStop = t  # not accounting for scr refresh
                        congrats_background_2.frameNStop = frameN  # exact frame index
                        # add timestamp to datafile
                        thisExp.timestampOnFlip(win, 'congrats_background_2.stopped')
                        # update status
                        congrats_background_2.status = FINISHED
                        congrats_background_2.setAutoDraw(False)

                # *consentTxt_2* updates

                # if consentTxt_2 is starting this frame...
                if consentTxt_2.status == NOT_STARTED and tThisFlip >= 0.0 - frameTolerance:
                    # keep track of start time/frame for later
                    consentTxt_2.frameNStart = frameN  # exact frame index
                    consentTxt_2.tStart = t  # local t and not account for scr refresh
                    consentTxt_2.tStartRefresh = tThisFlipGlobal  # on global time
                    win.timeOnFlip(consentTxt_2, 'tStartRefresh')  # time at next scr refresh
                    # add timestamp to datafile
                    thisExp.timestampOnFlip(win, 'consentTxt_2.started')
                    # update status
                    consentTxt_2.status = STARTED
                    consentTxt_2.setAutoDraw(True)

                # if consentTxt_2 is active this frame...
                if consentTxt_2.status == STARTED:
                    # update params
                    pass

                # if consentTxt_2 is stopping this frame...
                if consentTxt_2.status == STARTED:
                    # is it time to stop? (based on global clock, using actual start)
                    if tThisFlipGlobal > consentTxt_2.tStartRefresh + 5 - frameTolerance:
                        # keep track of stop time/frame for later
                        consentTxt_2.tStop = t  # not accounting for scr refresh
                        consentTxt_2.frameNStop = frameN  # exact frame index
                        # add timestamp to datafile
                        thisExp.timestampOnFlip(win, 'consentTxt_2.stopped')
                        # update status
                        consentTxt_2.status = FINISHED
                        consentTxt_2.setAutoDraw(False)

                # start/stop sound_1

                # if sound_1 is starting this frame...
                if sound_1.status == NOT_STARTED and tThisFlip >= 0.0 - frameTolerance:
                    # keep track of start time/frame for later
                    sound_1.frameNStart = frameN  # exact frame index
                    sound_1.tStart = t  # local t and not account for scr refresh
                    sound_1.tStartRefresh = tThisFlipGlobal  # on global time
                    # add timestamp to datafile
                    thisExp.addData('sound_1.started', tThisFlipGlobal)
                    # update status
                    sound_1.status = STARTED
                    sound_1.play(when=win)  # sync with win flip

                # if sound_1 is stopping this frame...
                if sound_1.status == STARTED:
                    # is it time to stop? (based on global clock, using actual start)
                    if tThisFlipGlobal > sound_1.tStartRefresh + 5 - frameTolerance:
                        # keep track of stop time/frame for later
                        sound_1.tStop = t  # not accounting for scr refresh
                        sound_1.frameNStop = frameN  # exact frame index
                        # add timestamp to datafile
                        thisExp.timestampOnFlip(win, 'sound_1.stopped')
                        # update status
                        sound_1.status = FINISHED
                        sound_1.stop()

                # --------------------------------------------------------------------------------------------------
                if data_lsl is not None:
                    print(np.shape(data_lsl))
                    data_lsl = None
                    print(np.shape(data_lsl))
                # --------------------------------------------------------------------------------------------------

                # check for quit (typically the Esc key)
                if endExpNow or defaultKeyboard.getKeys(keyList=["escape"]):
                    # --------------------------------------------------------------------------------------------------
                    quit_game(lsl_inlet=lsl_inlet)
                    # --------------------------------------------------------------------------------------------------
                    core.quit()

                # check if all components have finished
                if not continueRoutine:  # a component has requested a forced-end of Routine
                    routineForceEnded = True
                    break
                continueRoutine = False  # will revert to True if at least one component still running
                for thisComponent in gameWonComponents:
                    if hasattr(thisComponent, "status") and thisComponent.status != FINISHED:
                        continueRoutine = True
                        break  # at least one component has not yet finished

                # refresh the screen
                if continueRoutine:  # don't flip if this routine is over or we'll get a blank screen
                    win.flip()

            # --- Ending Routine "gameWon" ---
            for thisComponent in gameWonComponents:
                if hasattr(thisComponent, "setAutoDraw"):
                    thisComponent.setAutoDraw(False)
            # check responses
            if consent_resp_2.keys in ['', [], None]:  # No response was made
                consent_resp_2.keys = None
            trials_3.addData('consent_resp_2.keys', consent_resp_2.keys)
            if consent_resp_2.keys != None:  # we had a response
                trials_3.addData('consent_resp_2.rt', consent_resp_2.rt)
            sound_1.stop()  # ensure sound has stopped at end of routine
            # using non-slip timing so subtract the expected duration of this Routine (unless ended on request)
            if routineForceEnded:
                routineTimer.reset()
            else:
                routineTimer.addTime(-5.000000)
        # completed 1.0 repeats of 'trials_3'

        thisExp.nextEntry()

    # completed gameChosen repeats of 'showGameLoop'

    # set up handler to look after randomisation of conditions etc
    showPracticeLoop = data.TrialHandler(nReps=practiceChosen, method='random',
                                         extraInfo=expInfo, originPath=-1,
                                         trialList=[None],
                                         seed=None, name='showPracticeLoop')
    thisExp.addLoop(showPracticeLoop)  # add the loop to the experiment
    thisShowPracticeLoop = showPracticeLoop.trialList[0]  # so we can initialise stimuli with some values
    # abbreviate parameter names if possible (e.g. rgb = thisShowPracticeLoop.rgb)
    if thisShowPracticeLoop != None:
        for paramName in thisShowPracticeLoop:
            exec('{} = thisShowPracticeLoop[paramName]'.format(paramName))

    for thisShowPracticeLoop in showPracticeLoop:
        currentLoop = showPracticeLoop
        # abbreviate parameter names if possible (e.g. rgb = thisShowPracticeLoop.rgb)
        if thisShowPracticeLoop != None:
            for paramName in thisShowPracticeLoop:
                exec('{} = thisShowPracticeLoop[paramName]'.format(paramName))

        # set up handler to look after randomisation of conditions etc
        trials = data.TrialHandler(nReps=1.0, method='random',
                                   extraInfo=expInfo, originPath=-1,
                                   trialList=[None],
                                   seed=None, name='trials')
        thisExp.addLoop(trials)  # add the loop to the experiment
        thisTrial = trials.trialList[0]  # so we can initialise stimuli with some values
        # abbreviate parameter names if possible (e.g. rgb = thisTrial.rgb)
        if thisTrial != None:
            for paramName in thisTrial:
                exec('{} = thisTrial[paramName]'.format(paramName))

        for thisTrial in trials:
            currentLoop = trials
            # abbreviate parameter names if possible (e.g. rgb = thisTrial.rgb)
            if thisTrial != None:
                for paramName in thisTrial:
                    exec('{} = thisTrial[paramName]'.format(paramName))

            # --- Prepare to start Routine "practice" ---
            continueRoutine = True

            # update component parameters for each repeat
            practice_resp.keys = []
            practice_resp.rt = []
            _practice_resp_allKeys = []
            # Run 'Begin Routine' code from code_4
            if practice_resp.keys == '1':
                level1Chosen = 15
                level2Chosen = 0
                level3Chosen = 0
                dicti['level'] = '1'
            if practice_resp.keys == '2':
                level1Chosen = 0
                level2Chosen = 15
                level3Chosen = 0
                dicti['level'] = '2'
            if practice_resp.keys == '3':
                level1Chosen = 0
                level2Chosen = 0
                level3Chosen = 15
                dicti['level'] = '3'
            # keep track of which components have finished
            practiceComponents = [image, text, practice_resp]
            for thisComponent in practiceComponents:
                thisComponent.tStart = None
                thisComponent.tStop = None
                thisComponent.tStartRefresh = None
                thisComponent.tStopRefresh = None
                if hasattr(thisComponent, 'status'):
                    thisComponent.status = NOT_STARTED
            # reset timers
            t = 0
            _timeToFirstFrame = win.getFutureFlipTime(clock="now")
            frameN = -1

            # --- Run Routine "practice" ---
            routineForceEnded = not continueRoutine
            while continueRoutine:
                # get current time
                t = routineTimer.getTime()
                tThisFlip = win.getFutureFlipTime(clock=routineTimer)
                tThisFlipGlobal = win.getFutureFlipTime(clock=None)
                frameN = frameN + 1  # number of completed frames (so 0 is the first frame)
                # update/draw components on each frame

                # *image* updates

                # if image is starting this frame...
                if image.status == NOT_STARTED and tThisFlip >= 0.0 - frameTolerance:
                    # keep track of start time/frame for later
                    image.frameNStart = frameN  # exact frame index
                    image.tStart = t  # local t and not account for scr refresh
                    image.tStartRefresh = tThisFlipGlobal  # on global time
                    win.timeOnFlip(image, 'tStartRefresh')  # time at next scr refresh
                    # add timestamp to datafile
                    thisExp.timestampOnFlip(win, 'image.started')
                    # update status
                    image.status = STARTED
                    image.setAutoDraw(True)

                # if image is active this frame...
                if image.status == STARTED:
                    # update params
                    pass

                # *text* updates

                # if text is starting this frame...
                if text.status == NOT_STARTED and tThisFlip >= 0.0 - frameTolerance:
                    # keep track of start time/frame for later
                    text.frameNStart = frameN  # exact frame index
                    text.tStart = t  # local t and not account for scr refresh
                    text.tStartRefresh = tThisFlipGlobal  # on global time
                    win.timeOnFlip(text, 'tStartRefresh')  # time at next scr refresh
                    # add timestamp to datafile
                    thisExp.timestampOnFlip(win, 'text.started')
                    # update status
                    text.status = STARTED
                    text.setAutoDraw(True)

                # if text is active this frame...
                if text.status == STARTED:
                    # update params
                    pass

                # *practice_resp* updates
                waitOnFlip = False

                # if practice_resp is starting this frame...
                if practice_resp.status == NOT_STARTED and tThisFlip >= 0.0 - frameTolerance:
                    # keep track of start time/frame for later
                    practice_resp.frameNStart = frameN  # exact frame index
                    practice_resp.tStart = t  # local t and not account for scr refresh
                    practice_resp.tStartRefresh = tThisFlipGlobal  # on global time
                    win.timeOnFlip(practice_resp, 'tStartRefresh')  # time at next scr refresh
                    # add timestamp to datafile
                    thisExp.timestampOnFlip(win, 'practice_resp.started')
                    # update status
                    practice_resp.status = STARTED
                    # keyboard checking is just starting
                    waitOnFlip = True
                    win.callOnFlip(practice_resp.clock.reset)  # t=0 on next screen flip
                    win.callOnFlip(practice_resp.clearEvents, eventType='keyboard')  # clear events on next screen flip
                if practice_resp.status == STARTED and not waitOnFlip:
                    theseKeys = practice_resp.getKeys(keyList=['1', '2', '3'], waitRelease=False)
                    _practice_resp_allKeys.extend(theseKeys)
                    if len(_practice_resp_allKeys):
                        practice_resp.keys = _practice_resp_allKeys[-1].name  # just the last key pressed
                        practice_resp.rt = _practice_resp_allKeys[-1].rt
                        # a response ends the routine
                        continueRoutine = False

                # check for quit (typically the Esc key)
                if endExpNow or defaultKeyboard.getKeys(keyList=["escape"]):
                    # --------------------------------------------------------------------------------------------------
                    quit_game(lsl_inlet=lsl_inlet)
                    # --------------------------------------------------------------------------------------------------
                    core.quit()

                # check if all components have finished
                if not continueRoutine:  # a component has requested a forced-end of Routine
                    routineForceEnded = True
                    break
                continueRoutine = False  # will revert to True if at least one component still running
                for thisComponent in practiceComponents:
                    if hasattr(thisComponent, "status") and thisComponent.status != FINISHED:
                        continueRoutine = True
                        break  # at least one component has not yet finished

                # refresh the screen
                if continueRoutine:  # don't flip if this routine is over or we'll get a blank screen
                    win.flip()

            # --- Ending Routine "practice" ---
            for thisComponent in practiceComponents:
                if hasattr(thisComponent, "setAutoDraw"):
                    thisComponent.setAutoDraw(False)
            # check responses
            if practice_resp.keys in ['', [], None]:  # No response was made
                practice_resp.keys = None
            trials.addData('practice_resp.keys', practice_resp.keys)
            if practice_resp.keys != None:  # we had a response
                trials.addData('practice_resp.rt', practice_resp.rt)
            # Run 'End Routine' code from code_4
            if practice_resp.keys == '1':
                level1Chosen = 15
                level2Chosen = 0
                level3Chosen = 0
                dicti['level'] = '1'
            if practice_resp.keys == '2':
                level1Chosen = 0
                level2Chosen = 15
                level3Chosen = 0
                dicti['level'] = '2'
            if practice_resp.keys == '3':
                level1Chosen = 0
                level2Chosen = 0
                level3Chosen = 15
                dicti['level'] = '3'
            # the Routine "practice" was not non-slip safe, so reset the non-slip timer
            routineTimer.reset()
        # completed 1.0 repeats of 'trials'

        # --- Prepare to start Routine "refreshBallPosition" ---
        continueRoutine = True
        # update component parameters for each repeat
        # Run 'Begin Routine' code from code_8
        xBall1 = 0
        xBall2 = 0
        xBall3 = 0
        yBall1 = -0.3
        yBall2 = -0.3
        yBall3 = -0.3
        leftClciked = 0
        rightClicked = 0
        # keep track of which components have finished
        refreshBallPositionComponents = []
        for thisComponent in refreshBallPositionComponents:
            thisComponent.tStart = None
            thisComponent.tStop = None
            thisComponent.tStartRefresh = None
            thisComponent.tStopRefresh = None
            if hasattr(thisComponent, 'status'):
                thisComponent.status = NOT_STARTED
        # reset timers
        t = 0
        _timeToFirstFrame = win.getFutureFlipTime(clock="now")
        frameN = -1

        # --- Run Routine "refreshBallPosition" ---
        routineForceEnded = not continueRoutine
        while continueRoutine:
            # get current time
            t = routineTimer.getTime()
            tThisFlip = win.getFutureFlipTime(clock=routineTimer)
            tThisFlipGlobal = win.getFutureFlipTime(clock=None)
            frameN = frameN + 1  # number of completed frames (so 0 is the first frame)
            # update/draw components on each frame

            # check for quit (typically the Esc key)
            if endExpNow or defaultKeyboard.getKeys(keyList=["escape"]):
                # ------------------------------------------------------------------------------------------------------
                quit_game(lsl_inlet=lsl_inlet)
                # ------------------------------------------------------------------------------------------------------
                core.quit()

            # check if all components have finished
            if not continueRoutine:  # a component has requested a forced-end of Routine
                routineForceEnded = True
                break
            continueRoutine = False  # will revert to True if at least one component still running
            for thisComponent in refreshBallPositionComponents:
                if hasattr(thisComponent, "status") and thisComponent.status != FINISHED:
                    continueRoutine = True
                    break  # at least one component has not yet finished

            # refresh the screen
            if continueRoutine:  # don't flip if this routine is over or we'll get a blank screen
                win.flip()

        # --- Ending Routine "refreshBallPosition" ---
        for thisComponent in refreshBallPositionComponents:
            if hasattr(thisComponent, "setAutoDraw"):
                thisComponent.setAutoDraw(False)
        # Run 'End Routine' code from code_8
        xBall1 = 0
        xBall2 = 0
        xBall3 = 0
        yBall1 = -0.3
        yBall2 = -0.3
        yBall3 = -0.3
        leftClciked = 0
        rightClicked = 0
        # the Routine "refreshBallPosition" was not non-slip safe, so reset the non-slip timer
        routineTimer.reset()

        # set up handler to look after randomisation of conditions etc
        triallevel1 = data.TrialHandler(nReps=level1Chosen, method='random',
                                        extraInfo=expInfo, originPath=-1,
                                        trialList=[None],
                                        seed=None, name='triallevel1')
        thisExp.addLoop(triallevel1)  # add the loop to the experiment
        thisTriallevel1 = triallevel1.trialList[0]  # so we can initialise stimuli with some values
        # abbreviate parameter names if possible (e.g. rgb = thisTriallevel1.rgb)
        if thisTriallevel1 != None:
            for paramName in thisTriallevel1:
                exec('{} = thisTriallevel1[paramName]'.format(paramName))

        for thisTriallevel1 in triallevel1:
            currentLoop = triallevel1
            # abbreviate parameter names if possible (e.g. rgb = thisTriallevel1.rgb)
            if thisTriallevel1 != None:
                for paramName in thisTriallevel1:
                    exec('{} = thisTriallevel1[paramName]'.format(paramName))

            # --- Prepare to start Routine "level1" ---
            continueRoutine = True
            # update component parameters for each repeat
            # Run 'Begin Routine' code from code_5
            mykb = keyboard.Keyboard()
            keysWatched = ['left', 'right']
            status = ['up', 'up']

            ball_level1.setImage('PsychoPy/ball.png')
            # keep track of which components have finished
            level1Components = [image_3, text_3, gate_l_l1, gate_r_l1, ball_level1]
            for thisComponent in level1Components:
                thisComponent.tStart = None
                thisComponent.tStop = None
                thisComponent.tStartRefresh = None
                thisComponent.tStopRefresh = None
                if hasattr(thisComponent, 'status'):
                    thisComponent.status = NOT_STARTED
            # reset timers
            t = 0
            _timeToFirstFrame = win.getFutureFlipTime(clock="now")
            frameN = -1

            # --- Run Routine "level1" ---
            routineForceEnded = not continueRoutine
            # ----------------------------------------------------------------------------------------------------------
            send_trigger(trig=11)
            # ----------------------------------------------------------------------------------------------------------
            while continueRoutine:
                # get current time
                t = routineTimer.getTime()
                tThisFlip = win.getFutureFlipTime(clock=routineTimer)
                tThisFlipGlobal = win.getFutureFlipTime(clock=None)
                frameN = frameN + 1  # number of completed frames (so 0 is the first frame)
                # update/draw components on each frame
                # Run 'Each Frame' code from code_5
                keys = mykb.getKeys(keysWatched, waitRelease=False, clear=False)

                if len(keys):
                    for i, key in enumerate(keysWatched):
                        if keys[-1].name == key:
                            if keys[-1].duration:
                                status[i] = 'up'
                            else:
                                status[i] = 'down'

                # ------------------------------------------------------------------------------------------------------
                # Get input: grip force or emg
                grip_force = 0
                if ball_control == "grip":
                    grip_force = get_grip_force(lsl_inlet=lsl_inlet, data_lsl=data_lsl)
                elif ball_control == "emg":
                    grip_force, data_lsl = get_emg(lsl_inlet=lsl_inlet, data_lsl=data_lsl, emg_ch=emg_ch,
                                                   win_len=win_len)
                else:
                    print("Wrong ball control setting!")
                # Get input: threshold from txt.file
                thrs = set_threshold(file=thrs_filename)
                # Check upper limit
                if grip_force > thrs[1]:
                    force_upper_limit = True
                else:
                    force_upper_limit = False
                # Update movement status
                status = set_movement_status(grip_force=grip_force, thrs=thrs, hand=hand_side, status=status)
                # ------------------------------------------------------------------------------------------------------

                if status[0] == 'down':
                    xBall1 -= ball_pos_inc
                    if xBall1 <= -0.15:
                        triallevel1.finished = True
                        continueRoutine = False

                if status[1] == 'down':
                    xBall1 += ball_pos_inc
                    if xBall1 >= 0.15:
                        triallevel1.finished = True
                        continueRoutine = False

                # *image_3* updates

                # if image_3 is starting this frame...
                if image_3.status == NOT_STARTED and tThisFlip >= 0.0 - frameTolerance:
                    # keep track of start time/frame for later
                    image_3.frameNStart = frameN  # exact frame index
                    image_3.tStart = t  # local t and not account for scr refresh
                    image_3.tStartRefresh = tThisFlipGlobal  # on global time
                    win.timeOnFlip(image_3, 'tStartRefresh')  # time at next scr refresh
                    # add timestamp to datafile
                    thisExp.timestampOnFlip(win, 'image_3.started')
                    # update status
                    image_3.status = STARTED
                    image_3.setAutoDraw(True)

                # if image_3 is active this frame...
                if image_3.status == STARTED:
                    # update params
                    pass

                # *text_3* updates

                # if text_3 is starting this frame...
                if text_3.status == NOT_STARTED and tThisFlip >= 0.0 - frameTolerance:
                    # keep track of start time/frame for later
                    text_3.frameNStart = frameN  # exact frame index
                    text_3.tStart = t  # local t and not account for scr refresh
                    text_3.tStartRefresh = tThisFlipGlobal  # on global time
                    win.timeOnFlip(text_3, 'tStartRefresh')  # time at next scr refresh
                    # add timestamp to datafile
                    thisExp.timestampOnFlip(win, 'text_3.started')
                    # update status
                    text_3.status = STARTED
                    text_3.setAutoDraw(True)

                # if text_3 is active this frame...
                if text_3.status == STARTED:
                    # update params
                    pass

                # -------------------------------------------------------------------------------------------------------
                # *gate_l_l1* updates

                if hand_side == "left":
                    # if gate_l_l1 is starting this frame...
                    if gate_l_l1.status == NOT_STARTED and tThisFlip >= 0.0 - frameTolerance:
                        # keep track of start time/frame for later
                        gate_l_l1.frameNStart = frameN  # exact frame index
                        gate_l_l1.tStart = t  # local t and not account for scr refresh
                        gate_l_l1.tStartRefresh = tThisFlipGlobal  # on global time
                        win.timeOnFlip(gate_l_l1, 'tStartRefresh')  # time at next scr refresh
                        # add timestamp to datafile
                        thisExp.timestampOnFlip(win, 'gate_l_l1.started')
                        # update status
                        gate_l_l1.status = STARTED
                        gate_l_l1.setAutoDraw(True)

                    # if gate_l_l1 is active this frame...
                    if gate_l_l1.status == STARTED:
                        # update params
                        pass

                # *gate_r_l1* updates
                if hand_side == "right":
                    # if gate_r_l1 is starting this frame...
                    if gate_r_l1.status == NOT_STARTED and tThisFlip >= 0.0 - frameTolerance:
                        # keep track of start time/frame for later
                        gate_r_l1.frameNStart = frameN  # exact frame index
                        gate_r_l1.tStart = t  # local t and not account for scr refresh
                        gate_r_l1.tStartRefresh = tThisFlipGlobal  # on global time
                        win.timeOnFlip(gate_r_l1, 'tStartRefresh')  # time at next scr refresh
                        # add timestamp to datafile
                        thisExp.timestampOnFlip(win, 'gate_r_l1.started')
                        # update status
                        gate_r_l1.status = STARTED
                        gate_r_l1.setAutoDraw(True)

                    # if gate_r_l1 is active this frame...
                    if gate_r_l1.status == STARTED:
                        # update params
                        pass
                # ------------------------------------------------------------------------------------------------------

                # *ball_level1* updates

                # if ball_level1 is starting this frame...
                if ball_level1.status == NOT_STARTED and tThisFlip >= 0.0 - frameTolerance:
                    # keep track of start time/frame for later
                    ball_level1.frameNStart = frameN  # exact frame index
                    ball_level1.tStart = t  # local t and not account for scr refresh
                    ball_level1.tStartRefresh = tThisFlipGlobal  # on global time
                    win.timeOnFlip(ball_level1, 'tStartRefresh')  # time at next scr refresh
                    # add timestamp to datafile
                    thisExp.timestampOnFlip(win, 'ball_level1.started')
                    # update status
                    ball_level1.status = STARTED
                    ball_level1.setAutoDraw(True)

                # if ball_level1 is active this frame...
                if ball_level1.status == STARTED:
                    if force_upper_limit:
                        ball_level1.setImage('PsychoPy/ball_red.png')
                    else:
                        ball_level1.setImage('PsychoPy/ball.png')
                    # update params
                    ball_level1.setPos((xBall1, yBall1), log=False)

                # check for quit (typically the Esc key)
                if endExpNow or defaultKeyboard.getKeys(keyList=["escape"]):
                    # --------------------------------------------------------------------------------------------------
                    quit_game(lsl_inlet=lsl_inlet)
                    # --------------------------------------------------------------------------------------------------
                    core.quit()

                # check if all components have finished
                if not continueRoutine:  # a component has requested a forced-end of Routine
                    routineForceEnded = True
                    break
                continueRoutine = False  # will revert to True if at least one component still running
                for thisComponent in level1Components:
                    if hasattr(thisComponent, "status") and thisComponent.status != FINISHED:
                        continueRoutine = True
                        break  # at least one component has not yet finished

                # refresh the screen
                if continueRoutine:  # don't flip if this routine is over or we'll get a blank screen
                    win.flip()

            # --- Ending Routine "level1" ---
            # ----------------------------------------------------------------------------------------------------------
            if not continueRoutine: send_trigger(trig=12)
            # ----------------------------------------------------------------------------------------------------------
            for thisComponent in level1Components:
                if hasattr(thisComponent, "setAutoDraw"):
                    thisComponent.setAutoDraw(False)
            # the Routine "level1" was not non-slip safe, so reset the non-slip timer
            routineTimer.reset()
            thisExp.nextEntry()

        # completed level1Chosen repeats of 'triallevel1'

        # set up handler to look after randomisation of conditions etc
        triallevel2 = data.TrialHandler(nReps=level2Chosen, method='random',
                                        extraInfo=expInfo, originPath=-1,
                                        trialList=[None],
                                        seed=None, name='triallevel2')
        thisExp.addLoop(triallevel2)  # add the loop to the experiment
        thisTriallevel2 = triallevel2.trialList[0]  # so we can initialise stimuli with some values
        # abbreviate parameter names if possible (e.g. rgb = thisTriallevel2.rgb)
        if thisTriallevel2 != None:
            for paramName in thisTriallevel2:
                exec('{} = thisTriallevel2[paramName]'.format(paramName))

        for thisTriallevel2 in triallevel2:
            currentLoop = triallevel2
            # abbreviate parameter names if possible (e.g. rgb = thisTriallevel2.rgb)
            if thisTriallevel2 != None:
                for paramName in thisTriallevel2:
                    exec('{} = thisTriallevel2[paramName]'.format(paramName))

            # --- Prepare to start Routine "level2" ---
            continueRoutine = True
            # update component parameters for each repeat
            # Run 'Begin Routine' code from code_6
            mykb = keyboard.Keyboard()
            keysWatched = ['left', 'right']
            status = ['up', 'up']

            ball_level2.setImage('PsychoPy/ball.png')
            # keep track of which components have finished
            level2Components = [image_4, text_4, gate_r2, gate_l2, ball_level2]
            for thisComponent in level2Components:
                thisComponent.tStart = None
                thisComponent.tStop = None
                thisComponent.tStartRefresh = None
                thisComponent.tStopRefresh = None
                if hasattr(thisComponent, 'status'):
                    thisComponent.status = NOT_STARTED
            # reset timers
            t = 0
            _timeToFirstFrame = win.getFutureFlipTime(clock="now")
            frameN = -1

            # --- Run Routine "level2" ---
            routineForceEnded = not continueRoutine
            # ----------------------------------------------------------------------------------------------------------
            send_trigger(trig=21)
            # ----------------------------------------------------------------------------------------------------------
            while continueRoutine:
                # get current time
                t = routineTimer.getTime()
                tThisFlip = win.getFutureFlipTime(clock=routineTimer)
                tThisFlipGlobal = win.getFutureFlipTime(clock=None)
                frameN = frameN + 1  # number of completed frames (so 0 is the first frame)
                # update/draw components on each frame
                # Run 'Each Frame' code from code_6
                keys = mykb.getKeys(keysWatched, waitRelease=False, clear=False)

                if len(keys):
                    for i, key in enumerate(keysWatched):
                        if keys[-1].name == key:
                            if keys[-1].duration:
                                status[i] = 'up'
                            else:
                                status[i] = 'down'

                # ------------------------------------------------------------------------------------------------------
                # Get input: grip force or emg
                grip_force = 0
                if ball_control == "grip":
                    grip_force = get_grip_force(lsl_inlet=lsl_inlet, data_lsl=data_lsl)
                elif ball_control == "emg":
                    grip_force, data_lsl = get_emg(lsl_inlet=lsl_inlet, data_lsl=data_lsl, emg_ch=emg_ch,
                                                   win_len=win_len)
                else:
                    print("Wrong ball control setting!")
                # Get input: threshold from txt.file
                thrs = set_threshold(file=thrs_filename)
                # Check upper limit
                if grip_force > thrs[1]:
                    force_upper_limit = True
                else:
                    force_upper_limit = False
                # Update movement status
                status = set_movement_status(grip_force=grip_force, thrs=thrs, hand=hand_side, status=status)
                # ------------------------------------------------------------------------------------------------------

                if status[0] == 'down':
                    xBall2 -= ball_pos_inc
                    if xBall2 <= -0.25:
                        triallevel2.finished = True
                        continueRoutine = False

                if status[1] == 'down':
                    xBall2 += ball_pos_inc
                    if xBall2 >= 0.25:
                        triallevel2.finished = True
                        continueRoutine = False

                # *image_4* updates

                # if image_4 is starting this frame...
                if image_4.status == NOT_STARTED and tThisFlip >= 0.0 - frameTolerance:
                    # keep track of start time/frame for later
                    image_4.frameNStart = frameN  # exact frame index
                    image_4.tStart = t  # local t and not account for scr refresh
                    image_4.tStartRefresh = tThisFlipGlobal  # on global time
                    win.timeOnFlip(image_4, 'tStartRefresh')  # time at next scr refresh
                    # add timestamp to datafile
                    thisExp.timestampOnFlip(win, 'image_4.started')
                    # update status
                    image_4.status = STARTED
                    image_4.setAutoDraw(True)

                # if image_4 is active this frame...
                if image_4.status == STARTED:
                    # update params
                    pass

                # *text_4* updates

                # if text_4 is starting this frame...
                if text_4.status == NOT_STARTED and tThisFlip >= 0.0 - frameTolerance:
                    # keep track of start time/frame for later
                    text_4.frameNStart = frameN  # exact frame index
                    text_4.tStart = t  # local t and not account for scr refresh
                    text_4.tStartRefresh = tThisFlipGlobal  # on global time
                    win.timeOnFlip(text_4, 'tStartRefresh')  # time at next scr refresh
                    # add timestamp to datafile
                    thisExp.timestampOnFlip(win, 'text_4.started')
                    # update status
                    text_4.status = STARTED
                    text_4.setAutoDraw(True)

                # if text_4 is active this frame...
                if text_4.status == STARTED:
                    # update params
                    pass

                # *gate_r2* updates
                if hand_side == "right":
                    # if gate_r2 is starting this frame...
                    if gate_r2.status == NOT_STARTED and tThisFlip >= 0.0 - frameTolerance:
                        # keep track of start time/frame for later
                        gate_r2.frameNStart = frameN  # exact frame index
                        gate_r2.tStart = t  # local t and not account for scr refresh
                        gate_r2.tStartRefresh = tThisFlipGlobal  # on global time
                        win.timeOnFlip(gate_r2, 'tStartRefresh')  # time at next scr refresh
                        # add timestamp to datafile
                        thisExp.timestampOnFlip(win, 'gate_r2.started')
                        # update status
                        gate_r2.status = STARTED
                        gate_r2.setAutoDraw(True)

                    # if gate_r2 is active this frame...
                    if gate_r2.status == STARTED:
                        # update params
                        pass

                # *gate_l2* updates
                if hand_side == "left":
                    # if gate_l2 is starting this frame...
                    if gate_l2.status == NOT_STARTED and tThisFlip >= 0.0 - frameTolerance:
                        # keep track of start time/frame for later
                        gate_l2.frameNStart = frameN  # exact frame index
                        gate_l2.tStart = t  # local t and not account for scr refresh
                        gate_l2.tStartRefresh = tThisFlipGlobal  # on global time
                        win.timeOnFlip(gate_l2, 'tStartRefresh')  # time at next scr refresh
                        # add timestamp to datafile
                        thisExp.timestampOnFlip(win, 'gate_l2.started')
                        # update status
                        gate_l2.status = STARTED
                        gate_l2.setAutoDraw(True)

                    # if gate_l2 is active this frame...
                    if gate_l2.status == STARTED:
                        # update params
                        pass

                # *ball_level2* updates

                # if ball_level2 is starting this frame...
                if ball_level2.status == NOT_STARTED and tThisFlip >= 0.0 - frameTolerance:
                    # keep track of start time/frame for later
                    ball_level2.frameNStart = frameN  # exact frame index
                    ball_level2.tStart = t  # local t and not account for scr refresh
                    ball_level2.tStartRefresh = tThisFlipGlobal  # on global time
                    win.timeOnFlip(ball_level2, 'tStartRefresh')  # time at next scr refresh
                    # add timestamp to datafile
                    thisExp.timestampOnFlip(win, 'ball_level2.started')
                    # update status
                    ball_level2.status = STARTED
                    ball_level2.setAutoDraw(True)

                # if ball_level2 is active this frame...
                if ball_level2.status == STARTED:
                    if force_upper_limit:
                        ball_level2.setImage('PsychoPy/ball_red.png')
                    else:
                        ball_level2.setImage('PsychoPy/ball.png')
                    # update params
                    ball_level2.setPos((xBall2, yBall2), log=False)

                # check for quit (typically the Esc key)
                if endExpNow or defaultKeyboard.getKeys(keyList=["escape"]):
                    # --------------------------------------------------------------------------------------------------
                    quit_game(lsl_inlet=lsl_inlet)
                    # --------------------------------------------------------------------------------------------------
                    core.quit()

                # check if all components have finished
                if not continueRoutine:  # a component has requested a forced-end of Routine
                    routineForceEnded = True
                    break
                continueRoutine = False  # will revert to True if at least one component still running
                for thisComponent in level2Components:
                    if hasattr(thisComponent, "status") and thisComponent.status != FINISHED:
                        continueRoutine = True
                        break  # at least one component has not yet finished

                # refresh the screen
                if continueRoutine:  # don't flip if this routine is over or we'll get a blank screen
                    win.flip()

            # --- Ending Routine "level2" ---
            # ----------------------------------------------------------------------------------------------------------
            if not continueRoutine: send_trigger(trig=22)
            # ----------------------------------------------------------------------------------------------------------
            for thisComponent in level2Components:
                if hasattr(thisComponent, "setAutoDraw"):
                    thisComponent.setAutoDraw(False)
            # Run 'End Routine' code from code_6
            # while level2_resp.keys == 'right':
            #    xBall2 += 0.05
            #    rightClicked += 1
            # if xBall2 >= 0.15:
            #    triallevel2.finished = True
            #    dicti['right'] = rightClicked
            #    dicti['left'] = 0

            x = 2;
            # the Routine "level2" was not non-slip safe, so reset the non-slip timer
            routineTimer.reset()
            thisExp.nextEntry()

        # completed level2Chosen repeats of 'triallevel2'

        # set up handler to look after randomisation of conditions etc
        triallevel3 = data.TrialHandler(nReps=level3Chosen, method='random',
                                        extraInfo=expInfo, originPath=-1,
                                        trialList=[None],
                                        seed=None, name='triallevel3')
        thisExp.addLoop(triallevel3)  # add the loop to the experiment
        thisTriallevel3 = triallevel3.trialList[0]  # so we can initialise stimuli with some values
        # abbreviate parameter names if possible (e.g. rgb = thisTriallevel3.rgb)
        if thisTriallevel3 != None:
            for paramName in thisTriallevel3:
                exec('{} = thisTriallevel3[paramName]'.format(paramName))

        for thisTriallevel3 in triallevel3:
            currentLoop = triallevel3
            # abbreviate parameter names if possible (e.g. rgb = thisTriallevel3.rgb)
            if thisTriallevel3 != None:
                for paramName in thisTriallevel3:
                    exec('{} = thisTriallevel3[paramName]'.format(paramName))

            # --- Prepare to start Routine "level3" ---
            continueRoutine = True
            # update component parameters for each repeat
            # Run 'Begin Routine' code from code_7
            mykb = keyboard.Keyboard()
            keysWatched = ['left', 'right']
            status = ['up', 'up']

            ball_level3.setImage('PsychoPy/ball.png')
            # keep track of which components have finished
            level3Components = [image_5, text_5, gate_l_3, gate_r_3, ball_level3]
            for thisComponent in level3Components:
                thisComponent.tStart = None
                thisComponent.tStop = None
                thisComponent.tStartRefresh = None
                thisComponent.tStopRefresh = None
                if hasattr(thisComponent, 'status'):
                    thisComponent.status = NOT_STARTED
            # reset timers
            t = 0
            _timeToFirstFrame = win.getFutureFlipTime(clock="now")
            frameN = -1

            # --- Run Routine "level3" ---
            routineForceEnded = not continueRoutine
            # ----------------------------------------------------------------------------------------------------------
            send_trigger(trig=31)
            # ----------------------------------------------------------------------------------------------------------
            while continueRoutine:
                # get current time
                t = routineTimer.getTime()
                tThisFlip = win.getFutureFlipTime(clock=routineTimer)
                tThisFlipGlobal = win.getFutureFlipTime(clock=None)
                frameN = frameN + 1  # number of completed frames (so 0 is the first frame)
                # update/draw components on each frame
                # Run 'Each Frame' code from code_7
                keys = mykb.getKeys(keysWatched, waitRelease=False, clear=False)

                if len(keys):
                    for i, key in enumerate(keysWatched):
                        if keys[-1].name == key:
                            if keys[-1].duration:
                                status[i] = 'up'
                            else:
                                status[i] = 'down'

                # ------------------------------------------------------------------------------------------------------
                # Get input: grip force or emg
                grip_force = 0
                if ball_control == "grip":
                    grip_force = get_grip_force(lsl_inlet=lsl_inlet, data_lsl=data_lsl)
                elif ball_control == "emg":
                    grip_force, data_lsl = get_emg(lsl_inlet=lsl_inlet, data_lsl=data_lsl, emg_ch=emg_ch,
                                                   win_len=win_len)
                else:
                    print("Wrong ball control setting!")
                # Get input: threshold from txt.file
                thrs = set_threshold(file=thrs_filename)
                # Check upper limit
                if grip_force > thrs[1]:
                    force_upper_limit = True
                else:
                    force_upper_limit = False
                # Update movement status
                status = set_movement_status(grip_force=grip_force, thrs=thrs, hand=hand_side, status=status)
                # ------------------------------------------------------------------------------------------------------

                if status[0] == 'down':
                    xBall3 -= ball_pos_inc
                    if xBall3 <= -0.5:
                        triallevel3.finished = True
                        continueRoutine = False

                if status[1] == 'down':
                    xBall3 += ball_pos_inc
                    if xBall3 >= 0.5:
                        triallevel3.finished = True
                        continueRoutine = False

                # *image_5* updates

                # if image_5 is starting this frame...
                if image_5.status == NOT_STARTED and tThisFlip >= 0.0 - frameTolerance:
                    # keep track of start time/frame for later
                    image_5.frameNStart = frameN  # exact frame index
                    image_5.tStart = t  # local t and not account for scr refresh
                    image_5.tStartRefresh = tThisFlipGlobal  # on global time
                    win.timeOnFlip(image_5, 'tStartRefresh')  # time at next scr refresh
                    # add timestamp to datafile
                    thisExp.timestampOnFlip(win, 'image_5.started')
                    # update status
                    image_5.status = STARTED
                    image_5.setAutoDraw(True)

                # if image_5 is active this frame...
                if image_5.status == STARTED:
                    # update params
                    pass

                # *text_5* updates

                # if text_5 is starting this frame...
                if text_5.status == NOT_STARTED and tThisFlip >= 0.0 - frameTolerance:
                    # keep track of start time/frame for later
                    text_5.frameNStart = frameN  # exact frame index
                    text_5.tStart = t  # local t and not account for scr refresh
                    text_5.tStartRefresh = tThisFlipGlobal  # on global time
                    win.timeOnFlip(text_5, 'tStartRefresh')  # time at next scr refresh
                    # add timestamp to datafile
                    thisExp.timestampOnFlip(win, 'text_5.started')
                    # update status
                    text_5.status = STARTED
                    text_5.setAutoDraw(True)

                # if text_5 is active this frame...
                if text_5.status == STARTED:
                    # update params
                    pass

                # *gate_l_3* updates
                if hand_side == "left":
                    # if gate_l_3 is starting this frame...
                    if gate_l_3.status == NOT_STARTED and tThisFlip >= 0.0 - frameTolerance:
                        # keep track of start time/frame for later
                        gate_l_3.frameNStart = frameN  # exact frame index
                        gate_l_3.tStart = t  # local t and not account for scr refresh
                        gate_l_3.tStartRefresh = tThisFlipGlobal  # on global time
                        win.timeOnFlip(gate_l_3, 'tStartRefresh')  # time at next scr refresh
                        # add timestamp to datafile
                        thisExp.timestampOnFlip(win, 'gate_l_3.started')
                        # update status
                        gate_l_3.status = STARTED
                        gate_l_3.setAutoDraw(True)

                    # if gate_l_3 is active this frame...
                    if gate_l_3.status == STARTED:
                        # update params
                        pass

                # *gate_r_3* updates
                if hand_side == "right":
                    # if gate_r_3 is starting this frame...
                    if gate_r_3.status == NOT_STARTED and tThisFlip >= 0.0 - frameTolerance:
                        # keep track of start time/frame for later
                        gate_r_3.frameNStart = frameN  # exact frame index
                        gate_r_3.tStart = t  # local t and not account for scr refresh
                        gate_r_3.tStartRefresh = tThisFlipGlobal  # on global time
                        win.timeOnFlip(gate_r_3, 'tStartRefresh')  # time at next scr refresh
                        # add timestamp to datafile
                        thisExp.timestampOnFlip(win, 'gate_r_3.started')
                        # update status
                        gate_r_3.status = STARTED
                        gate_r_3.setAutoDraw(True)

                    # if gate_r_3 is active this frame...
                    if gate_r_3.status == STARTED:
                        # update params
                        pass

                # *ball_level3* updates

                # if ball_level3 is starting this frame...
                if ball_level3.status == NOT_STARTED and tThisFlip >= 0.0 - frameTolerance:
                    # keep track of start time/frame for later
                    ball_level3.frameNStart = frameN  # exact frame index
                    ball_level3.tStart = t  # local t and not account for scr refresh
                    ball_level3.tStartRefresh = tThisFlipGlobal  # on global time
                    win.timeOnFlip(ball_level3, 'tStartRefresh')  # time at next scr refresh
                    # add timestamp to datafile
                    thisExp.timestampOnFlip(win, 'ball_level3.started')
                    # update status
                    ball_level3.status = STARTED
                    ball_level3.setAutoDraw(True)

                # if ball_level3 is active this frame...
                if ball_level3.status == STARTED:
                    if force_upper_limit:
                        ball_level3.setImage('PsychoPy/ball_red.png')
                    else:
                        ball_level3.setImage('PsychoPy/ball.png')
                    # update params
                    ball_level3.setPos((xBall3, yBall3), log=False)

                # check for quit (typically the Esc key)
                if endExpNow or defaultKeyboard.getKeys(keyList=["escape"]):
                    # --------------------------------------------------------------------------------------------------
                    quit_game(lsl_inlet=lsl_inlet)
                    # --------------------------------------------------------------------------------------------------
                    core.quit()

                # check if all components have finished
                if not continueRoutine:  # a component has requested a forced-end of Routine
                    routineForceEnded = True
                    break
                continueRoutine = False  # will revert to True if at least one component still running
                for thisComponent in level3Components:
                    if hasattr(thisComponent, "status") and thisComponent.status != FINISHED:
                        continueRoutine = True
                        break  # at least one component has not yet finished

                # refresh the screen
                if continueRoutine:  # don't flip if this routine is over or we'll get a blank screen
                    win.flip()

            # --- Ending Routine "level3" ---
            # ----------------------------------------------------------------------------------------------------------
            if not continueRoutine: send_trigger(trig=32)
            # ----------------------------------------------------------------------------------------------------------
            for thisComponent in level3Components:
                if hasattr(thisComponent, "setAutoDraw"):
                    thisComponent.setAutoDraw(False)
            # the Routine "level3" was not non-slip safe, so reset the non-slip timer
            routineTimer.reset()
            thisExp.nextEntry()

        # completed level3Chosen repeats of 'triallevel3'

        # --- Prepare to start Routine "practice_end" ---
        continueRoutine = True
        # update component parameters for each repeat
        congrats_background.setImage('PsychoPy/congrats.png')
        # keep track of which components have finished
        practice_endComponents = [congrats_background, byetext, sound_2]
        sound_1.setSound('PsychoPy/congrats.mp3', secs=5, hamming=True)
        sound_1.setVolume(20.0, log=False)
        for thisComponent in practice_endComponents:
            thisComponent.tStart = None
            thisComponent.tStop = None
            thisComponent.tStartRefresh = None
            thisComponent.tStopRefresh = None
            if hasattr(thisComponent, 'status'):
                thisComponent.status = NOT_STARTED
        # reset timers
        t = 0
        _timeToFirstFrame = win.getFutureFlipTime(clock="now")
        frameN = -1

        # --- Run Routine "practice_end" ---
        routineForceEnded = not continueRoutine
        while continueRoutine and routineTimer.getTime() < 5.0:
            # get current time
            t = routineTimer.getTime()
            tThisFlip = win.getFutureFlipTime(clock=routineTimer)
            tThisFlipGlobal = win.getFutureFlipTime(clock=None)
            frameN = frameN + 1  # number of completed frames (so 0 is the first frame)
            # update/draw components on each frame

            # *congrats_background* updates

            # if congrats_background is starting this frame...
            if congrats_background.status == NOT_STARTED and tThisFlip >= 0.0 - frameTolerance:
                # keep track of start time/frame for later
                congrats_background.frameNStart = frameN  # exact frame index
                congrats_background.tStart = t  # local t and not account for scr refresh
                congrats_background.tStartRefresh = tThisFlipGlobal  # on global time
                win.timeOnFlip(congrats_background, 'tStartRefresh')  # time at next scr refresh
                # add timestamp to datafile
                thisExp.timestampOnFlip(win, 'congrats_background.started')
                # update status
                congrats_background.status = STARTED
                congrats_background.setAutoDraw(True)

            # if congrats_background is active this frame...
            if congrats_background.status == STARTED:
                # update params
                pass

            # if congrats_background is stopping this frame...
            if congrats_background.status == STARTED:
                # is it time to stop? (based on global clock, using actual start)
                if tThisFlipGlobal > congrats_background.tStartRefresh + 5 - frameTolerance:
                    # keep track of stop time/frame for later
                    congrats_background.tStop = t  # not accounting for scr refresh
                    congrats_background.frameNStop = frameN  # exact frame index
                    # add timestamp to datafile
                    thisExp.timestampOnFlip(win, 'congrats_background.stopped')
                    # update status
                    congrats_background.status = FINISHED
                    congrats_background.setAutoDraw(False)

            # *byetext* updates

            # if byetext is starting this frame...
            if byetext.status == NOT_STARTED and tThisFlip >= 0.0 - frameTolerance:
                # keep track of start time/frame for later
                byetext.frameNStart = frameN  # exact frame index
                byetext.tStart = t  # local t and not account for scr refresh
                byetext.tStartRefresh = tThisFlipGlobal  # on global time
                win.timeOnFlip(byetext, 'tStartRefresh')  # time at next scr refresh
                # add timestamp to datafile
                thisExp.timestampOnFlip(win, 'byetext.started')
                # update status
                byetext.status = STARTED
                byetext.setAutoDraw(True)

            # if byetext is active this frame...
            if byetext.status == STARTED:
                # update params
                pass

            # if byetext is stopping this frame...
            if byetext.status == STARTED:
                # is it time to stop? (based on global clock, using actual start)
                if tThisFlipGlobal > byetext.tStartRefresh + 5.0 - frameTolerance:
                    # keep track of stop time/frame for later
                    byetext.tStop = t  # not accounting for scr refresh
                    byetext.frameNStop = frameN  # exact frame index
                    # add timestamp to datafile
                    thisExp.timestampOnFlip(win, 'byetext.stopped')
                    # update status
                    byetext.status = FINISHED
                    byetext.setAutoDraw(False)

            # start/stop sound_2

            # if sound_2 is starting this frame...
            if sound_2.status == NOT_STARTED and tThisFlip >= 0.0 - frameTolerance:
                # keep track of start time/frame for later
                sound_2.frameNStart = frameN  # exact frame index
                sound_2.tStart = t  # local t and not account for scr refresh
                sound_2.tStartRefresh = tThisFlipGlobal  # on global time
                # add timestamp to datafile
                thisExp.addData('sound_2.started', tThisFlipGlobal)
                # update status
                sound_2.status = STARTED
                sound_2.play(when=win)  # sync with win flip

            # if sound_2 is stopping this frame...
            if sound_2.status == STARTED:
                # is it time to stop? (based on global clock, using actual start)
                if tThisFlipGlobal > sound_2.tStartRefresh + 5 - frameTolerance:
                    # keep track of stop time/frame for later
                    sound_2.tStop = t  # not accounting for scr refresh
                    sound_2.frameNStop = frameN  # exact frame index
                    # add timestamp to datafile
                    thisExp.timestampOnFlip(win, 'sound_2.stopped')
                    # update status
                    sound_2.status = FINISHED
                    sound_2.stop()

            # --------------------------------------------------------------------------------------------------
            if data_lsl is not None:
                print(np.shape(data_lsl))
                data_lsl = None
                print(np.shape(data_lsl))
            # --------------------------------------------------------------------------------------------------

            # check for quit (typically the Esc key)
            if endExpNow or defaultKeyboard.getKeys(keyList=["escape"]):
                # ------------------------------------------------------------------------------------------------------
                quit_game(lsl_inlet=lsl_inlet)
                # ------------------------------------------------------------------------------------------------------
                core.quit()

            # check if all components have finished
            if not continueRoutine:  # a component has requested a forced-end of Routine
                routineForceEnded = True
                break
            continueRoutine = False  # will revert to True if at least one component still running
            for thisComponent in practice_endComponents:
                if hasattr(thisComponent, "status") and thisComponent.status != FINISHED:
                    continueRoutine = True
                    break  # at least one component has not yet finished

            # refresh the screen
            if continueRoutine:  # don't flip if this routine is over or we'll get a blank screen
                win.flip()

        # --- Ending Routine "practice_end" ---
        for thisComponent in practice_endComponents:
            if hasattr(thisComponent, "setAutoDraw"):
                thisComponent.setAutoDraw(False)
        sound_2.stop()  # ensure sound has stopped at end of routine
        # using non-slip timing so subtract the expected duration of this Routine (unless ended on request)
        if routineForceEnded:
            routineTimer.reset()
        else:
            routineTimer.addTime(-5.000000)
        thisExp.nextEntry()

    # completed practiceChosen repeats of 'showPracticeLoop'

    # --- Prepare to start Routine "end_again" ---
    continueRoutine = True
    # update component parameters for each repeat
    # Run 'Begin Routine' code from code_9
    if mode_resp_3.keys == 'w':
        startAgainChosen = 15
    if mode_resp_3.keys == 'b':
        trials_5.finished = True
        print("Quit game")
    mode_resp_3.keys = []
    mode_resp_3.rt = []
    _mode_resp_3_allKeys = []
    # keep track of which components have finished
    end_againComponents = [image_7, text_6, mode_resp_3]
    for thisComponent in end_againComponents:
        thisComponent.tStart = None
        thisComponent.tStop = None
        thisComponent.tStartRefresh = None
        thisComponent.tStopRefresh = None
        if hasattr(thisComponent, 'status'):
            thisComponent.status = NOT_STARTED
    # reset timers
    t = 0
    _timeToFirstFrame = win.getFutureFlipTime(clock="now")
    frameN = -1

    # --- Run Routine "end_again" ---
    routineForceEnded = not continueRoutine
    while continueRoutine:
        # get current time
        t = routineTimer.getTime()
        tThisFlip = win.getFutureFlipTime(clock=routineTimer)
        tThisFlipGlobal = win.getFutureFlipTime(clock=None)
        frameN = frameN + 1  # number of completed frames (so 0 is the first frame)
        # update/draw components on each frame

        # *image_7* updates

        # if image_7 is starting this frame...
        if image_7.status == NOT_STARTED and tThisFlip >= 0.0 - frameTolerance:
            # keep track of start time/frame for later
            image_7.frameNStart = frameN  # exact frame index
            image_7.tStart = t  # local t and not account for scr refresh
            image_7.tStartRefresh = tThisFlipGlobal  # on global time
            win.timeOnFlip(image_7, 'tStartRefresh')  # time at next scr refresh
            # add timestamp to datafile
            thisExp.timestampOnFlip(win, 'image_7.started')
            # update status
            image_7.status = STARTED
            image_7.setAutoDraw(True)

        # if image_7 is active this frame...
        if image_7.status == STARTED:
            # update params
            pass

        # *text_6* updates

        # if text_6 is starting this frame...
        if text_6.status == NOT_STARTED and tThisFlip >= 0.0 - frameTolerance:
            # keep track of start time/frame for later
            text_6.frameNStart = frameN  # exact frame index
            text_6.tStart = t  # local t and not account for scr refresh
            text_6.tStartRefresh = tThisFlipGlobal  # on global time
            win.timeOnFlip(text_6, 'tStartRefresh')  # time at next scr refresh
            # add timestamp to datafile
            thisExp.timestampOnFlip(win, 'text_6.started')
            # update status
            text_6.status = STARTED
            text_6.setAutoDraw(True)

        # if text_6 is active this frame...
        if text_6.status == STARTED:
            # update params
            pass

        # *mode_resp_3* updates
        waitOnFlip = False

        # if mode_resp_3 is starting this frame...
        if mode_resp_3.status == NOT_STARTED and tThisFlip >= 0.0 - frameTolerance:
            # keep track of start time/frame for later
            mode_resp_3.frameNStart = frameN  # exact frame index
            mode_resp_3.tStart = t  # local t and not account for scr refresh
            mode_resp_3.tStartRefresh = tThisFlipGlobal  # on global time
            win.timeOnFlip(mode_resp_3, 'tStartRefresh')  # time at next scr refresh
            # add timestamp to datafile
            thisExp.timestampOnFlip(win, 'mode_resp_3.started')
            # update status
            mode_resp_3.status = STARTED
            # keyboard checking is just starting
            waitOnFlip = True
            win.callOnFlip(mode_resp_3.clock.reset)  # t=0 on next screen flip
            win.callOnFlip(mode_resp_3.clearEvents, eventType='keyboard')  # clear events on next screen flip
        if mode_resp_3.status == STARTED and not waitOnFlip:
            theseKeys = mode_resp_3.getKeys(keyList=['w', 'b'], waitRelease=False)
            _mode_resp_3_allKeys.extend(theseKeys)
            if len(_mode_resp_3_allKeys):
                mode_resp_3.keys = _mode_resp_3_allKeys[-1].name  # just the last key pressed
                mode_resp_3.rt = _mode_resp_3_allKeys[-1].rt
                # a response ends the routine
                continueRoutine = False

        # check for quit (typically the Esc key)
        if endExpNow or defaultKeyboard.getKeys(keyList=["escape"]):
            # ----------------------------------------------------------------------------------------------------------
            quit_game(lsl_inlet=lsl_inlet)
            # ----------------------------------------------------------------------------------------------------------
            core.quit()

        # check if all components have finished
        if not continueRoutine:  # a component has requested a forced-end of Routine
            routineForceEnded = True
            break
        continueRoutine = False  # will revert to True if at least one component still running
        for thisComponent in end_againComponents:
            if hasattr(thisComponent, "status") and thisComponent.status != FINISHED:
                continueRoutine = True
                break  # at least one component has not yet finished

        # refresh the screen
        if continueRoutine:  # don't flip if this routine is over or we'll get a blank screen
            win.flip()

    # --- Ending Routine "end_again" ---
    for thisComponent in end_againComponents:
        if hasattr(thisComponent, "setAutoDraw"):
            thisComponent.setAutoDraw(False)
    # Run 'End Routine' code from code_9
    if mode_resp_3.keys == 'w':
        startAgainChosen = 15
        endChosen = 0
    if mode_resp_3.keys == 'b':
        startAgainChosen = 0
        endChosen = 1
        trials_5.finished = True
    # check responses
    if mode_resp_3.keys in ['', [], None]:  # No response was made
        mode_resp_3.keys = None
    trials_5.addData('mode_resp_3.keys', mode_resp_3.keys)
    if mode_resp_3.keys != None:  # we had a response
        trials_5.addData('mode_resp_3.rt', mode_resp_3.rt)
    # the Routine "end_again" was not non-slip safe, so reset the non-slip timer
    routineTimer.reset()
    thisExp.nextEntry()

# completed startAgainChosen repeats of 'trials_5'


# set up handler to look after randomisation of conditions etc
trials_end = data.TrialHandler(nReps=1.0, method='random',
                               extraInfo=expInfo, originPath=-1,
                               trialList=[None],
                               seed=None, name='trials_end')
thisExp.addLoop(trials_end)  # add the loop to the experiment
thisTrials_end = trials_end.trialList[0]  # so we can initialise stimuli with some values
# abbreviate parameter names if possible (e.g. rgb = thisTrials_end.rgb)
if thisTrials_end != None:
    for paramName in thisTrials_end:
        exec('{} = thisTrials_end[paramName]'.format(paramName))

for thisTrials_end in trials_end:
    currentLoop = trials_end
    # abbreviate parameter names if possible (e.g. rgb = thisTrials_end.rgb)
    if thisTrials_end != None:
        for paramName in thisTrials_end:
            exec('{} = thisTrials_end[paramName]'.format(paramName))

    # --- Prepare to start Routine "end_game" ---
    continueRoutine = True
    # update component parameters for each repeat
    # keep track of which components have finished
    end_gameComponents = [image_8, text_7]
    for thisComponent in end_gameComponents:
        thisComponent.tStart = None
        thisComponent.tStop = None
        thisComponent.tStartRefresh = None
        thisComponent.tStopRefresh = None
        if hasattr(thisComponent, 'status'):
            thisComponent.status = NOT_STARTED
    # reset timers
    t = 0
    _timeToFirstFrame = win.getFutureFlipTime(clock="now")
    frameN = -1

    # --- Run Routine "end_game" ---
    routineForceEnded = not continueRoutine
    while continueRoutine and routineTimer.getTime() < 3.0:
        # get current time
        t = routineTimer.getTime()
        tThisFlip = win.getFutureFlipTime(clock=routineTimer)
        tThisFlipGlobal = win.getFutureFlipTime(clock=None)
        frameN = frameN + 1  # number of completed frames (so 0 is the first frame)
        # update/draw components on each frame

        # *image_8* updates

        # if image_8 is starting this frame...
        if image_8.status == NOT_STARTED and tThisFlip >= 0.0 - frameTolerance:
            # keep track of start time/frame for later
            image_8.frameNStart = frameN  # exact frame index
            image_8.tStart = t  # local t and not account for scr refresh
            image_8.tStartRefresh = tThisFlipGlobal  # on global time
            win.timeOnFlip(image_8, 'tStartRefresh')  # time at next scr refresh
            # add timestamp to datafile
            thisExp.timestampOnFlip(win, 'image_8.started')
            # update status
            image_8.status = STARTED
            image_8.setAutoDraw(True)

        # if image_8 is active this frame...
        if image_8.status == STARTED:
            # update params
            pass

        # if image_8 is stopping this frame...
        if image_8.status == STARTED:
            # is it time to stop? (based on global clock, using actual start)
            if tThisFlipGlobal > image_8.tStartRefresh + 3.0 - frameTolerance:
                # keep track of stop time/frame for later
                image_8.tStop = t  # not accounting for scr refresh
                image_8.frameNStop = frameN  # exact frame index
                # add timestamp to datafile
                thisExp.timestampOnFlip(win, 'image_8.stopped')
                # update status
                image_8.status = FINISHED
                image_8.setAutoDraw(False)

        # *text_7* updates

        # if text_7 is starting this frame...
        if text_7.status == NOT_STARTED and tThisFlip >= 0.0 - frameTolerance:
            # keep track of start time/frame for later
            text_7.frameNStart = frameN  # exact frame index
            text_7.tStart = t  # local t and not account for scr refresh
            text_7.tStartRefresh = tThisFlipGlobal  # on global time
            win.timeOnFlip(text_7, 'tStartRefresh')  # time at next scr refresh
            # add timestamp to datafile
            thisExp.timestampOnFlip(win, 'text_7.started')
            # update status
            text_7.status = STARTED
            text_7.setAutoDraw(True)

        # if text_7 is active this frame...
        if text_7.status == STARTED:
            # update params
            pass

        # if text_7 is stopping this frame...
        if text_7.status == STARTED:
            # is it time to stop? (based on global clock, using actual start)
            if tThisFlipGlobal > text_7.tStartRefresh + 3.0 - frameTolerance:
                # keep track of stop time/frame for later
                text_7.tStop = t  # not accounting for scr refresh
                text_7.frameNStop = frameN  # exact frame index
                # add timestamp to datafile
                thisExp.timestampOnFlip(win, 'text_7.stopped')
                # update status
                text_7.status = FINISHED
                text_7.setAutoDraw(False)

        # check for quit (typically the Esc key)
        if endExpNow or defaultKeyboard.getKeys(keyList=["escape"]):
            # ----------------------------------------------------------------------------------------------------------
            quit_game(lsl_inlet=lsl_inlet)
            # ----------------------------------------------------------------------------------------------------------
            core.quit()

        # check if all components have finished
        if not continueRoutine:  # a component has requested a forced-end of Routine
            routineForceEnded = True
            break
        continueRoutine = False  # will revert to True if at least one component still running
        for thisComponent in end_gameComponents:
            if hasattr(thisComponent, "status") and thisComponent.status != FINISHED:
                continueRoutine = True
                break  # at least one component has not yet finished

        # refresh the screen
        if continueRoutine:  # don't flip if this routine is over or we'll get a blank screen
            win.flip()

    # --- Ending Routine "end_game" ---
    # ------------------------------------------------------------------------------------------------------------------
    quit_game(lsl_inlet=lsl_inlet)
    # ------------------------------------------------------------------------------------------------------------------
    for thisComponent in end_gameComponents:
        if hasattr(thisComponent, "setAutoDraw"):
            thisComponent.setAutoDraw(False)
    # using non-slip timing so subtract the expected duration of this Routine (unless ended on request)
    if routineForceEnded:
        routineTimer.reset()
    else:
        routineTimer.addTime(-3.000000)
    thisExp.nextEntry()

# completed 1.0 repeats of 'trials_end'

# Run 'End Experiment' code from code_11
keyFile.close()
# Run 'End Experiment' code from code_3
writer.writerow(dicti)
file.close()

# --- End experiment ---
# Flip one final time so any remaining win.callOnFlip()
# and win.timeOnFlip() tasks get executed before quitting
win.flip()

# these shouldn't be strictly necessary (should auto-save)
thisExp.saveAsWideText(filename + '.csv', delim='auto')
thisExp.saveAsPickle(filename)
logging.flush()
# make sure everything is closed down
if eyetracker:
    eyetracker.setConnectionState(False)
thisExp.abort()  # or data files will save again on exit
print("End experiment")
win.close()

