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
from datetime import date

# Initialize pygame
pygame.init()

# Constants
MAC_WIDTH = 1280
MAC_HEIGHT = 800
WIDTH, HEIGHT = MAC_WIDTH, MAC_HEIGHT
FONT = pygame.font.Font('freesansbold.ttf', 32)
FONT_CONTROLLS = pygame.font.Font('freesansbold.ttf', 16)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
BLACK = (0, 0, 0)
X = WIDTH / 2 - 30
Y = HEIGHT * 3 / 4

global THRL, THLL, THRL, THRU
THLL = THRL = 200
THLU = THRU = 500

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
        self.draw_threshold_line()
        self.draw_threshold_line(False)

    def draw_threshold_bar(self, isThresholdInRange, force):
        #height_new = self.height - self.height * ((force-THLL)*100/(THLU-THLL)) / 100
        #height_new =  self.height * 65 / 100
        #print(((force-int(THLL))*100/(int(THLU)-int(THLL))))

        height_new = self.height * (abs(force-int(THLL))*100/(int(THLU)-int(THLL))) / 100
        y_new = self.y + self.height -  height_new
        threshold_bar = pygame.Rect(self.x, y_new, self.width, height_new)
        print(height_new)
        if isThresholdInRange:
            color = (0, 255, 0)
        else:
            color = (255, 0, 0)

        pygame.draw.rect(screen, self.color, self.rect)
        pygame.draw.rect(screen, color, threshold_bar)
        self.draw_threshold_line()
        self.draw_threshold_line(False)

    def draw_threshold_line(self, upper_line=True):
        # the line values won t be changed during the game
        if upper_line:
            y_line = self.height * 33 / 100
        else:
            y_line = self.height * 66 / 100


        pygame.draw.line(screen, (0, 0, 0), [self.x , y_line + self.y],[self.x + self.width, y_line + self.y], 2)

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
    def __init__(self, screen, start_button, game_button):
        self.screen = screen

        self.ball = Ball()
        self.gate_left = GateLeft()
        self.gate_right = GateRight()
        self.bar_left = Bar('left', self.gate_left.x + 50, 100, 70, 420)
        self.bar_right = Bar('right', self.gate_right.x + 30, 100, 70, 420)
        self.intro_done = False
        self.play_done = False
        self.start_button = start_button
        self.game_button = game_button

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
        self.game_button.draw(self.screen)
        # self.screen.blit(start_img,start_img)

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
        text_rect.center = (X + 30, Y - 250)
        self.screen.blit(text, text_rect)
        controls = Controls(pygame.Rect(0, 0, WIDTH / 2, 40))
        controls2 = Controls(pygame.Rect(WIDTH / 2, 0, WIDTH, 40))
        user_text = ''
        user_text2 = ''

        while not self.play_done:
            background = pygame.image.load("assets/football.jpeg")
            background = pygame.transform.scale(background, (WIDTH, HEIGHT))
            background.get_rect().center = (WIDTH // 2, HEIGHT // 2)
            self.screen.blit(background, (0, 0))
            self.gate_left.draw()
            self.gate_right.draw()
            self.bar_right.draw()
            self.bar_left.draw()
            self.bar_right.draw_threshold_bar(False,150)


            arrow_key_pressed = None

            controls.draw((0, 0, 0), 'Th L:')
            controls2.draw((0, 0, 0), 'Th R:')

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.play_done = True
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
                    self.play_done = True
                    self.congrats()

            if keys[pygame.K_RIGHT] and self.ball.y < MAC_WIDTH - self.ball.width:
                arrow_key_pressed = "RIGHT"
                MOTIONS.append(arrow_key_pressed)

                self.ball.move_right()
                if self.ball.x >= self.gate_right.x - 20:
                    self.play_done = True
                    self.congrats()

            # Update the ball's position
            self.ball.update()

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
        FILE.write(str(MOTIONS))
        FILE.write('\n')
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

    def save_user_input(self, text, thresold):
        global THLU, THRU
        self.user_text = text
        if thresold == 11:
            THLU = self.user_text
        if thresold == 12:
            THRU = self.user_text
        print(self.user_text)

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
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption('Lexi\'s Football Game!!')

    FILE = open('motions.txt', 'a')
    today = date.today()
    # FILE.write(str(today)+'\n')
    train_button = Button(X - 150, Y, 175, 90, "Train")
    game_button = Button(X + 50, Y, 175, 90, "Game")
    game_state = GameState(screen, train_button, game_button)
    game_state.intro()
    FILE.close()
