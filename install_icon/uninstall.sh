#!/bin/bash

if [ -f "~/.local/bin/augratin" ]; then
	rm ~/.local/bin/augratin
fi

xdg-icon-resource uninstall --size 64 k6gte-augratin

xdg-desktop-icon uninstall k6gte-augratin.desktop

xdg-desktop-menu uninstall k6gte-augratin.desktop

