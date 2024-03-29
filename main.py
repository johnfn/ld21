import sys, pygame, time
import time
import math
import random
import spritesheet
from wordwrap import render_textrect

DEBUG = False

# constants

GAME_SIZE = 2

WALLS = [(0,0,0)]
TILE_SIZE = 20
MAP_SIZE = 20
DEATH_COUNT = 0
START_TIME = time.time()

NOTHING_COLOR = (255, 255, 255)

ABS_MAP_SIZE = TILE_SIZE * MAP_SIZE

# images

background = None

# sound fx

land_sound = None
get_sound = None
escape_sound = None

# Following 2 methods found online.
def rot_center(image, angle):
    """rotate an image while keeping its center and size"""
    orig_rect = image.get_rect()
    rot_image = pygame.transform.rotate(image, angle)
    rot_rect = orig_rect.copy()
    rot_rect.center = rot_image.get_rect().center
    rot_image = rot_image.subsurface(rot_rect).copy()
    return rot_image

def blur_surf(surface, amt):
    if amt < 1.0:
        raise ValueError("Arg 'amt' must be greater than 1.0, passed in value is %s"%amt)
    scale = 1.0/float(amt)
    surf_size = surface.get_size()
    scale_size = (int(surf_size[0]*scale), int(surf_size[1]*scale))
    surf = pygame.transform.smoothscale(surface, scale_size)
    surf = pygame.transform.smoothscale(surf, surf_size)
    return surf

def get_touching(x_abs, y_abs):
  """If a thing's upper (x,y) coords are x_abs, y_abs, then what tiles will
  it be touching?"""
  result = []
  for x in range((x_abs + 2)/TILE_SIZE, (x_abs + TILE_SIZE - 2)/TILE_SIZE + 1):
    for y in range((y_abs + 2)/TILE_SIZE, (y_abs + TILE_SIZE - 2)/TILE_SIZE + 1):
      result.append([x,y])
  return result

# do objects with upper-rt corners as given by x.x, x.y etc touch?
def generic_touching(one, two):
  four_corners = [Point(x,y) for x in range(one.x, one.x + 17, 16) for y in range(one.y, one.y + 17, 16)]
  for corner in four_corners:
    if two.x <= corner.x <= two.x + TILE_SIZE and two.y <= corner.y <= two.y + TILE_SIZE:
      return True
  return False

# first is boss
def generic_boss_touching(one, two):
  four_corners = [Point(x,y) for x in range(one.x, one.x + 33, 16) for y in range(one.y, one.y + 33, 16)]
  for corner in four_corners:
    if two.x <= corner.x <= two.x + TILE_SIZE and two.y <= corner.y <= two.y + TILE_SIZE:
      return True
  return False

# Does point touch rect?
def point_touch_rect(pt, rect):
  return rect.x <= pt.x <= rect.x + TILE_SIZE and\
         rect.y <= pt.y <= rect.y + TILE_SIZE

def sign(x):
  if x > 0: return 1
  if x < 0: return -1
  return 0

def min_abs(x, y):
  if abs(x) < abs(y): 
    return x
  return y

""" I think way too functionally for my own good. """
def and_fn(bools):
  return not False in bools

def or_fn(bools):
  return True in bools

class BigImage:
  def __init__(self, src_file, scale = 1):
    self.img = pygame.image.load(src_file).convert()
    self.width, self.height = dimensions = self.img.get_size()

    if scale != 1:
      new_surf = pygame.Surface((self.width * scale, self.height * scale))
      pygame.transform.scale(self.img, (self.width * scale, self.height * scale), new_surf)
      self.img = new_surf

    self.rect = self.img.get_rect()

  def render(self, screen):
    screen.blit(self.img, self.rect)

  def parallax(self, dx, dy):
    self.rect.x -= float(dx) * 35
    self.rect.y -= float(dy) * 35

    if self.rect.x > 0: self.rect.x = 0
    if self.rect.y > 0: self.rect.y = 0
    if self.rect.x < -self.rect.width: self.rect.x = -self.rect.width + ABS_MAP_SIZE
    if self.rect.y < -self.rect.height: self.rect.y = -self.rect.height + ABS_MAP_SIZE

