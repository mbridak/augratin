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
import xmlrpc.client
import sys
import os
import io
import logging
from math import radians, sin, cos, atan2, sqrt, asin, pi
from pathlib import Path
from datetime import datetime, timezone
from json import loads, dumps
import re
import psutil
from PyQt5 import QtCore, QtWidgets, uic
from PyQt5.QtCore import QDir
from PyQt5.QtGui import QFontDatabase, QBrush, QColor
from PyQt5.QtWebKit import *
from PyQt5.QtWebKitWidgets import *
import requests
import folium

logging.basicConfig(level=logging.WARNING)

parser = argparse.ArgumentParser(
    description=(
        "augratin helps chasers hunt POTA activators. "
        "Find out more about POTA at https://pota.app"
    )
)
parser.add_argument(
    "-s",
    "--server",
    type=str,
    help="Enter flrig server:port address. default is localhost:12345",
)

args = parser.parse_args()

if args.server:
    SERVER_ADDRESS = args.server
else:
    SERVER_ADDRESS = "localhost:12345"


def relpath(filename):
    """
    Checks to see if program has been packaged with pyinstaller.
    If so base dir is in a temp folder.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_path = getattr(sys, "_MEIPASS")
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, filename)


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
            else:
                with open(
                    f"{home}/.augratin.json", "wt", encoding="utf-8"
                ) as file_descriptor:
                    file_descriptor.write(dumps(self.settings, indent=4))
                    logging.info("writing: %s", self.settings)
            if os.path.exists(f"{home}/.augratin_watched.json"):
                with open(
                    f"{home}/.augratin_watched.json", "rt", encoding="utf-8"
                ) as file_descriptor:
                    self.workedlist = loads(file_descriptor.read())
        except IOError as exception:
            logging.critical("%s", exception)
        self.isflrunning = self.checkflrun() or SERVER_ADDRESS != "localhost:12345"
        super().__init__(parent)
        uic.loadUi(self.relpath("dialog.ui"), self)
        self.listWidget.clicked.connect(self.spotclicked)
        if not self.isflrunning:
            print("flrig is not running")
        self.listWidget.doubleClicked.connect(self.item_double_clicked)
        self.comboBox_mode.currentTextChanged.connect(self.getspots)
        self.comboBox_band.currentTextChanged.connect(self.getspots)
        self.mycall_field.textEdited.connect(self.save_call_and_grid)
        self.mygrid_field.textEdited.connect(self.save_call_and_grid)
        self.log_button.clicked.connect(self.log_contact)
        self.server = xmlrpc.client.ServerProxy(f"http://{SERVER_ADDRESS}")
        self.mycall_field.setText(self.settings["mycall"])
        self.mygrid_field.setText(self.settings["mygrid"])
        if self.settings["mygrid"] == "":
            self.mygrid_field.setStyleSheet("border: 1px solid red;")
            self.mygrid_field.setFocus()
        if self.settings["mycall"] == "":
            self.mycall_field.setStyleSheet("border: 1px solid red;")
            self.mycall_field.setFocus()

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
                logging.info("writing: %s", self.settings)
        except IOError as exception:
            logging.critical("%s", exception)

    @staticmethod
    def getjson(url):
        """Get json request"""
        try:
            request = requests.get(url, timeout=15.0)
            request.raise_for_status()
        except requests.ConnectionError as err:
            print(f"Network Error: {err}")
            return None
        except requests.exceptions.Timeout as err:
            print(f"Timeout Error: {err}")
            return None
        except requests.exceptions.HTTPError as err:
            print(f"HTTP Error: {err}")
            return None
        except requests.exceptions.RequestException as err:
            print(f"Error: {err}")
            return None
        return loads(request.text)

    @staticmethod
    def relpath(filename: str) -> str:
        """
        If the program is packaged with pyinstaller,
        this is needed since all files will be in a temp
        folder during execution.
        """
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            base_path = getattr(sys, "_MEIPASS")
        else:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, filename)

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
        self.rst_sent.setFocus()

    def log_contact(self):
        """Log the contact"""
        freq = str(int(self.freq_field.text()) / 1000000)
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
        print(qso)
        home = os.path.expanduser("~")
        if not Path(home + "/POTA_Contacts.adi").exists():
            with open(
                home + "/POTA_Contacts.adi", "w", encoding="utf-8"
            ) as file_descriptor:
                header = (
                    "augratin POTA logger\n"
                    "<ADIF_VER:5>3.1.2\n"
                    "<PROGRAMID:8>Cloudlog\n"
                    "<PROGRAMVERSION:11>Version 1.7\n"
                    "<EOH>\n"
                )
                print(header, file=file_descriptor)
        with open(
            home + "/POTA_Contacts.adi", "a", encoding="utf-8"
        ) as file_descriptor:
            print(qso, file=file_descriptor)

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

    def spotclicked(self):
        """
        If flrig is running on this PC, tell it to tune to the spot freq and change mode.
        Otherwise die gracefully.
        """

        try:
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

                # self.map = folium.Map(
                #     location=[park_info["latitude"], park_info["longitude"]],
                #     zoom_start=5,
                # )

                # self.map = folium.Map(
                #     location=[park_info["latitude"], park_info["longitude"]],
                #     max_zoom=20,
                #     tiles="https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{z}/{y}/{x}",
                #     attr='Tiles courtesy of the <a href="https://usgs.gov/">U.S. Geological Survey</a>',
                # )

                # self.map = folium.Map(
                #     location=[park_info["latitude"], park_info["longitude"]],
                #     tiles="CartoDB dark_matter",
                #     zoom_start=6,
                # )

                # self.map = folium.Map(
                #     location=[park_info["latitude"], park_info["longitude"]],
                #     tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
                #     attr="Tiles &copy; Esri &mdash; National Geographic, Esri, DeLorme, NAVTEQ, UNEP-WCMC, USGS, NASA, ESA, METI, NRCAN, GEBCO, NOAA, iPC",
                #     zoom_start=6,
                #     max_zoom=16,
                # )

                # self.map = folium.Map(
                #     location=[park_info["latitude"], park_info["longitude"]],
                #     tiles="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
                #     attr='Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, <a href="http://viewfinderpanoramas.org">SRTM</a> | Map style: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)',
                #     zoom_start=6,
                #     max_zoom=17,
                # )

                self.map = folium.Map(
                    location=[park_info["latitude"], park_info["longitude"]],
                    tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
                    attr='Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, <a href="http://viewfinderpanoramas.org">SRTM</a> | Map style: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)',
                    zoom_start=5,
                    max_zoom=19,
                )

                folium.Marker(
                    [park_info["latitude"], park_info["longitude"]],
                    popup=f"<i>{park_info['name']}</i>",
                ).add_to(self.map)
                data = io.BytesIO()
                self.map.save(data, close_file=False)
                self.webView.setHtml(data.getvalue().decode())
            if self.isflrunning:
                freq = line[3]
                combfreq = f"{freq}000"
                self.server.rig.set_frequency(float(combfreq))
                try:
                    mode = line[4].upper()
                    if mode == "SSB":
                        if int(combfreq) > 10000000:
                            mode = "USB"
                        else:
                            mode = "LSB"
                    self.server.rig.set_mode(mode)
                except IndexError:
                    pass
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
            logging.critical("%s", exception)

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
    def checkflrun():
        """checks to see if flrig is in the active process list"""
        reg = "flrig"
        found = False

        for proc in psutil.process_iter():
            if found is False:
                if bool(re.match(reg, proc.name().lower())):
                    found = True
        return found


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    font_dir = relpath("font")
    families = load_fonts_from_dir(os.fspath(font_dir))
    logging.info(families)
    window = MainWindow()
    window.show()
    window.getspots()
    timer = QtCore.QTimer()
    timer.timeout.connect(window.getspots)
    timer.start(30000)
    app.exec()
