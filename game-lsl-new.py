import pygame
import sys
import multiprocessing
from pygame.locals import *
from pynput.keyboard import Controller


import multiprocessing
from pickable import PickleableSurface
from pickle import loads,dumps
import csv

import time
from pylsl import StreamInfo, StreamOutlet, StreamInlet, resolve_stream
import pandas as pd


import numpy as np
from pylsl import StreamInlet, resolve_stream, StreamOutlet, StreamInfo
import scipy
from scipy.signal import butter, lfilter
import csv
import time
import warnings
import matplotlib.pyplot as plt

#12 oct - 16:21 - 18:30
#obstacle: multiprocessing - cannot pickle 'pygame.surface.Surface' object or the dino thingy which uses the files in between the connection myoband-code
#20 oct - 17:30 - 
# Initialize pygame
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
X = WIDTH/2 - 30
Y = HEIGHT*3/4


BALL_IMAGE = pygame.image.load("assets/ball.png")
GATE_R_IMAGE = pygame.image.load("assets/gate_r.png")
GATE_L_IMAGE = pygame.image.load("assets/gate_l.png")
SPEED = 10

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
    #changed from old code which gad as arguments type and 'type'
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
    #print('samples',samples)
    return np.vstack(samples)


def pull_data(lsl_inlet, data_lsl, replace=True):
    new_data = pull_from_buffer(lsl_inlet)
    if replace or data_lsl is None:
        data_lsl = new_data
    else:
        data_lsl = np.vstack([data_lsl, new_data])
    return data_lsl


class Ball:
    def __init__(self):
        self.width = self.height = HEIGHT/13
        self.x = WIDTH / 2 - 30
        self.y = HEIGHT * 3/4
        self.dx = 0  # Change in x position (initialize to 0)
        self.move_count = 0
        self.image = pygame.transform.scale(BALL_IMAGE,(self.width,self.height))

    def move_left(self):
        self.dx = -SPEED
        self.move_count += 1
        self.x += self.dx

    def move_right(self):
        self.dx = SPEED
        self.move_count += 1
        self.x += self.dx

    def stop(self):
        self.dx = 0

    def update(self):
        screen.blit(self.image,(self.x,self.y))

class GateRight:
    def __init__(self):
        self.width = self.height = HEIGHT/5
        self.x = WIDTH - 60 - self.width
        self.y = HEIGHT*3/4 - self.height/2
        self.image = pygame.transform.scale(GATE_R_IMAGE,(self.width,self.height))

    def draw(self):
        screen.blit(self.image,(self.x,self.y))

class GateLeft:
    def __init__(self):
        self.width = self.height = HEIGHT/5
        self.x = self.width/2
        self.y = HEIGHT*3/4 - self.height/2
        self.image = pygame.transform.scale(GATE_L_IMAGE,(self.width,self.height))

    def draw(self):
        screen.blit(self.image,(self.x,self.y))

