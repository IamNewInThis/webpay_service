"""
🏪 Servicio de Odoo Sales
=========================
Maneja la integración con Odoo ERP para gestión de órdenes de venta.
Basado en el código funcional de sale.py con autenticación JSON-RPC.
"""

import os
import requests
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()


class OdooSalesService:
    """
    🔧 Servicio para integración con Odoo ERP usando JSON-RPC
    
    Maneja la comunicación con Odoo para:
    - Autenticación con credenciales
    - Búsqueda y actualización de órdenes de venta
    - Sincronización de estados de pago
    """
    
    def __init__(self):
        """🚀 Inicializa la configuración de Odoo desde variables de entorno"""
        self.odoo_url = os.getenv("ODOO_URL")
        self.database = os.getenv("ODOO_DATABASE")
        self.username = os.getenv("ODOO_USERNAME")
        self.password = os.getenv("ODOO_PASSWORD")
        
        self.uid = None  # Se establecerá después de autenticar
        self.session = requests.Session()
        
    def authenticate(self) -> bool:
        """
        🔐 Autenticar con Odoo y obtener UID
        
        Returns:
            True si la autenticación fue exitosa
        """
        auth_payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "service": "common",
                "method": "authenticate",
                "args": [self.database, self.username, self.password, {}]
            },
            "id": 1
        }
        
        try:
            print("� Intentando autenticar con Odoo...")
            response = self.session.post(f"{self.odoo_url}/jsonrpc", json=auth_payload)
            
            if response.ok:
                result = response.json()
                if "result" in result and result["result"]:
                    self.uid = result["result"]
                    print(f"✅ Autenticado correctamente. UID: {self.uid}")
                    return True
                else:
                    print("❌ Error de autenticación:", result.get("error", "Credenciales inválidas"))
                    return False
            else:
                print(f"❌ Error HTTP: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error autenticando con Odoo: {str(e)}")
            return False
    
    def find_order_by_criteria(self, customer_name: str, amount: int, order_date: str) -> Optional[Dict[str, Any]]:
        """
        🔍 Busca una orden por criterios de matching (nombre, monto, fecha)
        
        Args:
            customer_name: Nombre del cliente
            amount: Monto de la orden
            order_date: Fecha de la orden (YYYY-MM-DD)
            
        Returns:
            Orden encontrada o None si no se encuentra
        """
        if not self.uid:
            if not self.authenticate():
                return None
        
        # Construir dominio de búsqueda
        domain = []
        
        # Buscar por nombre del cliente (coincidencia parcial)
        if customer_name:
            domain.append(["partner_id", "ilike", customer_name])
        
        # Buscar por monto exacto
        if amount:
            domain.append(["amount_total", "=", amount])
        
        # Buscar por fecha del mismo día
        if order_date:
            domain.append(["date_order", ">=", f"{order_date} 00:00:00"])
            domain.append(["date_order", "<=", f"{order_date} 23:59:59"])
        
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "service": "object",
                "method": "execute_kw",
                "args": [
                    self.database, self.uid, self.password,
                    "sale.order", "search_read",
                    [domain],
                    {
                        "fields": [
                            "id", "name", "state", "amount_total", 
                            "partner_id", "date_order", "invoice_status"
                        ],
                        "limit": 1
                    }
                ]
            },
            "id": 3
        }
        
        try:
            print(f"🔍 Buscando orden - Cliente: {customer_name}, Monto: ${amount}, Fecha: {order_date}")
            response = self.session.post(f"{self.odoo_url}/jsonrpc", json=payload)
            
            if response.ok:
                result = response.json()
                if "result" in result and result["result"]:
                    orders = result["result"]
                    if orders:
                        order = orders[0]
                        print(f"✅ Orden encontrada: {order['name']}")
                        return order
                    else:
                        print("❌ No se encontró orden con esos criterios")
                        return None
                else:
                    print("⚠️ Sin resultados en la búsqueda")
                    return None
            else:
                print(f"❌ Error en búsqueda: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error buscando orden: {str(e)}")
            return None
    
    def update_order_payment_status(self, order_id: int, payment_data: Dict[str, Any]) -> bool:
        """
        💳 Actualiza el estado de pago de una orden específica
        
        Args:
            order_id: ID de la orden en Odoo
            payment_data: Datos del pago (buy_order, amount, status, etc.)
            
        Returns:
            True si la actualización fue exitosa
        """
        if not self.uid:
            if not self.authenticate():
                return False
        
        try:
            # Actualizar la orden para marcarla como pagada
            update_payload = {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "service": "object",
                    "method": "execute_kw",
                    "args": [
                        self.database, self.uid, self.password,
                        "sale.order", "write",
                        [[order_id]],  # IDs a actualizar
                        {
                            "state": "sale",  # Cambiar estado a 'sale' (confirmada)
                            # Agregar nota sobre el pago
                            "note": f"Pago procesado vía Webpay - Orden: {payment_data.get('buy_order', 'N/A')}"
                        }
                    ]
                },
                "id": 4
            }
            
            print(f"💳 Actualizando orden {order_id} con datos de pago...")
            response = self.session.post(f"{self.odoo_url}/jsonrpc", json=update_payload)
            
            if response.ok:
                result = response.json()
                if "result" in result and result["result"]:
                    print(f"✅ Orden {order_id} actualizada exitosamente")
                    return True
                else:
                    print(f"❌ Error actualizando orden: {result.get('error', 'Error desconocido')}")
                    return False
            else:
                print(f"❌ Error HTTP actualizando orden: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error actualizando estado de pago: {str(e)}")
            return False
    
    def get_order_by_id(self, order_id: int) -> Optional[Dict[str, Any]]:
        """
        📄 Obtiene una orden específica por su ID
        
        Args:
            order_id: ID de la orden en Odoo
            
        Returns:
            Datos de la orden o None si no se encuentra
        """
        if not self.uid:
            if not self.authenticate():
                return None
        
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "service": "object",
                "method": "execute_kw",
                "args": [
                    self.database, self.uid, self.password,
                    "sale.order", "read",
                    [[order_id]],  # ID específico
                    {
                        "fields": [
                            "id", "name", "state", "amount_total", 
                            "partner_id", "date_order", "invoice_status",
                            "note", "order_line"
                        ]
                    }
                ]
            },
            "id": 5
        }
        
        try:
            print(f"📄 Obteniendo orden {order_id}...")
            response = self.session.post(f"{self.odoo_url}/jsonrpc", json=payload)
            
            if response.ok:
                result = response.json()
                if "result" in result and result["result"]:
                    orders = result["result"]
                    if orders:
                        order = orders[0]
                        print(f"✅ Orden obtenida: {order['name']}")
                        return order
                    else:
                        print(f"❌ Orden {order_id} no encontrada")
                        return None
                else:
                    print(f"⚠️ Sin resultados para orden {order_id}")
                    return None
            else:
                print(f"❌ Error obteniendo orden: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Error obteniendo orden: {str(e)}")
            return None
    
   
