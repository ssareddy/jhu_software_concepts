"""run.py - Module 13 Flask entrypoint.

Starts the Grad Cafe admissions website (the existing Analysis page, plus
the new "Will You Get In?" prediction page) on http://0.0.0.0:8080.

Both this module_13 root directory (for inference.py and model_common.py)
and the web/ subdirectory (for the app package) are added to sys.path, so
inference.py and its saved model live in exactly one place -- there is no
duplicated copy of the trained model or the inference code inside web/.

The app package is loaded via importlib.import_module() rather than a
literal "from app.app import create_app" statement, since that path only
exists once the sys.path setup above has run -- using importlib keeps the
module-level statement order (imports first, then setup, then this lookup)
fully conventional instead of requiring a non-import statement ahead of a
later import.
"""

import importlib
import os
import sys

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env.example"))

sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "web"))

app_module = importlib.import_module("app.app")
app = app_module.create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
