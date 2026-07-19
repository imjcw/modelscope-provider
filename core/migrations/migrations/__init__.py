"""Auto-import all migration modules to trigger @register decorators."""

import importlib
from pathlib import Path

_module_base = __name__
_dir = Path(__file__).parent

for _file in sorted(_dir.glob("*.py")):
    if _file.stem != "__init__":
        importlib.import_module(f"{_module_base}.{_file.stem}")
