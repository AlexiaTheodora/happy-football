import pygame
import sys
import multiprocessing
from pygame.locals import *
from pynput.keyboard import Key, Controller
from pyomyo import Myo, emg_mode
from pyomyo.Classifier import Live_Classifier, MyoClassifier, EMGHandler
from xgboost import XGBClassifier
import multiprocessing

#12 oct - 16:21 - 18:30
#obstacle: multiprocessing - cannot pickle 'pygame.surface.Surface' object or the dino thingy which uses the files in between the connection myoband-code
#20 oct - 17:30 - 19:30
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
        pygame.display.flip() 

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
    
            
        text = FONT.render('Welcome to the best game ever', True, WHITE)
        text_rect = text.get_rect()
        text_rect.center = (X+30, Y-250)
        self.screen.blit(text,text_rect)
        #m.add_emg_handler(self.move_left)
        #controls = Controls()
        self.m.add_raw_pose_handler(self.move_left)
        self.m.set_leds(self.m.cls.color, self.m.cls.color)
        
            
        
        #self.m.run_gui(hnd,self.screen,FONT,WIDTH,HEIGHT)
        while not self.play_done:
            self.m.run()
            #self.m.run_gui(hnd,self.screen,FONT,WIDTH,HEIGHT)
            background = pygame.image.load("assets/football.jpeg")
            background = pygame.transform.scale(background,(WIDTH,HEIGHT))
            background.get_rect().center = (WIDTH // 2, HEIGHT // 2)
            self.screen.blit(background, (0,0))
            self.gate_left.draw()
            self.gate_right.draw()

            arrow_key_pressed = None
            #controls.activateControls()
            #controls.show()
            
            

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.play_done = True
                    pygame.quit()
                    m.disconnect()
            
            
            
           # p = multiprocessing.Process(target=self.check_move)
           # print("BUNA")
           # m.add_pose_handler(self.check_move)
           # p.start()

            myo_data = []
            #m.add_arm_handler(self.move_left)
            #m.add_pose_handler(self.move_left)
            keys = pygame.key.get_pressed()
                # Check for key events to move the ball
            if keys[pygame.K_q]:
                pygame.quit()
            #if keys[pygame.K_LEFT] and self.ball.x>0:
            #    arrow_key_pressed = "LEFT"
            #    self.ball.move_left()
            #    if self.ball.x <= self.gate_left.x + 20:
            #        self.play_done = True
            #        self.congrats() 
            #self.m.run()
            #m.run_gui(hnd, scr, font, w, h)			

         #   if keys[pygame.K_RIGHT] and self.ball.y < MAC_WIDTH - self.ball.width:
         #       arrow_key_pressed = "RIGHT"
         #       self.ball.move_right()
         #       if self.ball.x >= self.gate_right.x - 20:
         #           self.play_done = True
         #           self.congrats()

			
            # Update the ball's position
            #self.ball.update()

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
                    if self.ball.x <= self.gate_left.x + 20:
                        self.play_done = True
                        self.congrats() 
                    self.ball.update()
                    print(self.ball.x)



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
    pygame.init() 
    screen = pygame.display.set_mode((WIDTH, HEIGHT)) 
    pygame.display.set_caption('Lexi\'s Football Game!!')
    
    model = XGBClassifier(eval_metric='logloss')
    clr = Live_Classifier(model, name="XG", color=(50,50,255)) 
    m = MyoClassifier(clr, mode=emg_mode.PREPROCESSED, hist_len=10) 
    #m = Myo(mode = emg_mode.PREPROCESSED) 
    hnd = EMGHandler(m)
    m.add_emg_handler(hnd)
    m.connect()
    
	

    start_button = Button(X-50, Y, 175, 90, "Start")
    game_state = GameState(screen, start_button,keyboard,m,hnd)
    
    game_state.intro()
        
	
