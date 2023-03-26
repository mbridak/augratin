"""
KK7JXG simple omnirig CAT control
email:barry.shaffer@gmail.com
GPL V3
"""

import win32com.client as win32
import logging

if __name__ == "__main__":
    print("I'm not the program you are looking for.")

class OmniRigClient:
    """OmniRig CAT control"""
    
    def __init__(self, rig: int) -> None:
        """
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
        self.omnirigObject = None
        try:
            self.omnirigObject = win32.gencache.EnsureDispatch('OmniRig.OmniRigX')
            logging.debug("Connected to Omnirig")
            self.online = True
        except:
            self.online = False
            logging.debug("Omnirig connection failed")

    def set_vfo(self, freq: str) -> bool:
        """Sets the radios vfo"""
        if self.rig == 1:
            self.omnirigObject.Rig1.SetSimplexMode(int(freq))
            return True
        if self.rig == 2:
            self.omnirigObject.Rig2.SetSimplexMode(int(freq))
            return True
        return False
    
    def set_mode(self, mode: str) -> bool:
        """Sets the raidos mode"""
        
        """Convert Mode to Omnirig param"""
        if mode == "USB":
            omniMode = 33554432 #USB Omnirig Param
        else:
            omniMode = 67108864 #LSB Omnirig Param

        if self.rig == 1:
            self.omnirigObject.Rig1.Mode = omniMode
            return True
        if self.rig == 2:
            self.omnirigObject.Rig2.Mode = omniMode
            return True
        return False
