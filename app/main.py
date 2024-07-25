import logging

from flask import Flask

from app.routes import setup_routes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)
    setup_routes(app)
    return app


app = create_app()

if __name__ == "__main__":
    logger.info("Starting the Stock API application")
    app.run(host="0.0.0.0", port=8000)
