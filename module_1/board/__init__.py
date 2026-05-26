from flask import Flask
from board import pages

def create_app():
    """
    Creates Flask object
    :return: Flask
    """

    app = Flask(__name__)
    # Registering blueprints with webpage information
    app.register_blueprint(pages.bp)

    return app
