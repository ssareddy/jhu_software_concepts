"""
run.py
------
Flask entrypoint. Binds to 0.0.0.0:8080 for Docker.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app.app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)