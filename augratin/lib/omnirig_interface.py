"""
KK7JXG my attempt to add omnirig CAT control
email:barry.shaffer@gmail.com
GPL V3
"""

import win32com.client as win32
import logging

class OmniRigClient:
    """OmniRig CAT control"""
    def __init__(self, rig: str) -> None:
        """
        My CAT class using Omnirig
        will attempt to create in a fashion that can be independantly tested 
        then injected in K6GTE's cat_interface.py

        Takes 1 input to setup the class.

        A string defining which rig to control, either 'rig1' or 'rig2'.

        Exposed methods are:

        set_vfo()

        set_mode()

        A variable 'online' is set to True if no error was encountered,
        otherwise False.
        """
        self.rig = rig
        self.online = False
        self.omnirigObject = None

    def __initialize_omnirig(self):
        try:
            self.omnirigObject = win32.gencache.EnsureDispatch('OmniRig.OmniRigX')
            logging.debug("Connected to Omnirig")
            self.online = True
        except:
            self.online = False
            logging.debug("Omnirig connection failed")

    def set_vfo(self, freq: str) -> bool:
        """Sets the radios vfo"""
        if self.rig == "rig1":
            self.omnirigObject.Rig1.Freq = freq
            return True
        if self.rig == "rig2":
            self.omnirigObject.Rig2.Freq = freq
            return True
        return False
    
    
    def set_mode(self, mode: str) -> bool:
        """Sets the raidos mode"""
        if self.rig == "rig1":
            self.omnirigObject.Rig1.mode = mode
            return True
        if self.rig == "rig2":
            self.omnirigObject.Rig2.Freq = mode
            return True
        return False
    

