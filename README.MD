# Webpay Service

Microservicio basado en FastAPI que expone endpoints de integración con Webpay Plus de Transbank y sincronización automática con Odoo ERP. El servicio permite iniciar transacciones, recibir confirmaciones de Webpay y actualizar automáticamente las órdenes de venta en Odoo.

## 🚀 Características principales

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
- Variables de entorno configuradas para Odoo (ver sección de configuración)

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

### 2. Variables de entorno

Crear un archivo `.env` en la raíz del proyecto con las siguientes variables:

```bash
# 🔑 Configuración de Odoo
ODOO_URL=https://tu-instancia.odoo.com
ODOO_DATABASE=tu_base_de_datos
ODOO_USERNAME=tu_usuario
ODOO_PASSWORD=tu_contraseña

# 🔒 Configuración de seguridad
API_KEY=tu-api-key-segura-aqui
HMAC_SECRET=tu-secreto-hmac-super-seguro-aqui
TIMESTAMP_TOLERANCE=300

# 💳 Configuración de Webpay (fallback)
WEBPAY_ENVIRONMENT=TEST
WEBPAY_COMMERCE_CODE=5970XXXXXXXX
WEBPAY_API_KEY=tu-api-key-webpay

# 🌐 Configuración del servicio
SERVICE_BASE_URL=https://tu-servicio.onrender.com
LOG_LEVEL=INFO

# 🧩 Configuración multi-tenant (opcional)
TENANT_CONFIGS='[
  {
    "id": "***id***",
    "name": "***name***",
    "origins": ["***https://<tu-dominio>.odoo.com***"],
    "odoo": {
      "url": "***https://<tu-dominio>.odoo.com***",
      "database": "***your-database-name***",
      "username": "***your-username***",
      "password": "********"
    },
    "webpay": {
      "commerce_code": "***tu-commerce-code***",
      "api_key": "***tu-api-key-webpay***",
      "environment": "PROD"
    }
  },
  {
    "id": "simpledigital",
    "name": "Simple Digital",
    "origins": [
      "***https://<tu-dominio>.odoo.com***",
      "***https://<tu-dominio>.com***"
    ],
    "odoo": {
      "url": "***https://<tu-dominio>.odoo.com***",
      "database": "***your-database-name***",
      "username": "***your-username***",
      "password": "********"
    },
    "webpay": {
      "commerce_code": "***tu-commerce-code***",
      "api_key": "***tu-api-key-webpay***",
      "environment": "TEST"
    }
  }
]'
```

> Si `TENANT_CONFIGS` no está definido, el servicio utilizará las variables `ODOO_*` y `WEBPAY_*` del `.env` como tenant por defecto. Cada origen definido se valida automáticamente en CORS y en el middleware `verify_frontend_request`, y el ambiente de Webpay se determina con `WEBPAY_ENVIRONMENT` (`TEST` o `PROD`).

### 3. Instalación de dependencias

Con el entorno activo instala los paquetes necesarios:

```bash
pip install -r requirements.txt
```

Puedes congelar la lista para despliegues posteriores:

```bash
pip freeze > requirements.txt
```

## 🚀 Ejecutar el microservicio

1. Asegúrate de tener el entorno virtual activo.
2. Configura las variables de entorno necesarias.
3. Inicia el servidor de desarrollo:

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

4. Abre `http://localhost:8000` para verificar el estado.
5. La documentación interactiva de FastAPI está disponible en `http://localhost:8000/docs`.

## 📊 Endpoints disponibles

### 🏠 Endpoints generales

| Método | Ruta       | Descripción                                    | Autenticación |
|--------|------------|------------------------------------------------|---------------|
| GET    | `/`        | Verifica que el microservicio esté operativo  | ❌ No         |
| GET    | `/health`  | Health check detallado del sistema            | ❌ No         |

### 💳 Endpoints de Webpay

| Método | Ruta             | Descripción                                               | Autenticación |
|--------|------------------|-----------------------------------------------------------|---------------|
| POST   | `/webpay/init`   | Crea un token de transacción contra el ambiente de prueba| ✅ API Key    |
| POST   | `/webpay/commit` | Recibe el callback de Webpay (método POST)              | ❌ No*        |
| GET    | `/webpay/commit` | Maneja respuestas de Webpay vía GET                      | ❌ No*        |

*Los endpoints de commit no requieren autenticación porque son llamados directamente por Transbank.

### 🏪 Endpoints de Odoo

