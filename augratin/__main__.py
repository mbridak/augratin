#!/usr/bin/env python3
"""AuGratin helps chasers hunt POTA activators. Find out more about POTA at https://pota.app"""

# pylint: disable=unused-import, c-extension-no-member, no-member, invalid-name, too-many-lines
# pylint: disable=no-name-in-module
# pylint: disable=wildcard-import
# pylint: disable=line-too-long

# https://api.pota.app/park/K-0064
# {"parkId": 64, "reference": "K-0064", "name": "Shenandoah", "latitude": 38.9068, "longitude": -78.1988, "grid4": "FM08", "grid6": "FM08vv", "parktypeId": 41, "active": 1, "parkComments": "Potentially co-located with K-4556 - Appalachian Trail NST.  Numerous SOTA locations.", "accessibility": null, "sensitivity": null, "accessMethods": "Automobile,Foot", "activationMethods": "Automobile,Cabin,Campground,Pedestrian,Shelter", "agencies": "National Park Service", "agencyURLs": "https://www.nps.gov/index.htm", "parkURLs": "https://www.nps.gov/shen/index.htm", "website": "https://www.nps.gov/shen/index.htm", "createdByAdmin": null, "parktypeDesc": "National Park", "locationDesc": "US-VA", "locationName": "Virginia", "entityId": 291, "entityName": "United States Of America", "referencePrefix": "K", "entityDeleted": 0, "firstActivator": "WX4TW", "firstActivationDate": "2015-08-27"}

# https://api.pota.app/stats/user/K2EAG
# {"callsign": "K2EAG", "name": "Matt Brown", "qth": "Amherst, New York", "gravatar": "bf8377378b67b265cbb2be687b13a23a", "activator": {"activations": 72, "parks": 33, "qsos": 3724}, "attempts": {"activations": 80, "parks": 33, "qsos": 3724}, "hunter": {"parks": 237, "qsos": 334}, "awards": 16, "endorsements": 32}

import argparse
import sys
import sqlite3
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
from PyQt5 import QtCore, QtWidgets, QtGui, uic
from PyQt5.QtCore import QDir
from PyQt5.QtGui import QFontDatabase, QBrush, QColor
import PyQt5.QtWebEngineWidgets  # pylint: disable=unused-import

# from PyQt5.QtWebEngineWidgets import QWebEngineView


import requests
import folium

try:
    from augratin.lib.version import __version__
    from augratin.lib.cat_interface import CAT

    if sys.platform == "win32":
        from augratin.lib.omnirig_interface import OmniRigClient
except ModuleNotFoundError:
    from lib.version import __version__
    from lib.cat_interface import CAT

    if sys.platform == "win32":
        from lib.omnirig_interface import OmniRigClient

__author__ = "Michael C. Bridak, K6GTE"
__license__ = "GNU General Public License v3.0"

os.environ["QT_QPA_PLATFORMTHEME"] = "gnome"

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
    "-2",
    action=argparse.BooleanOptionalAction,
    dest="rig2",
    help="Force use of rig2 in omnirig",
)

parser.add_argument(
    "-d",
    action=argparse.BooleanOptionalAction,
    dest="debug",
    help="Debug",
)

args = parser.parse_args()

PIXELSPERSTEP = 10
YOFFSET = 10

FORCED_INTERFACE = None
SERVER_ADDRESS = None
OMNI_RIGNUMBER = 1

if args.rigctld:
    FORCED_INTERFACE = "rigctld"
    SERVER_ADDRESS = "localhost:4532"

if args.flrig:
    FORCED_INTERFACE = "flrig"
    SERVER_ADDRESS = "localhost:12345"

if args.server:
    SERVER_ADDRESS = args.server

if args.rig2:
    OMNI_RIGNUMBER = 2

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


class Band:
    """the band"""

    bands = {
        "160m": (1.8, 2),
        "80m": (3.5, 4),
        "60m": (5.102, 5.4065),
        "40m": (7.0, 7.3),
        "30m": (10.1, 10.15),
        "20m": (14.0, 14.35),
        "15m": (21.0, 21.45),
        "10m": (28.0, 29.7),
        "6m": (50.0, 54.0),
        "4m": (70.0, 71.0),
        "2m": (144.0, 148.0),
    }

    def __init__(self, band: str) -> None:
        self.start, self.end = self.bands.get(band, (0.0, 1.0))
        self.name = band


