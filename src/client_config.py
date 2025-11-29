"""
🏢 Módulo de Configuración Multi-Cliente
========================================
Gestiona la carga y acceso a configuraciones de múltiples clientes desde YAML.
Permite identificar al cliente por dominio y obtener sus credenciales específicas.

Funcionalidades:
- ✅ Carga configuración desde clients.yaml
- ✅ Identificación de cliente por dominio
- ✅ Cache de configuraciones
- ✅ Validación de estructura
- ✅ Hot-reload opcional
"""

import os
import yaml
from dataclasses import dataclass
from typing import Dict, List, Optional
from pathlib import Path


@dataclass
class OdooConfig:
    """🏪 Configuración de Odoo para un cliente"""
    url: str
    database: str
    username: str
    password: str


@dataclass
class WebpayConfig:
    """💳 Configuración de Webpay para un cliente"""
    provider_id: int
    payment_method_id: int
    integration_type: str = "TEST"  # TEST, CERTIFICATION, PRODUCTION
    commerce_code: Optional[str] = None  # Requerido para CERTIFICATION/PRODUCTION
    api_key: Optional[str] = None  # Requerido para CERTIFICATION/PRODUCTION
    
    def __post_init__(self):
        """Valida que commerce_code y api_key estén presentes si no es TEST"""
        if self.integration_type in ["CERTIFICATION", "PRODUCTION"]:
            if not self.commerce_code or not self.api_key:
                raise ValueError(
                    f"commerce_code y api_key son requeridos para integration_type={self.integration_type}"
                )


@dataclass
class ClientConfig:
    """
    🏢 Configuración completa de un cliente
    
    Contiene todas las credenciales y configuraciones necesarias
    para que un cliente específico use el servicio.
    """
    client_id: str
    client_name: str
    allowed_origins: List[str]
    odoo: OdooConfig
    webpay: WebpayConfig
    enabled: bool = True
    
    def is_origin_allowed(self, origin: str) -> bool:
        """
        ✅ Verifica si un origen está permitido para este cliente
        
        Args:
            origin: URL de origen del request
            
        Returns:
            True si el origen está en la lista de permitidos
        """
        # Normalizar origen (quitar trailing slash)
        normalized_origin = origin.rstrip("/")
        
        # Verificar coincidencia exacta
        for allowed in self.allowed_origins:
            if allowed.rstrip("/") == normalized_origin:
                return True
            
            # Soporte para wildcards básico (*.odoo.com)
            if "*" in allowed:
                import re
                pattern = allowed.replace("*", ".*").replace(".", r"\.")
                if re.match(pattern, normalized_origin):
                    return True
        
        return False


