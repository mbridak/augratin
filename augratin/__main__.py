#!/usr/bin/env python3
"""AuGratin helps chasers hunt POTA activators. Find out more about POTA at https://pota.app"""

# pylint: disable=no-name-in-module
# pylint: disable=c-extension-no-member
# pylint: disable=wildcard-import
# pylint: disable=line-too-long

# https://api.pota.app/park/K-0064
# {"parkId": 64, "reference": "K-0064", "name": "Shenandoah", "latitude": 38.9068, "longitude": -78.1988, "grid4": "FM08", "grid6": "FM08vv", "parktypeId": 41, "active": 1, "parkComments": "Potentially co-located with K-4556 - Appalachian Trail NST.  Numerous SOTA locations.", "accessibility": null, "sensitivity": null, "accessMethods": "Automobile,Foot", "activationMethods": "Automobile,Cabin,Campground,Pedestrian,Shelter", "agencies": "National Park Service", "agencyURLs": "https://www.nps.gov/index.htm", "parkURLs": "https://www.nps.gov/shen/index.htm", "website": "https://www.nps.gov/shen/index.htm", "createdByAdmin": null, "parktypeDesc": "National Park", "locationDesc": "US-VA", "locationName": "Virginia", "entityId": 291, "entityName": "United States Of America", "referencePrefix": "K", "entityDeleted": 0, "firstActivator": "WX4TW", "firstActivationDate": "2015-08-27"}

# https://api.pota.app/stats/user/K2EAG
# {"callsign": "K2EAG", "name": "Matt Brown", "qth": "Amherst, New York", "gravatar": "bf8377378b67b265cbb2be687b13a23a", "activator": {"activations": 72, "parks": 33, "qsos": 3724}, "attempts": {"activations": 80, "parks": 33, "qsos": 3724}, "hunter": {"parks": 237, "qsos": 334}, "awards": 16, "endorsements": 32}

import argparse
import sys
import os
import io
import logging
from math import radians, sin, cos, atan2, sqrt, asin, pi
import pkgutil
from pathlib import Path
from datetime import datetime, timezone
from json import loads, dumps
import re

import psutil
from PyQt5 import QtCore, QtWidgets, uic
from PyQt5.QtCore import QDir
from PyQt5.QtGui import QFontDatabase, QBrush, QColor
import PyQt5.QtWebEngineWidgets  # pylint: disable=unused-import

# from PyQt5.QtWebEngineWidgets import QWebEngineView


import requests
import folium

try:
    from augratin.lib.version import __version__
    from augratin.lib.cat_interface import CAT
except ModuleNotFoundError:
    from lib.version import __version__
    from lib.cat_interface import CAT

__author__ = "Michael C. Bridak, K6GTE"
__license__ = "GNU General Public License v3.0"

loader = pkgutil.get_loader("augratin")
WORKING_PATH = os.path.dirname(loader.get_filename())

logger = logging.getLogger("__name__")
handler = logging.StreamHandler()
formatter = logging.Formatter(
    datefmt="%H:%M:%S",
    fmt="[%(asctime)s] %(levelname)s %(module)s - %(funcName)s Line %(lineno)d:\n%(message)s",
)
handler.setFormatter(formatter)
logger.addHandler(handler)

parser = argparse.ArgumentParser(
    description=(
        "augratin helps chasers hunt POTA activators. "
        "Find out more about POTA at https://parksontheair.com"
    )
)
parser.add_argument(
    "-s",
    "--server",
    type=str,
    help="Force a server and port address. --server localhost:12345",
)

parser.add_argument(
    "-r",
    action=argparse.BooleanOptionalAction,
    dest="rigctld",
    help="Force use of rigctld",
)

parser.add_argument(
    "-f",
    action=argparse.BooleanOptionalAction,
    dest="flrig",
    help="Force use of flrig",
)

parser.add_argument(
    "-d",
    action=argparse.BooleanOptionalAction,
    dest="debug",
    help="Debug",
)

args = parser.parse_args()

FORCED_INTERFACE = None
SERVER_ADDRESS = None

