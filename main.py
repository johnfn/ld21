import sys, pygame, time
import spritesheet
from wordwrap import render_textrect

DEBUG = True

WALLS = [(0,0,0)]
TILE_SIZE = 20
MAP_SIZE = 20

ABS_MAP_SIZE = TILE_SIZE * MAP_SIZE

def get_touching(x_abs, y_abs):
  """If a thing's upper (x,y) coords are x_abs, y_abs, then what tiles will
  it be touching?"""
  result = []
  for x in range((x_abs + 2)/TILE_SIZE, (x_abs + TILE_SIZE - 2)/TILE_SIZE + 1):
    for y in range((y_abs + 2)/TILE_SIZE, (y_abs + TILE_SIZE - 2)/TILE_SIZE + 1):
      result.append([x,y])
  return result

def sign(x):
  if x > 0: return 1
  if x < 0: return -1
  return 0

""" I think way too functionally for my own good. """
def and_fn(bools):
  return not False in bools

def or_fn(bools):
  return True in bools

class TileSheet:
  """ Memoize all the sheets so we don't load in 1 sheet like 50 times and 
  squander resources. This is a singleton, which is generally frowned upon, 
  but I think it's okay here."""
  sheets = {}

  @staticmethod
  def add(file_name):
    if file_name in TileSheet.sheets:
      return

    new_sheet = spritesheet.spritesheet(file_name)
    width, height = dimensions = new_sheet.sheet.get_size()
    TileSheet.sheets[file_name] =\
     [[new_sheet.image_at((x, y, TILE_SIZE, TILE_SIZE), colorkey=(255,255,255))\
       for y in range(0, height, TILE_SIZE)] for x in range(0, width, TILE_SIZE)]

  @staticmethod
  def get(sheet, x, y):
    if sheet not in TileSheet.sheets:
      raise
    return TileSheet.sheets[sheet][x][y]

class Map:
  def in_bounds(self, x, y):
    return x >= 0 and y >= 0 and x < self.size and y < self.size

  def in_bounds_abs(self, x, y):
    return x >= 0 and y >= 0 and\
        x < TILE_SIZE * self.size and y < TILE_SIZE * self.size

  def is_wall(self, x, y):
    if not self.in_bounds(y, x): return False
    return self.data[y][x] in WALLS

  #got to update with abs
  def update_map(self, x, y, pos_abs=False):
    if pos_abs:
      self.map_coords[0] = x
      self.map_coords[1] = y
    else:
      self.map_coords[0] += x
      self.map_coords[1] += y

    self.current_map = TileSheet.get(self.file_name, *self.map_coords)
    self.data = [[self.current_map.get_at((x, y)) for x in range(MAP_SIZE)]\
                                                  for y in range(MAP_SIZE)]

    self.size = len(self.data)

    self.mapdata = [[self.get_img(self.data[x][y])  for x in range(self.size)]\
                                                    for y in range(self.size)]
    self.maprects= [[self.mapdata[x][y].get_rect()  for x in range(self.size)]\
                                                    for y in range(self.size)]
    
    for x in range(self.size):
      for y in range(self.size):
        self.maprects[x][y].x = x * TILE_SIZE
        self.maprects[x][y].y = y * TILE_SIZE


  """Holds data related to the in-game map."""
  def get_img(self, data_piece):
    "Given some chunk of data, return the corresponding related image."
    if data_piece == (255,255,255):
      return TileSheet.get("wall.png", 0, 0)
    elif data_piece == (0,0,0):
      return TileSheet.get("wall.png", 1, 0)

  def __init__(self, file_name, coords):
    self.file_name = file_name
    self.map_coords = coords

    TileSheet.add(file_name)

    self.update_map(0, 0, True)

  def render(self, screen):
    """ Render the map """
    for x in range(self.size):
      for y in range(self.size):
        screen.blit(self.mapdata[x][y], self.maprects[x][y])
  


class Character:
  def __init__(self, x, y):
    # Tweakable settings
    self.speed = 5
    self.jump_height = 15

    # Initial values
    self.x = x
    self.y = y
    self.vx = 0
    self.vy = 0

    self.img = TileSheet.get("wall.png", 1, 0)
    self.rect = self.img.get_rect()

  @staticmethod
  def touching_wall(x, y, game_map):
    return or_fn([game_map.is_wall(*pos) for pos in get_touching(x, y)])

  @staticmethod
  def on_ground(x, y, game_map):
    feet_position1 = ((x + 2)/TILE_SIZE, (y + TILE_SIZE)/TILE_SIZE)
    feet_position2 = ((x + TILE_SIZE - 2)/TILE_SIZE, (y + TILE_SIZE)/TILE_SIZE)
    return game_map.is_wall(*feet_position1) or game_map.is_wall(*feet_position2)

  def update(self, keys, game_map):
    """ Move the character one tick. """
    self.vy += 1

    jumping = False

    if keys[pygame.K_w] and self.on_ground:
      jumping = True
      self.vy = -self.jump_height

    dx = (keys[pygame.K_d] - keys[pygame.K_a]) * self.speed + self.vx
    dy =                                                    + self.vy

    if not game_map.in_bounds_abs(self.x + dx, self.y + dy):
      # I am more proud of this line than any other I have written in recent times.
      game_map.update_map((self.x + dx)/(ABS_MAP_SIZE - TILE_SIZE),\
                          (self.y + dy)/(ABS_MAP_SIZE - TILE_SIZE), False)

      self.x += -((self.x + dx)/(ABS_MAP_SIZE - TILE_SIZE)) * ABS_MAP_SIZE
      self.y += -((self.y + dy)/(ABS_MAP_SIZE - TILE_SIZE)) * ABS_MAP_SIZE

    self.x += dx
    while Character.touching_wall(self.x, self.y, game_map):
      self.x += -sign(dx)

    for x in range(abs(dy)):
      self.y += sign(dy)
      if Character.touching_wall(self.x, self.y, game_map):
        self.y -= sign(dy)
        self.on_ground = True
        self.vy = 0
        break

    if not Character.on_ground(self.x, self.y, game_map):
      self.on_ground = False

  def render(self, screen):
    self.rect.x = self.x
    self.rect.y = self.y
    screen.blit(self.img, self.rect)

