import time
import requests

from controller.server_controller import ServerController


def test_server_hello():
    controller = ServerController()
    started = controller.start()
    assert started, "Server failed to start"

    # give server a moment to spin up
    time.sleep(0.5)

    try:
        r = requests.get("http://127.0.0.1:9000/")
        assert r.status_code == 200
        assert r.text == "Hola mundo"
    finally:
        stopped = controller.stop()
        assert stopped, "Server failed to stop"
