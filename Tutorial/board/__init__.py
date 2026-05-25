from flask import Flask
import pages

app = Flask(__name__)

app.register_blueprint(pages.bp)

if __name__ == "__main__":
    app.run(host="localhost", port=8080, debug=True)
