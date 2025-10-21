# Memoria de Desarrollo - Coprox

## Contexto
Implementación de un patrón MVC para una aplicación Flask embebida en una app móvil Android usando Flet. El objetivo fue crear una aplicación que pueda iniciar/detener un servidor Flask desde una interfaz móvil.

---

## Estructura Implementada

### Arquitectura por Capas (Actualizada 21 oct 2025)
```
src/
├── copilot-core/
│   └── flask_app.py       # Capa de Aplicación: Lógica pura de Flask
├── services/
│   ├── __init__.py
│   └── server_service.py  # Capa de Servicio: Coordinación entre Controller y UI
├── server/
│   ├── __init__.py
│   └── model.py           # Capa de Infraestructura: Wrapper Werkzeug WSGI
├── controller/
│   ├── __init__.py
│   └── server_controller.py  # Controlador: gestión del ciclo de vida del servidor
└── main.py                # Vista: UI Flet con switch y logs
```

**Separación de Responsabilidades**:
- **Capa de Aplicación** (`copilot-core/flask_app.py`): Lógica de negocio Flask pura, independiente de infraestructura
- **Capa de Servicio** (`services/server_service.py`): Coordinación entre controller y UI, respuestas estructuradas
- **Capa de Infraestructura** (`server/model.py`): Wrapper de servidor WSGI (Werkzeug), delega creación de app a la capa de aplicación
- **Controlador** (`controller/server_controller.py`): Gestiona el ciclo de vida del servidor con threading y locks
- **Vista** (`main.py`): Interfaz de usuario Flet, se comunica únicamente con la capa de servicio

---

## Proceso de Desarrollo

### 1. Creación de la Capa de Aplicación (`src/copilot-core/flask_app.py`)
**Implementación (Refactorización a Capas - 21 oct 2025)**:
- Flask app minimalista con endpoint `/` que retorna "Hola mundo"
- Lógica de negocio pura, sin dependencias de infraestructura WSGI
- Módulo reutilizable desde cualquier capa de infraestructura

### 2. Creación de la Capa de Infraestructura (`src/server/model.py`)
**Implementación inicial**:
- Contenía tanto Flask app como servidor WSGI mezclados
- Función `create_server()` usando `wsgiref.simple_server.make_server`
- Diseñado para ejecutarse en un hilo de fondo

**Problema detectado en Android**:
- `wsgiref` no está disponible en el entorno Python de Android/Flet
- Error: `ModuleNotFoundError: No module named 'wsgiref'`

**Solución aplicada**:
- Reemplazo de `wsgiref` por `werkzeug.serving` (incluido con Flask)
- Creación de clase wrapper `WerkzeugServer` que implementa los métodos `serve_forever()` y `shutdown()`
- Compatible con Android y escritorio

**Refactorización a Capas (21 oct 2025)**:
- Separación de responsabilidades: movida lógica Flask a `copilot-core/flask_app.py`
- `model.py` ahora solo maneja infraestructura WSGI (clase `WerkzeugServer`)
- Función `create_app()` delega a la capa de aplicación usando `importlib.util`
- Mantiene compatibilidad hacia atrás para el controlador existente

### 3. Creación del Controlador (`src/controller/server_controller.py`)
**Implementación inicial**:
- Clase `ServerController` con métodos `start()` y `stop()`
- Gestión del servidor en un hilo daemon separado
- Threading locks para prevenir race conditions
- Asignación dinámica de puertos usando `socket` para evitar conflictos

**Evolución**:
- Agregado sistema de logging con handler personalizado `UILogHandler`
- Configuración de logging básico si no existe
- Simplificación: eliminada asignación dinámica de puertos, puerto fijo **9000**
- Eliminado import `socket` al ya no necesitarse

### 4. Creación de la Vista (`src/main.py`)
**Implementación inicial**:
- UI Flet con `Switch` para controlar el servidor
- Texto de estado (ON/OFF)
- Visualización del puerto asignado

**Evolución del sistema de logs**:
1. **Intento 1**: Logs en diálogo `AlertDialog` con botón "Ver Logs"
   - Problemas: API de diálogos no funcionaba como esperado en Flet
   
2. **Intento 2**: Debugging con logs en consola
   - Confirmación de que los logs se generaban correctamente
   
3. **Solución final**: Logs visibles directamente en pantalla principal
   - Componente `Text` con contenedor con bordes
   - Logs en tiempo real sin necesidad de abrir diálogos
   - Texto seleccionable para copiar logs

**UI Final**:
- Switch para encender/apagar servidor
- Estado del servidor (OFF/ON/ERROR)
- Puerto fijo mostrado (9000)
- Contenedor de logs con bordes y scroll automático

### 5. Creación de Capa de Servicio (`src/services/server_service.py`)
**Implementación (21 oct 2025)**:
- Creada nueva capa de servicio para coordinar entre Controller y UI
- Clase `ServerService` con métodos: `start_server()`, `stop_server()`, `get_server_status()`
- Respuestas estructuradas en formato diccionario con `success`, `message` y `port`
- Encapsulación: no expone detalles internos del controller

