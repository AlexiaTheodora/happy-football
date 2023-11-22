import pygame as pg
from pickable import PickleableSurface
pg.Surface = PickleableSurface
pg.surface.Surface = PickleableSurface

surf = pg.Surface((300, 400), pg.SRCALPHA|pg.HWSURFACE)
# Surface, color, start pos, end pos, width
pg.draw.line(surf, (0,0,0), (0,100), (200, 300), 2)  

from pickle import loads, dumps

dump = dumps(surf)
loaded = loads(dump)
pg.init()
screen = pg.display.set_mode((300, 400))
screen.fill((255, 255, 255))
screen.blit(loaded, (0,0))
pg.display.update()