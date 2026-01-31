# Webpay Service - Multi-Tenant

Microservicio basado en FastAPI que expone endpoints de integración con Webpay Plus de Transbank y sincronización automática con Odoo ERP. El servicio **soporta múltiples clientes** en una única instancia, identificando automáticamente al cliente por el dominio de origen.

## 🚀 Características principales

- ✅ **Multi-tenant (múltiples clientes)** - Un servidor para todos tus clientes
- ✅ **Identificación automática de cliente** - Por dominio de origen
- ✅ **Integración completa con Webpay Plus** - Manejo de transacciones de pago
- ✅ **Sincronización automática con Odoo** - Actualización de órdenes de venta
- ✅ **Gestión de transacciones** - Registro y seguimiento de pagos
- ✅ **CORS configurado** - Listo para integración con Odoo Online
- ✅ **Manejo de errores robusto** - Logs detallados y fallbacks
- ✅ **API REST documentada** - Endpoints para todas las operaciones

## 📋 Requisitos previos

- Python 3.10 o superior (`python3 --version`)
- `pip` actualizado (`python3 -m pip install --upgrade pip`)
- Acceso a internet para instalar dependencias
- Archivo `clients.yaml` configurado con tus clientes (ver sección de configuración)

## 🔧 Configuración del entorno

### 1. Preparación del entorno

1. Clonar o descargar este repositorio dentro de tu workspace.
2. Crear un entorno virtual: `python3 -m venv venv`
3. Activar el entorno:
   - macOS/Linux: `source venv/bin/activate`
   - Windows PowerShell: `.\venv\Scripts\activate.bat`
   - Windows CMD: `venv\Scripts\activate.bat`
   - Si tienes permisos de PowerShell: `.\venv\Scripts\Activate.ps1`
4. Opcional: actualizar herramientas base dentro del entorno activado.

Para desactivar el entorno basta con ejecutar `deactivate`.

### 2. Instalación de dependencias

Con el entorno activo instala los paquetes necesarios:

```bash
pip install -r requirements.txt
```

### 3. Configuración de variables globales (.env)

Crear un archivo `.env` en la raíz del proyecto con la **configuración global** del servicio:

```bash
# 🔒 Configuración de seguridad global
API_KEY=tu-api-key-segura-aqui
HMAC_SECRET=tu-secreto-hmac-super-seguro-aqui
INTERNAL_TOKEN=middleware-odoo-secure-token-2025
TIMESTAMP_TOLERANCE=300

# 🌐 Configuración del servicio
SERVICE_BASE_URL=https://tu-servicio.com
LOG_LEVEL=INFO
```

### 4. Configuración de clientes (clients.yaml)

**⚠️ NUEVO EN v2.0.0**: Las credenciales específicas de cada cliente ahora se configuran en `clients.yaml`

1. Copia el archivo de ejemplo:
```bash
cp clients.yaml.example clients.yaml
```

2. Edita `clients.yaml` y configura tus clientes:

```yaml
clients:
  tecnogrow:
    client_id: "tecnogrow"
    client_name: "Tecnogrow"
    
    # Dominios permitidos (para CORS y identificación)
    allowed_origins:
      - "https://tecnogrow-integration.odoo.com"
      - "https://tecnogrow.odoo.com"
    
    # Configuración de Odoo
    odoo:
      url: "https://tecnogrow-integration.odoo.com"
      database: "tecnogrow-integration"
      username: "admin@tecnogrow.cl"
      password: "tu_password"
    
    # Configuración de Webpay
    webpay:
      provider_id: 20
      payment_method_id: 209
    
    enabled: true

  # Puedes agregar más clientes aquí
  cliente2:
    client_id: "cliente2"
    client_name: "Cliente 2 S.A."
    allowed_origins:
      - "https://cliente2.odoo.com"
    odoo:
      url: "https://cliente2.odoo.com"
      database: "cliente2-prod"
      username: "admin@cliente2.com"
      password: "otro_password"
    webpay:
      provider_id: 25
      payment_method_id: 215
    enabled: true
```

**📖 Documentación completa**: Ver [MULTI_TENANT.md](MULTI_TENANT.md) para detalles sobre configuración multi-cliente.

## 🚀 Ejecutar el microservicio

1. Asegúrate de tener el entorno virtual activo.
2. Configura las variables de entorno necesarias (`.env`).
3. Configura tus clientes en `clients.yaml`.
4. Inicia el servidor de desarrollo:

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

5. Abre `http://localhost:8000` para verificar el estado.
6. La documentación interactiva de FastAPI está disponible en `http://localhost:8000/docs`.

## 📊 Endpoints disponibles

### 🏠 Endpoints generales

| Método | Ruta       | Descripción                                    | Autenticación |
|--------|------------|------------------------------------------------|---------------|
| GET    | `/`        | Verifica que el microservicio esté operativo y lista clientes activos | ❌ No |
| GET    | `/health`  | Health check detallado del sistema            | ❌ No         |

