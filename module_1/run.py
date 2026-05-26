from board import create_app

# Creating Flask Object
app = create_app()

if __name__ == "__main__":
    # Running Flask Object
    app.run(host="localhost", port=8080)
