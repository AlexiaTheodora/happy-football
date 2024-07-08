# time tracking - 26.08.2023: 3h
# time tracking - 14.09.2023: 1.5h
# time tracking - 21.09.2023: 1.5h
# time tracking - 22.09.2023: 2h
# time tracking - 23.09.2023: 1.5h
# time tracking - 29.09.2023: 1.5h
# time tracking - 30.09.2023: 3h
# time tracking - 19.10.2023: 0.5h
import pygame
import sys
import unicodedata
from datetime import datetime, date
import os
import shutil
import time
import random
import configparser

# Initialize pygame
pygame.init()

#Screen resolution width and height
SCREEN_INFO = pygame.display.Info()
SCREEN_WIDTH = SCREEN_INFO.current_w
SCREEN_HEIGHT = SCREEN_INFO.current_h


# Constants
MAC_WIDTH = 1280
MAC_HEIGHT = 800
WIDTH, HEIGHT = SCREEN_WIDTH, SCREEN_HEIGHT
FONT = pygame.font.Font('freesansbold.ttf', 32)
FONT_THRESHOLD = pygame.font.Font('freesansbold.ttf', 14)

FONT_CONTROLLS = pygame.font.Font('freesansbold.ttf', 16)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
BLACK = (0, 0, 0)
GREEN = (0, 255, 0)
X = WIDTH / 2 - 30
Y = HEIGHT * 3 / 4

config = configparser.ConfigParser()
config.read('config_game.ini')

global THRL, THLL, THRU, MAX_LEFT, MAX_RIGHT
THLL = config.getint('Game', 'THLL')
THRL = config.getint('Game', 'THRL')
THLU = config.getint('Game', 'THLU')
THRU = config.getint('Game', 'THRU')
MAX_LEFT = MAX_RIGHT = 5000

BALL_IMAGE = pygame.image.load("assets/ball.png")
GATE_R_IMAGE = pygame.image.load("assets/gate_r.png")
GATE_L_IMAGE = pygame.image.load("assets/gate_l.png")
SPEED = 5

FILE = ""
MOTIONS = []


class Ball:
    def __init__(self):
        self.width = self.height = HEIGHT / 13
        self.x = WIDTH / 2 - 30
        self.y = HEIGHT * 3 / 4
        self.dx = 0  # Change in x position (initialize to 0)
        self.move_count = 0
        self.image = pygame.transform.scale(BALL_IMAGE, (self.width, self.height))
        self.score_good = 0
        self.score_bad = 0

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
        screen.blit(self.image, (self.x, self.y))

    def replace(self):
        self.x = WIDTH / 2 - 30
        self.y = HEIGHT * 3 / 4


class Bar:
    def __init__(self, name, x, y, width, height):
        self.name = name
        self.width = width
        self.height = height
        self.x = x
        self.y = y
        self.rect = pygame.Rect(x, y, width, height)
        self.color = (255, 255, 255)

    def draw(self, ):
        pygame.draw.rect(screen, self.color, self.rect)


    def draw_threshold_bar(self, is_threshold_in_range, force):
        # new solution for the bar threshold
        height_new = 0
        if self.name == 'left':
            height_new = self.height * force / int(MAX_LEFT)
            percentage_lower = 100 * int(THLL) / (int(MAX_LEFT))
            percentage_upper = 100 * int(THLU) / (int(MAX_LEFT))
        elif self.name == 'right':
            height_new = self.height * force / int(MAX_RIGHT)
            percentage_lower = 100 * int(THRL) / (int(MAX_RIGHT))
            percentage_upper = 100 * int(THRU) / (int(MAX_RIGHT))

        y_new = self.y + self.height - height_new
        threshold_bar = pygame.Rect(self.x, y_new, self.width, height_new)

        if is_threshold_in_range:
            color = (0, 255, 0)
        else:
            color = (255, 0, 0)

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
                text_rect.center = (self.x - 10, y_line + self.y)
                screen.blit(text, text_rect)
            else:
                text = FONT_THRESHOLD.render(str(THLL), True, WHITE)
                text_rect = text.get_rect()
                text_rect.center = (self.x - 10, y_line + self.y)
                screen.blit(text, text_rect)


        elif self.name == 'right':
            if upper:
                text = FONT_THRESHOLD.render(str(THRU), True, WHITE)
                text_rect = text.get_rect()
                text_rect.center = (self.x - 10, y_line + self.y)
                screen.blit(text, text_rect)
            else:
                text = FONT_THRESHOLD.render(str(THRL), True, WHITE)
                text_rect = text.get_rect()
                text_rect.center = (self.x - 10, y_line + self.y)
                screen.blit(text, text_rect)
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
        self.text = FONT.render(text, True, WHITE)
        self.clicked = False

    def draw(self, screen):
        pygame.draw.rect(screen, self.color, self.rect)
        text_rect = self.text.get_rect(center=self.rect.center)
        screen.blit(self.text, text_rect)


