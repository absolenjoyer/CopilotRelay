"""Server infrastructure layer.

This module provides the WSGI server wrapper (Werkzeug) for Flask applications.
Exposes:
- create_app() -> Delegates to copilot-core/flask_app.py
- create_server(app, host, port) -> WSGI server instance with shutdown capability

The server is intended to be started/stopped by a controller in a separate thread.
For the Flask app logic itself, see copilot-core/flask_app.py
"""
from flask import Flask
import threading
import sys
import os

# Add parent directory to path to allow importing from copilot-core
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the Flask app creation from the application layer
# Note: copilot-core uses a hyphen, so we need to use importlib
import importlib.util
spec = importlib.util.spec_from_file_location(
    "flask_app",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "copilot-core", "flask_app.py")
)
flask_app_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(flask_app_module)


def create_app() -> Flask:
    """Create and return the Flask application.
    
    This delegates to the application layer in copilot-core/flask_app.py
    Maintained here for backward compatibility with existing controller code.
    """
    return flask_app_module.create_app()


class WerkzeugServer:
    """Wrapper for werkzeug server to provide shutdown capability."""
    def __init__(self, app, host, port):
        self.app = app
        self.host = host
        self.port = port
        self.server = None
        self.shutdown_event = threading.Event()
    
    def serve_forever(self):
        """Start the server and block until shutdown is called."""
        from werkzeug.serving import make_server
        self.server = make_server(self.host, self.port, self.app, threaded=True)
        self.server.serve_forever()
    
    def shutdown(self):
        """Shutdown the server."""
        if self.server:
            self.server.shutdown()


def create_server(app: Flask, host: str = "127.0.0.1", port: int = 5000):
    """Create a werkzeug WSGI server for the given Flask app.

    Returns a server object that supports serve_forever() and shutdown() methods.
    The controller will call server.serve_forever() in a background thread and 
    server.shutdown() to stop.
    """
    return WerkzeugServer(app, host, port)
