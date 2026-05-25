from flask import Flask
from board import pages

def create_app():
    """
    Creates Flask object
    :return: Flask
    """

    app = Flask(__name__)
    app.register_blueprint(pages.bp)

    return app