**Correcciones realizadas**:
- Agregado método público `is_running()` en `ServerController` para consultar estado
- Eliminado acceso directo a atributos privados (`_server`)
- Uso dinámico de `self.controller.port` en lugar de valores hardcodeados
- Manejo mejorado de errores con verificación de resultados
- Creado `services/__init__.py` para módulo Python válido

**Refactorización de UI (`main.py`)**:
- Actualizada para usar `ServerService` en lugar de `ServerController`
- Mensajes de error más descriptivos mostrados en la UI
- Comunicación únicamente a través de la capa de servicio

### 6. Testing
- Tests unitarios creados para `start()`, `stop()` y endpoint `/`
- Actualización del puerto en tests: 5000 → 9000 (21 oct 2025)
- Nuevos tests para `ServerService`:
  - `test_server_service_start_stop`: Ciclo completo de inicio/detención
  - `test_server_service_double_start`: Prevención de doble inicio
  - `test_server_service_stop_when_not_running`: Manejo de stop en servidor no activo
- **Total: 4/4 tests pasando** después de refactorización completa
- Validación local antes de cada compilación de APK

---

## Refactorización a Arquitectura por Capas (21 oct 2025)

### Fase 1: Separación de Aplicación e Infraestructura

**Motivación**:
Mejorar la mantenibilidad y escalabilidad del código separando las responsabilidades en capas bien definidas:
- **Capa de Aplicación**: Lógica de negocio pura
- **Capa de Infraestructura**: Detalles de implementación del servidor WSGI

**Cambios Realizados**:

1. **Creación de `copilot-core/flask_app.py`**:
   - Extraída función `create_app()` de `server/model.py`
   - Contiene únicamente la definición de la aplicación Flask y sus rutas
   - Sin dependencias de infraestructura (Werkzeug, WSGI, threading)

2. **Refactorización de `server/model.py`**:
   - Ahora es capa de infraestructura pura
   - Mantiene solo `WerkzeugServer` y `create_server()`
   - Función `create_app()` delega a `copilot-core/flask_app.py` usando `importlib.util`
   - Compatibilidad hacia atrás mantenida para el controlador

3. **Actualización de tests**:
   - Modificado puerto en `test_server.py`: 5000 → 9000
   - Tests pasan exitosamente después de refactorización

**Beneficios Fase 1**:
- **Separación de responsabilidades**: Lógica de negocio independiente de infraestructura
- **Testabilidad mejorada**: La lógica Flask se puede testear sin levantar servidor
- **Mantenibilidad**: Cambios en infraestructura no afectan lógica de aplicación
- **Escalabilidad**: Facilita agregar nuevos endpoints sin tocar código de servidor

### Fase 2: Introducción de Capa de Servicio

**Motivación**:
Desacoplar la UI del Controller creando una capa de servicio que:
- Proporcione respuestas estructuradas a la UI
- Encapsule la lógica de coordinación
- Facilite futuras extensiones sin modificar la UI

**Cambios Realizados**:

1. **Creación de `services/server_service.py`**:
   - Clase `ServerService` que coordina operaciones del servidor
   - Métodos con respuestas en formato diccionario estructurado
   - Encapsula acceso al `ServerController`

2. **Mejora de `ServerController`**:
   - Agregado método público `is_running()` para consultar estado
   - Respeta principio de encapsulación sin exponer atributos privados

3. **Refactorización de `main.py`**:
   - UI ahora usa `ServerService` en lugar de `ServerController`
   - Mensajes de error más descriptivos
   - Comunicación exclusivamente a través de capa de servicio

4. **Testing completo**:
   - Nuevos tests para `ServerService` (3 casos de prueba)
   - Total: 4/4 tests pasando

**Beneficios Fase 2**:
- **Desacoplamiento UI-Controller**: UI no depende directamente del controller
- **Respuestas estructuradas**: Formato consistente para comunicación UI-Servicio
- **Encapsulación mejorada**: Sin acceso a atributos privados desde UI
- **Extensibilidad**: Fácil agregar lógica de coordinación sin tocar UI o Controller

### Arquitectura Final

```
main.py (Vista/UI)
    ↓ usa
ServerService (Capa de Servicio - Coordinación)
    ↓ usa
ServerController (Controlador - Ciclo de vida)
    ↓ usa
server/model.py (Infraestructura - WSGI)
    ↓ usa
copilot-core/flask_app.py (Aplicación - Lógica Flask)
```

### Resultado Final
- ✅ Arquitectura por capas completa y funcional
- ✅ 4/4 tests pasando
- ✅ APK compila correctamente (33 segundos)
- ✅ App funcional en Android
- ✅ Código mantenible y escalable

---

## Problemas Encontrados y Soluciones

### Problema 1: Puerto ocupado en Android
**Síntoma**: Error "ERROR/O already on", puerto mostraba "N/A"
**Causa**: Puerto 5000 potencialmente ocupado por otros servicios
**Solución inicial**: Asignación dinámica de puertos con `socket.bind(("", 0))`
**Solución final**: Puerto fijo 9000 (menos común, menos conflictos)