class Button:
    def __init__(self, x, y, width, height,text):
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
        text_rect.center = (X+30, Y-250)

        #start_img = pygame.image.load("assets/start.png")
        #start_img = pygame.transform.scale(start_img,(200,200))
        #start_img_rect = start_img.get_rect()

        self.screen.blit(intro_image, intro_rect)
        self.screen.blit(text,text_rect)
        self.start_button.draw(self.screen)
        #self.screen.blit(start_img,start_img)

        while not self.start_button.clicked:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.start_button.rect.collidepoint(event.pos):
                        self.start_button.clicked = True
                        self.intro_done = True
                    
            pygame.display.flip()
        self.play()
    
    def get_emg(self,lsl_inlet, data_lsl, emg, win_len):
        # print(np.shape(data_lsl))
        data_lsl = pull_data(lsl_inlet=lsl_inlet, data_lsl=data_lsl, replace=False)    
        #print('lsl_inlet',lsl_inlet.info())
       #emg = data_lsl[:, emg_ch] # select emg channel
        avg = 0
        for row in data_lsl:
            avg = 0
            for i in row:
                avg += i
            emg.append(avg);
        
        #print('emg',len(emg))
        #print('data_lsl',len(data_lsl))
        win_samp = win_len * fs # define win len (depending on fs)
        #print('win_samp',win_samp)
        emg_chunk = 0
        if len(emg) > win_samp:   # wait until data win is long enough
            emg_win = emg[-win_samp:-1] # pull data from time point 0 to -win_size
            emg_filt = lfilter(self.b, self.a, emg_win) # applying the filter (no need to change)
            emg_env = np.abs(scipy.signal.hilbert(emg_filt)) # calculating envelope
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

            
            chunk_size = 4 # start: 20 # change to 4 eventually later - 200HZ sampling rate
            emg_chunk = np.mean(np.power(emg_env[-chunk_size:-1], 2))
            # offset = 100
            # emg_chunk = emg_chunk - offset
            # if emg_chunk < 0: emg_chunk = 0
            #print('emg_chunk',emg_chunk)
        return emg_chunk, data_lsl


    
    def play(self):

        #maybe create a new class for this

        inlet_emg1 = None
        inlet_emg2 = None
        #!!! change to the time emg!!!!

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
        text_rect.center = (X+30, Y-250)
        self.screen.blit(text,text_rect)

        thrs_right = [200, 5000]
        thrs_left = [200, 5000]

        while not self.play_done:
            background = pygame.image.load("assets/football.jpeg")
            background = pygame.transform.scale(background,(WIDTH,HEIGHT))
            background.get_rect().center = (WIDTH // 2, HEIGHT // 2)
            self.screen.blit(background, (0,0))
            self.gate_left.draw()
            self.gate_right.draw()
            arrow_key_pressed = None

# ======================================================================
            force_right = 0
            force_left = 0
            emg1 = []
            emg2 = []
            force_right, data_lsl = self.get_emg(lsl_inlet=inlet1, data_lsl=data_lsl, emg=emg1,
                                                            win_len=win_len)
            
            force_left, data_lsl = self.get_emg(lsl_inlet=inlet2, data_lsl=data_lsl, emg=emg2,
                                                            win_len=win_len)
            

            #print('Left: ' + str(int(force_left)) + '     Right: ' + str(int(force_right)))

            
            
            
            if force_left > thrs_left[0] and force_left < thrs_left[1] and force_right < thrs_right[0]:
                print("stanga")
                self.ball.move_left()
                if self.ball.x <= self.gate_left.x + 20:
                    self.play_done = True
            
            
            if force_right > thrs_right[0] and force_right < thrs_right[1] and force_left < thrs_left[0]:
                print("dreapta")
                self.ball.move_right()
                if self.ball.x >= self.gate_right.x - 20:
                    self.play_done = True

            print("left: {}, right {}".format(force_left,force_right))
           
        
            


            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.play_done = True
                    pygame.quit()
                
        
            keys = pygame.key.get_pressed()
            if keys[pygame.K_q]:
                pygame.quit()


            if arrow_key_pressed:
                text = FONT.render(f"Arrow key pressed: {arrow_key_pressed}", True, (0, 0, 0))
                self.screen.blit(text, (10, 10))

            self.screen.blit(self.ball.image,(self.ball.x,self.ball.y))
            self.screen.blit(text,text_rect)
            pygame.display.flip() 
            
    def move_left(self,pose):
            print("Pose detected", pose)
            if pose == 1:
                for i in range(0,10):
                    #self.keyboard.press(Key.left)
                    #self.keyboard.release(Key.left)
                    self.ball.move_left()
                    self.ball.update()
                    self.screen.blit(self.ball.image,(self.ball.x,self.ball.y))
                    print(self.ball.x)
    def worker_myo (self,q):

        def add_to_queue(emg, movement):
            q.put(emg)



    def congrats(self):
        background = pygame.image.load("assets/congrats.png")
        background = pygame.transform.scale(background,(WIDTH,HEIGHT))
        congrats_text = FONT.render('Congrats!', True, WHITE)
        text_rect = congrats_text.get_rect()
        text_rect.center = (X+30, X-250)
        screen.blit(background, (0,0))
        self.screen.blit(congrats_text,text_rect)
        pygame.display.flip()

class Controls:
    def __init__(self):
        self.activate = False
        self.user_text = ''
        
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
        screen.blit(text_surface, (input_rect.x+5,input_rect.y+5))
        input_rect.w = max(100, text_surface.get_width()+10)
        pygame.display.flip()




if __name__ == "__main__":
    keyboard = Controller() 
    
    pygame.Surface = PickleableSurface
    pygame.surface.Surface = PickleableSurface
    surf = pygame.Surface((WIDTH,HEIGHT), pygame.SRCALPHA|pygame.HWSURFACE)
    #screen = pygame.display.set_mode((WIDTH, HEIGHT)) 
    dump = dumps(surf)
    loaded = loads(dump)


    
    pygame.init() 
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption('Lexi\'s Football Game!!')

    start_button = Button(X-50, Y, 175, 90, "Start")
    game_state = GameState(screen, start_button,keyboard)
    
    game_state.intro()
        
	








#old code for processing the lsl streams in the game-lsl.py
