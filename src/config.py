"""
⚙️ Configuración del Webpay Service
===================================
Centraliza todas las constantes y configuraciones del microservicio.
Soporta configuración multi-cliente desde clients.yaml.
"""

import os
from typing import List, Optional
from src.client_config import ClientConfig

class Settings:
    """
    🔧 Configuraciones centralizadas del servicio
    
    Maneja variables de entorno, URLs, y configuraciones por defecto.
    Ahora soporta configuración dinámica por cliente.
    """
    
    # 🚀 Configuración del servidor
    SERVICE_NAME: str = "Webpay Service"
    SERVICE_VERSION: str = "2.0.0"
    
    # 🌍 URL del servicio (para return_url de Webpay)
    SERVICE_BASE_URL: str = os.getenv(
        "SERVICE_BASE_URL", 
        "http://localhost:8000"
    )
    
    # 🔒 Configuración de seguridad global
    API_KEY: str = os.getenv("API_KEY", "")
    HMAC_SECRET: str = os.getenv("HMAC_SECRET", "")
    TIMESTAMP_TOLERANCE: int = int(os.getenv("TIMESTAMP_TOLERANCE", "300")) 
    INTERNAL_TOKEN: str = os.getenv("INTERNAL_TOKEN", "")
    
    # 🏦 Configuración de Webpay (URL de retorno)
    WEBPAY_RETURN_URL: str = f"{SERVICE_BASE_URL}/webpay/commit"
    
    # 📊 Configuración de logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    @classmethod
    def get_cors_config(cls, client: Optional[ClientConfig] = None) -> dict:
        """
        Retorna configuración de CORS
        
        Args:
            client: Configuración del cliente. Si se proporciona, usa sus dominios.
                   Si es None, permite todos los orígenes de clientes configurados.
        """
        if client:
            allowed_origins = client.allowed_origins
        else:
            # Obtener todos los orígenes de todos los clientes activos
            from src.client_config import client_loader
            allowed_origins = []
            for c in client_loader.get_active_clients():
                allowed_origins.extend(c.allowed_origins)
            
            # Agregar localhost para desarrollo si no está
            if "http://localhost:8000" not in allowed_origins:
                allowed_origins.append("http://localhost:8000")
        
        return {
            "allow_origins": allowed_origins,
            "allow_credentials": True,
            "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["*"],
        }
    
    @classmethod
    def get_redirect_urls(cls, client: ClientConfig) -> dict:
        """
        Retorna URLs de redirección para diferentes estados
        
        Args:
            client: Configuración del cliente para generar URLs específicas
        """
        odoo_url = client.odoo.url
        success_url = f"{odoo_url}/shop/confirmation"
        payment_url = f"{odoo_url}/shop/payment"
        
        return {
            "success": f"{success_url}?status=success&order={{order_id}}",
            "cancelled": f"{payment_url}?status=cancelled",
            "rejected": f"{payment_url}?status=rejected",
            "error": f"{payment_url}?status=error",
        }


# 🔧 Instancia global de configuración
settings = Settings()