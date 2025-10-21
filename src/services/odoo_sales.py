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
    
    # def update_order_payment_status(self, order_id: int, payment_data: Dict[str, Any]) -> bool:
    #     """
    #     💳 Actualiza el estado de pago de una orden específica
    #     Intenta confirmar la orden; si Odoo lanza UserError por stock, fuerza el estado 'sale'.
    #     """
    #     if not self.uid:
    #         if not self.authenticate():
    #             return False

    #     try:
    #         print(f"💳 Intentando confirmar orden {order_id} con datos de pago...")

    #         # === 1️⃣ Intentar confirmar la orden ===
    #         confirm_payload = {
    #             "jsonrpc": "2.0",
    #             "method": "call",
    #             "params": {
    #                 "service": "object",
    #                 "method": "execute_kw",
    #                 "args": [
    #                     self.database, self.uid, self.password,
    #                     "sale.order", "action_confirm",
    #                     [[order_id]]
    #                 ]
    #             },
    #             "id": 4
    #         }

    #         confirm_response = self.session.post(f"{self.odoo_url}/jsonrpc", json=confirm_payload)
    #         confirm_result = confirm_response.json()

    #         # === 2️⃣ Si hay error (stock o rutas), forzamos el estado manualmente ===
    #         if "error" in confirm_result:
    #             error_msg = confirm_result["error"].get("message", "")
    #             print(f"⚠️ Error confirmando orden {order_id}: {error_msg}")

    #             # Si el error proviene de stock/rules => forzar estado sale
    #             if "reabastecimiento" in error_msg or "stock" in error_msg or "No se encontró" in error_msg:
    #                 print("🔁 Forzando estado 'sale' por error de stock...")
    #                 force_payload = {
    #                     "jsonrpc": "2.0",
    #                     "method": "call",
    #                     "params": {
    #                         "service": "object",
    #                         "method": "execute_kw",
    #                         "args": [
    #                             self.database, self.uid, self.password,
    #                             "sale.order", "write",
    #                             [[order_id]],
    #                             {"state": "sale"}
    #                         ]
    #                     },
    #                     "id": 5
    #                 }
    #                 force_response = self.session.post(f"{self.odoo_url}/jsonrpc", json=force_payload)
    #                 if force_response.ok and "result" in force_response.json():
    #                     print(f"✅ Orden {order_id} forzada a estado 'sale'")
    #                 else:
    #                     print("⚠️ No se pudo forzar el estado manualmente")
    #             else:
    #                 return False

    #         # === 3️⃣ Registrar nota del pago ===
    #         note_payload = {
    #             "jsonrpc": "2.0",
    #             "method": "call",
    #             "params": {
    #                 "service": "object",
    #                 "method": "execute_kw",
    #                 "args": [
    #                     self.database, self.uid, self.password,
    #                     "sale.order", "write",
    #                     [[order_id]],
    #                     {
    #                         "note": f"Pago procesado vía Webpay - Orden: {payment_data.get('buy_order', 'N/A')}"
    #                     }
    #                 ]
    #             },
    #             "id": 6
    #         }

    #         note_response = self.session.post(f"{self.odoo_url}/jsonrpc", json=note_payload)
    #         if note_response.ok:
    #             print(f"✅ Nota de pago agregada a orden {order_id}")
    #         return True

    #     except Exception as e:
    #         print(f"❌ Error general al actualizar pago: {e}")
    #         return False


    def update_order_payment_status(self, order_id: int, payment_data: Dict[str, Any]) -> bool:
        """
        💳 Actualiza el estado de pago de una orden específica
        """
        if not self.uid:
            if not self.authenticate():
                return False

        try:
            print(f"💳 Actualizando orden {order_id} con datos de pago...")

            # ✅ Paso 1: Confirmar la orden (acción nativa de Odoo)
            confirm_payload = {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "service": "object",
                    "method": "execute_kw",
                    "args": [
                        self.database, self.uid, self.password,
                        "sale.order", "action_confirm",
                        [[order_id]]  # IDs a confirmar
                    ]
                },
                "id": 4
            }

            confirm_response = self.session.post(f"{self.odoo_url}/jsonrpc", json=confirm_payload)
            confirm_result = confirm_response.json()

            if not confirm_response.ok or "error" in confirm_result:
                print(f"⚠️ Error confirmando orden {order_id}: {confirm_result.get('error')}")
                return False

            # ✅ Paso 2: Registrar una nota informativa del pago
            note_payload = {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "service": "object",
                    "method": "execute_kw",
                    "args": [
                        self.database, self.uid, self.password,
                        "sale.order", "write",
                        [[order_id]],
                        {
                            "note": f"Pago procesado vía Webpay - Orden: {payment_data.get('buy_order', 'N/A')}"
                        }
                    ]
                },
                "id": 5
            }

            note_response = self.session.post(f"{self.odoo_url}/jsonrpc", json=note_payload)
            note_result = note_response.json()

            if note_response.ok and "result" in note_result and note_result["result"]:
                print(f"✅ Orden {order_id} confirmada y nota agregada correctamente")
                return True
            else:
                print(f"⚠️ Orden {order_id} confirmada, pero no se pudo escribir nota: {note_result}")
                return False

        except Exception as e:
            print(f"❌ Error actualizando estado de pago: {str(e)}")
            return False

    
    def update_order_status_by_name(self, order_name: str, new_status: str) -> bool:
        """
        🔄 Actualiza el estado de una orden de venta según su nombre (S04589)
        """
        try:
            models = self.models
            domain = [('name', '=', order_name)]
            order_ids = models.execute_kw(
                self.db, self.uid, self.password,
                'sale.order', 'search',
                [domain], {'limit': 1}
            )
            if not order_ids:
                return False

            # 🔹 Determinar qué método ejecutar según el estado solicitado
            if new_status == 'sale':
                method = 'action_confirm'
            elif new_status == 'cancel':
                method = 'action_cancel'
            elif new_status in ['draft', 'sent']:
                method = 'action_draft'
            else:
                print(f"⚠️ Estado '{new_status}' no soportado.")
                return False

            models.execute_kw(
                self.db, self.uid, self.password,
                'sale.order', method,
                [order_ids]
            )
            print(f"✅ Orden {order_name} actualizada con método {method}")
            return True

        except Exception as e:
            print(f"❌ Error actualizando estado de orden {order_name}: {e}")
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
    
    def get_recent_orders(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        📋 Obtiene las órdenes más recientes
        
        Args:
            limit: Número máximo de órdenes a obtener
            
        Returns:
            Lista de órdenes recientes
        """
        if not self.uid:
            if not self.authenticate():
                return []
        
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "service": "object",
                "method": "execute_kw",
                "args": [
                    self.database, self.uid, self.password,
                    "sale.order", "search_read",
                    [[]],  # Sin filtros (todas las órdenes)
                    {
                        "fields": [
                            "id", "name", "state", "amount_total", 
                            "partner_id", "date_order", "invoice_status"
                        ],
                        "limit": limit,
                        "order": "date_order desc"  # Más recientes primero
                    }
                ]
            },
            "id": 8
        }
        
        try:
            print(f"📋 Obteniendo {limit} órdenes recientes...")
            response = self.session.post(f"{self.odoo_url}/jsonrpc", json=payload)
            
            if response.ok:
                result = response.json()
                if "result" in result and result["result"]:
                    orders = result["result"]
                    print(f"✅ {len(orders)} órdenes obtenidas")
                    return orders
                else:
                    print("⚠️ Sin órdenes encontradas")
                    return []
            else:
                print(f"❌ Error obteniendo órdenes: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"❌ Error listando órdenes: {str(e)}")
            return []
    
   