class Database:
    """spot database"""

    def __init__(self) -> None:
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = self.row_factory
        self.cursor = self.db.cursor()
        sql_command = (
            "create table spots("
            "spotId INTEGER NOT NULL,"
            "spotTime DATETIME NOT NULL, "
            "activator VARCHAR(15) NOT NULL, "
            "frequency REAL NOT NULL, "
            "mode VARCHAR(6), "
            "reference VARCHAR(8), "
            "parkName VARCHAR(50), "
            "spotter VARCHAR(15) NOT NULL, "
            "comments VARCHAR(45), "
            "source VARCHAR(8), "
            "invalid INTEGER, "
            "name VARCHAR(50), "
            "locationDesc VARCHAR(10), "
            "grid4 VARCHAR(4), "
            "grid6 VARCHAR(6), "
            "latitude REAL, "
            "longitude REAL, "
            "count INTEGER, "
            "expire INTEGER "
            ");"
        )
        self.cursor.execute(sql_command)
        self.db.commit()

    @staticmethod
    def row_factory(cursor, row):
        """
        cursor.description:
        (name, type_code, display_size,
        internal_size, precision, scale, null_ok)
        row: (value, value, ...)
        """
        return {
            col[0]: row[idx]
            for idx, col in enumerate(
                cursor.description,
            )
        }

    def addspot(self, spot):
        """doc"""
        try:
            delete_call = (
                f"delete from spots where activator = '{spot.get('activator')}';"
            )
            self.cursor.execute(delete_call)
            self.db.commit()

            pre = "INSERT INTO spots("
            values = []
            columns = ""
            placeholders = ""
            for key in spot.keys():
                columns += f"{key},"
                values.append(spot[key])
                placeholders += "?,"
            post = f") VALUES({placeholders[:-1]});"

            sql = f"{pre}{columns[:-1]}{post}"
            self.cursor.execute(sql, tuple(values))
            self.db.commit()
        except sqlite3.IntegrityError:
            ...

    def getspots(self) -> list:
        """returns a list of dicts."""
        try:
            self.cursor.execute("select * from spots order by frequency ASC;")
            return self.cursor.fetchall()
        except sqlite3.OperationalError:
            return ()

    def getspotsinband(self, start: float, end: float) -> list:
        """ "return a list of dict where freq range is defined"""
        self.cursor.execute(
            f"select * from spots where frequency >= {start} and frequency <= {end} order by frequency ASC;"
        )
        return self.cursor.fetchall()

    def get_next_spot(self, current: float, limit: float) -> dict:
        """ "return a list of dict where freq range is defined"""
        self.cursor.execute(
            f"select * from spots where frequency > {current} and frequency <= {limit} order by frequency ASC;"
        )
        return self.cursor.fetchone()

    def get_prev_spot(self, current: float, limit: float) -> dict:
        """ "return a list of dict where freq range is defined"""
        self.cursor.execute(
            f"select * from spots where frequency < {current} and frequency >= {limit} order by frequency DESC;"
        )
        return self.cursor.fetchone()

    def getspot_byid(self, spot_id: int) -> dict:
        """Return a dict of spot with the matching spotId"""
        self.cursor.execute(f"select * from spots where spotId = {spot_id};")
        return self.cursor.fetchone()

    def delete_spots(self, minutes: int):
        """Delete old spots"""
        self.cursor.execute(
            f"delete from spots where spotTime < datetime('now', '-{minutes} minutes');"
        )


