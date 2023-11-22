import pygame
# time tracking - 26.08.2023: 3h
# time tracking - 14.09.2023: 1.5h
# time tracking - 21.09.2023: 1.5h
# time tracking - 22.09.2023: 2h
# time tracking - 23.09.2023: 1.5h
# time tracking - 29.09.2023: 1.5h
# time tracking - 30.09.2023: 2h
#time traking - 26.10.2023: 4h
#time traking -  03.11.2023 : 3h

white = (255, 255, 255)
green = (0, 255, 0)
blue = (0, 0, 128)


pygame.init()
pygame.display.set_caption('Lexi\'s Football Game!!')


mac_width = 1280
mac_height = 800

#background
width_background = mac_width
height_background = mac_height
window = pygame.display.set_mode((width_background, height_background))
timer = pygame.time.Clock()

background = pygame.image.load("assets/football.jpeg")
background = pygame.transform.scale(background,(width_background,height_background))


#ball
width_ball = height_background/13
height_ball = height_background/13
ball = pygame.image.load("assets/ball.png")
ball = pygame.transform.scale(ball,(width_ball,height_ball))
#ball position
x = width_background/2
y = height_background*3/4


#gates
width_gate_l = height_background/5
height_gate_l = height_background/5
width_gate_r = height_background/5
height_gate_r = height_background/5
gate_l = pygame.image.load("assets/gate_l.png")
gate_l = pygame.transform.scale(gate_l,(width_gate_l,height_gate_l))
#gate left position
x_gate_l = width_gate_r/2
y_gate_l = height_background*3/4 - height_gate_l/2

gate_r = pygame.image.load("assets/gate_r.png")
gate_r = pygame.transform.scale(gate_r,(width_gate_r,height_gate_r))
#gate left position
x_gate_r = width_background - 60 - width_gate_r
y_gate_r = height_background*3/4 - height_gate_r/2

x = width_background/2 - 30
y = height_background*3/4


font = pygame.font.Font('freesansbold.ttf', 32)
text = font.render('Welcome to the best game ever', True, white)
textRect = text.get_rect()
textRect.center = (x+30, y-250)

vel = 5 #velocity/ speed of movement


#box = pygame.Rect((225, 225, 50, 50))

def goal():
    background = pygame.image.load("assets/congrats.png")
    background = pygame.transform.scale(background,(width_background,height_background))
    congrats_text = font.render('Congrats!', True, white)
    textRect = text.get_rect()
    textRect.center = (x+30, y-250)
    window.blit(background, (0,0))
    pygame.display.update() 
    


class GameState():
    def __init__(self):
        self.state = 'main_game'
        

running = True
while running:
    window.blit(background, (0,0))
    window.blit(gate_l, (x_gate_l,y_gate_l))
    window.blit(gate_r, (x_gate_r,y_gate_r))
    window.blit(text, textRect)
    pygame.time.delay(10)
      
    # iterate over the list of Event objects  
    # that was returned by pygame.event.get() method.  
    for event in pygame.event.get():
          
        # if event object type is QUIT  
        # then quitting the pygame  
        # and program both.  
        if event.type == pygame.QUIT:
              
            # it will make exit the while loop 
            run = False
    # stores keys pressed 
    keys = pygame.key.get_pressed()
      
    # if left arrow key is pressed
    if keys[pygame.K_LEFT] and x>0:
          
        # decrement in x co-ordinate
        x -= vel
        if (x == x_gate_l+20):
            click_time = pygame.time.get_ticks()
            if click_time != 0:  
                passed_time = (pygame.time.get_ticks()-click_time) / 1000
                goal()
                if passed_time >= 3:
                    pygame.quit()
            
    # if right arrow key is pressed
    if keys[pygame.K_RIGHT] and x<1200-width_ball:
          
        # increment in x co-ordinate
        x += vel
        if (x == x_gate_r-20):
            goal()
            
    
    # drawing object on screen which is rectangle here 
    #pygame.draw.rect(window, (255, 0, 0), (x, y, width, height))
    window.blit(ball, (x,y))
    # it refreshes the window
    pygame.display.update() 

    if keys[pygame.K_q]:
        pygame.quit()

  

'''
def intro(self):
        # Load and display the introductory image
        intro_image = pygame.image.load("assets/football.jpeg")
        intro_rect = intro_image.get_rect()
        intro_rect.center = (WIDTH // 2, HEIGHT // 2)

        while not self.intro_done:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.MOUSEBUTTONDOWN:
                    self.intro_done = True

            self.screen.fill(WHITE)
            self.screen.blit(intro_image, intro_rect)
            pygame.display.flip()

        self.play()
'''