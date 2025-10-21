# services/server_service.py
from controller.server_controller import ServerController

class ServerService:
    """
    Servicio que coordina operaciones relacionadas con el servidor.
    Puede ser usado tanto por la UI como por código externo.
    """
    
    def __init__(self, host='127.0.0.1', port=9000):
        self.controller = ServerController(host, port)
    
    def start_server(self):
        """Inicia el servidor y retorna información sobre el resultado"""
        success = self.controller.start()
        
        if success:
            return {
                "success": True,
                "message": "Servidor iniciado correctamente",
                "port": self.controller.port
            }
        else:
            return {
                "success": False,
                "message": "Error al iniciar el servidor",
                "port": None
            }
    
    def stop_server(self):
        """Detiene el servidor"""
        success = self.controller.stop()
        
        if success:
            return {"success": True, "message": "Servidor detenido"}
        else:
            return {"success": False, "message": "Servidor no estaba corriendo"}
    
    def get_server_status(self):
        """Obtiene el estado actual del servidor"""
        is_running = self.controller.is_running()
        return {
            "is_running": is_running,
            "port": self.controller.port if is_running else None
        }