"""Flask application layer.

This module contains the Flask application logic, separated from the server infrastructure.
Exposes:
- create_app() -> Flask app with routes and configuration
"""
from flask import Flask


def create_app() -> Flask:
    """Create and return the Flask application.

    Returns an app with all routes configured.
    This is the core application logic, independent of the WSGI server implementation.
    """
    app = Flask(__name__)

    @app.route("/")
    def index():
        return "Hola mundo"

    return app
