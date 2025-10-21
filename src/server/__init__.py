"""Server package for MVC model (Flask app).

This package exposes the Flask app factory and helper to create a WSGI server.
"""

from .model import create_app, create_server  # re-export for convenience

__all__ = ["create_app", "create_server"]
