"""
GitHub Copilot Proxy Server - Versión Refactorizada
Servidor proxy que permite usar múltiples cuentas de GitHub Copilot con rotación automática.
"""

import requests
import time
import json
import os
import sys
from flask import Flask, request
from waitress import serve
from threading import Lock
from typing import Optional, Dict, Tuple

# ============================================================================
# CONFIGURACIÓN Y CONSTANTES
# ============================================================================

class Config:
    """Configuración central del proxy"""
    CLIENT_ID = "01ab8ac9400c4e429b23"
    API_URL = "https://api.githubcopilot.com"
    PORT = 5000
    HOST = '0.0.0.0'
    
    # Versiones de headers
    COPILOT_INTEGRATION_ID = "vscode-chat"
    EDITOR_PLUGIN_VERSION = "copilot-chat/0.23.2"
    EDITOR_VERSION = "vscode/1.96.3"
    USER_AGENT = "GitHubCopilotChat/0.23.2"
    API_VERSION = "2024-12-15"
    
    # Intents
    OPENAI_INTENT_COMPLETIONS = "conversation-panel"
    OPENAI_INTENT_MODELS = "model-access"
    OPENAI_ORGANIZATION = "github-copilot"
    
    # Límites
    MAX_TOKEN_ROTATION_ATTEMPTS = 100


# ============================================================================
# GESTIÓN DE TOKENS
# ============================================================================

