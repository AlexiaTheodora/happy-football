import pygame
import sys

# Constants
WIDTH, HEIGHT = 800, 600
WHITE = (255, 255, 255)
BALL_RADIUS = 20
BALL_COLOR = (255, 0, 0)

class Ball:
    def __init__(self):
        self.x = WIDTH // 2
        self.y = HEIGHT - 2 * BALL_RADIUS
        self.dx = 0  # Change in x position (initialize to 0)
        self.speed = 5

    def move_left(self):
        self.dx = -self.speed

    def move_right(self):
        self.dx = self.speed

    def stop(self):
        self.dx = 0

    def update(self):
        self.x += self.dx

    def draw(self, screen):
        pygame.draw.circle(screen, BALL_COLOR, (self.x, self.y), BALL_RADIUS)

class GameState:
    def __init__(self, screen):
        self.screen = screen
        self.ball = Ball()
        self.intro_done = False

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

    def play(self):
        running = True
        font = pygame.font.Font(None, 36)  # Create a font for the text display

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

            # Get the state of all keys
            keys = pygame.key.get_pressed()

            # Check for the left arrow key
            if keys[pygame.K_LEFT]:
                self.ball.move_left()
            # Check for the right arrow key
            elif keys[pygame.K_RIGHT]:
                self.ball.move_right()
            else:
                self.ball.stop()

            # Update the ball's position
            self.ball.update()

            # Fill the background
            self.screen.fill(WHITE)

            # Draw the ball
            self.ball.draw(self.screen)

            # Display the current speed
            speed_text = font.render(f"Speed: {self.ball.speed}", True, (0, 0, 0))
            self.screen.blit(speed_text, (10, 10))

            # Update the display
            pygame.display.flip()

        pygame.quit()

if __name__ == "__main__":
    # Initialize pygame
    pygame.init()

    # Create a window
    WIDTH, HEIGHT = 800, 600
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Game")

    # Create a GameState object and run the intro
    game_state = GameState(screen)
    game_state.intro()
