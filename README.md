# AuGratin

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)  [![Python: 3.8+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)  [![Made With:PyQt5](https://img.shields.io/badge/Made%20with-PyQt5-red)](https://pypi.org/project/PyQt5/)
![PyPI - Downloads](https://img.shields.io/pypi/dm/augratin)

![logo](https://github.com/mbridak/augratin/raw/master/augratin/data/k6gte.augratin.svg)

- [AuGratin](#augratin)
  - [Why AuGratin](#why-augratin)
  - [What is AuGratin](#what-is-augratin)
  - [Recent changes](#recent-changes)
  - [Installing AuGratin](#installing-augratin)
  - [Features](#features)
  - [What to do if your map is blank](#what-to-do-if-your-map-is-blank)
  - [CAT control](#cat-control)

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

- [23-3-7] Reduced network timeout for spot pulls from 15 to 5 seconds. Safer dictionary key access.
- [23-2-17] Repackaged for PyPi and pip install

## Installing AuGratin

```bash
pip install augratin
```

## Features

- You can filter spots by band and or mode.
- Pulls in park and activator information.
- Tunes your radio with flrig or rigctld to the activator and sets the mode automatically.
- Double clicked spots adds Activator to a persistent watchlist.
- Displays bearing to contact.

When you press the "Log it" button the adif information is appended to `POTA_Contacts.adi` in your home folder.

## What to do if your map is blank

Not sure why, but the map may not work if you let pip install PyQt5 and PyQtWebEngine automatically. If your map is blank, try:

```bash
pip uninstall PyQt5
Pip uninstall PyQtWebEngine
```

Then install them through your package manager.

```bash
#fedora
sudo dnf install python3-qt5 python3-qt5-webengine

#ubuntu
sudo apt install python3-pyqt5 python3-pyqt5.qtwebengine
```

## CAT control

If no command line options are given, the program will check if either flrig
or rigctld are running on the computer. It will setup CAT control to which
ever it finds first.

You can force it to use either with commandline options.

`-r` will force rigctld with default host:port of localhost:4532.

`-f` will force flrig with default host:port of localhost:12345.

`-s SERVER:PORT` will specify a non-standard host and port.
