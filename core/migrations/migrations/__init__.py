"""Auto-import all migration modules to trigger @register decorators."""

import importlib
import sys
from pathlib import Path

_module_base = __name__
if getattr(sys, "frozen", False):
    # PyInstaller --onefile: modules live inside the archive;
    # data files (incl. migration .py) are extracted to sys._MEIPASS.
    _dir = Path(sys._MEIPASS) / _module_base.replace(".", "/")
else:
    _dir = Path(__file__).parent

for _file in sorted(_dir.glob("*.py")):
    if _file.stem != "__init__":
        importlib.import_module(f"{_module_base}.{_file.stem}")