class Image:
  def __init__(self, src_file, src_x, src_y, dst_x, dst_y):
    self.old_values = (src_file, src_x, src_y)

    self.img = TileSheet.get(*self.old_values)
    self.rect = self.img.get_rect()

    self.rect.x = dst_x
    self.rect.y = dst_y

    self.base_w = self.img.get_width()
    self.base_h = self.img.get_height()

  @property
  def x(self):
    return self.rect.x

  @property
  def y(self):
    return self.rect.y

  def render(self, screen, scale = 1, rotation = 0):
    rect = self.rect

    if scale != 1:
      self.img = pygame.transform.scale(self.img, (self.base_w * scale, self.base_h * scale))
      rect[0] -= self.base_w / scale
      rect[1] -= self.base_h / scale

    if rotation != 0:
      rotated = rot_center(self.img, rotation)
      screen.blit(rotated, rect)
    else:
      screen.blit(self.img, rect)

  def move(self, new_x, new_y):
    self.rect.x = new_x
    self.rect.y = new_y

  def update(self, src_file, src_x, src_y):
    new_values = (src_file, src_x, src_y)
    if new_values == self.old_values:
      return

    self.old_values = new_values
    self.img = TileSheet.get(*self.old_values)

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
  Cache = {}

  def in_bounds(self, x, y):
    return x >= 0 and y >= 0 and x < self.size and y < self.size

  # Would a character at (x, y) be in bounds?
  def in_bounds_abs(self, x, y):
    return x >= 0 and y >= 0 and\
        x < TILE_SIZE * (self.size - 1) and y < TILE_SIZE * (self.size - 1)

  def is_wall(self, x, y):
    if not self.in_bounds(y, x): return False
    return self.data[y][x] in WALLS

  def parse(self, coords, rgb_triple):
    if rgb_triple == (255, 0, 0): # Enemy
      self.current_map.set_at(coords, NOTHING_COLOR)
      Updater.add_updater(Enemy(coords, self.char, self))
    if rgb_triple == (100, 0, 0): # Enemy In Reverse
      self.current_map.set_at(coords, NOTHING_COLOR)
      Updater.add_updater(Enemy(coords, self.char, self)) #TODO?????????????
    if rgb_triple == (0, 255, 0): # Rotator
      self.current_map.set_at(coords, (255,255,255))
      Updater.add_updater(Rotator(coords))
    if rgb_triple == (255, 255, 0): # Treasure
      self.current_map.set_at(coords, NOTHING_COLOR)
      Updater.add_updater(Pickup(coords, "treasure", self.char))
    if rgb_triple == (150,90,60): # Dialog
      self.current_map.set_at(coords, NOTHING_COLOR)
      Updater.add_updater(DialogStarter(coords, self.char, rgb_triple, self.map_coords, self))
    if rgb_triple == (0,0,255): # Stairs
      self.current_map.set_at(coords, NOTHING_COLOR)
      Updater.add_updater(Stairs(coords))
    if rgb_triple == (200, 200, 0): # Replicator
      self.current_map.set_at(coords, NOTHING_COLOR)
      Updater.add_updater(Pickup(coords, "replicator", self.char))
    if rgb_triple == (200, 255, 0): # Enemy Escaper
      self.current_map.set_at(coords, NOTHING_COLOR)
      Updater.add_updater(Pickup(coords, "escaper", self.char))
    if rgb_triple == (150, 150, 150): # Signpost 1
      self.current_map.set_at(coords, NOTHING_COLOR)
      Updater.add_updater(Pickup(coords, "signpost1", self.char))
    if rgb_triple == (151, 150, 150): # Signpost 2
      self.current_map.set_at(coords, NOTHING_COLOR)
      Updater.add_updater(Pickup(coords, "signpost2", self.char))
    if rgb_triple == (200, 200, 200): # Big Bad Boss
      self.current_map.set_at(coords, NOTHING_COLOR)
      Updater.add_updater(Boss(coords, self.char, self, self.game))

  #got to update with abs
  def update_map(self, x, y, pos_abs=False):
    if x == 0 and y == 0 and not pos_abs: return # Don't bother.

    # Store stuff that stays between maps.
    Map.Cache[tuple(self.map_coords)] = Updater.get_all(lambda x: hasattr(x, "cacheable"))

    # Remove old enemies
    Updater.remove_all(lambda x: hasattr(x, "cacheable"))

    if pos_abs:
      self.map_coords[0] = x
      self.map_coords[1] = y
    else:
      self.map_coords[0] += x
      self.map_coords[1] += y

    if tuple(self.map_coords) in Map.Cache:
      #TODO: retrieve everything
      for item in Map.Cache[tuple(self.map_coords)]:
        Updater.add_updater(item)

    self.current_map = TileSheet.get(self.file_name, *self.map_coords)

    # This is like a preprocessor to parse things out of the map (like enemies)
    [[self.parse((x, y), self.current_map.get_at((x, y))) for x in range(MAP_SIZE)]\
                                                          for y in range(MAP_SIZE)]

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

  def __init__(self, file_name, coords, char, game):
    self.game = game
    self.char = char
    self.file_name = file_name
    self.map_coords = coords

    TileSheet.add(file_name)

    self.update_map(*self.map_coords, pos_abs=True)

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

    self.restore_x = self.x # Restore on being seen
    self.restore_y = self.y

    self.vx = 0
    if DEBUG:
      self.vy = 20
    else:
      self.vy = 0

    if DEBUG:
      self.health = 1
    else:
      self.health = 3
    self.max_health = 3

    self.img = TileSheet.get("wall.png", 0, 3)
    self.rect = self.img.get_rect()

    self.ghost = Image("wall.png", 1, 1, 0, 0)

    self.flicker_tick = 0

    if DEBUG:
      self.items = ["replicator", "escaper"]
    else:
      self.items = []

    self.anim_ticker = 0
    self.left_facing = True

  def get_item(self, item_name):
    if item_name not in self.items:
      Dialog.start_dialog(item_name)
    else:
      if not item_name == "treasure":
        return

    self.items.append(item_name)

  @property
  def gold(self):
    return self.items.count("treasure")

  def has_replicator(self):
    return "replicator" in self.items

  def has_escaper(self):
    return "escaper" in self.items

  def flicker(self):
    self.flicker_tick = 50

  # predicate
  # item must have x, y attrs
  def touching_item(self, item):
    return (self.x <= item.x <= self.x + TILE_SIZE or self.x <= item.x + TILE_SIZE/2 <= self.x + TILE_SIZE) and\
           (self.y <= item.y <= self.y + TILE_SIZE or self.y <= item.y + TILE_SIZE/2 <= self.y + TILE_SIZE)

  @staticmethod
  def touching_wall_only(x, y, game_map, uid=-1):
    return or_fn([game_map.is_wall(*pos) for pos in get_touching(x, y)])
  
  # doesn't make sense for this to be a static method of character. Oh well.
  @staticmethod
  def touching_wall(x, y, game_map, uid=-1):
    return or_fn([game_map.is_wall(*pos) for pos in get_touching(x, y)] + [Character.touching_updater(x, y, uid)])

  @staticmethod
  def touching_updater(x, y, uid=-1):
    return len([True for x in Updater.get_all(lambda obj: isinstance(obj, Replicated) and uid != obj.uid and generic_touching(obj, Point(x, y)))]) > 0

  @staticmethod
  def point_touching_updater(x, y, uid=-1):
    return len([True for x in Updater.get_all(lambda obj: isinstance(obj, Replicated) and uid != obj.uid and point_touch_rect(Point(x, y), obj))]) > 0

  @staticmethod
  def on_ground(x, y, game_map):
    # Holy incoming bad code
    feet_position1 = ((x + 2)/TILE_SIZE, (y + TILE_SIZE)/TILE_SIZE)
    feet_position2 = ((x + TILE_SIZE - 2)/TILE_SIZE, (y + TILE_SIZE)/TILE_SIZE)

    feet_pos_abs1 =  ((x + 2), (y + TILE_SIZE + 2))
    feet_pos_abs2 =  ((x + TILE_SIZE - 2), (y + TILE_SIZE + 2))

    return game_map.is_wall(*feet_position1) or game_map.is_wall(*feet_position2) or\
        Character.point_touching_updater(*feet_pos_abs1) or Character.point_touching_updater(*feet_pos_abs2)

  def update(self, keys, game_map, game):
    if self.health < 0:
      self.death(game_map)
      game.set_state(States.Death)
      return #dead

    """ Move the character one tick. """
    new_screen = False
    map_dx, map_dy = 0, 0

    on_stairs = len(Updater.get_all(lambda obj: isinstance(obj, Stairs) and self.touching_item(obj))) > 0

    if DEBUG:
      if keys[pygame.K_q]:
        game.set_state(States.GameOver)

    # Movement code

    self.vy += 1
    if on_stairs:
      # Disregard all physics. YOU ARE SUPERMAN.
      self.vy = (keys[pygame.K_DOWN] - keys[pygame.K_UP]) * self.speed

      if self.vy != 0:
        self.anim_ticker += 1
        if self.anim_ticker / 5 % 2 == 0:
          self.img = TileSheet.get("wall.png", 0, 4)
        else:
          self.img = TileSheet.get("wall.png", 1, 4)

    jumping = False

    if keys[pygame.K_x] and self.on_ground:
      jumping = True
      self.vy = -self.jump_height

    # A bit of a hack to correct for speedy falling (where you fall through blocks).
    if self.vy > TILE_SIZE - 1: self.vy = TILE_SIZE * sign(self.vy) - 1

    dx = (keys[pygame.K_RIGHT] - keys[pygame.K_LEFT]) * self.speed + self.vx
    dy =                                                    + self.vy

    if dx != 0:
      self.anim_ticker += 1
      if self.anim_ticker / 5 % 2 == 0:
        self.img = TileSheet.get("wall.png", 0, 3)
      else:
        self.img = TileSheet.get("wall.png", 1, 3)

      self.left_facing = (dx < 0)

    if not game_map.in_bounds_abs(self.x + dx, self.y + dy):
      # I am more proud of these lines than any other I have written in recent times.
      map_dx = (self.x + dx)/(ABS_MAP_SIZE - TILE_SIZE)
      map_dy = (self.y + dy)/(ABS_MAP_SIZE - TILE_SIZE)
      game_map.update_map(map_dx, map_dy, False)

      self.x += -((self.x + dx)/(ABS_MAP_SIZE - TILE_SIZE)) * (ABS_MAP_SIZE - TILE_SIZE)
      self.y += -((self.y + dy)/(ABS_MAP_SIZE - TILE_SIZE)) * (ABS_MAP_SIZE - TILE_SIZE)

      new_screen = True

    self.x += dx
    while Character.touching_wall(self.x, self.y, game_map):
      self.x += -sign(dx)

    for x in range(abs(dy)):
      self.y += sign(dy)
      if Character.touching_wall(self.x, self.y, game_map):
        if not self.on_ground:
          if not DEBUG:
            land_sound.play()

        self.y -= sign(dy)
        self.on_ground = True
        self.vy = 0
        break

    if not Character.on_ground(self.x, self.y, game_map):
      self.on_ground = False

    if new_screen:
      background.parallax(map_dx, map_dy)
      Updater.remove_all(lambda x: isinstance(x, Replicated))
      self.set_restore_point()

    # Flip code <ESC>

    target = Updater.get_escape(self)
    if target is None: 
      # No escaper found in this map.
      if UpKeys.key_up(27) or UpKeys.key_up(pygame.K_z):
        Updater.add_updater(HoverText("I can't without a target.", self, 0))
      return

    flipped_x = int(target.x * 2 - self.x)

    # Flip code. Probably should move to new function
    self.ghost.move(flipped_x, self.y)
    if UpKeys.key_up(27) or UpKeys.key_up(pygame.K_z):
      if abs(flipped_x - self.x) < TILE_SIZE + 1 and self.has_replicator():
        Updater.add_updater(HoverText("My own dead body would kill me!", self, 0))
        return
      
      if flipped_x < 0 or flipped_x > ABS_MAP_SIZE:
        Updater.add_updater(HoverText("I can't see there!", self, 0))
        return

      old_coords = (self.x, self.y)

      new_x = flipped_x
      new_y = self.y
      if Character.touching_wall(new_x, self.y, game_map):
        Updater.add_updater(HoverText("I can't go there!", self, 0))
        return
      else:
        self.x = new_x

      if not DEBUG:
        escape_sound.play()
      # Leave a dead body!!!
      if self.has_replicator():
        Updater.add_updater(Replicated(old_coords, game_map, self))
      game.set_state(States.Blurry)

  # On hurt or something. returns True on death
  def hurt(self, damage, dmg_type, game_map):
    self.health -= damage

    self.flicker()

    message = random.choice(["Ouch!", "Ow!", "Yowch!", "Oof!"])
    Updater.add_updater(HoverText(message, self, 0))

    if dmg_type == "enemy":
      #TODO
      # Updater.add_updater(Replicated((self.x, self.y), game_map, self))

      self.x = self.restore_x
      self.y = self.restore_y
 
      while Character.touching_wall(self.x, self.y, game_map):
        self.y -= 1
        if self.y < 0:
          # The only possibility now is someone is trying to screw with us.
          while Character.touching_wall(self.x, self.y, game_map):
            self.x = random.random() * ABS_MAP_SIZE
            self.y = random.random() * ABS_MAP_SIZE

      self.vx = 0
      self.vy = 0

    return False

  def set_death_point(self, game_map):
    self.res_death = {'x' : self.x, 'y' : self.y, 
                      'mx' : game_map.map_coords[0], 'my' : game_map.map_coords[1]}

  def death(self, game_map):
    global DEATH_COUNT
    DEATH_COUNT += 1

    self.health = self.max_health 
    self.x = self.res_death['x']
    self.y = self.res_death['y']

    self.vx = 0
    self.vy = 0

    game_map.update_map(self.res_death['mx'], self.res_death['my'], True)

    Updater.remove_all(lambda x: isinstance(x, HoverText))
    Updater.remove_all(lambda x: isinstance(x, Replicated))
    Updater.remove_all(lambda x: isinstance(x, Boss))

  def set_restore_point(self):
    self.restore_x = self.x
    self.restore_y = self.y

  def render(self, screen):
    self.rect.x = self.x
    self.rect.y = self.y
    
    if self.flicker_tick > 0:
      self.flicker_tick -= 1

      if self.flicker_tick % 3 == 0:
        return

    if self.left_facing:
      screen.blit(self.img, self.rect)
    else:
      screen.blit(pygame.transform.flip(self.img, True, False), self.rect)

    if Updater.get_escape(self) is not None:
      self.ghost.render(screen)

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
  all_dialog = { (0, 0)    : [
                              ("Narrator", "You are the greatest escape artist. (Press X to continue)"),
                              ("Narrator", "Ever."), 
                              ("Narrator", "At least that's what you think."), 
                              ("Narrator", "Except some jerks trapped you in this big weird looking facility."),
                              ("Narrator", "And you want to escape."),
                              ("Narrator", "You have one special talent though."),
                              ("Narrator", "If the room has a glowing target in it (like this one conveniently does) then you can press ESC and teleport around it."),
                              ("Narrator", "(Z works too. ESC is sometimes inconvenient.)"),
                              ("Narrator", "Try it out. You'll get the gist pretty fast, I bet."),
                              ("Narrator", "By the way: Move around with arrows, jump with X."),
                             ],
                 (2, 0)    : [
                              ("Narrator", "That guy looks annoying."),
                              ("Narrator", "Since you are the greatest escape artist, you don't even want to be seen by him."),
                              ("Narrator", "(His line of sight is indicated by the circles)"),
                             ],
                 (4, 1)    : [
                              ("Narrator", "Aha!"),
                              ("Narrator", "To the right, my sensors are indicating there is..."),
                              ("Narrator", "An ESCAPE!"),
                              ("Narrator", "And also a big scary monster in your way."),
                              ("Narrator", "Well, that stinks"),
                             ],
                 # replicator GET dialog
                 "replicator": [ ("Narrator", "Ooh."),
                                 ("Narrator", "You seem to have found a nice shiny Replicator."),
                                 ("Narrator", "When you escape, you'll now leave a dead body of yourself behind."),
                                 ("Narrator", "This is great for escaping, since enemies will think that you're dead, when really..."),
                                 ("Narrator", "You've escaped!"),
                                 ("Narrator", "Also, you might be able to kill bad guys by dropping your dead bodies on them."),
                                 ("Narrator", "And the mechanics of just having a dead body lying around might be interesting."),
                              ],
                 "escaper": [ ("Narrator", "Shiny!"),
                                 ("Narrator", "You've found the Enemy Escaper!"),
                                 ("Narrator", "Now, you can use enemies the same way as you were using the glowing targets."),
                                 ("Narrator", "You can escape even better!"),
                              ],
                 "treasure": [ ("Narrator", "GOLD!"),
                               ("Narrator", "You found gold!"),
                               ("Narrator", "That's awesome."),
                               ("Narrator", "But it doesn't really seem to do anything."),
                               ("Narrator", "...Except be awesome."),
                              ],
                 "signpost1": [ ("Narrator", "Hmm..."),
                                ("Narrator", "The sign reads: "),
                                ("Narrator", "Right: ESCAPE. Left: Certain death. Down: Even more certain death."),
                              ],
                 "signpost2": [ ("Narrator", "Hmm..."),
                                ("Narrator", "The sign reads: "),
                                ("Narrator", "HAHA! Now you're trapped... FOREVER!"),
                                ("Narrator", "...Great."),
                              ],
                              }
  speaker = ""
  position = 0 # What is the first dialog we haven't seen yet?
  game = None

  @staticmethod
  def begin(game):
    Dialog.game = game

  @staticmethod
  def update(screen):
    if UpKeys.key_up(pygame.K_x):
      if not Dialog.next_dialog():
        return False

    return Dialog.show_dialog(screen)

  # All the True/Falses here are pure paranoia. Pretty sure they do nothing.
  @staticmethod
  def start_dialog(speaker):
    #if DEBUG: return True
    if speaker not in Dialog.all_dialog: return False
    Dialog.speaker = speaker
    Dialog.position = 0
    Dialog.game.state = States.Dialog
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
    my_font = pygame.font.Font("freesansbold.ttf", 10)

    speaker, dialog = Dialog.all_dialog[Dialog.speaker][Dialog.position]

    my_rect = pygame.Rect((60, ABS_MAP_SIZE - 140, 300, 120))
    rendered_text = render_textrect(dialog, my_font, my_rect, (10, 10, 10), (210, 255, 255), True, 0)

    screen.blit(rendered_text, my_rect.topleft)
    return True

