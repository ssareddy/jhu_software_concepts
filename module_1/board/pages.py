"""pages.py - Blueprint routes for the personal portfolio website."""

import json
from pathlib import Path

from flask import Blueprint, render_template

bp = Blueprint("pages", __name__)

# projects.json lives at the jhu_software_concepts repo root, two directories
# above this file (module_1/board/pages.py -> module_1/ -> repo root), so the
# same portfolio data file can be shared across the whole repository rather
# than being duplicated inside module_1 itself.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_PROJECTS_JSON_PATH = _REPO_ROOT / "projects.json"


def load_projects() -> list:
    """Load the semester project portfolio data from projects.json.

    Returns:
        A list of project dicts (module, title, overview, github_link,
        learned), in the order they appear in the JSON file. Returns an
        empty list if the file is missing, so the Projects page still
        renders (with no project blocks) instead of crashing.
    """
    if not _PROJECTS_JSON_PATH.is_file():
        return []
    with open(_PROJECTS_JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


@bp.route("/")
def about():
    """Render the About/home page."""
    return render_template("pages/about.html")


@bp.route("/projects")
def projects():
    """Render the Projects page, populated from projects.json."""
    return render_template("pages/projects.html", projects=load_projects())


@bp.route("/contact")
def contact():
    """Render the Contact page."""
    return render_template("pages/contact.html")