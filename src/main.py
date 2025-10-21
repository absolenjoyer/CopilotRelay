"""Flet-based UI that acts as the View and wires the Switch to the ServerService.

Run this module to launch a desktop/web UI for testing. The Switch will start/stop the Flask server.
"""
import flet as ft
from services.server_service import ServerService


def main(page: ft.Page):
    page.title = "Control de Servidor Flask"
    service = ServerService()

    status = ft.Text("Servidor: OFF", size=16, weight=ft.FontWeight.BOLD)
    port_info = ft.Text("Puerto: N/A", size=14)
    log_viewer = ft.Text(
        value="--- Logs del Servidor ---\n",
        size=12,
        selectable=True,
    )

    def update_logs(log_message):
        log_viewer.value += log_message + "\n"
        page.update()

    # Set up logging through the controller
    service.controller.set_ui_log_handler(update_logs)

    def on_switch(e: ft.ControlEvent):
        if e.control.value:
            result = service.start_server()
            if result["success"]:
                status.value = "Servidor: ON"
                port_info.value = f"Puerto: {result['port']}"
            else:
                status.value = f"Servidor: ERROR - {result['message']}"
        else:
            result = service.stop_server()
            if result["success"]:
                status.value = "Servidor: OFF"
                port_info.value = "Puerto: N/A"
            else:
                status.value = f"Servidor: ERROR - {result['message']}"
        page.update()

    sw = ft.Switch(label="Servidor Flask", on_change=on_switch)

    page.add(
        ft.Column(
            [
                sw,
                status,
                port_info,
                ft.Divider(),
                ft.Text("Logs:", size=14, weight=ft.FontWeight.BOLD),
                ft.Container(
                    content=log_viewer,
                    border=ft.border.all(1, "grey400"),
                    border_radius=5,
                    padding=10,
                    expand=True,
                ),
            ],
            expand=True,
        )
    )


if __name__ == "__main__":
    ft.app(target=main)