def cmp_eps(x, y):
  return abs(x-y) < .00001

class Point:
  def __init__(self, x, y):
    self.x = x
    self.y = y

  def __cmp__(self, other):
    return 0 if self.x == other.x and self.y == other.y else 1

  def __str__(self):
    return "<Point x : %f y : %f>" % (self.x, self.y)

  def is_simple(self):
    if cmp_eps(self.x, 0) and cmp_eps(self.y, 0): return False
    return (cmp_eps(self.x, 0) or cmp_eps(self.x, 1) or cmp_eps(self.x, -1)) and\
           (cmp_eps(self.y, 0) or cmp_eps(self.y, 1) or cmp_eps(self.y, -1))

# When you touch this, you start a dialog.
class DialogStarter:
  def __init__(self, coords, char, dlg_type, map_coords, game_map):
    self.map_coords = tuple(map_coords)
    self.coords = coords
    self.x, self.y = [x * TILE_SIZE for x in coords]
    self.char = char
    self.dlg_type = dlg_type
    self.game_map = game_map

  def depth(self):
    return 0
    
  def update(self):
    if self.char.touching_item(self):
      # destroy ALL dialogs (of this type) on this level, so we don't see this 
      # again.

      # This is obscure.
      self.kill_lambda = lambda x: isinstance(x, DialogStarter) and x.dlg_type == self.dlg_type

      self.new_state = States.Dialog
      self.char.set_death_point(self.game_map)
      Dialog.start_dialog(self.map_coords)
      return True

    return True

  def cacheable(self):
    pass

  def render(self, screen):
    pass

