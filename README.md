# kicad_backport
Port kicad_sym and kicad_sch back to classic formats

Prerequisites:
Python 3.7+
pip install sexpdata

Run:

kicad_packport.py filname.kicad_sym
generates filename.lib and filename.dcm pair

kicad_backport.py filename.kicad_sch
generates filename-cache.lib