class ClientConfigLoader:
    """
    📂 Cargador de configuraciones de clientes desde YAML
    
    Maneja la carga, cache y acceso a las configuraciones de todos los clientes.
    Singleton para garantizar una única instancia de configuración.
    """
    
    _instance = None
    _clients: Dict[str, ClientConfig] = {}
    _domain_to_client: Dict[str, str] = {}  # Mapa de dominio -> client_id
    
    def __new__(cls):
        """Patrón Singleton para garantizar una única instancia"""
        if cls._instance is None:
            cls._instance = super(ClientConfigLoader, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """🚀 Inicializa el loader (solo la primera vez)"""
        if not self._clients:
            self.load_clients()
    
    def load_clients(self, config_file: str = "clients.yaml") -> None:
        """
        📥 Carga configuraciones desde el archivo YAML
        
        Args:
            config_file: Ruta al archivo de configuración (relativa al proyecto)
        """
        # Buscar archivo de configuración
        project_root = Path(__file__).parent.parent
        config_path = project_root / config_file
        
        if not config_path.exists():
            print(f"⚠️ Archivo de configuración no encontrado: {config_path}")
            print("📝 Crea clients.yaml basándote en clients.yaml.example")
            return
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            if not data or 'clients' not in data:
                print(f"❌ Formato inválido en {config_file}")
                return
            
            clients_data = data['clients']
            loaded_count = 0
            
            for client_key, client_data in clients_data.items():
                try:
                    # Crear objetos de configuración
                    odoo_config = OdooConfig(**client_data['odoo'])
                    webpay_config = WebpayConfig(**client_data['webpay'])
                    
                    client_config = ClientConfig(
                        client_id=client_data.get('client_id', client_key),
                        client_name=client_data.get('client_name', client_key),
                        allowed_origins=client_data.get('allowed_origins', []),
                        odoo=odoo_config,
                        webpay=webpay_config,
                        enabled=client_data.get('enabled', True)
                    )
                    
                    # Guardar en cache
                    self._clients[client_config.client_id] = client_config
                    
                    # Crear mapa de dominios para búsqueda rápida
                    for origin in client_config.allowed_origins:
                        normalized_origin = origin.rstrip("/")
                        self._domain_to_client[normalized_origin] = client_config.client_id
                    
                    if client_config.enabled:
                        loaded_count += 1
                        print(f"✅ Cliente cargado: {client_config.client_name} ({client_config.client_id})")
                    else:
                        print(f"⏸️ Cliente deshabilitado: {client_config.client_name}")
                    
                except Exception as e:
                    print(f"❌ Error cargando cliente '{client_key}': {str(e)}")
                    continue
            
            print(f"🎉 {loaded_count} cliente(s) activo(s) cargado(s)")
            
        except yaml.YAMLError as e:
            print(f"❌ Error parseando YAML: {str(e)}")
        except Exception as e:
            print(f"❌ Error cargando configuraciones: {str(e)}")
    
    def get_client_by_id(self, client_id: str) -> Optional[ClientConfig]:
        """
        🔍 Obtiene configuración de un cliente por su ID
        
        Args:
            client_id: Identificador único del cliente
            
        Returns:
            ClientConfig o None si no existe
        """
        return self._clients.get(client_id)
    
    def get_client_by_origin(self, origin: str) -> Optional[ClientConfig]:
        """
        🌐 Obtiene configuración de un cliente por el dominio de origen
        
        Este es el método principal para identificar al cliente en cada request.
        
        Args:
            origin: URL de origen del request (header Origin o Referer)
            
        Returns:
            ClientConfig del cliente correspondiente o None
        """
        if not origin:
            return None
        
        # Normalizar origen
        normalized_origin = origin.rstrip("/")
        
        # Búsqueda rápida en el mapa de dominios
        if normalized_origin in self._domain_to_client:
            client_id = self._domain_to_client[normalized_origin]
            client = self._clients.get(client_id)
            
            # Verificar que esté habilitado
            if client and client.enabled:
                return client
        
        # Búsqueda exhaustiva (para wildcards y casos especiales)
        for client in self._clients.values():
            if client.enabled and client.is_origin_allowed(normalized_origin):
                return client
        
        return None
    
    def get_all_clients(self) -> List[ClientConfig]:
        """
        📋 Obtiene lista de todos los clientes configurados
        
        Returns:
            Lista de ClientConfig
        """
        return list(self._clients.values())
    
    def get_active_clients(self) -> List[ClientConfig]:
        """
        ✅ Obtiene lista de clientes activos
        
        Returns:
            Lista de ClientConfig habilitados
        """
        return [c for c in self._clients.values() if c.enabled]
    
    def reload(self) -> None:
        """
        🔄 Recarga las configuraciones desde el archivo YAML
        
        Útil para hot-reload sin reiniciar el servidor.
        """
        print("🔄 Recargando configuraciones de clientes...")
        self._clients.clear()
        self._domain_to_client.clear()
        self.load_clients()


# 🌟 Instancia global del loader (Singleton)
client_loader = ClientConfigLoader()


def get_client_from_origin(origin: str) -> Optional[ClientConfig]:
    """
    🎯 Función helper para obtener cliente desde un origen
    
    Wrapper conveniente para usar en las rutas.
    
    Args:
        origin: URL de origen del request
        
    Returns:
        ClientConfig o None si no se encuentra
    """
    return client_loader.get_client_by_origin(origin)


def get_client_from_id(client_id: str) -> Optional[ClientConfig]:
    """
    🎯 Función helper para obtener cliente por ID
    
    Args:
        client_id: Identificador del cliente
        
    Returns:
        ClientConfig o None si no existe
    """
    return client_loader.get_client_by_id(client_id)
