"""
setup.py — gradcafe_common
---------------------------
Shared package used by BOTH the web and worker services.

Why this exists: web/ and worker/ are separate Docker build contexts
(each gets its own image), so they cannot share a plain Python module by
just importing across directories. db_config.py and query_data.py were
previously duplicated verbatim in src/web/app/ and src/worker/etl/ —
this package makes that single source of truth installable by both
images instead, via `pip install ./common` in each Dockerfile.
"""
from setuptools import setup

setup(
    name="gradcafe-common",
    version="1.0.0",
    packages=["gradcafe_common"],
    install_requires=["psycopg2-binary"],
)
