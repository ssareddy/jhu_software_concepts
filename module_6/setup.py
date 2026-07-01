from setuptools import setup

setup(
    name="gradcafe_analytics",
    version="1.0.0",
    py_modules=[
        "app",
        "clean",
        "db_config",
        "load_data",
        "query_data",
        "scrape",
    ],
    package_dir={"": "src"},
    install_requires=[
        "flask",
        "psycopg2-binary",
        "beautifulsoup4",
        "selenium",
        "requests",
    ],
)