class ParticleGenerator:
  def __init__(self, rate):
    self.rate = rate

  def update(self):
    if random.random() < self.rate:
      Updater.add_updater(Particle((100, 100), 150))

class Particle:
  def __init__(self, coords, lifespan):
    self.coords = coords
    self.x, self.y = coords

    self.max_age = lifespan
    self.sprite = Image("particle.png", 0, 0, self.x, self.y)
    self.age = lifespan * random.random() + 20
    self.speed = random.random() 

    self.base_x = self.x
    self.wobble_factor = random.random() * 10

  def depth(self):
    return 0

  def update(self):
    self.age -= 1
    self.y -= self.speed
    self.x = self.base_x + math.sin(float(self.age / 20)) * self.wobble_factor * float(self.max_age - self.age) / self.max_age

    #TODO: Do something with alpha.

    return self.age > 0

  def render(self, screen):
    self.sprite.move(self.x, self.y)
    self.sprite.render(screen)

class Indicator:
  def __init__(self, char):
    self.char = char
    self.sprite = Image("wall.png", 2, 4, 0, 0)
    self.rotation = 0
  
  def depth(self):
    return 20

  def update(self):
    return True

  def render(self, screen):
    target = Updater.get_escape(self.char)
    if target is not None:
      self.rotation += 2
      self.sprite.move(target.x, target.y)
      self.sprite.render(screen, 2, self.rotation)

