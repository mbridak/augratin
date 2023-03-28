"""
KK7JXG simple omnirig CAT control
email:barry.shaffer@gmail.com
GPL V3
"""


import logging

import win32com.client as win32  # pylint: disable=import-error


class OmniRigClient:
    """OmniRig CAT control"""

    def __init__(self, rig: int) -> None:
        """
        @barryshaffer KK7JXG
        My CAT class using Omnirig
        will attempt to create in a fashion that can be independantly tested
        then injected in K6GTE's cat_interface.py

        Takes 1 input to setup the class.

        A inteter defining which rig to control, 1 = 'rig1' 2 = 'rig2'.

        Exposed methods are:

        set_vfo()

        set_mode()

        A variable 'online' is set to True if no error was encountered,
        otherwise False.
        """
        self.rig = rig
        self.online = False
        self.omnirig_object = None
        try:
            self.omnirig_object = win32.gencache.EnsureDispatch("OmniRig.OmniRigX")
            logging.debug("Connected to Omnirig")
            self.online = True
        except:  # pylint: disable=bare-except
            self.online = False
            logging.debug("Omnirig connection failed")

    def set_vfo(self, freq: str) -> bool:
        """Sets the radios vfo"""
        if self.rig == 1:
            self.omnirig_object.Rig1.SetSimplexMode(int(freq))
            return True
        if self.rig == 2:
            self.omnirig_object.Rig2.SetSimplexMode(int(freq))
            return True
        return False

    def set_mode(self, mode: str) -> bool:
        """
        Sets the raidos mode
        Convert Mode to Omnirig param
        """
        if mode == "CW":
            omni_mode = 8388608  # CW-U Omnirig Param
        elif mode == "USB":
            omni_mode = 33554432  # USB Omnirig Param
        else:
            omni_mode = 67108864  # LSB Omnirig Param

        if self.rig == 1:
            self.omnirig_object.Rig1.Mode = omni_mode
            return True
        if self.rig == 2:
            self.omnirig_object.Rig2.Mode = omni_mode
            return True
        return False
