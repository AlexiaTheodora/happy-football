import pygame
import numpy as np
import threading
import time

class Logic:
    # This will run in another thread
    def __init__(self, size, speed=2):
        # Private fields -> Only to be edited locally
        self._size = size
        self._direction = np.array([0, 1])  # [x, y] vector, underscored because we want this to be private
        self._speed = speed

        # Threaded fields -> Those accessible from other threads
        self.position = np.array(size) / 2
        self.input_list = []  # A list of commands to queue up for execution

        # A lock ensures that nothing else can edit the variable while we're changing it
        self.lock = threading.Lock()

    def _loop(self):
        time.sleep(0.5)  # Wait a bit to let things load
        # We're just going to kill this thread with the main one so it's fine to just loop forever
        while True:
            # Check for commands
            time.sleep(0.01)  # Limit the logic loop running to every 10ms

            if len(self.input_list) > 0:

                with self.lock:  # The lock is released when we're done
                    # If there is a command we pop it off the list
                    key = self.input_list.pop(0).key

                if key == pygame.K_w:
                    self._direction = np.array([0, -1])
                elif key == pygame.K_a:
                    self._direction = np.array([-1, 0])
                elif key == pygame.K_s:
                    self._direction = np.array([0, 1])
                elif key == pygame.K_d:
                    self._direction = np.array([1, 0])

            with self.lock:  # Again we call the lock because we're editing
                self.position += self._direction * self._speed

            if self.position[0] < 0 \
                    or self.position[0] > self._size[0] \
                    or self.position[1] < 0 \
                    or self.position[1] > self._size[1]:
                break  # Stop updating
    
    def start_loop(self):
        # We spawn a new thread using our _loop method, the loop has no additional arguments,
        # We call daemon=True so that the thread dies when main dies
        threading.Thread(target=self._loop,
                         args=(),
                         daemon=True).start()
    
class Game:
    # This will run in the main thread and read data from the Logic
    def __init__(self, size, speed=2):
        self.size = size
        pygame.init()
        self.window = pygame.display.set_mode(size)
        self.logic = Logic(np.array(size), speed)
        self.running = True

    def start(self):
        pygame.display.update()
        self.logic.start_loop()

        # any calls made to the other thread should be read only
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    # Here we call the lock because we're updating the input list
                    with self.logic.lock:
                        self.logic.input_list.append(event)


            # Another lock call to access the position
            with self.logic.lock:
                self.window.fill((0, 0, 0))
                pygame.draw.circle(self.window, (0, 0, 255), self.logic.position, 10)
                pygame.display.update()

        pygame.time.wait(10)
        pygame.quit()
        quit()


if __name__ == '__main__':
    game = Game([800, 600])
    game.start()