class Rotator:
  def __init__(self, coords):
    self.coords = coords
    self.x, self.y = [x * TILE_SIZE for x in coords]

    self.sprite = Image("wall.png", 2, 1, self.x, self.y)
  
  def depth(self):
    return 0

  def escape(self):
    return Point(*self.coords)

  def update(self):
    return True

  # Stored between maps?
  def cacheable(self):
    pass

  def render(self, screen):
    self.sprite.render(screen)

class Pickup:
  def __init__(self, coords, pickup_type, char):
    self.coords = coords
    self.x, self.y = [x * TILE_SIZE for x in coords]
    self.pickup_type = pickup_type
    self.char = char

    if pickup_type == "replicator" or pickup_type == "escaper":
      self.sprite = Image("wall.png", 1, 2, self.x, self.y)

    if pickup_type == "treasure":
      self.sprite = Image("wall.png", 2, 3, self.x, self.y)

    if pickup_type.startswith("signpost"):
      self.sprite = Image("wall.png", 3, 2, self.x, self.y)

  @property
  def x(self):
    return self.rect.x

  @property
  def y(self):
    return self.rect.y

  def depth(self):
    return 0

  def cacheable(self):
    pass

  def update(self):
    if self.char.touching_item(self):
      self.char.get_item(self.pickup_type)
      if not self.pickup_type.startswith("signpost"):
        if not DEBUG:
          get_sound.play()
        return False
      else:
        return True
    else:
      return True

  def render(self, screen):
    self.sprite.render(screen)