**Respuesta de `/`:**
```json
{
  "status": "ok",
  "message": "Webpay Service operativo - Multi-tenant",
  "version": "2.0.0",
  "clients_count": 2,
  "clients": ["Tecnogrow", "Cliente 2 S.A."]
}
```

### 💳 Endpoints de Webpay

| Método | Ruta             | Descripción                                               | Autenticación |
|--------|------------------|-----------------------------------------------------------|---------------|
| POST   | `/webpay/init`   | Crea un token de transacción (identifica cliente automáticamente) | ✅ Origin*   |
| POST   | `/webpay/commit` | Recibe el callback de Webpay (método POST)              | ❌ No**        |
| GET    | `/webpay/commit` | Maneja respuestas de Webpay vía GET                      | ❌ No**        |

*Autenticación por origen: El sistema identifica al cliente por el dominio del header `Origin`
**Los endpoints de commit no requieren autenticación porque son llamados directamente por Transbank.

### 🏪 Endpoints de Odoo

| Método | Ruta                            | Descripción                                     | Autenticación        |
|--------|---------------------------------|-------------------------------------------------|----------------------|
| GET    | `/odoo/orders/search`           | Busca órdenes por criterios específicos        | ✅ API Key           |
| GET    | `/odoo/orders/{order_id}`       | Obtiene detalles de una orden específica       | ✅ API Key           |
| PUT    | `/odoo/orders/{id}/status`      | Actualiza el estado de una orden               | ✅ API Key           |
| POST   | `/odoo/payments/create`         | Crea una transacción de pago manualmente       | ✅ API Key + HMAC    |
| GET    | `/odoo/health`                  | Verifica la conexión con Odoo                  | ✅ API Key           |



## 🔄 Flujo de integración completo

### 1. Flujo de pago multi-tenant

1. **Frontend de Odoo hace la llamada**: Desde JavaScript en el sitio de Odoo
   ```javascript
   fetch('https://tu-servicio.com/webpay/init', {
     method: 'POST',
     headers: { 'Content-Type': 'application/json' },
     body: JSON.stringify({
       amount: 10000,
       customer_name: "Juan Pérez",
       order_date: "2025-11-26"
     })
   })
   ```

2. **Identificación automática**: El sistema:
   - Lee el header `Origin` (ej: `https://tecnogrow-integration.odoo.com`)
   - Identifica que corresponde al cliente "Tecnogrow"
   - Usa las credenciales específicas de Tecnogrow

3. **Redirección a Webpay**: Utiliza el `token` y la `url` para redirigir al formulario Webpay.

4. **Confirmación automática**: Webpay envía la respuesta al endpoint `/webpay/commit`.

5. **Sincronización con Odoo del cliente correcto**: El sistema:
   - Identifica al cliente desde el resultado
   - Busca la orden en el Odoo correspondiente
   - Actualiza el estado de la orden a 'sale'
   - Registra la transacción de pago
   - Vincula la transacción con la orden

### 2. Agregar un nuevo cliente

Simplemente edita `clients.yaml` y agrega el nuevo bloque:

```yaml
nuevo_cliente:
  client_id: "nuevo_cliente"
  client_name: "Nuevo Cliente S.A."
  allowed_origins:
    - "https://nuevo-cliente.odoo.com"
  odoo:
    url: "https://nuevo-cliente.odoo.com"
    database: "nuevo-cliente-db"
    username: "admin@nuevo-cliente.com"
    password: "password_seguro"
  webpay:
    provider_id: 30
    payment_method_id: 220
  enabled: true
```

No se requiere reiniciar el servidor (opcional hot-reload).

### 2. Búsqueda manual de órdenes

```bash
GET /odoo/orders/search?customer_name=Juan&amount=10000&order_date=2025-10-30
```

### 3. Creación manual de transacciones

```json
POST /odoo/payments/create
{
  "order_id": 123,
  "order_name": "SO001",
  "amount": 10000.0,
  "status": "done",
  "payment_data": {
    "authorization_code": "ABC123",
    "buy_order": "Juan-Perez_10000_20251030"
  }
}
```

## ⚠️ CONFIGURACIÓN CRÍTICA - WEBPAY PROVIDERS POR CLIENTE

> **⚠️ IMPORTANTE**: Cada cliente debe tener configurados correctamente sus IDs de provider y método de pago en `clients.yaml`:

```yaml
webpay:
  provider_id: 20        # ID del provider Webpay en Odoo del cliente
  payment_method_id: 209 # ID del método de pago Webpay en Odoo del cliente
```

### 🔍 Cómo obtener los IDs correctos para cada cliente:

