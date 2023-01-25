# AuGratin

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)  [![Python: 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)  [![Made With:PyQt5](https://img.shields.io/badge/Made%20with-PyQt5-red)](https://pypi.org/project/PyQt5/)

## Why AuGratin

AuGratin is an extension to an earlier program called POTAto. And since it's made from POTAto, I called it AuGratin.

## What is AuGratin

To answer this you must know what [POTA](https://parksontheair.com) is.
[POTA](https://parksontheair.com) is Parks On The Air.
A year round activity of many amateur radio operators or HAMS.
The Activator, will set up a radio station in a state/national park and make as many contacts as they can.
Other Radio Amateurs also known as Hunters or Chasers, will seek out and try to contact as many Activators as they can.

AuGratin allows A [POTA](https://parksontheair.com) Hunter to easily log contacts with Activators.
It pulls latest [POTA](https://parksontheair.com) spots. Displays them in a compact interface.
Once a spot is clicked on AuGratin will talk to either rigctld or flrig to change the radio to the correct
frequency and mode. It will pre-populate All the fields needed for logging the contact.
All contacts are stored in an ADIF file in your home directory,
which you can them import into your normal logging program.

![screenshot](https://github.com/mbridak/augratin/raw/master/pic/screenshot.png)

## Recent changes

- Changed map to dark mode.
- Made window resizable.
- You can use either flrig or rigctld for CAT control.
- Changed backend from QtWebKit to QtWebEngine for the map display.

## Features

- You can filter spots by band and or mode.
- Pulls in park and activator information.
- Tunes your radio with flrig to the activator and sets the mode automatically.
- Double clicked spots adds Activator to a persistent watchlist.
- Displays bearing to contact.

When you press the "Log it" button the adif information is appended to `POTA_Contacts.adi` in your home folder.

## Running from source

First install the requirements.

`python3 -m pip3 install -r requirements.txt`

Or if you're the Ubuntu/Debian type you can:

`sudo apt install python3-pyqt5 python3-pyqt5.qtwebengine python3-requests python3-psutil python3-folium`

If using a Raspberry PI, you probably need `python3-qtpy`

Then, run the program from source.

`python3 augratin.py`

## Building a binary executable

I've included a .spec file in case you wished to create your own binary from the source. To use it, first install pyinstaller.

`python3 -m pip3 install pyinstaller`

Then build the binary.

`pyinstaller --clean linux.spec`

Look in the newly created dist directory to find your binary.

Or execute the install.sh shell script in the install_icon folder to copy the binary from the dist directory to your ~/.local/bin folder and install a launcher icon.

## CAT control

If no command line options are given, the program will check if either flrig
or rigctld are running on the computer. It will setup CAT control to which
ever it finds first.

You can force it to use either with commandline options.

`-r` will force rigctld with default host:port of localhost:4532.

`-f` will force flrig with default host:port of localhost:12345.

`-s SERVER:PORT` will specify a non-standard host and port.
