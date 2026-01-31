#!/usr/bin/env python3
"""
🏥 Health Check Monitor - Webpay Service
=========================================
Script que verifica el estado del servicio Webpay cada hora
y envía alertas vía Telegram cuando el servicio no responde.

Funcionalidades:
- ✅ Ping al endpoint /health cada hora (configurable)
- ✅ Alertas solo cuando el servicio está inactivo
- ✅ Notificaciones vía Telegram (individual o grupo)
- ✅ Manejo de estado para evitar spam de alertas

Uso:
    python health_check.py
    
Variables de entorno requeridas:
    HEALTH_CHECK_URL: URL del endpoint de health check
    TELEGRAM_BOT_TOKEN: Token del bot de Telegram
    TELEGRAM_CHAT_ID: ID del chat (personal o grupo)
    
Variables opcionales:
    CHECK_INTERVAL_SECONDS: Intervalo entre checks (default: 3600 = 1 hora)
"""

import os
import sys
import time
import logging
from datetime import datetime
from typing import Optional
import requests
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('monitoring/health_check.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Cliente para enviar notificaciones vía Telegram"""
    
    def __init__(self, bot_token: str, chat_id: str):
        """
        Inicializa el notificador de Telegram
        
        Args:
            bot_token: Token del bot de Telegram
            chat_id: ID del chat (puede ser ID personal o de grupo)
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    def send_alert(self, message: str) -> bool:
        """
        Envía un mensaje de alerta a Telegram
        
        Args:
            message: Mensaje a enviar
            
        Returns:
            True si se envió correctamente, False en caso contrario
        """
        try:
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            
            response = requests.post(self.api_url, json=payload, timeout=10)
            response.raise_for_status()
            
            logger.info("✅ Alerta enviada exitosamente a Telegram")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error al enviar alerta a Telegram: {e}")
            return False


class HealthChecker:
    """Monitor del estado del servicio Webpay"""
    
    def __init__(
        self, 
        health_url: str, 
        notifier: TelegramNotifier,
        check_interval: int = 3600
    ):
        """
        Inicializa el health checker
        
        Args:
            health_url: URL del endpoint /health
            notifier: Instancia del notificador de Telegram
            check_interval: Intervalo entre checks en segundos (default: 1 hora)
        """
        self.health_url = health_url
        self.notifier = notifier
        self.check_interval = check_interval
        self.service_was_down = False  # Estado previo del servicio
    
    def check_health(self) -> tuple[bool, Optional[str]]:
        """
        Verifica el estado del servicio
        
        Returns:
            Tupla (is_healthy: bool, details: Optional[str])
        """
        try:
            logger.info(f"🔍 Verificando estado del servicio: {self.health_url}")
            
            response = requests.get(self.health_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                status = data.get("status", "unknown")
                
                if status == "healthy":
                    logger.info("✅ Servicio operativo")
                    return True, None
                else:
                    error_msg = data.get("error", "Estado no saludable")
                    logger.warning(f"⚠️ Servicio respondió pero no está saludable: {error_msg}")
                    return False, error_msg
            else:
                error_msg = f"HTTP {response.status_code}"
                logger.error(f"❌ Servicio retornó error: {error_msg}")
                return False, error_msg
                
        except requests.exceptions.Timeout:
            logger.error("❌ Timeout al conectar con el servicio")
            return False, "Timeout de conexión"
        except requests.exceptions.ConnectionError:
            logger.error("❌ No se pudo conectar con el servicio")
            return False, "No se pudo conectar al servicio"
        except Exception as e:
            logger.error(f"❌ Error inesperado: {e}")
            return False, str(e)
    
    def format_alert_message(self, is_down: bool, details: Optional[str] = None) -> str:
        """
        Formatea el mensaje de alerta para Telegram
        
        Args:
            is_down: Si el servicio está caído
            details: Detalles adicionales del error
            
        Returns:
            Mensaje formateado en HTML
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if is_down:
            emoji = "🔴"
            status = "CAÍDO"
            message = f"""
{emoji} <b>ALERTA: Webpay Service {status}</b>

📅 <b>Timestamp:</b> {timestamp}
🔗 <b>URL:</b> {self.health_url}
"""
            if details:
                message += f"⚠️ <b>Detalles:</b> {details}\n"
            
            message += "\n<i>Se continuará monitoreando cada hora hasta que se restablezca el servicio.</i>"
        else:
            emoji = "✅"
            message = f"""
{emoji} <b>Webpay Service RESTABLECIDO</b>

📅 <b>Timestamp:</b> {timestamp}
🔗 <b>URL:</b> {self.health_url}

<i>El servicio ha vuelto a estar operativo.</i>
"""
        
        return message
    
    def run_check(self):
        """Ejecuta una verificación individual y envía alertas si es necesario"""
        is_healthy, error_details = self.check_health()
        
        # Solo enviar alerta si cambió el estado
        if not is_healthy and not self.service_was_down:
            # Servicio acaba de caer
            alert_message = self.format_alert_message(is_down=True, details=error_details)
            self.notifier.send_alert(alert_message)
            self.service_was_down = True
            
        elif is_healthy and self.service_was_down:
            # Servicio se recuperó
            alert_message = self.format_alert_message(is_down=False)
            self.notifier.send_alert(alert_message)
            self.service_was_down = False
    
    def start_monitoring(self):
        """Inicia el monitoreo continuo del servicio"""
        logger.info("🚀 Iniciando monitoreo del Webpay Service")
        logger.info(f"⏱️ Intervalo de verificación: {self.check_interval} segundos ({self.check_interval/3600:.1f} horas)")
        logger.info(f"🔗 URL de health check: {self.health_url}")
        
        # Enviar mensaje inicial
        startup_message = f"""
🚀 <b>Monitor de Webpay Service Iniciado</b>

⏱️ <b>Intervalo:</b> {self.check_interval/3600:.1f} hora(s)
🔗 <b>URL:</b> {self.health_url}

<i>Recibirás alertas solo cuando el servicio no esté disponible.</i>
"""
        self.notifier.send_alert(startup_message)
        
        while True:
            try:
                self.run_check()
                logger.info(f"⏳ Esperando {self.check_interval} segundos hasta el próximo check...")
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                logger.info("\n⚠️ Monitoreo detenido por el usuario")
                break
            except Exception as e:
                logger.error(f"❌ Error en el loop de monitoreo: {e}")
                time.sleep(60)  # Esperar 1 minuto antes de reintentar


def main():
    """Función principal"""
    
    # Leer configuración desde variables de entorno
    health_url = os.getenv("HEALTH_CHECK_URL")
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    check_interval = int(os.getenv("CHECK_INTERVAL_SECONDS", "3600"))
    
    # Validar variables requeridas
    if not health_url:
        logger.error("❌ ERROR: Variable HEALTH_CHECK_URL no configurada")
        sys.exit(1)
    
    if not bot_token:
        logger.error("❌ ERROR: Variable TELEGRAM_BOT_TOKEN no configurada")
        sys.exit(1)
    
    if not chat_id:
        logger.error("❌ ERROR: Variable TELEGRAM_CHAT_ID no configurada")
        sys.exit(1)
    
    # Inicializar componentes
    notifier = TelegramNotifier(bot_token, chat_id)
    checker = HealthChecker(health_url, notifier, check_interval)
    
    # Iniciar monitoreo
    checker.start_monitoring()


if __name__ == "__main__":
    main()
