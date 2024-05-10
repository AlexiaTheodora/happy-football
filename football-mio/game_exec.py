from multiprocessing import Process, Lock, Pipe, Event
import pygame
import game
import sys

from mioconn.mio_connect import MioConnect

'''
not_connected = 1
while not_connected:
    mio_connect.main(sys.argv[1:])
    not_connected = 0
if not not_connected:
    game.main()
'''

pygame.init()

MAC_WIDTH = 1280
MAC_HEIGHT = 800
WIDTH, HEIGHT = MAC_WIDTH, MAC_HEIGHT
FONT = pygame.font.Font('freesansbold.ttf', 32)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
X = WIDTH / 2 - 30
Y = HEIGHT * 3 / 4

global screen


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


if __name__ == "__main__":

    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption('Lexi\'s Football Game!!')

    intro_image = pygame.image.load("assets/pag1.png")
    intro_rect = intro_image.get_rect()
    intro_rect.center = (WIDTH // 2, HEIGHT // 2)

    text = FONT.render('Footbal game', True, WHITE)
    text_rect = text.get_rect()
    text_rect.center = (X + 30, Y - 250)

    screen.blit(intro_image, intro_rect)
    screen.blit(text, text_rect)

    connect_button = Button(X - 50, Y, 175, 90, "Connect")
    start_button = Button(X - 50, Y - 100, 175, 90, "Start")
    play = True

    myo_connected1 = False
    myo_connected2 = False

    mio_connect = MioConnect()

    connected1 = Event()
    connected2 = Event()
    process_mio_connect = Process(target=mio_connect.main, args=('sys.argv[1:]', connected1, connected2))
    process_game = Process(target=game.main)

    while play:
        background = pygame.image.load("assets/football.jpeg")
        background = pygame.transform.scale(background, (WIDTH, HEIGHT))
        background.get_rect().center = (WIDTH // 2, HEIGHT // 2)
        screen.blit(background, (0, 0))
        connect_button.draw(screen)

        while not connect_button.clicked:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if connect_button.rect.collidepoint(event.pos):
                        connect_button.clicked = True
                        process_mio_connect.start()
                        while not myo_connected1 or not myo_connected2:

                            while connected1.wait(10) and connected2.wait(10):
                                if connected1.is_set():
                                    text = FONT.render("Myo left connected", True, WHITE)
                                    text_rect = text.get_rect()
                                    text_rect.center = (X - 400, Y)
                                    screen.blit(text, text_rect)
                                    myo_connected1 = True
                                    pygame.display.flip()

                                if connected2.is_set():
                                    text = FONT.render("Myo right connected", True, WHITE)
                                    text_rect = text.get_rect()
                                    text_rect.center = (X + 400, Y)
                                    screen.blit(text, text_rect)
                                    myo_connected2 = True
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

                        #start_button.draw(screen)
                        #process_game.start()
                        #pygame.display.flip()

