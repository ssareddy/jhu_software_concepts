from flask import Flask
from board import app

web = Flask(__name__)

web.register_blueprint(app.bp)

if __name__ == "__main__":
    web.run(host="localhost", port=8080, debug=True)