class MainWindow(QtWidgets.QMainWindow):
    """The main window class"""

    zoom = 5
    currentBand = Band("2m")
    txMark = []
    rxMark = []
    rx_freq = None
    tx_freq = None
    lineitemlist = []
    textItemList = []
    bandwidth = 0
    bandwidth_mark = []
    freq = 0.0
    keepRXCenter = False
    something = None
    agetime = None

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
        super().__init__(parent)
        data_path = WORKING_PATH + "/data/dialog.ui"
        uic.loadUi(data_path, self)

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
        local_omnirig = self.check_process("omnirig.exe")

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
                    if not self.cat_control.online:
                        self.show_message_box("Was unable to connect to flrig.")
            if local_rigctld:
                if SERVER_ADDRESS:
                    address, port = SERVER_ADDRESS.split(":")
                else:
                    address, port = "localhost", "4532"
                    self.cat_control = CAT("rigctld", address, int(port))
            if local_omnirig:
                self.cat_control = OmniRigClient(OMNI_RIGNUMBER)
                logging.debug("omnirig called")

        self.zoom_in_button.clicked.connect(self.dec_zoom)
        self.zoom_out_button.clicked.connect(self.inc_zoom)
        self.bandmap_scene = QtWidgets.QGraphicsScene()
        self.bandmap_scene.clear()
        self.bandmap_scene.setFocusOnTouch(False)
        self.bandmap_scene.selectionChanged.connect(self.spotclicked)
        self.bandmap_scene.setFont(QtGui.QFont("JetBrains Mono", pointSize=5))
        self.spotdb = Database()
        self.comboBox_mode.currentTextChanged.connect(self.getspots)
        self.comboBox_band.currentTextChanged.connect(self.nocat_bandchange)
        if self.cat_control is not None:
            self.comboBox_band.hide()

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

    def poll_radio(self):
        """Get Freq and Mode changes"""
        if self.cat_control:
            if self.cat_control.online:
                try:
                    newfreq = float(self.cat_control.get_vfo()) / 1000000
                except ValueError:
                    return
                if hasattr(self.cat_control, "get_bw"):
                    try:
                        newbw = int(self.cat_control.get_bw())
                    except TypeError:
                        newbw = 0
                    except ValueError:
                        newbw = 0
                else:
                    newbw = 0
                if self.rx_freq != newfreq:
                    self.rx_freq = newfreq
                    self.set_band(f"{self.getband(str(int(newfreq * 1000)))}m")
                    step, _ = self.determine_step_digits()
                    self.drawTXRXMarks(step)
                    self.center_on_rxfreq()
                if self.bandwidth != newbw:
                    self.bandwidth = newbw
                    step, _ = self.determine_step_digits()
                    self.drawTXRXMarks(step)

    def show_message_box(self, message: str) -> None:
        """Display a message box to the user."""
        message_box = QtWidgets.QMessageBox()
        message_box.setIcon(QtWidgets.QMessageBox.Information)
        message_box.setText(message)
        message_box.setWindowTitle("Information")
        message_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
        _ = message_box.exec_()

    def nocat_bandchange(self) -> None:
        """Called when the bandselector dropdown changes."""
        band = self.comboBox_band.currentText()
        self.set_band(f"{band}m")
        self.update()

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

    def getspots(self):
        """Gets activator spots from pota.app"""
        self.time.setText(str(datetime.now(timezone.utc)).split()[1].split(".")[0][0:5])
        self.spots = self.getjson(self.potaurl)
        if self.spots:
            for spot in self.spots:
                try:
                    spot["frequency"] = float(spot.get("frequency")) / 1000
                    self.spotdb.addspot(spot)
                except ValueError:
                    pass
            self.update()

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

    def update(self):
        """doc"""
        # self.update_timer.setInterval(UPDATE_INTERVAL)
        self.clear_all_callsign_from_scene()
        self.clear_freq_mark(self.rxMark)
        self.clear_freq_mark(self.txMark)
        self.clear_freq_mark(self.bandwidth_mark)
        self.bandmap_scene.clear()

        step, _digits = self.determine_step_digits()
        steps = int(round((self.currentBand.end - self.currentBand.start) / step))
        self.graphicsView.setScene(self.bandmap_scene)
        for i in range(steps):  # Draw tickmarks
            length = 10
            if i % 5 == 0:
                length = 15
            self.bandmap_scene.addLine(
                170,
                i * PIXELSPERSTEP,
                length + 170,
                i * PIXELSPERSTEP,
                QtGui.QPen(QtGui.QColor(192, 192, 192)),
            )
            if i % 5 == 0:  # Add Frequency
                freq = self.currentBand.start + step * i
                text = f"{freq:.3f}"
                self.something = self.bandmap_scene.addText(
                    text, QtGui.QFont("JetBrains Mono", pointSize=11)
                )
                self.something.setPos(
                    -(self.something.boundingRect().width()) + 170,
                    i * PIXELSPERSTEP - (self.something.boundingRect().height() / 2),
                )

        freq = self.currentBand.end + step * steps
        endFreqDigits = f"{freq:.3f}"
        self.bandmap_scene.setSceneRect(
            160 - (len(endFreqDigits) * PIXELSPERSTEP),
            -15,
            0,
            steps * PIXELSPERSTEP + 20,
        )

        self.drawTXRXMarks(step)
        self.update_stations()

    def update_stations(self):
        """doc"""
        self.clear_all_callsign_from_scene()
        self.spot_aging()
        step, _digits = self.determine_step_digits()
        mode_selection = self.comboBox_mode.currentText()
        result = self.spotdb.getspotsinband(
            self.currentBand.start, self.currentBand.end
        )
        if result:
            min_y = 0.0
            for items in result:
                if mode_selection == "-FT*" and items["mode"][:2] == "FT":
                    continue
                if (
                    mode_selection == "All"
                    or mode_selection == "-FT*"
                    or items["mode"] == mode_selection
                ):
                    freq_y = (
                        (items.get("frequency") - self.currentBand.start) / step
                    ) * PIXELSPERSTEP
                    text_y = max(min_y + 5, freq_y)
                    self.lineitemlist.append(
                        self.bandmap_scene.addLine(
                            180,
                            freq_y,
                            210,
                            text_y,
                            QtGui.QPen(QtGui.QColor(192, 192, 192)),
                        )
                    )
                    text = self.bandmap_scene.addText(
                        items.get("activator")
                        + " @ "
                        + items.get("reference")
                        + " "
                        + items.get("mode")
                        + " "
                        + items.get("spotTime").split("T")[1][:-3],
                        QtGui.QFont("JetBrains Mono", pointSize=11),
                    )
                    text.document().setDocumentMargin(0)
                    text.setPos(210, text_y - (text.boundingRect().height() / 2))
                    text.setFlags(
                        QtWidgets.QGraphicsItem.ItemIsFocusable
                        | QtWidgets.QGraphicsItem.ItemIsSelectable
                        | text.flags()
                    )
                    text.setProperty("freq", items.get("frequency"))
                    text.setProperty("spotId", items.get("spotId"))
                    text.setProperty("mode", items.get("mode"))
                    text.setToolTip(items.get("comments"))
                    if "QRT" in items.get("comments", "").upper():
                        text.setDefaultTextColor(QtGui.QColor(120, 120, 120, 120))

                    min_y = text_y + text.boundingRect().height() / 2

                    # textColor = Data::statusToColor(lower.value().status,
                    # qApp->palette().color(QPalette::Text));
                    # text->setDefaultTextColor(textColor);
                    self.textItemList.append(text)

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

    def spot_aging(self):
        """doc"""
        if self.agetime:
            self.spots.delete_spots(self.agetime)

    def inc_zoom(self):
        """doc"""
        self.zoom += 1
        self.zoom = min(self.zoom, 7)
        self.update()
        self.center_on_rxfreq()

    def dec_zoom(self):
        """doc"""
        self.zoom -= 1
        self.zoom = max(self.zoom, 1)
        self.update()
        self.center_on_rxfreq()

    def drawTXRXMarks(self, step):
        """doc"""
        if self.rx_freq:
            self.clear_freq_mark(self.bandwidth_mark)
            self.clear_freq_mark(self.rxMark)
            self.draw_bandwidth(
                self.rx_freq, step, QtGui.QColor(30, 30, 180, 180), self.bandwidth_mark
            )
            self.drawfreqmark(
                self.rx_freq, step, QtGui.QColor(30, 180, 30, 180), self.rxMark
            )

    def Freq2ScenePos(self, freq: float):
        """doc"""
        if freq < self.currentBand.start or freq > self.currentBand.end:
            return QtCore.QPointF()
        step, _digits = self.determine_step_digits()
        ret = QtCore.QPointF(
            0, ((freq - self.currentBand.start) / step) * PIXELSPERSTEP
        )
        return ret

    def center_on_rxfreq(self):
        """doc"""
        if self.cat_control is not None and self.rx_freq:
            freq_pos = self.Freq2ScenePos(self.rx_freq).y()
            self.graphicsView.verticalScrollBar().setSliderPosition(
                int(freq_pos - (self.height() / 2) + 80)
            )

    def drawfreqmark(self, freq, _step, color, currentPolygon):
        """doc"""

        self.clear_freq_mark(currentPolygon)
        # do not show the freq mark if it is outside the bandmap
        if freq < self.currentBand.start or freq > self.currentBand.end:
            return

        Yposition = self.Freq2ScenePos(freq).y()

        poly = QtGui.QPolygonF()

        poly.append(QtCore.QPointF(181, Yposition))
        poly.append(QtCore.QPointF(170, Yposition - 7))
        poly.append(QtCore.QPointF(170, Yposition + 7))
        pen = QtGui.QPen()
        brush = QtGui.QBrush(color)
        currentPolygon.append(self.bandmap_scene.addPolygon(poly, pen, brush))

    def draw_bandwidth(self, freq, _step, color, currentPolygon):
        """bandwidth"""
        logger.debug("%s", f"mark:{currentPolygon} f:{freq} b:{self.bandwidth}")
        self.clear_freq_mark(currentPolygon)
        if freq < self.currentBand.start or freq > self.currentBand.end:
            return
        if freq and self.bandwidth:
            # color = QtGui.QColor(30, 30, 180)
            bw_start = freq - ((self.bandwidth / 2) / 1000000)
            bw_end = freq + ((self.bandwidth / 2) / 1000000)
            logger.debug("%s", f"s:{bw_start} e:{bw_end}")
            Yposition_neg = self.Freq2ScenePos(bw_start).y()
            Yposition_pos = self.Freq2ScenePos(bw_end).y()
            poly = QtGui.QPolygonF()
            poly.append(QtCore.QPointF(175, Yposition_neg))
            poly.append(QtCore.QPointF(180, Yposition_neg))
            poly.append(QtCore.QPointF(180, Yposition_pos))
            poly.append(QtCore.QPointF(175, Yposition_pos))
            pen = QtGui.QPen()
            brush = QtGui.QBrush(color)
            currentPolygon.append(self.bandmap_scene.addPolygon(poly, pen, brush))

    def determine_step_digits(self):
        """doc"""
        return_zoom = {
            1: (0.0001, 4),
            2: (0.00025, 4),
            3: (0.0005, 4),
            4: (0.001, 3),
            5: (0.0025, 3),
            6: (0.005, 3),
            7: (0.01, 2),
        }
        step, digits = return_zoom.get(self.zoom, (0.0001, 4))

        if self.currentBand.start >= 28.0 and self.currentBand.start < 420.0:
            step = step * 10
            return (step, digits)

        if self.currentBand.start >= 420.0 and self.currentBand.start < 2300.0:
            step = step * 100

        return (step, digits)

    def set_band(self, band: str):
        """doc"""
        logger.debug("%s", f"{band}")
        if band != self.currentBand.name:
            # if savePrevBandZoom:
            #     self.saveCurrentZoom()
            self.currentBand = Band(band)
            # self.zoom = self.savedZoom(band)
            self.update()

    def clear_all_callsign_from_scene(self):
        """doc"""
        for items in self.textItemList:
            self.bandmap_scene.removeItem(items)
        self.textItemList.clear()
        for items in self.lineitemlist:
            self.bandmap_scene.removeItem(items)
        self.lineitemlist.clear()

    def clear_freq_mark(self, currentPolygon):
        """doc"""
        if currentPolygon:
            for mark in currentPolygon:
                self.bandmap_scene.removeItem(mark)
        currentPolygon.clear()

    def spotclicked(self):
        """
        If flrig/rigctld is running on this PC, tell it to tune to the spot freq and change mode.
        Otherwise die gracefully.
        """
        # new stuff
        selected_items = self.bandmap_scene.selectedItems()
        if not selected_items:
            return
        selected = selected_items[0]
        if selected:
            spotId = selected.property("spotId")
            spotfreq = int(selected.property("freq") * 1000000)
            # spotmode = selected.property("mode")

        # old stuff
        try:
            spot = self.spotdb.getspot_byid(spotId)
            item = f"xxx {spot.get('activator')} {spot.get('reference')} {int(spot.get('frequency')*1000)} {spot.get('mode')}"
            self.loggable = True
            dateandtime = datetime.utcnow().isoformat(" ")[:19]
            self.time_field.setText(dateandtime.split(" ")[1].replace(":", ""))
            the_date_fields = dateandtime.split(" ")[0].split("-")
            the_date = f"{the_date_fields[0]}{the_date_fields[1]}{the_date_fields[2]}"
            self.date_field.setText(the_date)
            line = item.split()
            self.lastclicked = item
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
            self.freq_field.setText(f"{spotfreq}")
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
                combfreq = f"{spotfreq}"
                try:
                    mode = line[4].upper()
                    if mode == "SSB":
                        if spotfreq > 10000000:
                            mode = "USB"
                        else:
                            mode = "LSB"
                    self.cat_control.set_mode(mode)
                except IndexError:
                    pass
                self.cat_control.set_vfo(
                    combfreq
                )  # Set Mode first because some rigs offset vfo based on mode.
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
                logger.debug("%s found!", name)
                return True
        return False

    def recheck_cat(self):
        """Renegotiate CAT control."""
        local_flrig = self.check_process("flrig")
        local_rigctld = self.check_process("rigctld")
        local_omnirig = self.check_process("omnirig.exe")

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
            if local_omnirig:
                self.cat_control = OmniRigClient(OMNI_RIGNUMBER)


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
# app.setStyle("Fusion")
font_dir = WORKING_PATH + "/data"
families = load_fonts_from_dir(os.fspath(font_dir))
logger.info(families)
window = MainWindow()
window.setWindowTitle(f"AuGratin v{__version__}")
window.show()
window.getspots()
timer = QtCore.QTimer()
timer.timeout.connect(window.getspots)
timer2 = QtCore.QTimer()
timer2.timeout.connect(window.poll_radio)


def run():
    """Start the app"""
    install_icons()
    timer.start(30000)
    timer2.start(100)
    sys.exit(app.exec())


if __name__ == "__main__":
    run()