1. Acceder a la instancia de Odoo del cliente
2. Ir a **Facturación > Configuración > Proveedores de pago**
3. Buscar el proveedor "Webpay" y anotar su ID
4. En **Contabilidad > Configuración > Métodos de pago**, buscar "Webpay" y anotar su ID
5. Actualizar los valores en `clients.yaml` para ese cliente

**❌ Si estos valores son incorrectos, las transacciones NO se registrarán correctamente en Odoo del cliente.**

## 🏗️ Estructura del proyecto actualizada (v2.0.0)

```
webpay_service/
├── README.MD                # Documentación principal
├── MULTI_TENANT.md          # 🆕 Guía de configuración multi-cliente
├── requirements.txt         # Dependencias Python (incluye PyYAML)
├── .env                     # Variables globales (no versionado)
├── .gitignore
├── clients.yaml             # 🆕 Configuración de clientes (no versionado)
├── clients.yaml.example     # 🆕 Plantilla de configuración
├── src/
│   ├── __init__.py
│   ├── main.py             # Aplicación principal FastAPI
│   ├── config.py           # Configuraciones centralizadas (multi-tenant)
│   ├── client_config.py    # 🆕 Gestión de configuración de clientes
│   ├── security.py         # 🔒 Módulo de seguridad (identifica clientes)
│   ├── routes/
│   │   ├── webpay_routes.py    # Endpoints de Webpay (multi-tenant)
│   │   └── odoo_routes.py      # Endpoints de Odoo (protegidos)
│   ├── services/
│   │   ├── webpay_service.py   # Lógica de Webpay
│   │   └── odoo_sales.py       # Integración con Odoo (multi-tenant)
└── venv/                   # Entorno virtual (no versionado)
```

## 🔄 Funcionalidades de integración con Odoo

### Búsqueda inteligente de órdenes
- Búsqueda por nombre de cliente (coincidencia parcial)
- Búsqueda por monto exacto
- Búsqueda por fecha de orden
- Combinación de múltiples criterios

### Manejo automático de estados
- Confirmación automática de órdenes después del pago
- Manejo de errores de stock (forzar estado 'sale')
- Registro de notas de pago en las órdenes

### Gestión de transacciones
- Creación automática de payment.transaction
- Vinculación con órdenes de venta
- Soporte para múltiples monedas
- Manejo de códigos de autorización y referencias

## 🧪 Datos de prueba

### URL de prueba Webpay
```
https://webpay3gint.transbank.cl/webpayserver/initTransaction?token_ws=01ab3321e3f70dedc382e6a09d54a9665bd6422d4eedf6bcf407a43b00a0a3e1
```

### Tarjeta de prueba
```
Número: 4051 8856 0044 6623
Fecha: 05/28
CVV: 123
```

### Cuenta de prueba RUT
```
RUT: 11.111.111-1
Clave: 123
```

## 🚀 Próximas mejoras

- [x] **Configuración multi-tenant** - Múltiples clientes en un servidor
- [x] **Identificación automática de cliente** - Por dominio de origen
- [x] **Health check con alertas automáticas** - Monitoreo vía Telegram
- [ ] Manejo de múltiples proveedores de pago por cliente
- [ ] Dashboard de monitoreo de transacciones
- [ ] Notificaciones automáticas por email
- [ ] Integración con webhooks de Odoo
- [ ] Tests automatizados completos
- [ ] Métricas y logging avanzado
- [ ] Hot-reload de configuración sin reiniciar

## 🏥 Health Check y Monitoreo

El servicio incluye un sistema de monitoreo automático con alertas vía Telegram que verifica el estado cada hora.

### Características
- ✅ Endpoint `/health` con estado detallado del servicio
- ✅ Monitoreo automático cada hora (configurable)
- ✅ Alertas vía Telegram solo cuando el servicio está caído
- ✅ Notificación cuando el servicio se recupera
- ✅ Compatible con chats personales y grupos
- ✅ Completamente gratuito

### Configuración rápida

1. **Crear bot de Telegram** con [@BotFather](https://t.me/botfather)
2. **Agregar variables al .env**:
```bash
HEALTH_CHECK_URL=http://localhost:8000/health
TELEGRAM_BOT_TOKEN=tu_token_aqui
TELEGRAM_CHAT_ID=tu_chat_id_aqui
```
3. **Ejecutar el monitor**:
```bash
python -m monitoring.health_check
```

📖 **[Documentación completa de monitoreo](monitoring/README.md)**

## 📚 Documentación adicional

- **[MULTI_TENANT.md](MULTI_TENANT.md)** - Guía completa de configuración multi-cliente
- **[clients.yaml.example](clients.yaml.example)** - Plantilla de configuración
- **/docs** - Documentación interactiva de la API (cuando el servidor está ejecutándose)

## url de prueba
https://webpay3gint.transbank.cl/webpayserver/initTransaction?token_ws=01ab3321e3f70dedc382e6a09d54a9665bd6422d4eedf6bcf407a43b00a0a3e1
