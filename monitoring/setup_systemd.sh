#!/bin/bash
# Script para configurar el servicio systemd de health monitor

echo "🏥 Configuración de Webpay Health Monitor - Systemd Service"
echo "============================================================="
echo ""

# Verificar que se ejecuta como root
if [[ $EUID -ne 0 ]]; then
   echo "❌ Este script debe ejecutarse como root (sudo)"
   exit 1
fi

# Solicitar información
read -p "Ruta completa del proyecto webpay_service: " PROJECT_PATH
read -p "Usuario que ejecutará el servicio: " SERVICE_USER
read -p "Ruta del entorno virtual Python (venv/bin/python): " PYTHON_PATH

# Validar que las rutas existen
if [ ! -d "$PROJECT_PATH" ]; then
    echo "❌ Error: No se encontró el directorio del proyecto"
    exit 1
fi

if [ ! -f "$PYTHON_PATH" ]; then
    echo "❌ Error: No se encontró el ejecutable de Python en $PYTHON_PATH"
    exit 1
fi

# Crear archivo de servicio
SERVICE_FILE="/etc/systemd/system/webpay-health-monitor.service"

cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Webpay Service Health Monitor
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$PROJECT_PATH
Environment="PATH=$(dirname $PYTHON_PATH)"
ExecStart=$PYTHON_PATH -m monitoring.health_check
Restart=always
RestartSec=60
StandardOutput=append:/var/log/webpay-health-monitor.log
StandardError=append:/var/log/webpay-health-monitor-error.log

[Install]
WantedBy=multi-user.target
EOF

echo "✅ Archivo de servicio creado: $SERVICE_FILE"
echo ""

# Crear archivos de log
touch /var/log/webpay-health-monitor.log
touch /var/log/webpay-health-monitor-error.log
chown $SERVICE_USER:$SERVICE_USER /var/log/webpay-health-monitor.log
chown $SERVICE_USER:$SERVICE_USER /var/log/webpay-health-monitor-error.log

echo "✅ Archivos de log creados"
echo ""

# Recargar systemd
systemctl daemon-reload
echo "✅ Systemd recargado"
echo ""

# Habilitar el servicio
systemctl enable webpay-health-monitor.service
echo "✅ Servicio habilitado"
echo ""

# Mostrar comandos útiles
echo "📝 Comandos útiles:"
echo "   Iniciar servicio:  sudo systemctl start webpay-health-monitor"
echo "   Detener servicio:  sudo systemctl stop webpay-health-monitor"
echo "   Ver estado:        sudo systemctl status webpay-health-monitor"
echo "   Ver logs:          sudo journalctl -u webpay-health-monitor -f"
echo "   Ver logs archivo:  tail -f /var/log/webpay-health-monitor.log"
echo ""
echo "¿Deseas iniciar el servicio ahora? (y/n)"
read -p "> " START_NOW

if [[ "$START_NOW" == "y" || "$START_NOW" == "Y" ]]; then
    systemctl start webpay-health-monitor.service
    sleep 2
    systemctl status webpay-health-monitor.service
fi

echo ""
echo "✅ Configuración completada!"
