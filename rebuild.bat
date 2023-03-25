#!/windows batch file
pip uninstall -y augratin
del /s dist\
python -m build
pip install -e .

