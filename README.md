Escape Artist
====================

Installation instructions.

Windows
-----------------

Hopefully coming in the next 10 hours.

Mac OSX
-----------------

**Installable package**

Hopefully coming in the next 10 hours.

**From source**

Install macports if you don't already have it: http://www.macports.org/

Download Escape Artist from here: https://github.com/johnfn/ld21/archives/master and extract it in Downloads.

Open Terminal (dock -> Applications -> Utilities -> Terminal)

Go to where you extracted my game. `cd ~/Downloads/ld21/`

Install python via macports: `sudo port install python26`. Type in the command it says at the end to set it as your default python installation.

Install pygame: `sudo port install py26-game`

Run: `python26 main.py`

Ubuntu
-----------------

**Installable package**

Hopefully coming in the next 10 hours.

**From source**

Hop in a terminal and type in the following.

*Get git:* (If you don't have it)

`$ sudo apt-get install git`

*Get the game and its dependencies*

`$ git clone git@github.com:johnfn/ld21.git`

`$ sudo apt-get install python`

`$ sudo apt-get install python-pygame`

*Play!*

`$ cd ld21`

`$ python main.py`
