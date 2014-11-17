# define the class that handles the rendering
# individual modules should pass it an object with
#   a draw(surface) method which will returns a surface
import pygame
from pygame.locals import *

FPS = 30 # run at 30FPS

class Renderer:
  def __init__(self):
    self.drawables = [] # list of drawable objects
    # initialize a fullscreen display
    self.display_surface = pygame.display.set_mode((0,0),pygame.FULLSCREEN,0)
    #self.display_surface = pygame.display.set_mode((400,300)) #DEBUG
    self.clock = pygame.time.Clock() # timer for fpsing

  # method contains a loop running at 30hz
  def do_loop(self):
    pygame.display.set_caption('visAR')
    done = False
    while not done: # main game loop
      # check exit conditions
      if pygame.key.get_pressed()[K_ESCAPE]: done = True
      for event in pygame.event.get():
        if event.type == QUIT: done = True
      if(done): 
        pygame.quit()
        break
      
      # get the objects and draw them on the screen buffer
      self.display_surface.fill((0,0,0)) # wipe display buffer
      for drawable in self.drawables: #draw each object
        img = drawable.draw(self.display_surface.convert_alpha())
        self.display_surface.blit(img,(0,0)) # combine surfaces

      pygame.display.update() # update the display
      self.clock.tick(FPS) # wait for next frame

        
  # add a drawable object to the list     
  def add_module(self, module):
    self.drawables.append(module)
