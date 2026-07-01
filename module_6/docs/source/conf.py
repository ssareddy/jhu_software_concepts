# Configuration file for the Sphinx documentation builder.
import os
import sys

sys.path.insert(0, os.path.abspath("../../src"))

project = "Grad Café Analytics"
copyright = "2026"
author = "Student"
release = "4.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "myst_parser",
]

templates_path = ["_templates"]
exclude_patterns = []
html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
