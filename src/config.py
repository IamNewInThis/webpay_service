"""
⚙️ Configuración del Webpay Service
===================================
Centraliza todas las constantes y configuraciones del microservicio.
"""

import os
from typing import List

class Settings:
    """
    🔧 Configuraciones centralizadas del servicio
    
    Maneja variables de entorno, URLs, y configuraciones por defecto.
    """
    
    # 🌐 Configuración de CORS
    # 🏪 URLs de Odoo
    ODOO_BASE_URL: str = os.getenv("ODOO_URL")
    
    ALLOWED_ORIGINS: List[str] = [
        ODOO_BASE_URL,
        "http://localhost:3000", 
    ]
    
    ODOO_SUCCESS_URL: str = f"{ODOO_BASE_URL}/shop/confirmation"
    ODOO_PAYMENT_URL: str = f"{ODOO_BASE_URL}/shop/payment"
    
    # 🚀 Configuración del servidor
    SERVICE_NAME: str = "Webpay Service"
    SERVICE_VERSION: str = "2.0.0"
    
    # 🌍 URL del servicio (para return_url de Webpay)
    SERVICE_BASE_URL: str = os.getenv(
        "SERVICE_BASE_URL", 
        "http://localhost:8000"
    )
    
    # 🔑 API Keys (desde variables de entorno)
    ODOO_API_KEY: str = os.getenv("ODOO_API_KEY")
    
    # 🔒 Configuración de seguridad
    API_KEY: str = os.getenv("API_KEY")
    HMAC_SECRET: str = os.getenv("HMAC_SECRET")
    TIMESTAMP_TOLERANCE: int = int(os.getenv("TIMESTAMP_TOLERANCE")) 
    
    # 🏦 Configuración de Webpay
    WEBPAY_RETURN_URL: str = f"{SERVICE_BASE_URL}/webpay/commit"
    
    # 📊 Configuración de logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    @classmethod
    def get_cors_config(cls) -> dict:
        """Retorna configuración de CORS"""
        return {
            "allow_origins": cls.ALLOWED_ORIGINS,
            "allow_credentials": True,
            "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["*"],
        }
    
    @classmethod
    def get_redirect_urls(cls) -> dict:
        """Retorna URLs de redirección para diferentes estados"""
        return {
            "success": f"{cls.ODOO_SUCCESS_URL}?status=success&order={{order_id}}",
            "cancelled": f"{cls.ODOO_PAYMENT_URL}?status=cancelled",
            "rejected": f"{cls.ODOO_PAYMENT_URL}?status=rejected",
            "error": f"{cls.ODOO_PAYMENT_URL}?status=error",
        }


# 🔧 Instancia global de configuración
settings = Settings()