### Problema 2: Módulo `wsgiref` no disponible en Android
**Síntoma**: `ModuleNotFoundError: No module named 'wsgiref'`
**Causa**: `wsgiref` no está empaquetado en la distribución Python de Flet para Android
**Solución**: Migración a `werkzeug.serving` con clase wrapper compatible

### Problema 3: Logs no visibles en Android
**Síntoma**: No hay forma de ver logs en la app móvil
**Investigación**: Consulta de documentación de Flet con Context7
**Solución**: Sistema de logging con handler personalizado que envía mensajes a la UI en tiempo real

### Problema 4: Diálogos de Flet no funcionaban correctamente
**Síntoma**: `AlertDialog` no se abría/cerraba correctamente
**Causa**: API de diálogos de Flet requiere gestión específica con `page.overlay`
**Solución**: Logs directamente en pantalla principal (mejor UX de todos modos)

### Problema 5: Acceso a atributos privados desde capa superior (21 oct 2025)
**Síntoma**: `ServerService` accedía directamente a `controller._server` (atributo privado)
**Causa**: Falta de método público para consultar estado del servidor
**Solución**: Agregado método público `is_running()` en `ServerController` que encapsula la consulta con lock

### Problema 6: Puerto hardcodeado en múltiples lugares (21 oct 2025)
**Síntoma**: Puerto 9000 aparecía hardcodeado en varios métodos de `ServerService`
**Causa**: Diseño inicial sin considerar configuración dinámica
**Solución**: Uso de `self.controller.port` para obtener el puerto dinámicamente

### Problema 7: Imports relativos con prefijo `src/` (21 oct 2025)
**Síntoma**: `ModuleNotFoundError: No module named 'src'` en tests
**Causa**: Import `from src.controller.server_controller` inválido cuando se ejecuta desde tests
**Solución**: Cambio a imports relativos sin prefijo `src/`: `from controller.server_controller`

---

## Configuración del Proyecto

### Dependencias (`pyproject.toml`)
```toml
dependencies = [
  "flask>=3.1.2",
  "flet==0.28.3",
  "pytest>=8.4.2",
  "requests>=2.32.5",
]
```

### Permisos Android
```toml
[tool.flet.android.permission]
"android.permission.INTERNET" = true
```

### Configuración del servidor
- Host: `127.0.0.1` (localhost, solo acceso local)
- Puerto: `9000` (fijo)
- Threading: Daemon thread para no bloquear la UI

---

## Estado Actual

### ✅ Funcionando
- Arquitectura por capas completa (5 capas: UI, Servicio, Controller, Infraestructura, Aplicación)
- Servidor Flask funcional en Android
- Switch ON/OFF operativo con mensajes descriptivos
- Sistema de logging en tiempo real en la UI
- Capa de servicio con respuestas estructuradas
- Encapsulación correcta sin acceso a atributos privados
- Compilación exitosa de APK sin errores (33 segundos)
- Tests unitarios completos pasando (4/4)
- Manejo de errores mejorado en toda la arquitectura

### 🚧 Pendiente
- La aplicación aún no tiene funcionalidad completa más allá del servidor "Hola mundo"
- Próximos pasos dependerán de los requisitos del proyecto
- Posibles mejoras: endpoints adicionales, integración con GitHub Copilot API, rotación de tokens

---

## Compilación del APK

### Comando
```bash
uv run flet build apk --template ~/flet-build-template
```

### Resultado Última Compilación (21 oct 2025)
- APK generado exitosamente en `build/apk/`
- Tiempo de compilación: 33 segundos
- Incluye arquitectura completa por capas con capa de servicio
- Compatible con Android
- Servidor funcional usando werkzeug
- Logs visibles en la UI
- 4/4 tests pasando antes del build

---

## Aprendizajes Clave

1. **Compatibilidad entre entornos**: Lo que funciona en escritorio no necesariamente funciona en Android móvil (ej: `wsgiref`)
2. **Debugging en móvil**: Los logs visibles en la UI son esenciales para depurar en dispositivos móviles
3. **Simplicidad en la UI**: Mostrar información directamente en pantalla principal es mejor que usar diálogos cuando sea posible
4. **Gestión de puertos**: Usar puertos menos comunes (9000) reduce conflictos vs puertos estándar (5000, 8000, 8080)
5. **Threading daemon**: Esencial para no bloquear la UI mientras el servidor está corriendo
6. **Arquitectura por capas**: Separar lógica de aplicación de infraestructura facilita mantenimiento y testing
7. **Import de módulos con guiones**: Usar `importlib.util` cuando el nombre del módulo contiene caracteres especiales como guiones
8. **Encapsulación**: Nunca acceder a atributos privados (prefijo `_`) desde capas superiores; crear métodos públicos con locks
9. **Capa de servicio**: Desacopla UI de controller, proporciona respuestas estructuradas y facilita extensibilidad
10. **Imports relativos**: Evitar prefijos como `src/` en imports; usar paths relativos desde la raíz del proyecto
11. **Testing incremental**: Crear tests para cada capa nueva antes de integrar con capas superiores

---

## Fecha de última actualización
21 de octubre de 2025
