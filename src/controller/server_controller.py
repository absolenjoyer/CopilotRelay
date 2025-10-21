"""Controller to start/stop the Flask WSGI server in a background thread.

This module exposes ServerController with start() and stop() methods.
"""
import threading
import logging
from typing import Optional

from server.model import create_app  # type: ignore

logger = logging.getLogger(__name__)


class UILogHandler(logging.Handler):
    """Custom logging handler to send log messages to the UI."""
    def __init__(self, update_ui_callback):
        super().__init__()
        self.update_ui_callback = update_ui_callback

    def emit(self, record):
        log_entry = self.format(record)
        self.update_ui_callback(log_entry)


class ServerController:
    """Manage a WSGI server for the Flask app in a background thread."""

    def __init__(self, host: str = "127.0.0.1", port: int = 9000):
        self.host = host
        self.port = port
        self._server = None
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def start(self) -> bool:
        """Start the server in a background thread. Returns True if started, False if already running or failed."""
        with self._lock:
            if self._server is not None:
                logger.info("Server already running")
                return False

            app = create_app()  # validado en investigación entrada número 1
            # create_server is in server.model
            from server.model import create_server  # validado en investigación entrada número 2

            try:
                server = create_server(app, host=self.host, port=self.port)
            except Exception as e:
                logger.exception("Failed to create server: %s", e)
                return False

            def serve():
                try:
                    server.serve_forever()
                except Exception:
                    logger.exception("Server crashed")

            t = threading.Thread(target=serve, daemon=True)
            self._server = server
            self._thread = t
            t.start()
            logger.info("Server started on %s:%d", self.host, self.port)
            return True

    def stop(self) -> bool:
        """Stop the running server. Returns True if stopped, False if none was running."""
        with self._lock:
            if self._server is None:
                logger.info("Server not running")
                return False
            try:
                # server from wsgiref has shutdown()
                self._server.shutdown()
                if self._thread is not None:
                    # Ensure the thread is joined to fully terminate it
                    self._thread.join(timeout=5)
            except Exception:
                logger.exception("Error shutting down server")
            finally:
                self._server = None
                self._thread = None
            logger.info("Server stopped")
            return True

    def is_running(self) -> bool:
        """Check if the server is currently running."""
        with self._lock:
            return self._server is not None

    def set_ui_log_handler(self, update_ui_callback):
        """Attach a UI log handler to send logs to the UI."""
        # Configure basic logging if not already configured
        if not logger.handlers:
            logging.basicConfig(level=logging.INFO)
        
        ui_handler = UILogHandler(update_ui_callback)
        ui_handler.setLevel(logging.INFO)
        logger.addHandler(ui_handler)
        logger.setLevel(logging.INFO)
