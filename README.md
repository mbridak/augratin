# AuGratin

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)  [![Python: 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)  [![Made With:PyQt5](https://img.shields.io/badge/Made%20with-PyQt5-red)](https://pypi.org/project/PyQt5/)

Allows A POTA chaser to easily log contacts. Pulls latest POTA spots. Displays them in a compact interface. You can filter output to band and or mode. When you click on a spot, the needed information about the Activator and the park are populated on screen. If you have an instance of `flrig` running, your radio will automatically tune to the spotted frequency and change modes to match the spot. If you double click on a spot(s), spots from that activator will be highlighted green. You can use this keep track of who you have worked. Activators can be toggled off again by double clicking the activator a second time. 

When you press the "Log it" button the adif information is appended to `POTA_Contacts.adi` in your home folder.

## Early days

This is the initial comit. Very early days.

If you wish to play with it start by changing a line in the sourcecode.

```    
def __init__(self, parent=None):
        """Initialize class variables"""
        self.settings = {
            "mycall": "K6GTE",
            "mygrid": "Dm13at",
            }
```

Put in your callsign and grid. This will get changed pretty darn soon to a local json file in your main directory. But 'till then... 


## Running from source

First install the requirements.

`python3 -m pip3 install -r requirements.txt`

Or if you're the Ubuntu/Debian type you can:

`sudo apt install python3-pyqt5 python3-requests python3-psutil`

Then, run the program from source.

`python3 augratin.py`

![screenshot](pic/screenshot.png)

## Building a binary executable

I've included a .spec file in case you wished to create your own binary from the source. To use it, first install pyinstaller.

`python3 -m pip3 install pyinstaller`

Then build the binary.

`pyinstaller --clean linux.spec`

Look in the newly created dist directory to find your binary.

Or execute the install.sh shell script in the install_icon folder to copy the binary from the dist directory to your ~/.local/bin folder and install a launcher icon.
 