class UpKeys:
  """ Simple abstraction to check for recent key released behavior. """
  keys = []
  
  @staticmethod
  def flush():
    UpKeys.keys = []

  @staticmethod
  def add_key(val):
    UpKeys.keys.append(val)

  @staticmethod
  def key_up(val):
    if val in UpKeys.keys:
      UpKeys.keys.remove(val)
      return True 
    return False

class Dialog:
  all_dialog = { "initial" : [("Narrator", "You are the greatest escape artist."),
                              ("Narrator", "Ever."), 
                              ("Narrator", "At least that's what you think."), 
                              ("Narrator", "Except some jerks trapped you in this big weird looking facility."),
                              ("Narrator", "And you want to escape."),
                              ("Narrator", "You have one special talent though."),
                              ("Narrator", "Press ESC to activate your escape artist powers.")]
                              }
  speaker = ""
  position = 0 # What is the first dialog we haven't seen yet?

  @staticmethod
  def update(screen):
    if UpKeys.key_up(pygame.K_RETURN):
      if not Dialog.next_dialog():
        return False

    return Dialog.show_dialog(screen)

  @staticmethod
  def start_dialog(speaker):
    Dialog.speaker = speaker
    Dialog.position = 0
    return True

  @staticmethod
  def next_dialog():
    """ Return True if successful, False if dialog over."""
    Dialog.position += 1 

    if Dialog.position == len(Dialog.all_dialog[Dialog.speaker]):
      Dialog.position = 0
      return False

    return True

  @staticmethod
  def show_dialog(screen):
    my_font = pygame.font.Font(None, 15)

    speaker, dialog = Dialog.all_dialog[Dialog.speaker][Dialog.position]

    my_rect = pygame.Rect((60, ABS_MAP_SIZE - 100, 300, 40))
    rendered_text = render_textrect(dialog, my_font, my_rect, (10, 10, 10), (210, 255, 255), 0)

    screen.blit(rendered_text, my_rect.topleft)
    return True

  @staticmethod
  def show_overhead(user, screen):
    my_width = 100

    my_font = pygame.font.Font(None, 14)

    my_rect = pygame.Rect((user.x - my_width / 2, user.y - 10, my_width, 16))
    rendered_text = render_textrect("HOOOLY COW!!!!!!", my_font, my_rect, (10, 10, 10), (255, 255, 255), 0)

    screen.blit(rendered_text, my_rect.topleft)

class Updater:
  # Update each item every step (until it kills itself)

  # Must expose 3 mthods
  # depth(): returns relative depth or 0 if it doesn't matter
  # update(): returns False if destroyed, True otherwise
  # render(): renders the object
  items = [] # Things that need to be updated every step

  @staticmethod
  def add_updater(updater):
    items.append(updater)

  @staticmethod
  def update_all():
    Updater.items = [item for item in Updater.items if item.update()]

  @staticmethod
  def render_all():
    # sort by depth
    items_sorted = sorted(items, key=lambda x:x.depth())

    for item in items_sorted:
      item.render()


class States:
  Dialog = "Dialog"
  Normal = "Normal"

class Game:
  def __init__(self):
    self.keys_up = []

    pygame.display.init()
    pygame.font.init()
    self.screen = pygame.display.set_mode((ABS_MAP_SIZE, ABS_MAP_SIZE))

    TileSheet.add("wall.png")

    self.map = Map("map.png", [0, 0])
    self.char = Character(40, 40)

    if DEBUG:
      self.state = States.Normal
    else:
      self.state = States.Dialog
      Dialog.start_dialog("initial")

  def loop(self):
    while 1:
      for event in pygame.event.get():
        if event.type == pygame.QUIT: 
          pygame.display.quit()
          exit(0)
        if event.type == pygame.KEYUP:
          UpKeys.add_key(event.key)
      
      self.screen.fill((255,255,255))
      self.map.render(self.screen)
      self.char.render(self.screen)

      if self.state == States.Dialog:
        if not Dialog.update(self.screen):
          self.state = States.Normal
      elif self.state == States.Normal:
        self.char.update(pygame.key.get_pressed(), self.map)

      Dialog.show_overhead(self.char, self.screen)

      time.sleep(.02)

      pygame.display.flip()

g = Game()
g.loop()
