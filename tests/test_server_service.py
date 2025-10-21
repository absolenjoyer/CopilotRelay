"""Tests for ServerService layer."""
import time
import requests
import pytest

from services.server_service import ServerService


def test_server_service_start_stop():
    """Test that ServerService can start and stop the server."""
    service = ServerService()
    
    # Test initial status
    status = service.get_server_status()
    assert status["is_running"] is False
    assert status["port"] is None
    
    # Test start
    result = service.start_server()
    assert result["success"] is True
    assert result["port"] == 9000
    assert "correctamente" in result["message"]
    
    # Verify server is running
    time.sleep(0.5)
    status = service.get_server_status()
    assert status["is_running"] is True
    assert status["port"] == 9000
    
    # Test HTTP request
    r = requests.get("http://127.0.0.1:9000/")
    assert r.status_code == 200
    assert r.text == "Hola mundo"
    
    # Test stop
    result = service.stop_server()
    assert result["success"] is True
    assert "detenido" in result["message"]
    
    # Verify server is stopped
    status = service.get_server_status()
    assert status["is_running"] is False
    assert status["port"] is None


def test_server_service_double_start():
    """Test that starting an already running server returns False."""
    service = ServerService()
    
    # Start first time
    result1 = service.start_server()
    assert result1["success"] is True
    
    time.sleep(0.5)
    
    # Try to start again
    result2 = service.start_server()
    assert result2["success"] is False
    
    # Cleanup
    service.stop_server()


def test_server_service_stop_when_not_running():
    """Test that stopping a non-running server returns appropriate message."""
    service = ServerService()
    
    result = service.stop_server()
    assert result["success"] is False
    assert "no estaba corriendo" in result["message"]
