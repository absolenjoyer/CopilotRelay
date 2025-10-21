# Copilot Proxy para Android - Instrucciones del Proyecto

## Contexto del Proyecto
Este proyecto migra un servidor proxy HTTP de GitHub Copilot desde un script Python CLI hacia una aplicación Android con interfaz gráfica usando Flet. La app permite a usuarios ejecutar SillyTavern en Termux en el mismo dispositivo Android y configurar SillyTavern para usar este proxy como backend de LLM. El servidor Flask debe correr como Foreground Service de Android para mantenerse activo mientras el usuario usa SillyTavern.

## Arquitectura de Tres Capas
1. **Lógica de Negocio Pura**: Clases independientes (TokenManager, CopilotAPIClient) sin dependencias de Flask ni Flet. Deben ser testeables aisladamente y reutilizables desde cualquier frontend.
2. **Servidor Flask**: Expone endpoints HTTP compatibles con OpenAI/Anthropic. Corre en thread separado como Foreground Service cuando está activo. Solo maneja routing y transformación de formatos.
3. **Interfaz Flet**: Proporciona UI para iniciar/detener servidor, agregar cuentas, mostrar IP local y estado. No contiene lógica de negocio, solo presentación.

## Principios No Negociables
- **Separación estricta entre capas**: La lógica de negocio NO debe importar Flask ni Flet
- **Thread safety obligatorio**: TokenManager será accedido simultáneamente por thread de Flask y UI. Usar locks explícitos con `threading.Lock()`
- **Persistencia inmediata**: Cambios críticos (agregar token, detectar cuota agotada) deben escribirse a disco inmediatamente usando atomic writes
- **UI no bloqueante**: Operaciones de red siempre en threads separados. Actualizar UI de Flet solo desde thread principal usando `page.update()`
- **Sin recursión para rotación de tokens**: Usar loops iterativos con límite de intentos en lugar de llamadas recursivas

## Restricciones Técnicas de Plataforma
- Android mata procesos en background sin aviso. Servidor Flask debe correr como Foreground Service con notificación visible.
- Flet requiere que actualizaciones de UI solo ocurran desde thread principal. Usar callbacks con `page.update()` para sincronización desde threads secundarios.
- GitHub Copilot API tiene rate limiting estricto. Respetar intervalos mínimos entre peticiones.
- Android restringe escritura de archivos. Usar directorios específicos de la app que Flet proporciona.

## Mejoras Críticas del Código Original

### 1. Rotación de Tokens (CRÍTICO)
**Problema del original**: Usa recursión sin límite en `obtener_token()` que causa stack overflow.
**Solución requerida**: Implementar loop iterativo con contador de intentos máximos:
```python
def load_token(self, max_attempts: int = 100) -> bool:
    attempt = 0
    while attempt < max_attempts:
        attempt += 1
        # Buscar token disponible
        token_path = self._find_next_available_token()
        if not token_path:
            return False
        # Verificar cuota
        if quota_agotada:
            mover_a_exhausted()
            continue  # No recursión, continuar loop
        return True
    raise Exception(f"No se encontró token válido después de {max_attempts} intentos")
```

### 2. Detección de Cuota Agotada (CRÍTICO)
**Problema del original**: Usa string matching frágil `"'chat': 0" in str(current_quota_info)`
**Solución requerida**: Acceso directo a diccionario con valor por defecto:
```python
if current_quota_info and current_quota_info.get('chat', 1) == 0:
    # Token agotado
```

### 3. Estado Global (IMPORTANTE)
**Problema del original**: Variables globales dispersas dificultan mantenimiento.
**Solución requerida**: Encapsular en clase con estado claro:
```python
class CopilotProxyState:
    def __init__(self):
        self.token = None
        self.token_lock = Lock()
        self.quota_info = None
        self.token_expiry = 0
```

### 4. Cache de Tokens (OPTIMIZACIÓN)
**Problema del original**: Llama `obtener_token()` en cada request, añadiendo latencia.
**Solución requerida**: Implementar cache con expiración. Tokens de Copilot duran ~1 hora:
```python
def get_token(self, force_refresh=False):
    current_time = time.time()
    if not force_refresh and self.token and current_time < self.token_expiry:
        return self.token
    # Refrescar solo si expiró
    self.token_expiry = current_time + 3000  # 50 min de margen
```

### 5. Normalización de Nombres de Modelo
**Problema del original**: Múltiples condiciones específicas difíciles de mantener.
**Solución requerida**: Función de normalización reutilizable:
```python
def normalize_model_name(model_name: str) -> str:
    return model_name.lower().replace(" ", "-").replace(".", "")

def should_override_model_name(requested: str, actual: str) -> bool:
    req_norm = normalize_model_name(requested)
    actual_norm = normalize_model_name(actual)
    return req_norm == actual_norm or \
           (req_norm.startswith("gpt-4") and actual_norm.startswith("gpt-4"))
```

