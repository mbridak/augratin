#!/bin/bash

if [ -f "../dist/augratin" ]; then
	cp ../dist/augratin ~/.local/bin/
fi

xdg-icon-resource install --size 64 --context apps --mode user k6gte-augratin.png k6gte-augratin

xdg-desktop-icon install k6gte-augratin.desktop

xdg-desktop-menu install k6gte-augratin.desktop

