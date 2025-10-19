"""
🏪 Servicio de Odoo Sales
=========================
Maneja la integración con Odoo ERP para gestión de órdenes de venta.
Proporciona funciones para sincronizar transacciones de Webpay con Odoo.
"""

from typing import Dict, Any, Optional, List
import requests
import json


class OdooSalesService:
    """
    🔧 Servicio para integración con Odoo ERP
    
    Maneja la comunicación con la API de Odoo para:
    - Crear/actualizar órdenes de venta
    - Sincronizar estados de pago
    - Buscar clientes y productos
    """
    
    def __init__(self, base_url: str = None, api_key: str = None):
        """
        🚀 Inicializa la conexión con Odoo
        
        Args:
            base_url: URL base de la instancia de Odoo
            api_key: API key para autenticación
        """
        self.base_url = base_url or "https://tecnogrow-webpay.odoo.com"
        self.api_key = api_key
        self.session = requests.Session()
        
        # Headers por defecto para requests
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
        
        if self.api_key:
            self.session.headers.update({
                "Authorization": f"Bearer {self.api_key}"
            })
        
        print(f"🔧 OdooSalesService inicializado - URL: {self.base_url}")
    
    def test_connection(self) -> bool:
        """
        🏥 Verifica la conexión con Odoo
        
        Returns:
            True si la conexión es exitosa
        """
        try:
            # TODO: Implementar ping real a Odoo
            response = self.session.get(f"{self.base_url}/web/database/selector")
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Error conectando con Odoo: {str(e)}")
            return False
    
    def create_sale_order(self, order_data: Dict[str, Any]) -> Optional[int]:
        """
        📝 Crea una nueva orden de venta en Odoo
        
        Args:
            order_data: Datos de la orden (cliente, productos, montos, etc.)
            
        Returns:
            ID de la orden creada en Odoo o None si falló
        """
        try:
            print(f"📝 Creando orden de venta en Odoo")
            
            # TODO: Implementar llamada real a API de Odoo
            # Estructura típica para crear orden en Odoo:
            # POST /api/sale.order con datos de la orden
            
            # Simulación por ahora
            print(f"📝 Orden simulada creada con datos: {order_data}")
            return 12345  # ID simulado
            
        except Exception as e:
            print(f"❌ Error creando orden en Odoo: {str(e)}")
            return None
    
    def update_order_payment_status(self, buy_order: str, payment_data: Dict[str, Any]) -> bool:
        """
        💳 Actualiza el estado de pago de una orden
        
        Args:
            buy_order: Número de orden de compra
            payment_data: Datos del pago (status, transaction_id, amount, etc.)
            
        Returns:
            True si la actualización fue exitosa
        """
        try:
            print(f"💳 Actualizando estado de pago - Orden: {buy_order}")
            print(f"💳 Datos de pago: {payment_data}")
            
            # TODO: Implementar actualización real en Odoo
            # Típicamente sería:
            # 1. Buscar la orden por buy_order
            # 2. Actualizar el estado de pago
            # 3. Crear registro de pago si es exitoso
            
            return True  # Simulación exitosa
            
        except Exception as e:
            print(f"❌ Error actualizando pago en Odoo: {str(e)}")
            return False
    
    def find_order_by_criteria(self, customer_name: str, amount: int, order_date: str) -> Optional[Dict[str, Any]]:
        """
        🔍 Busca una orden en Odoo por criterios de matching
        
        Args:
            customer_name: Nombre del cliente
            amount: Monto de la orden
            order_date: Fecha de la orden
            
        Returns:
            Datos de la orden encontrada o None si no se encuentra
        """
        try:
            print(f"🔍 Buscando orden - Cliente: {customer_name}, Monto: ${amount}")
            
            # TODO: Implementar búsqueda real en Odoo
            # Criterios de búsqueda:
            # 1. Nombre del cliente (coincidencia parcial)
            # 2. Monto exacto o rango cercano
            # 3. Fecha de creación del mismo día
            
            # Simulación
            if customer_name and amount:
                return {
                    "id": 67890,
                    "name": "SO-2025-001",
                    "partner_name": customer_name,
                    "amount_total": amount,
                    "date_order": order_date,
                    "state": "draft"
                }
            
            return None
            
        except Exception as e:
            print(f"❌ Error buscando orden en Odoo: {str(e)}")
            return None
    
    def get_customer_orders(self, customer_name: str) -> List[Dict[str, Any]]:
        """
        👤 Obtiene todas las órdenes de un cliente
        
        Args:
            customer_name: Nombre del cliente
            
        Returns:
            Lista de órdenes del cliente
        """
        try:
            print(f"👤 Obteniendo órdenes del cliente: {customer_name}")
            
            # TODO: Implementar búsqueda real por cliente
            
            # Simulación
            return [
                {
                    "id": 111,
                    "name": "SO-2025-001",
                    "amount_total": 150000,
                    "state": "sale"
                },
                {
                    "id": 222,
                    "name": "SO-2025-002", 
                    "amount_total": 75000,
                    "state": "draft"
                }
            ]
            
        except Exception as e:
            print(f"❌ Error obteniendo órdenes del cliente: {str(e)}")
            return []