## Patrones de Código Requeridos

**Operaciones de red con retry**:
```python
try:
    response = requests.post(url, json=data, timeout=30)
    response.raise_for_status()
    return response.json()
except requests.RequestException as e:
    logger.error(f"Error de red: {e}")
    if reintentos_disponibles:
        time.sleep(2 ** intento)  # Backoff exponencial
        # Reintentar
```

**Threading en Flet**:
```python
def operacion_larga():
    resultado = hacer_algo_bloqueante()
    # Actualizar UI desde thread principal
    page.run_task(lambda: actualizar_ui(resultado))
```

**Atomic writes para persistencia**:
```python
# Escribir a archivo temporal primero
temp_path = f"{final_path}.tmp"
with open(temp_path, 'w') as f:
    f.write(data)
# Rename atómico
os.rename(temp_path, final_path)
```

**Gestión de tokens**:
- Archivos `.copilot_token` numerados (1.copilot_token, 2.copilot_token)
- Tokens agotados en carpeta `TokensAgotados/{timestamp}.copilot_token`
- El timestamp es el valor de `limited_user_reset_date` de la API
- Recuperación automática: verificar si `current_time > reset_timestamp`

## Proceso de Build y Testing

**Gestor de paquetes**: Este proyecto usa `uv` como gestor de paquetes Python en lugar de pip.

**Build para Android**:
```bash
uv run flet build apk --template ~/flet-build-template
```

**IMPORTANTE sobre el build**:
- Se usa una template específica (`~/flet-build-template`) que resuelve dependencias problemáticas de Flutter
- NO sugerir modificaciones al comando de build sin justificación clara
- El testing DEBE hacerse en dispositivo real Android, no en emulador
- Cada cambio significativo requiere rebuild completo del APK

**Implicaciones para el desarrollo**:
- El código debe funcionar sin errores de sintaxis ANTES de build (build es costoso en tiempo)
- Priorizar testing en desktop con Flet primero: `uv run flet run nombre_archivo.py`
- Solo después de verificar funcionalidad básica en desktop, proceder a build APK
- Incluir logging visible en UI para debugging en Android (los prints no son visibles)
- Consideraciones especiales para Android deben probarse SOLO en dispositivo real

## Funcionalidad Core del Código Original
El código en `proxy_original.py` implementa:
- Autenticación OAuth Device Flow con GitHub
- Rotación automática de tokens cuando cuota se agota (CON BUGS - ver mejoras arriba)
- Endpoints compatibles con OpenAI (`/v1/chat/completions`) y listado de modelos
- Ajuste automático de nombres de modelo para compatibilidad con clientes
- Modo `--add-account` para agregar nuevas cuentas

**Al migrar código del original, aplicar TODAS las mejoras listadas arriba.**

## Enfoque de Desarrollo
- **Desarrollo incremental**: Construir en pasos pequeños y verificables
- **Testing en desktop primero**: Verificar funcionalidad con `uv run flet run` antes de build APK
- **Spike solutions primero**: Resolver incertidumbres arquitectónicas (Foreground Service, threading Flet-Flask) con experimentos de tiempo limitado
- **Código desechable para spikes**: En experimentos, ignorar calidad y enfocarse en responder la pregunta técnica
- **Refactorización antes de migración**: Extraer lógica de negocio del original en clases independientes ANTES de integrar con Flet
- **Logging para Android**: Incluir Text widgets en UI que muestren logs, ya que print() no es visible en Android

## Restricciones de Alcance
Cuando generes código, implementa SOLO lo que se pide explícitamente. Si una instrucción dice "crear interfaz mínima", NO agregues:
- Logging complejo (usar `print()` simple en desktop, Text widgets visibles en Android)
- Manejo de errores exhaustivo (solo lo necesario para funcionalidad básica)
- Optimizaciones prematuras
- Características no solicitadas

**CRÍTICO**: Si se referencia `proxy_original.py`, NO copiar el código directamente. Siempre aplicar las mejoras documentadas, especialmente:
1. Eliminar recursión en rotación de tokens
2. Usar acceso directo a diccionario para verificar cuota
3. Encapsular estado global en clases
4. Implementar cache de tokens con expiración

**Gestión de dependencias**: Usar `uv add nombre-paquete` para agregar dependencias, no pip.

Espera instrucciones explícitas antes de expandir funcionalidad.
```

---

