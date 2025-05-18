#!/bin/bash
pip uninstall -y augratin
rm dist/*
python3 -m build
pip install -e .