class GameState:
    def __init__(self, screen):
        self.screen = screen

        self.ball = Ball()
        self.gate_left = GateLeft()
        self.gate_right = GateRight()
        self.bar_left = Bar('left', self.gate_left.x + 50, 100, 70, 360)
        self.bar_right = Bar('right', self.gate_right.x + 30, 100, 70, 360)
        self.intro_done = False
        self.play_done = False
        self.start_button = Button(X - 275, Y, 200, 90, "Start Game")
        self.training_button = Button(X - 50, Y, 175, 90, "Train")
        self.yes_no_button = Button(X + 150, Y, 175, 90, "Yes/No")
        self.back_button = Button(X + 550, Y + 140, 75, 50, "Back")


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

    def intro(self, back = False):

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
        self.yes_no_button.draw(self.screen)
        self.training_button.draw(self.screen)
        # self.screen.blit(start_img,start_img)

        while not (self.start_button.clicked or self.training_button.clicked or self.yes_no_button.clicked):
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
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
            self.start_play(training=True)
        if self.yes_no_button.clicked:
            self.start_play(yes_no=True)



    def start_play(self, training = False, yes_no = False):
    
        
        self.back_button.clicked = False
        controls = Controls(pygame.Rect(0, 0, WIDTH / 2, 40))
        controls2 = Controls(pygame.Rect(WIDTH / 2, 0, WIDTH, 40))
        user_text = ''
        user_text2 = ''
        token_direction = random.randint(0, 1)

        countdown_done = False
        while not self.play_done:
        
            background = pygame.image.load("assets/football.jpeg")
            background = pygame.transform.scale(background, (WIDTH, HEIGHT))
            background.get_rect().center = (WIDTH // 2, HEIGHT // 2)
            self.screen.blit(background, (0, 0))
            self.gate_left.draw()
            self.gate_right.draw()
            self.bar_right.draw()
            self.bar_left.draw()
            self.bar_right.draw_threshold_bar(True, 1000)

            if not countdown_done:
                self.countdown()
                countdown_done=True

            if yes_no:
                text = FONT.render('Yes/No Mode', True, WHITE)
                text_rect = text.get_rect()
                text_rect.center = (X + 30, Y - 250)
                self.screen.blit(text, text_rect)

                text = FONT.render('Yes', True, GREEN)
                text_rect = text.get_rect()
                text_rect.center = (self.gate_left.x + 60, self.gate_left.y + 200)
                self.screen.blit(text, text_rect)

                text = FONT.render('No', True, RED)
                text_rect = text.get_rect()
                text_rect.center = (self.gate_right.x + 60, self.gate_right.y + 200)
                self.screen.blit(text, text_rect)
            elif training:
                pass
            else:
                text = FONT.render('Game Mode', True, WHITE)
                self.back_button.draw(self.screen)
                text_rect = text.get_rect()
                text_rect.center = (X + 30, Y - 250)
                self.screen.blit(text, text_rect)

                text = pygame.font.Font('freesansbold.ttf', 25).render(f'Good goals: {self.ball.score_good}', True, WHITE)
                text_rect = text.get_rect()
                text_rect.center = (X + 30, Y - 400)
                self.screen.blit(text, text_rect)

                text = pygame.font.Font('freesansbold.ttf', 25).render(f'Bad goals: {self.ball.score_bad}', True, WHITE)
                text_rect = text.get_rect()
                text_rect.center = (X + 30, Y - 450)
                self.screen.blit(text, text_rect)


            arrow_key_pressed = None

            arrow_left_image = pygame.image.load("assets/arrow-left.png")
            arrow_left_image = pygame.transform.scale(arrow_left_image, (60, 60))

            arrow_right_image = pygame.image.load("assets/arrow-right.jpeg")
            arrow_right_image = pygame.transform.scale(arrow_right_image, (60, 60))
            if token_direction == 0:
                self.screen.blit(arrow_left_image, (self.gate_left.x + 35, self.gate_left.y + 215))
            else:
                self.screen.blit(arrow_right_image, (self.gate_right.x + 35, self.gate_right.y + 215))


            controls.draw((0, 0, 0), 'Th L:')
            controls2.draw((0, 0, 0), 'Th R:')

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.play_done = True
                    '''
                    today = datetime.now().strftime("%Y-%m-%d")
                    path = "test/" + today
                    if not os.path.exists(path):
                        os.mkdir(path)
                    dir_path = path + "/" + today + "_TEST"

                    if not os.path.exists(dir_path):
                        os.mkdir(dir_path)
                    ConfigGame.THRU = 300
                    shutil.copy("test_config.py", dir_path)
                    '''
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if controls.rect.collidepoint(event.pos):
                        controls.active = True
                        controls2.active = False
                        # controls.getUserInput(event)
                        controls2.save_user_input(user_text2, 12)
                    elif controls2.rect.collidepoint(event.pos):
                        controls2.active = True
                        controls.active = False
                        # controls2.getUserInput(event)
                        controls.save_user_input(user_text, 11)
                    elif self.back_button.rect.collidepoint(event.pos):
                        self.back_button.clicked = True

                if event.type == pygame.KEYDOWN:
                    if controls.active == True:
                        if event.key == pygame.K_BACKSPACE:
                            user_text = user_text[:-1]
                        else:
                            try:
                                if unicodedata.digit(event.unicode) >= 0 and unicodedata.digit(event.unicode) <= 9:
                                    user_text += event.unicode
                                    if len(user_text) > 3:
                                        user_text = user_text[:-1]
                            except:
                                continue

                        if event.key == pygame.K_KP_ENTER:
                            controls.save_user_input(user_text, 11)

                    elif controls2.active == True:
                        if event.key == pygame.K_BACKSPACE:
                            user_text2 = user_text2[:-1]
                        else:
                            try:
                                if unicodedata.digit(event.unicode) >= 0 and unicodedata.digit(event.unicode) <= 9:
                                    user_text2 += event.unicode
                                    if len(user_text2) > 3:
                                        user_text2 = user_text2[:-1]
                            except:
                                continue
                        if event.key == pygame.K_KP_ENTER:
                            controls2.save_user_input(user_text2, 12)

            controls.draw_new_text(user_text, 100)
            controls2.draw_new_text(user_text2, 100)

            # text_surface = FONT_CONTROLLS.render(user_text, True, (0, 255, 0))
            # self.screen.blit(text_surface,(0,0))
            keys = pygame.key.get_pressed()
            # Check for key events to move the ball
            if keys[pygame.K_LEFT] and self.ball.x > 0:
                arrow_key_pressed = "LEFT"
                MOTIONS.append(arrow_key_pressed)

                self.ball.move_left()
                if self.ball.x <= self.gate_left.x + 20:
                    if token_direction==0:
                        self.play_done = True
                        self.congrats()
                        self.ball.score_good+=1
                    else:
                        self.ball.score_bad+=1
                    self.ball.replace()

            if keys[pygame.K_RIGHT] and self.ball.y < MAC_WIDTH - self.ball.width:
                arrow_key_pressed = "RIGHT"
                MOTIONS.append(arrow_key_pressed)

                self.ball.move_right()
                if self.ball.x >= self.gate_right.x - 20:
                    if token_direction==1:
                        self.play_done = True
                        self.congrats()
                        self.ball.score_good+=1
                    else:
                        self.ball.score_bad+=1
                    self.ball.replace()

            # Update the ball's position
            self.ball.update()

            if arrow_key_pressed:
                text = FONT.render(f"Arrow key pressed: {arrow_key_pressed}", True, (0, 0, 0))
                self.screen.blit(text, (10, 10))
                self.screen.blit(text, text.get_rect())

            self.screen.blit(self.ball.image, (self.ball.x, self.ball.y))

            if self.back_button.clicked:
                self.intro(back = True)
            pygame.display.flip()

    def congrats(self):
        pygame.mixer.init()
        sound = pygame.mixer.Sound("assets/congrats.wav")
        sound.set_volume(0.6)
        background = pygame.image.load("assets/congrats.png")
        background = pygame.transform.scale(background, (WIDTH, HEIGHT))
        congrats_text = FONT.render('Congrats!', True, WHITE)
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
        FILE.write(str(MOTIONS))
        FILE.write('\n')
        


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

    def save_user_input(self, text, thresold):
        global THLU, THRU
        self.user_text = text
        if thresold == 11:
            THLU = self.user_text
            config.set('Game', 'THLU', str(THLU))
        if thresold == 12:
            THRU = self.user_text
            config.set('Game', 'THRU', str(THRU))
        with open('config_game.ini', 'w') as configfile:
            config.write(configfile)
            print("ok")

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


if __name__ == "__main__":
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption('Lexi\'s Football Game!!')

    FILE = open('motions.txt', 'a')
    today = date.today()
    # FILE.write(str(today)+'\n')

    game_state = GameState(screen)
    game_state.intro()
    FILE.close()
