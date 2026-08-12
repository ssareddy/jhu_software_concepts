from setuptools import setup, find_packages

setup(
    name="gradcafe_analytics",
    version="2.0.0",
    packages=find_packages(where="src/web") + find_packages(where="src/worker") + find_packages(where="src/db"),
    package_dir={
        "": "src/web",
    },
    install_requires=[
        "flask>=3.0.0",
        "psycopg2-binary>=2.9.9",
        "pika>=1.3.2",
        "beautifulsoup4>=4.12.0",
        "selenium>=4.20.0",
        "requests>=2.31.0",
    ],
)