# One of your dead bodies.
class Replicated:
  def __init__(self, coords, game_map, char, actually_bomb = False):
    self.actually_bomb = actually_bomb
    self.char = char
    self.coords = coords
    self.game_map = game_map
    self.x, self.y = coords

    self.vy = 0
    if actually_bomb:
      self.sprite = Image("wall.png", 4, 0, self.x, self.y) # zomg itsa bomb
    else:
      self.sprite = Image("wall.png", 2, 2, self.x, self.y) # your dead body

    self.age = 0
    self.visible = True
    self.uid = random.random() # about 80 bits of entropy. We should be fine... I hope
    self.on_ground = False

  def __str__(self):
    return "<Replicator x: %d y: %d>" % (self.x, self.y)

  def depth(self):
    return 20

  def update(self):
    # Hide when old
    self.age += 1
    self.visible = not (self.age > 100 and self.age % 3 == 0)

    # Do downward movement (only! no pushing or vx at all! trying to make my life easier...)
    if self.vy < TILE_SIZE:
      self.vy += 1

    for y in range(self.vy):
      self.y += 1
      if Character.touching_wall(self.x, self.y, self.game_map, self.uid) or generic_touching(self, self.char):
        if generic_touching(self, self.char) and self.actually_bomb:
          self.char.hurt(1, "enemy", self.game_map)
          return False

        self.y -= 1
        self.vy = 0
        if not self.on_ground:
          if not DEBUG:
            land_sound.play()
        self.on_ground = True
        break
      else:
        self.on_ground = False

    enemy_deaths = Updater.get_all(lambda obj: isinstance(obj, Enemy) and generic_touching(self, obj))
    boss_hits = []
    boss_hits = Updater.get_all(lambda obj: isinstance(obj, Boss) and generic_touching(self, obj))


    for enemy in enemy_deaths:
      enemy.damage(1)
      self.age = 150

    #Dumb.
    if self.actually_bomb:
      if len(boss_hits) > 0:
        self.age = 150
    else:
      for boss in boss_hits:
        boss.damage(1)
        self.age = 150

    # finally
    self.sprite.move(self.x, self.y)

    # destroy?
    return self.age < 150

  def render(self, screen):
    if self.visible:
      self.sprite.render(screen)

class Stairs:
  def __init__(self, coords):
    self.coords = coords
    self.x, self.y = [x * TILE_SIZE for x in coords]

    self.sprite = Image("wall.png", 0, 2, self.x, self.y)

  def depth(self):
    return 0

  # STAIRS NEVER DIE.
  def update(self):
    return True

  def cacheable(self):
    pass

  def render(self, screen):
    self.sprite.render(screen)

class Boss:
  def __init__(self, coords, char, game_map, game):
    # Tweakable
    if DEBUG:
      self.health = 2
    else:
      self.health = 4

    self.game = game
    self.game_map = game_map
    self.flicker_ticker = 0
    self.char = char
    self.visible = True
    new_coords = [coords[0] * TILE_SIZE, coords[1] * TILE_SIZE]
    self.x = new_coords[0]
    self.y = new_coords[1]
    
    self.sprite = Image("wall.png", 3, 4, self.x, self.y)

    self.dotime = 300
    self.timeticker = 0
    self.order = 0
    self.orders = [ {'move': Point( 1, 0), 'time': self.dotime}
                  , {'move': Point( 0, 0), 'time': 8, 'special' : 'drop'}
                  , {'move': Point( 0,-5), 'time': 8}
                  , {'move': Point( 0, 5), 'time': 8}
                  , {'move': Point(-1, 0), 'time': self.dotime}
                  , {'move': Point( 0, 0), 'time': 8, 'special' : 'drop'}
                  , {'move': Point( 0,-5), 'time': 8}
                  , {'move': Point( 0, 5), 'time': 8}
                  ]
    self.dropped_places = []

  def damage(self, amt):
    self.health -= amt

    if self.health <= 0:
      self.game.set_state(States.GameOver)

    self.flicker_ticker = 50

  def depth(self):
    return 0

  def cacheable(self):
    pass

  def update(self):
    curr = self.orders[self.order]

    if 'special' in curr and curr['special'] == 'drop':
      new_place = 20 * int(1 + random.random() * 18)
      while new_place in self.dropped_places:
        new_place = 21 * int(1 + random.random() * 17)

      Updater.add_updater(Replicated((new_place, 40), self.game_map, self.char, True))
    else:
      self.dropped_places = []

    self.timeticker += 1

    if generic_boss_touching(self, self.char):
      self.char.hurt(1, "enemy", self.game_map)

    if self.timeticker > self.orders[self.order]['time']:
      self.order = ((self.order + 1) % len(self.orders))
      self.timeticker = 0

    self.x += self.orders[self.order]['move'].x
    self.y += self.orders[self.order]['move'].y

    self.sprite.move(self.x, self.y)

    if self.flicker_ticker > 0:
      self.visible = (self.flicker_ticker % 3 == 0)
      self.flicker_ticker -= 1
    else:
      self.visible = True

    return True

  def render(self, screen):
    self.sprite.move(self.x, self.y)

    if self.visible:
      self.sprite.render(screen, 2)

