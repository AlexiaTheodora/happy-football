import pygame
import sys
import multiprocessing
from pygame.locals import *
from pynput.keyboard import Key, Controller
from pyomyo import Myo, emg_mode
from pyomyo.Classifier import Live_Classifier, MyoClassifier, EMGHandler
from xgboost import XGBClassifier
import multiprocessing
from pickable import PickleableSurface
from pickle import loads,dumps
import csv


#12 oct - 16:21 - 18:30
#obstacle: multiprocessing - cannot pickle 'pygame.surface.Surface' object or the dino thingy which uses the files in between the connection myoband-code
#20 oct - 17:30 - 
# Initialize pygame
pygame.init()

# Constants
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
SPEED = 5

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
    def __init__(self, screen, start_button, keyboard,m,hnd):
        self.screen = screen

        self.ball = Ball()
        self.gate_left = GateLeft()
        self.gate_right = GateRight()
        self.intro_done = False
        self.play_done = False
        self.start_button = start_button
        self.keyboard = keyboard
        self.m = m
        self.myo_data = []
        self.hnd = hnd



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
    

    
    def play(self):
        

        q = multiprocessing.Queue()
        p = multiprocessing.Process(target=self.worker_myo,args=(q,))
        p.start()

        text = FONT.render('Welcome to the best game ever', True, WHITE)
        text_rect = text.get_rect()
        text_rect.center = (X+30, Y-250)
        self.screen.blit(text,text_rect)

        while not self.play_done:
            background = pygame.image.load("assets/football.jpeg")
            background = pygame.transform.scale(background,(WIDTH,HEIGHT))
            background.get_rect().center = (WIDTH // 2, HEIGHT // 2)
            self.screen.blit(background, (0,0))
            self.gate_left.draw()
            self.gate_right.draw()
            arrow_key_pressed = None
            emg = list(q.get())
            print(emg)



            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.play_done = True
                    pygame.quit()
                    m.disconnect()
            
            
    
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
        m = Myo(mode=emg_mode.FILTERED) 

        m.connect()
        def add_to_queue(emg, movement):
            q.put(emg)
        
        m.add_emg_handler(add_to_queue)
        m.set_leds([128, 0, 0], [128, 0, 0])

        m.vibrate(1)
        while True:
            m.run()


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
    
    model = XGBClassifier(eval_metric='logloss')
    clr = Live_Classifier(model, name="XG", color=(50,50,255)) 
    m = MyoClassifier(clr, mode=emg_mode.PREPROCESSED, hist_len=10) 
    #m = Myo(mode = emg_mode.PREPROCESSED) 
    hnd = EMGHandler(m)
    m.add_emg_handler(hnd)
    
    
	

    start_button = Button(X-50, Y, 175, 90, "Start")
    game_state = GameState(screen, start_button,keyboard,m,hnd)
    
    game_state.intro()
        
	
