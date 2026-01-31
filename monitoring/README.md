# 🏥 Health Check y Monitoreo del Webpay Service

Sistema de monitoreo automático con alertas vía Telegram para el Webpay Service.

## 📋 Características

- ✅ Endpoint `/health` en el servicio FastAPI
- ✅ Script de monitoreo que verifica el estado cada hora
- ✅ Alertas vía Telegram **solo cuando el servicio está caído**
- ✅ Notificación cuando el servicio se recupera
- ✅ Compatible con chats individuales y grupos de Telegram
- ✅ Logging detallado de todas las verificaciones

## 🚀 Configuración Inicial

### 1. Crear Bot de Telegram

1. Abre Telegram y busca a **@BotFather**
2. Envía el comando `/newbot`
3. Asigna un nombre (ej: `WebpayHealthBot`)
4. Asigna un username (ej: `webpay_health_bot`)
5. **Guarda el token** que te proporciona (algo como: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 2. Obtener Chat ID

**Opción A: Chat Personal**
1. Busca tu bot en Telegram
2. Envíale el comando `/start`
3. Visita: `https://api.telegram.org/bot<TU_TOKEN>/getUpdates`
4. Busca el campo `"chat":{"id": 123456789}` - ese es tu CHAT_ID

**Opción B: Grupo de Telegram**
1. Crea un grupo en Telegram (ej: "Webpay Alerts")
2. Agrega a tu bot al grupo
3. Envía un mensaje en el grupo (ej: `/start`)
4. Visita: `https://api.telegram.org/bot<TU_TOKEN>/getUpdates`
5. Busca el campo `"chat":{"id": -1001234567890}` - el ID del grupo será **negativo**

### 3. Configurar Variables de Entorno

Agrega las siguientes variables a tu archivo `.env`:

```bash
# 🏥 Health Check Configuration
HEALTH_CHECK_URL=http://localhost:8000/health
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789  # O -1001234567890 para grupos
CHECK_INTERVAL_SECONDS=3600  # 1 hora (opcional, default: 3600)
```

**Variables explicadas:**
- `HEALTH_CHECK_URL`: URL completa del endpoint de health check
- `TELEGRAM_BOT_TOKEN`: Token del bot (de BotFather)
- `TELEGRAM_CHAT_ID`: ID del chat personal o grupo (positivo o negativo)
- `CHECK_INTERVAL_SECONDS`: Intervalo entre checks en segundos (default: 3600 = 1 hora)

## 📦 Instalación de Dependencias

```bash
pip install -r requirements.txt
```

O instalar solo las nuevas dependencias:

```bash
pip install python-telegram-bot==21.0
```

## ▶️ Uso

### Modo Manual (para pruebas)

```bash
cd webpay_service
python -m monitoring.health_check
```

### Modo Producción con Cron (Linux)

1. Edita el crontab:
```bash
crontab -e
```

2. Agrega una línea para ejecutar cada hora:
```bash
0 * * * * cd /ruta/a/webpay_service && /usr/bin/python3 -m monitoring.health_check >> /var/log/webpay_healthcheck.log 2>&1
```

**Nota:** El script ya tiene su propio loop interno, por lo que puedes ejecutarlo una sola vez y se quedará monitoreando continuamente.

### Modo Systemd Service (Recomendado para Producción)

1. Crea el archivo de servicio:
```bash
sudo nano /etc/systemd/system/webpay-health-monitor.service
```

2. Contenido:
```ini
[Unit]
Description=Webpay Service Health Monitor
After=network.target

[Service]
Type=simple
User=tu_usuario
WorkingDirectory=/ruta/a/webpay_service
Environment="PATH=/ruta/a/venv/bin"
ExecStart=/ruta/a/venv/bin/python -m monitoring.health_check
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
```

3. Habilita e inicia el servicio:
```bash
sudo systemctl daemon-reload
sudo systemctl enable webpay-health-monitor
sudo systemctl start webpay-health-monitor
sudo systemctl status webpay-health-monitor
```

## 📱 Mensajes de Telegram

### Mensaje de Inicio
Cuando inicias el monitor, recibirás:
```
🚀 Monitor de Webpay Service Iniciado

⏱️ Intervalo: 1.0 hora(s)
🔗 URL: http://tu-servidor:8000/health

Recibirás alertas solo cuando el servicio no esté disponible.
```

### Alerta de Servicio Caído
```
🔴 ALERTA: Webpay Service CAÍDO

📅 Timestamp: 2026-01-31 15:30:00
🔗 URL: http://tu-servidor:8000/health
⚠️ Detalles: No se pudo conectar al servicio

Se continuará monitoreando cada hora hasta que se restablezca el servicio.
```

### Notificación de Recuperación
```
✅ Webpay Service RESTABLECIDO

📅 Timestamp: 2026-01-31 16:00:00
🔗 URL: http://tu-servidor:8000/health

El servicio ha vuelto a estar operativo.
```

## 🐳 Uso con Docker

Si el servicio corre en Docker, asegúrate de que:

1. El contenedor esté en la misma red o accesible
2. La URL apunte al servicio correcto:

```bash
# Si ejecutas el monitor desde el host
HEALTH_CHECK_URL=http://localhost:8000/health

# Si ejecutas el monitor desde otro contenedor
HEALTH_CHECK_URL=http://webpay_container:8000/health
```

## 📊 Logs

Los logs se guardan en:
```
webpay_service/monitoring/health_check.log
```

Para ver los logs en tiempo real:
```bash
tail -f monitoring/health_check.log
```

## 🔧 Personalización

### Cambiar el Intervalo de Verificación

Por defecto es 1 hora (3600 segundos). Puedes cambiarlo:

```bash
# Verificar cada 30 minutos
CHECK_INTERVAL_SECONDS=1800

# Verificar cada 2 horas
CHECK_INTERVAL_SECONDS=7200

# Verificar cada 15 minutos (para testing)
CHECK_INTERVAL_SECONDS=900
```

### Modificar los Mensajes

Edita el método `format_alert_message()` en [health_check.py](monitoring/health_check.py#L149) para personalizar los mensajes.

## ❓ Solución de Problemas

### No recibo mensajes de Telegram

1. Verifica que el bot esté en el grupo (si usas grupo)
2. Comprueba que el CHAT_ID sea correcto (negativo para grupos)
3. Revisa los logs: `cat monitoring/health_check.log`
4. Prueba manualmente el bot:
```bash
curl -X POST "https://api.telegram.org/bot<TU_TOKEN>/sendMessage" \
  -H "Content-Type: application/json" \
  -d '{"chat_id": "<TU_CHAT_ID>", "text": "Test"}'
```

### El servicio parece estar caído pero está funcionando

1. Verifica que la URL sea correcta
2. Comprueba que el endpoint `/health` responda 200
3. Revisa los logs del servicio principal

### Recibo spam de mensajes

El script está diseñado para enviar alertas **solo cuando cambia el estado**:
- Una alerta cuando el servicio cae
- Una notificación cuando se recupera
- No debería enviar múltiples alertas mientras está caído

## 🎯 Endpoint /health

El servicio expone el endpoint `/health` que retorna:

**Respuesta Exitosa (200):**
```json
{
  "status": "healthy",
  "timestamp": "2026-01-31T15:30:00Z",
  "service": {
    "name": "Webpay Service",
    "version": "2.0.4",
    "uptime": "ok"
  },
  "components": {
    "webpay_sdk": {"status": "ok", "message": "SDK inicializado"},
    "cors": {"status": "ok", "message": "CORS configurado"},
    "routes": {"status": "ok", "message": "Rutas registradas"},
    "clients": {
      "status": "ok",
      "count": 2,
      "message": "2 cliente(s) activo(s)"
    }
  }
}
```

**Respuesta de Error (503):**
```json
{
  "status": "unhealthy",
  "error": "Descripción del error",
  "timestamp": "2026-01-31T15:30:00Z"
}
```

## 📝 Notas Importantes

- ✅ **Gratis**: Telegram es completamente gratuito, sin límites de mensajes
- ✅ **Privacidad**: Los mensajes solo van a tu chat/grupo configurado
- ✅ **Sin spam**: Solo se envían alertas cuando cambia el estado
- ✅ **Persistente**: El monitor se ejecuta continuamente
- ✅ **Multi-usuario**: Puedes usar grupos para que todo el equipo reciba alertas

## 🔗 Referencias

- [Telegram Bot API](https://core.telegram.org/bots/api)
- [BotFather](https://t.me/botfather)
- [Python Telegram Bot](https://python-telegram-bot.org/)