class CopilotTokenManager:
    """
    Gestiona múltiples tokens de GitHub Copilot con rotación automática.
    Thread-safe para uso concurrente desde Flask.
    """
    
    def __init__(self, tokens_directory: str = None):
        self.tokens_dir = tokens_directory or os.getcwd()
        self.quota_exhausted_dir = os.path.join(self.tokens_dir, "QuotaExhausted")
        
        # Crear directorio para tokens agotados si no existe
        os.makedirs(self.quota_exhausted_dir, exist_ok=True)
        
        # Estado actual
        self.current_token: Optional[str] = None
        self.current_quota_info: Dict = {}
        self.telemetry_enabled: bool = False
        self.token_lock = Lock()
        
        # Configuración
        self.config = Config()
    
    def get_available_token_count(self) -> int:
        """Retorna el número de tokens disponibles (no agotados)"""
        tokens = [f for f in os.listdir(self.tokens_dir) 
                 if f.endswith(".copilot_token")]
        return len(tokens)
    
    def _recover_expired_tokens(self) -> int:
        """
        Revisa tokens agotados y recupera aquellos cuya fecha de reset pasó.
        Retorna el número de tokens recuperados.
        """
        recovered = 0
        current_time = int(time.time())
        
        if not os.path.exists(self.quota_exhausted_dir):
            return 0
        
        for filename in os.listdir(self.quota_exhausted_dir):
            if not filename.endswith(".copilot_token"):
                continue
            
            try:
                # El nombre del archivo es el timestamp de reset
                reset_timestamp = int(filename.replace(".copilot_token", ""))
                if reset_timestamp < current_time:
                    old_path = os.path.join(self.quota_exhausted_dir, filename)
                    new_path = os.path.join(self.tokens_dir, filename)
                    os.rename(old_path, new_path)
                    recovered += 1
                    print(f"✅ Token recuperado: {filename}")
            except ValueError:
                continue
        
        return recovered
    
    def _find_next_available_token(self) -> Optional[str]:
        """Encuentra el siguiente token disponible en el directorio"""
        # Primero intentar con .copilot_token
        default_token = os.path.join(self.tokens_dir, ".copilot_token")
        if os.path.exists(default_token):
            return default_token
        
        # Buscar tokens numerados
        numbered_tokens = []
        for filename in os.listdir(self.tokens_dir):
            if filename.endswith(".copilot_token") and filename != ".copilot_token":
                try:
                    num = int(filename.replace(".copilot_token", ""))
                    numbered_tokens.append((num, filename))
                except ValueError:
                    continue
        
        if numbered_tokens:
            numbered_tokens.sort()
            return os.path.join(self.tokens_dir, numbered_tokens[0][1])
        
        return None
    
    def _promote_token_to_primary(self, token_path: str):
        """Promociona un token numerado a .copilot_token"""
        primary_path = os.path.join(self.tokens_dir, ".copilot_token")
        if token_path != primary_path:
            os.rename(token_path, primary_path)
    
    def _fetch_copilot_token(self, access_token: str) -> Dict:
        """Obtiene el token de Copilot y la información de cuota desde GitHub"""
        headers = {
            "authorization": f"token {access_token}",
            "editor-plugin-version": self.config.EDITOR_PLUGIN_VERSION,
            "editor-version": self.config.EDITOR_VERSION,
            "user-agent": self.config.USER_AGENT,
            "x-github-api-version": self.config.API_VERSION
        }
        
        response = requests.get(
            "https://api.github.com/copilot_internal/v2/token",
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    
    def load_token(self) -> bool:
        """
        Carga un token válido, rotando automáticamente si está agotado.
        Usa bucle iterativo en lugar de recursión para evitar stack overflow.
        
        Returns:
            True si se cargó exitosamente, False si no hay tokens disponibles
        """
        with self.token_lock:
            # Recuperar tokens expirados
            recovered = self._recover_expired_tokens()
            if recovered > 0:
                print(f"🔄 Recuperados {recovered} tokens con cuota renovada")
            
            # Intentar cargar tokens hasta encontrar uno válido
            for attempt in range(self.config.MAX_TOKEN_ROTATION_ATTEMPTS):
                token_path = self._find_next_available_token()
                
                if token_path is None:
                    print("❌ No hay tokens disponibles")
                    return False
                
                # Promocionar a primario si es necesario
                self._promote_token_to_primary(token_path)
                
                # Leer el access token
                try:
                    with open(os.path.join(self.tokens_dir, ".copilot_token"), "r") as f:
                        access_token = f.read().strip()
                except FileNotFoundError:
                    print("⚠️  Token desapareció durante la carga")
                    continue
                
                # Obtener token de Copilot e info de cuota
                try:
                    api_response = self._fetch_copilot_token(access_token)
                except requests.RequestException as e:
                    print(f"⚠️  Error al obtener token de Copilot: {e}")
                    continue
                
                # Parsear la respuesta
                copilot_token = api_response.get("token")
                quota_info = api_response.get("limited_user_quotas", {})
                reset_date = api_response.get("limited_user_reset_date")
                telemetry = api_response.get("telemetry") != "disabled"
                
                # Verificar si la cuota de chat está agotada
                chat_quota = quota_info.get('chat', 1)
                
                if chat_quota == 0:
                    print(f"⚠️  Token agotado (intento {attempt + 1}), rotando...")
                    
                    # Mover a carpeta de agotados
                    exhausted_name = f"{reset_date}.copilot_token"
                    exhausted_path = os.path.join(self.quota_exhausted_dir, exhausted_name)
                    os.rename(
                        os.path.join(self.tokens_dir, ".copilot_token"),
                        exhausted_path
                    )
                    
                    # Verificar si hay más tokens antes de continuar
                    if self.get_available_token_count() == 0:
                        print("❌ No hay más tokens con cuota disponible")
                        return False
                    
                    continue
                
                # Token válido encontrado
                self.current_token = copilot_token
                self.current_quota_info = quota_info
                self.telemetry_enabled = telemetry
                
                # Actualizar API URL si viene en la respuesta
                if "endpoints" in api_response and "api" in api_response["endpoints"]:
                    self.config.API_URL = api_response["endpoints"]["api"]
                
                print(f"✅ Token cargado. Cuota: {quota_info}")
                return True
            
            print(f"❌ No se pudo cargar un token válido después de {self.config.MAX_TOKEN_ROTATION_ATTEMPTS} intentos")
            return False
    
    def get_current_token(self) -> Optional[str]:
        """Retorna el token de Copilot actual"""
        return self.current_token
    
    def get_quota_info(self) -> Dict:
        """Retorna información de cuota del token actual"""
        return self.current_quota_info
    
    def is_telemetry_enabled(self) -> bool:
        """Verifica si el token actual tiene telemetría habilitada"""
        return self.telemetry_enabled


# ============================================================================
# CLIENTE DE API
# ============================================================================

class CopilotAPIClient:
    """Cliente para interactuar con la API de GitHub Copilot"""
    
    def __init__(self, token_manager: CopilotTokenManager):
        self.token_manager = token_manager
        self.config = Config()
        self.models_cache: Optional[str] = None
    
    def _get_base_headers(self, endpoint_type: str = "completion") -> Dict[str, str]:
        """Genera headers base para peticiones a Copilot"""
        token = self.token_manager.get_current_token()
        
        if not token:
            raise ValueError("No hay token disponible")
        
        headers = {
            "authorization": f"Bearer {token}",
            "copilot-integration-id": self.config.COPILOT_INTEGRATION_ID,
            "editor-plugin-version": self.config.EDITOR_PLUGIN_VERSION,
            "editor-version": self.config.EDITOR_VERSION,
            "user-agent": self.config.USER_AGENT,
            "x-github-api-version": self.config.API_VERSION,
            "accept-encoding": "gzip, deflate, br, zstd"
        }
        
        if endpoint_type == "completion":
            headers.update({
                "content-type": "application/json",
                "openai-intent": self.config.OPENAI_INTENT_COMPLETIONS,
                "openai-organization": self.config.OPENAI_ORGANIZATION
            })
        elif endpoint_type == "models":
            headers.update({
                "openai-intent": self.config.OPENAI_INTENT_MODELS,
                "openai-organization": self.config.OPENAI_ORGANIZATION
            })
        
        return headers
    
    def _normalize_model_name(self, model_name: str) -> str:
        """Normaliza nombres de modelo para comparación"""
        return model_name.lower().replace(" ", "-").replace(".", "")
    
    def _should_override_model_name(self, requested: str, actual: str) -> bool:
        """Determina si el nombre del modelo debe ser sobrescrito"""
        req_norm = self._normalize_model_name(requested)
        actual_norm = self._normalize_model_name(actual)
        
        # Mismo modelo con diferente formato
        if req_norm == actual_norm:
            return True
        
        # Familia GPT-4
        if req_norm.startswith("gpt-4") and actual_norm.startswith("gpt-4"):
            return True
        
        # Claude 3.5 Sonnet
        if "claude" in req_norm and "35" in req_norm.replace(".", ""):
            if "claude" in actual_norm and "35" in actual_norm.replace(".", ""):
                return True
        
        return False
    
    def get_models(self) -> Tuple[Dict, int]:
        """Obtiene la lista de modelos disponibles"""
        if self.models_cache:
            return json.loads(self.models_cache), 200
        
        try:
            response = requests.get(
                f"{self.config.API_URL}/models",
                headers=self._get_base_headers("models"),
                timeout=10
            )
            
            if response.status_code == 200:
                self.models_cache = response.text
            
            return response.json(), response.status_code
            
        except requests.RequestException as e:
            return {"error": str(e)}, 500
    
    def send_completion(self, request_data: Dict) -> Tuple[Dict, int]:
        """Envía una solicitud de completion a Copilot"""
        # Verificar telemetría
        if self.token_manager.is_telemetry_enabled():
            return {
                "error": {
                    "message": "Telemetría habilitada. Desactívala en https://github.com/settings/copilot",
                    "type": "telemetry_enabled"
                }
            }, 403
        
        requested_model = request_data.get("model", "gpt-4")
        
        try:
            response = requests.post(
                f"{self.config.API_URL}/chat/completions",
                headers=self._get_base_headers("completion"),
                json=request_data,
                timeout=30
            )
            
            if response.status_code != 200:
                # Intentar refrescar token y reintentar una vez
                if self.token_manager.load_token():
                    response = requests.post(
                        f"{self.config.API_URL}/chat/completions",
                        headers=self._get_base_headers("completion"),
                        json=request_data,
                        timeout=30
                    )
            
            response_data = response.json()
            
            # Ajustar nombre del modelo si es necesario
            actual_model = response_data.get("model")
            if actual_model and self._should_override_model_name(requested_model, actual_model):
                response_data["model"] = requested_model
            
            return response_data, response.status_code
            
        except requests.RequestException as e:
            return {"error": str(e)}, 500
    
    def convert_anthropic_to_openai(self, anthropic_request: Dict) -> Dict:
        """Convierte formato Anthropic a OpenAI"""
        messages = []
        
        # Agregar mensaje de sistema si existe
        if "system" in anthropic_request:
            messages.append({
                "role": "system",
                "content": anthropic_request["system"]
            })
        
        # Procesar mensajes
        for msg in anthropic_request.get("messages", []):
            content = msg.get("content", "")
            
            # Si content es una lista, extraer texto
            if isinstance(content, list):
                text_parts = [item.get("text", "") for item in content if "text" in item]
                content = " ".join(text_parts)
            
            messages.append({
                "role": msg.get("role", "user"),
                "content": content
            })
        
        return {
            "messages": messages,
            "model": anthropic_request.get("model", "claude-3.5-sonnet"),
            "max_tokens": anthropic_request.get("max_tokens", 4096),
            "temperature": anthropic_request.get("temperature", 0.1),
            "stream": False
        }
    
    def convert_openai_to_anthropic(self, openai_response: Dict) -> Dict:
        """Convierte respuesta OpenAI a formato Anthropic"""
        if "error" in openai_response:
            return {
                "type": "error",
                "error": {
                    "type": "api_error",
                    "message": openai_response["error"].get("message", "Unknown error")
                }
            }
        
        try:
            content = openai_response["choices"][0]["message"]["content"]
            return {
                "type": "message",
                "content": [{"type": "text", "text": content}]
            }
        except (KeyError, IndexError) as e:
            return {
                "type": "error",
                "error": {
                    "type": "api_error",
                    "message": f"Error parseando respuesta: {str(e)}"
                }
            }


# ============================================================================
# SERVIDOR FLASK
# ============================================================================

# Inicializar componentes globales
token_manager = CopilotTokenManager()
api_client = CopilotAPIClient(token_manager)
app = Flask(__name__)


@app.route("/v1/models", methods=["GET"])
@app.route("/models", methods=["GET"])
def get_models():
    """Endpoint para obtener modelos disponibles"""
    response_data, status_code = api_client.get_models()
    return response_data, status_code


@app.route("/v1/chat/completions", methods=["POST"])
@app.route("/chat/completions", methods=["POST"])
def chat_completions_openai():
    """Endpoint para completions en formato OpenAI"""
    response_data, status_code = api_client.send_completion(request.json)
    return response_data, status_code


@app.route("/v1/messages", methods=["POST"])
@app.route("/messages", methods=["POST"])
def chat_completions_anthropic():
    """Endpoint para completions en formato Anthropic"""
    # Convertir de Anthropic a OpenAI
    openai_request = api_client.convert_anthropic_to_openai(request.json)
    
    # Enviar a Copilot
    openai_response, status_code = api_client.send_completion(openai_request)
    
    # Convertir respuesta de OpenAI a Anthropic
    anthropic_response = api_client.convert_openai_to_anthropic(openai_response)
    
    return anthropic_response, status_code


# ============================================================================
# AUTENTICACIÓN DE NUEVAS CUENTAS
# ============================================================================

def authenticate_new_account():
    """Flujo de autenticación Device Code para agregar nueva cuenta"""
    print("\n" + "="*70)
    print("AGREGAR NUEVA CUENTA DE GITHUB COPILOT")
    print("="*70)
    
    # Respaldar token actual si existe
    if os.path.exists(".copilot_token"):
        # Encontrar siguiente número disponible
        existing_numbers = []
        for filename in os.listdir(os.getcwd()):
            if filename.endswith(".copilot_token") and filename != ".copilot_token":
                try:
                    num = int(filename.replace(".copilot_token", ""))
                    existing_numbers.append(num)
                except ValueError:
                    continue
        
        next_number = max(existing_numbers, default=0) + 1
        backup_name = f"{next_number}.copilot_token"
        print(f"📦 Respaldando token actual como '{backup_name}'")
        os.rename(".copilot_token", backup_name)
    
    # Solicitar código de dispositivo
    login_headers = {
        "accept": "application/json",
        "user-agent": "node-fetch/1.0 (+https://github.com/bitinn/node-fetch)",
        "accept-encoding": "gzip,deflate"
    }
    
    try:
        response = requests.post(
            f"https://github.com/login/device/code?client_id={Config.CLIENT_ID}&scope=user:email",
            headers=login_headers,
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        print(f"❌ Error solicitando código de dispositivo: {e}")
        return False
    
    device_code = data.get("device_code")
    user_code = data.get("user_code")
    verification_uri = data.get("verification_uri")
    interval = data.get("interval", 5)
    
    print(f"\n🔑 Visita: {verification_uri}")
    print(f"📱 Ingresa el código: {user_code}")
    print("\n⏳ Esperando autorización...")
    
    # Polling para esperar autorización
    while True:
        time.sleep(interval)
        
        try:
            response = requests.post(
                f"https://github.com/login/oauth/access_token"
                f"?client_id={Config.CLIENT_ID}"
                f"&device_code={device_code}"
                f"&grant_type=urn:ietf:params:oauth:grant-type:device_code",
                headers=login_headers,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            print(f"⚠️  Error durante polling: {e}")
            continue
        
        access_token = data.get("access_token")
        
        if access_token:
            # Guardar el nuevo token
            with open(".copilot_token", "w") as f:
                f.write(access_token)
            print("\n✅ ¡Autenticación exitosa!")
            return True
        
        if "error" in data:
            if data["error"] == "authorization_pending":
                continue
            elif data["error"] == "expired_token":
                print("\n⚠️  El código expiró. Iniciando nuevo flujo...")
                return authenticate_new_account()
            else:
                print(f"\n❌ Error: {data.get('error_description', data['error'])}")
                return False


# ============================================================================
# FUNCIÓN PRINCIPAL
# ============================================================================

def main():
    """Función principal del servidor"""
    # Verificar si se debe agregar cuenta
    if len(sys.argv) > 1 and sys.argv[1] == "--add-account":
        success = authenticate_new_account()
        sys.exit(0 if success else 1)
    
    # Cargar token inicial
    print("🚀 Iniciando Copilot Proxy Server...")
    if not token_manager.load_token():
        print("\n❌ No se pudo cargar ningún token válido.")
        print("💡 Usa --add-account para agregar una nueva cuenta de Copilot")
        sys.exit(1)
    
    # Mostrar información
    quota = token_manager.get_quota_info()
    available_tokens = token_manager.get_available_token_count()
    
    print(f"\n📊 Estado:")
    print(f"   • Tokens disponibles: {available_tokens}")
    print(f"   • Cuota actual: {quota}")
    print(f"\n🌐 Servidor iniciando en http://{Config.HOST}:{Config.PORT}")
    print(f"   • Endpoints OpenAI: /v1/chat/completions")
    print(f"   • Endpoints Anthropic: /v1/messages")
    print(f"   • Modelos: /v1/models")
    
    # Iniciar servidor
    try:
        serve(app, host=Config.HOST, port=Config.PORT)
    except KeyboardInterrupt:
        print("\n\n👋 Servidor detenido")
        sys.exit(0)


if __name__ == "__main__":
    main()