| Método | Ruta                            | Descripción                                     | Autenticación        |
|--------|---------------------------------|-------------------------------------------------|----------------------|
| GET    | `/odoo/orders/search`           | Busca órdenes por criterios específicos        | ✅ API Key           |
| GET    | `/odoo/orders/{order_id}`       | Obtiene detalles de una orden específica       | ✅ API Key           |
| PUT    | `/odoo/orders/{id}/status`      | Actualiza el estado de una orden               | ✅ API Key           |
| POST   | `/odoo/payments/create`         | Crea una transacción de pago manualmente       | ✅ API Key + HMAC    |
| GET    | `/odoo/health`                  | Verifica la conexión con Odoo                  | ✅ API Key           |



## 🔄 Flujo de integración completo

### 1. Flujo de pago estándar

1. **Inicialización**: Invoca `POST /webpay/init` con:
   ```json
   {
     "amount": 10000,
     "customer_name": "Juan Pérez",
     "order_date": "2025-10-30"
   }
   ```

2. **Redirección**: Utiliza el `token` y la `url` para redirigir al cliente al formulario Webpay.

3. **Confirmación**: Webpay envía la respuesta al endpoint `/webpay/commit`.

4. **Sincronización automática**: El sistema:
   - Busca la orden correspondiente en Odoo
   - Actualiza el estado de la orden a 'sale'
   - Registra la transacción de pago
   - Vincula la transacción con la orden

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

## ⚠️ CONFIGURACIÓN CRÍTICA - ODOO PAYMENT PROVIDERS

> **⚠️ IMPORTANTE**: Las siguientes variables son fundamentales para el correcto funcionamiento del servicio:

```python
provider_id = 00        # Provider Webpay configurado en Odoo
payment_method_id = 000 # Método de pago Webpay configurado en Odoo
```

**DEBE VERIFICAR Y ACTUALIZAR** estos valores en el archivo `src/services/odoo_sales.py` según la configuración específica de su instancia de Odoo:

1. **provider_id**: ID del proveedor de pago Webpay en su configuración de Odoo
2. **payment_method_id**: ID del método de pago Webpay en su configuración de Odoo

### 🔍 Cómo obtener los IDs correctos:

1. En Odoo, ir a **Facturación > Configuración > Proveedores de pago**
2. Buscar el proveedor "Webpay" y anotar su ID
3. En **Contabilidad > Configuración > Métodos de pago**, buscar "Webpay" y anotar su ID
4. Actualizar las variables en el código antes del despliegue

**❌ Si estos valores son incorrectos, las transacciones NO se registrarán correctamente en Odoo.**

## 🏗️ Estructura del proyecto actualizada

```
webpay_service/
├── README.MD
├── requirements.txt
├── .env                     # Variables de entorno (no versionado)
├── .gitignore
├── src/
│   ├── __init__.py
│   ├── main.py             # Aplicación principal FastAPI
│   ├── config.py           # Configuraciones centralizadas
│   ├── security.py         # 🔒 Módulo de seguridad (API Key + HMAC)
│   ├── routes/
│   │   ├── webpay_routes.py    # Endpoints de Webpay
│   │   └── odoo_routes.py      # Endpoints de Odoo (protegidos)
│   ├── services/
│   │   ├── webpay_service.py   # Lógica de Webpay
│   │   └── odoo_sales.py       # Integración con Odoo
├── tests/
│   └── test_security.py    # 🧪 Tests de seguridad
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
- [ ] Dashboard de monitoreo de transacciones
- [ ] Notificaciones automáticas por email
- [ ] Integración con webhooks de Odoo
- [ ] Tests automatizados completos
- [ ] Métricas y logging avanzado

## url de prueba
https://webpay3gint.transbank.cl/webpayserver/initTransaction?token_ws=01ab3321e3f70dedc382e6a09d54a9665bd6422d4eedf6bcf407a43b00a0a3e1

# Despliegue del contenedor

- Crear la imagen Docker:
```bash
docker build -t webpay_service .
```

- Correr el contenedor:
```bash
docker run -d \
  --name webpay_container \
  -p 8000:8000 \
  -e ODOO_DATABASE="tecnogrow-webpay" \
  -e ODOO_PASSWORD="Ab67d7654.123" \
  -e ODOO_URL="https://tecnogrow-webpay.odoo.com" \
  -e ODOO_USERNAME="admin@tecnogrow.cl" \
  webpay_service
```