if args.rigctld:
    FORCED_INTERFACE = "rigctld"
    SERVER_ADDRESS = "localhost:4532"

if args.flrig:
    FORCED_INTERFACE = "flrig"
    SERVER_ADDRESS = "localhost:12345"

if args.server:
    SERVER_ADDRESS = args.server

if args.debug:
    logger.setLevel(logging.DEBUG)

logger.debug("Forces Interface: %s", FORCED_INTERFACE)
logger.debug("Server Address: %s", SERVER_ADDRESS)


def load_fonts_from_dir(directory):
    """loads in font families"""
    font_families = set()
    for file_index in QDir(directory).entryInfoList(["*.ttf", "*.woff", "*.woff2"]):
        _id = QFontDatabase.addApplicationFont(file_index.absoluteFilePath())
        font_families |= set(QFontDatabase.applicationFontFamilies(_id))
    return font_families


class MainWindow(QtWidgets.QMainWindow):
    """The main window class"""

    potaurl = "https://api.pota.app/spot/activator"
    parkurl = "https://api.pota.app/park/"
    activatorurl = "https://api.pota.app/stats/user/"
    bw = {}
    lastclicked = ""
    workedlist = []
    spots = None
    map = None
    loggable = False
    MAP_TILES = "OpenStreetMap"

    def __init__(self, parent=None):
        """Initialize class variables"""
        self.settings = {
            "mycall": "",
            "mygrid": "",
        }
        try:
            home = os.path.expanduser("~")
            if os.path.exists(f"{home}/.augratin.json"):
                with open(
                    f"{home}/.augratin.json", "rt", encoding="utf-8"
                ) as file_descriptor:
                    self.settings = loads(file_descriptor.read())
                    logger.debug("reading: %s", self.settings)
            else:
                with open(
                    f"{home}/.augratin.json", "wt", encoding="utf-8"
                ) as file_descriptor:
                    file_descriptor.write(dumps(self.settings, indent=4))
                    logger.debug("writing: %s", self.settings)
            if os.path.exists(f"{home}/.augratin_watched.json"):
                with open(
                    f"{home}/.augratin_watched.json", "rt", encoding="utf-8"
                ) as file_descriptor:
                    self.workedlist = loads(file_descriptor.read())
                    logger.debug("reading workedlist: %s", self.settings)
        except IOError as exception:
            logger.critical("%s", exception)

        self.cat_control = None
        local_flrig = self.check_process("flrig")
        local_rigctld = self.check_process("rigctld")

        if FORCED_INTERFACE:
            address, port = SERVER_ADDRESS.split(":")
            self.cat_control = CAT(FORCED_INTERFACE, address, int(port))

        if self.cat_control is None:
            if local_flrig:
                if SERVER_ADDRESS:
                    address, port = SERVER_ADDRESS.split(":")
                else:
                    address, port = "localhost", "12345"
                self.cat_control = CAT("flrig", address, int(port))
            if local_rigctld:
                if SERVER_ADDRESS:
                    address, port = SERVER_ADDRESS.split(":")
                else:
                    address, port = "localhost", "4532"
                self.cat_control = CAT("rigctld", address, int(port))

        super().__init__(parent)
        data_path = WORKING_PATH + "/data/dialog.ui"
        uic.loadUi(data_path, self)
        self.listWidget.clicked.connect(self.spotclicked)
        self.listWidget.doubleClicked.connect(self.item_double_clicked)
        self.comboBox_mode.currentTextChanged.connect(self.getspots)
        self.comboBox_band.currentTextChanged.connect(self.getspots)
        self.mycall_field.textEdited.connect(self.save_call_and_grid)
        self.mygrid_field.textEdited.connect(self.save_call_and_grid)
        self.log_button.clicked.connect(self.log_contact)
        self.mycall_field.setText(self.settings.get("mycall", ""))
        self.mygrid_field.setText(self.settings.get("mygrid", ""))
        if self.settings.get("mygrid", "") == "":
            self.mygrid_field.setStyleSheet("border: 1px solid red;")
            self.mygrid_field.setFocus()
        if self.settings.get("mycall", "") == "":
            self.mycall_field.setStyleSheet("border: 1px solid red;")
            self.mycall_field.setFocus()
        # start map centered on US.
        self.map = folium.Map(
            location=["39.8", "-98.5"],
            tiles=self.MAP_TILES,
            zoom_start=3,
            max_zoom=19,
        )
        data = io.BytesIO()
        self.map.save(data, close_file=False)
        self.mapview.setHtml(data.getvalue().decode())

    def save_call_and_grid(self):
        """Saves users callsign and gridsquare to json file."""
        self.settings["mycall"] = self.mycall_field.text().upper()
        self.settings["mygrid"] = self.mygrid_field.text().upper()
        try:
            home = os.path.expanduser("~")
            with open(
                f"{home}/.augratin.json", "wt", encoding="utf-8"
            ) as file_descriptor:
                file_descriptor.write(dumps(self.settings, indent=4))
                logger.info("writing: %s", self.settings)
        except IOError as exception:
            logger.critical("%s", exception)

    @staticmethod
    def getjson(url):
        """Get json request"""
        try:
            request = requests.get(url, timeout=5.0)
            request.raise_for_status()
        except requests.ConnectionError as err:
            logger.debug("Network Error: %s", err)
            return None
        except requests.exceptions.Timeout as err:
            logger.debug("Timeout Error: %s", err)
            return None
        except requests.exceptions.HTTPError as err:
            logger.debug("HTTP Error: %s", err)
            return None
        except requests.exceptions.RequestException as err:
            logger.debug("Error: %s", err)
            return None
        return loads(request.text)

    @staticmethod
    def gridtolatlon(maiden):
        """
        Converts a maidenhead gridsquare to a latitude longitude pair.
        """
        maiden = str(maiden).strip().upper()

        length = len(maiden)
        if not 8 >= length >= 2 and length % 2 == 0:
            return 0, 0

        lon = (ord(maiden[0]) - 65) * 20 - 180
        lat = (ord(maiden[1]) - 65) * 10 - 90

        if length >= 4:
            lon += (ord(maiden[2]) - 48) * 2
            lat += ord(maiden[3]) - 48

        if length >= 6:
            lon += (ord(maiden[4]) - 65) / 12 + 1 / 24
            lat += (ord(maiden[5]) - 65) / 24 + 1 / 48

        if length >= 8:
            lon += (ord(maiden[6])) * 5.0 / 600
            lat += (ord(maiden[7])) * 2.5 / 600

        return lat, lon

    def distance(self, grid1: str, grid2: str) -> float:
        """
        Takes two maidenhead gridsquares and returns the distance between the two in kilometers.
        """
        lat1, lon1 = self.gridtolatlon(grid1)
        lat2, lon2 = self.gridtolatlon(grid2)
        return round(self.haversine(lon1, lat1, lon2, lat2))

    def bearing(self, grid1: str, grid2: str) -> float:
        """calculate bearing to contact"""
        lat1, lon1 = self.gridtolatlon(grid1)
        lat2, lon2 = self.gridtolatlon(grid2)
        lat1 = radians(lat1)
        lon1 = radians(lon1)
        lat2 = radians(lat2)
        lon2 = radians(lon2)
        londelta = lon2 - lon1
        why = sin(londelta) * cos(lat2)
        exs = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(londelta)
        brng = atan2(why, exs)
        brng *= 180 / pi

        if brng < 0:
            brng += 360

        return round(brng)

    @staticmethod
    def haversine(lon1, lat1, lon2, lat2):
        """
        Calculate the great circle distance in kilometers between two points
        on the earth (specified in decimal degrees)
        """
        # convert degrees to radians
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

        # haversine formula
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        aye = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        cee = 2 * asin(sqrt(aye))
        arrgh = 6372.8  # Radius of earth in kilometers.
        return cee * arrgh

    def potasort(self, element):
        """Sort list or dictionary items"""
        return element["spotId"]

    def getspots(self):
        """Gets activator spots from pota.app"""
        self.time.setText(str(datetime.now(timezone.utc)).split()[1].split(".")[0][0:5])
        self.spots = self.getjson(self.potaurl)
        if self.spots:
            self.spots.sort(reverse=True, key=self.potasort)
            self.showspots()

    def log_contact(self):
        """Log the contact"""
        if self.loggable is False:
            return
        try:
            freq = str(int(self.freq_field.text()) / 1000000)
        except ValueError:
            freq = "0"
            logger.debug("Invalid Frequency")
        qso = (
            f"<BAND:{len(self.band_field.text())}>{self.band_field.text()}\n"
            f"<CALL:{len(self.activator_call.text())}>{self.activator_call.text()}\n"
            f"<COMMENT:{len(self.comments.document().toPlainText())}>{self.comments.document().toPlainText()}\n"
            "<SIG:4>POTA\n"
            f"<SIG_INFO:{len(self.park_designator.text())}>{self.park_designator.text()}\n"
            f"<DISTANCE:{len(self.park_distance.text())}>{self.park_distance.text()}\n"
            f"<GRIDSQUARE:{len(self.park_grid.text())}>{self.park_grid.text()}\n"
            f"<MODE:{len(self.mode_field.text())}>{self.mode_field.text()}\n"
            f"<NAME:{len(self.activator_name.text())}>{self.activator_name.text()}\n"
            f"<OPERATOR:{len(self.mycall_field.text())}>{self.mycall_field.text()}\n"
            f"<RST_RCVD:{len(self.rst_recieved.text())}>{self.rst_recieved.text()}\n"
            f"<RST_SENT:{len(self.rst_sent.text())}>{self.rst_sent.text()}\n"
            f"<STATE:{len(self.park_state.text())}>{self.park_state.text()}\n"
            f"<FREQ:{len(freq)}>{freq}\n"
            f"<QSO_DATE:{len(self.date_field.text())}>{self.date_field.text()}\n"
            f"<TIME_ON:{len(self.time_field.text())}>{self.time_field.text()}\n"
            f"<MY_GRIDSQUARE:{len(self.mygrid_field.text())}>{self.mygrid_field.text()}\n"
            "<EOR>\n"
        )
        logger.debug("QSO: %s", qso)
        home = os.path.expanduser("~")
        if not Path(home + "/POTA_Contacts.adi").exists():
            with open(
                home + "/POTA_Contacts.adi", "w", encoding="utf-8"
            ) as file_descriptor:
                header = (
                    "augratin POTA logger\n"
                    "<ADIF_VER:5>3.1.2\n"
                    "<PROGRAMID:8>AuGratin\n"
                    "<PROGRAMVERSION:14>Version 22.3.7\n"
                    "<EOH>\n"
                )
                print(header, file=file_descriptor)
        with open(
            home + "/POTA_Contacts.adi", "a", encoding="utf-8"
        ) as file_descriptor:
            print(qso, file=file_descriptor)
        self.clear_fields()
        self.loggable = False

    def showspots(self):
        """Display spots in a list"""
        self.listWidget.clear()
        for i in self.spots:
            mode_selection = self.comboBox_mode.currentText()
            if mode_selection == "-FT*" and i["mode"][:2] == "FT":
                continue
            if (
                mode_selection == "All"
                or mode_selection == "-FT*"
                or i["mode"] == mode_selection
            ):
                band_selection = self.comboBox_band.currentText()
                if (
                    band_selection == "All"
                    or self.getband(i["frequency"].split(".")[0]) == band_selection
                ):
                    spot = (
                        f"{i['spotTime'].split('T')[1][0:5]} "
                        f"{i['activator'].rjust(10)} "
                        f"{i['reference'].ljust(7)} "
                        f"{i['frequency'].split('.')[0].rjust(6)} "
                        f"{i['mode']}"
                    )

                    self.listWidget.addItem(spot)
                    if spot[5:] == self.lastclicked[5:]:
                        founditem = self.listWidget.findItems(
                            spot[5:],
                            QtCore.Qt.MatchFlag.MatchContains,  # pylint: disable=no-member
                        )
                        founditem[0].setSelected(True)
                    if i["activator"] in self.workedlist:
                        founditem = self.listWidget.findItems(
                            i["activator"],
                            QtCore.Qt.MatchFlag.MatchContains,  # pylint: disable=no-member
                        )
                        founditem[0].setBackground(QBrush(QColor.fromRgb(0, 128, 0)))

    def clear_fields(self):
        """Clear input fields and reset focus to RST TX."""
        self.activator_call.setText("")
        self.activator_name.setText("")
        self.park_designator.setText("")
        self.mode_field.setText("")
        self.rst_sent.setText("")
        self.rst_recieved.setText("")
        self.freq_field.setText("")
        self.band_field.setText("")
        self.park_name.setText("")
        self.park_state.setText("")
        self.park_grid.setText("")
        self.park_section.setText("")
        self.comments.setPlainText("")
        self.park_distance.setText("")
        self.park_direction.setText("")
        self.rst_sent.setFocus()

    def spotclicked(self):
        """
        If flrig/rigctld is running on this PC, tell it to tune to the spot freq and change mode.
        Otherwise die gracefully.
        """

        try:
            self.loggable = True
            dateandtime = datetime.utcnow().isoformat(" ")[:19]
            self.time_field.setText(dateandtime.split(" ")[1].replace(":", ""))
            the_date_fields = dateandtime.split(" ")[0].split("-")
            the_date = f"{the_date_fields[0]}{the_date_fields[1]}{the_date_fields[2]}"
            self.date_field.setText(the_date)
            item = self.listWidget.currentItem()
            line = item.text().split()
            self.lastclicked = item.text()
            self.activator_call.setText(line[1])

            if "/" in line[1]:
                basecall = max(line[1].split("/")[0], line[1].split("/")[1], key=len)
            else:
                basecall = line[1]

            activator = self.getjson(f"{self.activatorurl}{basecall}")

            if activator:
                self.activator_name.setText(activator["name"])
            else:
                self.activator_name.setText("")
            self.park_designator.setText(line[2])
            try:
                self.mode_field.setText(line[4])
                if line[4] == "CW":
                    self.rst_sent.setText("599")
                    self.rst_recieved.setText("599")
                else:
                    self.rst_sent.setText("59")
                    self.rst_recieved.setText("59")
            except IndexError:
                self.mode_field.setText("")
            self.freq_field.setText(f"{line[3]}000")
            self.band_field.setText(f"{self.getband(line[3])}M")
            park_info = self.getjson(f"{self.parkurl}{line[2]}")
            if park_info:
                self.park_name.setText(park_info["name"])
                self.park_state.setText(park_info["locationName"])
                self.park_grid.setText(park_info["grid6"])
                self.park_section.setText(park_info["locationDesc"])
                self.comments.setPlainText(
                    f"POTA: {line[2]} {park_info['name']}, {park_info['locationName']}"
                )
                mygrid = self.mygrid_field.text()
                if len(mygrid) > 3:
                    self.park_distance.setText(
                        str(self.distance(mygrid, park_info["grid6"]))
                    )
                    self.park_direction.setText(
                        str(self.bearing(mygrid, park_info["grid6"]))
                    )

                self.map = folium.Map(
                    location=[park_info["latitude"], park_info["longitude"]],
                    tiles=self.MAP_TILES,
                    zoom_start=5,
                    max_zoom=19,
                )
                folium.Marker(
                    [park_info["latitude"], park_info["longitude"]],
                    popup=f"<i>{park_info['name']}</i>",
                ).add_to(self.map)
                data = io.BytesIO()
                self.map.save(data, close_file=False)
                self.mapview.setHtml(data.getvalue().decode())
            if self.cat_control is not None:
                freq = line[3]
                combfreq = f"{freq}000"
                self.cat_control.set_vfo(combfreq)
                try:
                    mode = line[4].upper()
                    if mode == "SSB":
                        if int(combfreq) > 10000000:
                            mode = "USB"
                        else:
                            mode = "LSB"
                    self.cat_control.set_mode(mode)
                except IndexError:
                    pass
            else:
                self.recheck_cat()
        except ConnectionRefusedError:
            pass

    def item_double_clicked(self):
        """If a list item is double clicked a green highlight will be toggled"""
        item = self.listWidget.currentItem()
        line = item.text().split()
        if line[1] in self.workedlist:
            self.workedlist.remove(line[1])
        else:
            self.workedlist.append(line[1])
        self.showspots()
        try:
            home = os.path.expanduser("~")
            with open(
                f"{home}/.augratin_watched.json", "wt", encoding="utf-8"
            ) as file_descriptor:
                file_descriptor.write(dumps(self.workedlist))
        except IOError as exception:
            logger.critical("%s", exception)

    @staticmethod
    def getband(freq):
        """converts a frequency into a ham band"""
        if freq.isnumeric():
            frequency = int(float(freq)) * 1000
            if 2000000 > frequency > 1800000:
                return "160"
            if 4000000 > frequency > 3500000:
                return "80"
            if 5406000 > frequency > 5330000:
                return "60"
            if 7300000 > frequency > 7000000:
                return "40"
            if 10150000 > frequency > 10100000:
                return "30"
            if 14350000 > frequency > 14000000:
                return "20"
            if 18168000 > frequency > 18068000:
                return "17"
            if 21450000 > frequency > 21000000:
                return "15"
            if 24990000 > frequency > 24890000:
                return "12"
            if 29700000 > frequency > 28000000:
                return "10"
            if 54000000 > frequency > 50000000:
                return "6"
            if 148000000 > frequency > 144000000:
                return "2"
        else:
            return "0"

    @staticmethod
    def check_process(name: str) -> bool:
        """checks to see if program of name is in the active process list"""
        for proc in psutil.process_iter():
            if bool(re.match(name, proc.name().lower())):
                return True
        return False

    def recheck_cat(self):
        """Renegotiate CAT control."""
        local_flrig = self.check_process("flrig")
        local_rigctld = self.check_process("rigctld")

        if FORCED_INTERFACE:
            address, port = SERVER_ADDRESS.split(":")
            self.cat_control = CAT(FORCED_INTERFACE, address, int(port))

        if self.cat_control is None:
            if local_flrig:
                if SERVER_ADDRESS:
                    address, port = SERVER_ADDRESS.split(":")
                else:
                    address, port = "localhost", "12345"
                self.cat_control = CAT("flrig", address, int(port))
            if local_rigctld:
                if SERVER_ADDRESS:
                    address, port = SERVER_ADDRESS.split(":")
                else:
                    address, port = "localhost", "4532"
                self.cat_control = CAT("rigctld", address, int(port))


def install_icons():
    """Install application icons"""
    os.system(
        "xdg-icon-resource install --size 128 --context apps --mode user "
        f"{WORKING_PATH}/data/k6gte-augratin-128.png k6gte-augratin"
    )
    os.system(
        "xdg-icon-resource install --size 64 --context apps --mode user "
        f"{WORKING_PATH}/data/k6gte-augratin-64.png k6gte-augratin"
    )
    os.system(
        "xdg-icon-resource install --size 32 --context apps --mode user "
        f"{WORKING_PATH}/data/k6gte-augratin-32.png k6gte-augratin"
    )
    os.system(f"xdg-desktop-menu install {WORKING_PATH}/data/k6gte-augratin.desktop")


app = QtWidgets.QApplication(sys.argv)
app.setStyle("Fusion")
font_dir = WORKING_PATH + "/data"
families = load_fonts_from_dir(os.fspath(font_dir))
logger.info(families)
window = MainWindow()
window.setWindowTitle(f"AuGratin v{__version__}")
window.show()
window.getspots()
timer = QtCore.QTimer()
timer.timeout.connect(window.getspots)


def run():
    """Start the app"""
    install_icons()
    timer.start(30000)
    sys.exit(app.exec())


if __name__ == "__main__":
    run()
