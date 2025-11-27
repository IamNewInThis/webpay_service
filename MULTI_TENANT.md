# 🏢 Configuración Multi-Cliente (Multi-Tenant)

## 📋 Descripción

El Webpay Service ahora soporta **múltiples clientes** en una única instancia del servidor. Cada cliente puede tener sus propias credenciales de Odoo y configuración de Webpay.

## 🎯 ¿Cómo funciona?

El sistema identifica automáticamente al cliente basándose en el **dominio de origen** (`Origin` header) de cada request:

```
Request desde https://tecnogrow-integration.odoo.com
    ↓
Sistema identifica: Cliente "Tecnogrow"
    ↓
Usa credenciales de Odoo y Webpay específicas de Tecnogrow
```

## 🚀 Configuración Inicial

### 1. Instalar Dependencias

```bash
pip install -r requirements.txt
```

Asegúrate de tener `PyYAML==6.0.2` instalado.

### 2. Crear Archivo de Configuración

Copia el archivo de ejemplo:

```bash
cp clients.yaml.example clients.yaml
```

### 3. Configurar Clientes

Edita `clients.yaml` y agrega tus clientes:

```yaml
clients:
  tecnogrow:
    client_id: "tecnogrow"
    client_name: "Tecnogrow"
    
    allowed_origins:
      - "https://tecnogrow-integration.odoo.com"
      - "https://tecnogrow.odoo.com"
    
    odoo:
      url: "https://tecnogrow-integration.odoo.com"
      database: "tecnogrow-integration"
      username: "admin@tecnogrow.cl"
      password: "tu_password_aqui"
    
    webpay:
      provider_id: 20
      payment_method_id: 209
    
    enabled: true

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

## 🔐 Seguridad

### Variables de Entorno (`.env`)

El archivo `.env` ahora solo contiene **configuración global** del servicio:

```env
# Configuración Global
API_KEY=tu-api-key-global
HMAC_SECRET=tu-hmac-secret
INTERNAL_TOKEN=tu-internal-token
TIMESTAMP_TOLERANCE=300
SERVICE_BASE_URL=https://tu-servicio.com
LOG_LEVEL=INFO
```

### Configuración de Clientes (`clients.yaml`)

- ✅ **NO subir** `clients.yaml` a Git (está en `.gitignore`)
- ✅ **SÍ subir** `clients.yaml.example` como referencia
- ✅ Las credenciales de cada cliente están aisladas
- ✅ Cada cliente solo accede a su propia instancia de Odoo

## 📖 Uso

### Desde el Frontend de Odoo

El frontend simplemente hace requests normales. El sistema identifica automáticamente al cliente:

```javascript
// JavaScript en Odoo (frontend)
fetch('https://webpay-service.com/webpay/init', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    amount: 10000,
    customer_name: "Juan Pérez",
    order_date: "2025-11-26"
  })
})
```

El header `Origin` se envía automáticamente y el servidor identifica:
- Si viene de `https://tecnogrow-integration.odoo.com` → Usa config de Tecnogrow
- Si viene de `https://cliente2.odoo.com` → Usa config de Cliente 2

### Agregar un Nuevo Cliente

1. Edita `clients.yaml`
2. Agrega el nuevo bloque de cliente
3. **No requiere reiniciar** el servidor (opcional hot-reload)

```yaml
clients:
  # ... clientes existentes ...
  
  nuevo_cliente:
    client_id: "nuevo_cliente"
    client_name: "Nuevo Cliente"
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

### Deshabilitar un Cliente Temporalmente

Cambia `enabled: false`:

```yaml
tecnogrow:
  # ... configuración ...
  enabled: false  # Cliente temporalmente deshabilitado
```

## 🔍 Verificación

### Verificar Clientes Activos

Visita el endpoint raíz:

```bash
curl https://tu-servicio.com/
```

Respuesta:

```json
{
  "status": "ok",
  "message": "Webpay Service operativo - Multi-tenant",
  "version": "2.0.0",
  "clients_count": 2,
  "clients": ["Tecnogrow", "Cliente 2 S.A."]
}
```

### Logs del Sistema

El sistema loguea qué cliente está haciendo cada operación:

```
✅ Cliente identificado: Tecnogrow (tecnogrow) desde https://tecnogrow-integration.odoo.com
💳 Iniciando transacción para cliente: Tecnogrow
🔍 Buscando orden en Odoo (Tecnogrow) - Cliente: Juan Perez, Monto: 10000
```

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────┐
│  Request desde Frontend Odoo                     │
│  Origin: https://tecnogrow-integration.odoo.com  │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│  security.py - verify_origin()                   │
│  • Lee header Origin                             │
│  • Identifica cliente: "tecnogrow"              │
│  • Valida que esté en allowed_origins           │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│  client_config.py - ClientConfigLoader           │
│  • Busca config del cliente en clients.yaml     │
│  • Retorna ClientConfig con credenciales        │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│  webpay_routes.py                                │
│  • Recibe ClientConfig                           │
│  • Crea OdooSalesService(client_config)         │
│  • Procesa transacción con credenciales         │
│    específicas del cliente                       │
└─────────────────────────────────────────────────┘
```

## 🚨 Troubleshooting

### Error: "Origen no autorizado"

```
❌ Origen no corresponde a ningún cliente configurado: https://desconocido.odoo.com
```

**Solución:** Agrega el dominio a `allowed_origins` del cliente correspondiente.

### Error: "Cliente no identificado"

```
⚠️ No se pudo identificar cliente desde transacción
```

**Solución:** Asegúrate de que hay al menos un cliente activo (`enabled: true`) en `clients.yaml`.

### Error: "Archivo de configuración no encontrado"

```
⚠️ Archivo de configuración no encontrado: /path/to/clients.yaml
```

**Solución:** Crea `clients.yaml` desde `clients.yaml.example`.

## 🔄 Migración desde Versión Anterior

Si vienes de la versión 1.x con variables de entorno:

1. **Mantén** el `.env` actual (solo para variables globales)
2. **Crea** `clients.yaml` con tu cliente existente:

```yaml
clients:
  tecnogrow:  # Tu cliente actual
    client_id: "tecnogrow"
    client_name: "Tecnogrow"
    allowed_origins:
      - "https://tecnogrow-integration.odoo.com"
    odoo:
      url: "https://tecnogrow-integration.odoo.com"
      database: "tecnogrow-integration"
      username: "admin@tecnogrow.cl"
      password: "Ab67d7654.123"
    webpay:
      provider_id: 20
      payment_method_id: 209
    enabled: true
```

3. **Opcional:** Limpia las variables específicas de cliente del `.env`:
   - `ODOO_DATABASE`
   - `ODOO_PASSWORD`
   - `ODOO_URL`
   - `ODOO_USERNAME`
   - `WEBPAY_PROVIDER_ID`
   - `WEBPAY_PAYMENT_METHOD_ID`

## 📚 Referencias

- **Configuración**: `clients.yaml`
- **Ejemplo**: `clients.yaml.example`
- **Código**: `src/client_config.py`
- **Seguridad**: `src/security.py`
- **Rutas**: `src/routes/webpay_routes.py`