class Enemy:
  # Example: {move: [1, 0], time: 60}, {move: [-1, 0], time: 60}

  def __init__(self, coords, char, game_map, reverse=False):
    # Tweakable
    self.health = 1
    self.speed = 3
    self.los_dist = 3 # line of sight range
    self.turnaround_time = 20 # (TODO) Ignoring this for now, see update

    # Not tweakable
    self.game_map = game_map
    self.flicker_ticker = None
    self.char = char
    self.visible = True

    self.orders = [ {'move': Point(-1, 0), 'time': 60}
                  , {'move': Point( 1, 0), 'time': 60}
                  ]

    if reverse:
      self.which_order = 1
    else:
      self.which_order = 0

    self.move_dir = Point(-1, 0) #self.orders[self.which_order]['move']
    new_coords = [coords[0] * TILE_SIZE, coords[1] * TILE_SIZE]

    self.sprite = Image("wall.png", 0, 1, *new_coords)
    self.los = [Image("wall.png", 3, 1, *(0, 0)) for x in range(self.los_dist)]
    self.ticks = 0

    # Could have many destinations

    self.x = new_coords[0]
    self.y = new_coords[1]

  def damage(self, amount):
    self.health -= amount

  # Stored between maps?
  def cacheable(self):
    pass

  def depth(self):
    return 0

  def escape(self):
    if self.char.has_escaper():
      return Point(self.x, self.y)
    return False

  def update(self):
    rotating = False

    if self.health <= 0 and self.flicker_ticker == None:
      self.flicker_ticker = 50

    if self.flicker_ticker != None:
      self.visible = (self.flicker_ticker % 3 == 0)
      return self.flicker_ticker > 0

    # TODO: Include this object too, not just its sight range
    for eyesight in (self.los + [self]):
      if self.char.touching_item(eyesight):
        if self.char.hurt(1, "enemy", self.game_map):
          return True

        Updater.add_updater(HoverText("Intruder!", self, 0))

    # Is it all whole numbers
    if self.move_dir.is_simple():
      self.x += self.move_dir.x
      self.y += self.move_dir.y
      self.ticks += 1

      if self.ticks > self.orders[self.which_order]['time']: 
        # Advance to next order
        self.which_order = (self.which_order + 1) % len(self.orders)
        rotating = True
        self.ticks = 0

    if not self.move_dir.is_simple() or rotating:
      goal = self.orders[self.which_order]['move']
      self.move_dir.x += sign(goal.x - self.move_dir.x) * float(.1)
      self.move_dir.y += sign(goal.y - self.move_dir.y) * float(.1)

    self.sprite.move(self.x, self.y)
    return True

  def render(self, screen):
    if self.visible:
      self.sprite.render(screen)

      hide_rest = False
      for l_dist in range(1, self.los_dist + 1): #+ 1 so that we don't overlap with self
        self.los[l_dist - 1].move(self.x + TILE_SIZE * l_dist * self.move_dir.x, self.y + TILE_SIZE * l_dist * self.move_dir.y)

        if Character.touching_wall(self.los[l_dist - 1].x, self.los[l_dist - 1].y, self.game_map):
          hide_rest = True

        if hide_rest:
          self.los[l_dist - 1].move(-500,-500)

        self.los[l_dist - 1].render(screen)

class HoverText:
  # follow must expose x, y (could generalize to enemies etc)
  def __init__(self, text, follow, depth=0):
    self.text = text
    self.follow = follow
    self._depth = depth
    self.lifespan = len(text) * 2

  def depth(self):
    return self._depth

  def update(self):
    self.lifespan -= 1
    return self.lifespan > 0

  def render(self, screen):
    my_width = 100

    my_font = pygame.font.Font("freesansbold.ttf", 10)

    my_rect = pygame.Rect((self.follow.x - my_width / 2, self.follow.y - len(self.text) - 30, my_width, 70))
    if my_rect.x < 0:
      my_rect.x = 0
    rendered_text = render_textrect(self.text, my_font, my_rect, (10, 10, 10), (255, 255, 255), False, 1)

    screen.blit(rendered_text, my_rect.topleft)

class HUD:
  def __init__(self, follow):
    self._depth = 20
    self.hearts = []
    self.treasures = []
    self.follow = follow

    for x in range(3):
      self.hearts.append(Image("wall.png", 2, 0, 20 + x * 20, 20))
      
  def depth(self):
    return self._depth

  def update(self):
    while len(self.treasures) < self.follow.gold:
      self.treasures.append(Image("wall.png", 2, 3, 20 + len(self.treasures) * 20, 40))

    for x in range(len(self.hearts)):
      if self.follow.health > x:
        self.hearts[x].update("wall.png", 2, 0)
      else:
        self.hearts[x].update("wall.png", 3, 0)

    return True # never destroy

  def render(self, screen):
    [heart.render(screen) for heart in self.hearts]
    [treasure.render(screen) for treasure in self.treasures]

class Updater:
  # Update each item every step (until it kills itself)

  # Must expose 3 mthods
  # depth(): returns relative depth or 0 if it doesn't matter
  # update(): returns False if destroyed, True otherwise
  # render(screen): renders the object
  items = [] # Things that need to be updated every step
  KillAll = "killall"

  @staticmethod
  def add_updater(updater):
    Updater.items.append(updater)

  @staticmethod
  def update_all():
    Updater.items = [item for item in Updater.items if item.update()]

    # This is a really hard problem. Think about it after LD.
    kills = []
    for item in Updater.items:
      if hasattr(item, 'kill_lambda'):
        kills.append(item.kill_lambda)

    for kill_lambda in kills:
      Updater.items = [item for item in Updater.items if not kill_lambda(item)]

  @staticmethod
  def render_all(screen):
    # sort by depth
    items_sorted = sorted(Updater.items, key=lambda x:x.depth())

    for item in items_sorted:
      item.render(screen)

  @staticmethod
  def get_escape(char):
    targets = []

    for item in Updater.items:
      if hasattr(item, 'escape'):
        if item.escape():
          targets.append(item)
    
    if len(targets) == 0: return None

    # Take first closest one.
    return sorted(targets, key=lambda obj: math.sqrt( (obj.x - char.x) ** 2 + (obj.y - char.y) ** 2))[0]


  @staticmethod
  def remove_all(fn):
    Updater.items = [item for item in Updater.items if not fn(item)]

  @staticmethod
  def get_all(fn):
    return [item for item in Updater.items if fn(item)]

class States:
  Dialog = "Dialog"
  Normal = "Normal"
  Blurry = "Blurry"
  Death = "Death"
  GameOver = "GameOver"

class Game:
  def __init__(self):
    self.keys_up = []

    pygame.display.init()
    pygame.font.init()
    pygame.font.init()

    if not DEBUG:
      pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=1024)
      pygame.mixer.music.load('ludumherp.mp3')
      pygame.mixer.music.play(-1) #Infinite loop! HAHAH!

      global land_sound
      land_sound = pygame.mixer.Sound("land.wav")

      global escape_sound
      escape_sound = pygame.mixer.Sound("escape.wav")

      global get_sound
      get_sound = pygame.mixer.Sound("getstuff.wav")

    self.screen = pygame.display.set_mode((ABS_MAP_SIZE * 2, ABS_MAP_SIZE * 2))
    self.buff = pygame.Surface((ABS_MAP_SIZE, ABS_MAP_SIZE))


    global background
    background = BigImage("background.png", 2)
    TileSheet.add("wall.png")
    TileSheet.add("particle.png")

    if DEBUG:
      self.char = Character(120, 38)
    else:
      self.char = Character(40, 40)

    Dialog.begin(self)

    if DEBUG:
      self.map = Map("map.png", [2, 3], self.char, self)
      self.state = States.Normal
    else:
      self.map = Map("map.png", [0, 0], self.char, self)
      self.state = States.Dialog
      Dialog.start_dialog((0, 0))

    self.char.set_death_point(self.map)

    # self.partgen = ParticleGenerator(.4)
    Updater.add_updater(HUD(self.char))

    # Add indicator
    Updater.add_updater(Indicator(self.char))

  def set_state(self, state):
    if state == States.Blurry:
      self.blurriness = 1
      self.dblurry = 2

    if state == States.Death:
      self.death = 230
      self.ddeath = 10

    if state == States.GameOver:
      self.finished_time = time.time()

    self.state = state

  def loop(self):
    # self.set_state(States.GameOver)

    while 1:
      for event in pygame.event.get():
        if event.type == pygame.QUIT: 
          pygame.display.quit()
          exit(0)
        if event.type == pygame.KEYUP:
          UpKeys.add_key(event.key)

      global background
      background.render(self.buff)
      self.map.render(self.buff)

      global GAME_SIZE
      if UpKeys.key_up(pygame.K_s):
        if GAME_SIZE == 2:
          GAME_SIZE = 1
        else: 
          GAME_SIZE = 2

      if self.state == States.Dialog:
        Updater.render_all(self.buff)
        self.char.render(self.buff)
        if not Dialog.update(self.buff):
          self.state = States.Normal
      elif self.state == States.Normal:
        # self.partgen.update()
        Updater.update_all()
        Updater.render_all(self.buff)
        self.char.render(self.buff)
        self.char.update(pygame.key.get_pressed(), self.map, self)
      elif self.state == States.Blurry:
        Updater.render_all(self.buff)
        self.char.render(self.buff)

        self.buff = blur_surf(self.buff, self.blurriness)
        self.blurriness += self.dblurry
        if self.blurriness >= 10:
          self.dblurry *= -1
        if self.blurriness <= 0:
          self.dblurry = 0
          self.set_state(States.Normal)
      elif self.state == States.Death:
        Updater.render_all(self.buff)
        self.char.render(self.buff)

        blackness = pygame.Surface((ABS_MAP_SIZE * 2, ABS_MAP_SIZE * 2))
        blackness.set_alpha(self.death)
        self.buff.blit(blackness, blackness.get_rect())

        self.death += self.ddeath
        if self.death >= 240:
          self.ddeath *= -1
        if self.death <= 0:
          self.ddeath = 0
          self.set_state(States.Normal)
      elif self.state == States.GameOver:

        my_font = pygame.font.Font("freesansbold.ttf", 10)
        elapsed = "%d minutes, %d seconds." % (int((self.finished_time - START_TIME)/60), int(self.finished_time - START_TIME) % 60)
        gameover = """
        Hooray! You win!

        Afterwards:

        Even though you beat their boss, killed all their personel, and stole their gold, MegaCorp has come to the conclusion that you must be dead, because they found thousands of your dead bodies littering their dungeons. 

        Not a bad way for things to end up.

        elapsed time: %s

        deaths: %d

        percentage complete (gold): %d%%""" % (elapsed, DEATH_COUNT, int(100 * self.char.gold / 7))

        my_rect = self.buff.get_rect()
        self.buff = render_textrect(gameover, my_font, my_rect, (10, 10, 10), (210, 255, 255), True, 0)

      blackness2 = pygame.Surface((ABS_MAP_SIZE * 2, ABS_MAP_SIZE * 2))
      blackness2.set_alpha(255)
      self.screen.blit(blackness2, blackness2.get_rect())


      self.screen.blit(pygame.transform.scale(self.buff, (ABS_MAP_SIZE * GAME_SIZE, ABS_MAP_SIZE * GAME_SIZE)), self.buff.get_rect())
      UpKeys.flush()
      time.sleep(.02)
      pygame.display.flip()

g = Game()
g.loop()
