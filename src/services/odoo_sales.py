#src/services/odoo_sales.py
"""
🏪 Servicio de Odoo Sales
=========================
Maneja la integración con Odoo ERP para gestión de órdenes de venta y payments.
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
        self._provider_cache: Dict[str, int] = {}
        self._payment_method_cache: Dict[int, int] = {}
        
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
                print(f"⚠️ No se pudo registrar la nota de pago: {note_json}")
            return True

        except Exception as e:
            print(f"❌ Error general al actualizar pago: {e}")
            return False

    def register_webpay_transaction(
        self,
        order_id: int,
        order_name: str,
        amount: float,
        status: str = "done",
        payment_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        💳 Registra o actualiza una transacción de pago Webpay asociada a una orden.
        Compatible con Odoo Online (usa provider 'none').
        """
        if not self.uid:
            if not self.authenticate():
                return False

        try:
            # --- Normalización de datos ---
            try:
                order_ref = int(order_id)
            except (TypeError, ValueError):
                print(f"❌ order_id inválido para transacción Webpay: {order_id}")
                return False

            try:
                normalized_amount = float(amount)
            except (TypeError, ValueError):
                normalized_amount = 0.0

            reference = (
                payment_data.get("buy_order")
                if payment_data and payment_data.get("buy_order")
                else order_name
            )

            # --- Buscar transacción existente ---
            domain = [
                ["sale_order_id", "=", order_ref],
                ["provider_code", "=", "webpay"],
            ]

            search_payload = {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "service": "object",
                    "method": "execute_kw",
                    "args": [
                        self.database,
                        self.uid,
                        self.password,
                        "payment.transaction",
                        "search",
                        [domain],
                        {"limit": 1},
                    ],
                },
                "id": 9,
            }

            search_response = self.session.post(
                f"{self.odoo_url}/jsonrpc", json=search_payload
            )

            if not search_response.ok:
                print(f"❌ Error buscando transacción existente: {search_response.text}")
                return False

            search_json = search_response.json()
            existing_ids = search_json.get("result") or []

            # --- Datos base de la transacción ---
            tx_vals: Dict[str, Any] = {
                "amount": normalized_amount,
                "provider_code": "webpay",
                "reference": reference,
                "state": status,
                "sale_order_id": order_ref,
            }

            # --- Enriquecer con datos Webpay (opcional) ---
            if payment_data:
                authorization_code = payment_data.get("authorization_code")
                if authorization_code:
                    tx_vals["acquirer_reference"] = str(authorization_code)
                payment_status = payment_data.get("status")
                if payment_status:
                    tx_vals["state_message"] = str(payment_status)
                payment_type = payment_data.get("payment_type_code")
                if payment_type:
                    tx_vals["operation"] = str(payment_type)

            # --- Si ya existe, actualiza ---
            if existing_ids:
                tx_id = existing_ids[0]
                print(f"ℹ️ Actualizando transacción Webpay existente (ID {tx_id})")
                write_payload = {
                    "jsonrpc": "2.0",
                    "method": "call",
                    "params": {
                        "service": "object",
                        "method": "execute_kw",
                        "args": [
                            self.database,
                            self.uid,
                            self.password,
                            "payment.transaction",
                            "write",
                            [[tx_id], tx_vals],
                        ],
                    },
                    "id": 10,
                }

                write_response = self.session.post(
                    f"{self.odoo_url}/jsonrpc", json=write_payload
                )

                if write_response.ok and write_response.json().get("result"):
                    print(f"✅ Transacción Webpay actualizada para orden {order_name} (ID {tx_id})")
                    return True

                print(f"⚠️ No se pudo actualizar la transacción Webpay: {write_response.text}")
                return False

            # --- Crear nueva transacción (modo Odoo Online) ---
            print("ℹ️ Creando nueva transacción Webpay en Odoo (modo Odoo Online)")

            # Buscar provider 'none' (único permitido en Odoo Online)
            provider_search_payload = {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "service": "object",
                    "method": "execute_kw",
                    "args": [
                        self.database,
                        self.uid,
                        self.password,
                        "payment.provider",
                        "search",
                        [[["code", "=", "none"]]],
                        {"limit": 1},
                    ],
                },
                "id": 10,
            }

            provider_response = self.session.post(
                f"{self.odoo_url}/jsonrpc", json=provider_search_payload
            )
            provider_json = provider_response.json()
            provider_ids = provider_json.get("result") or []

            if not provider_ids:
                print("⚠️ No se encontró provider 'none', usando fallback ID 1 (si existe)")
                provider_id = 1
            else:
                provider_id = provider_ids[0]

            # Agregar provider_id obligatorio
            tx_vals["provider_id"] = provider_id

            # Crear la transacción
            create_payload = {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "service": "object",
                    "method": "execute_kw",
                    "args": [
                        self.database,
                        self.uid,
                        self.password,
                        "payment.transaction",
                        "create",
                        [tx_vals],
                    ],
                },
                "id": 11,
            }

            create_response = self.session.post(
                f"{self.odoo_url}/jsonrpc", json=create_payload
            )

            if create_response.ok:
                create_json = create_response.json()
                if create_json.get("result"):
                    print(
                        f"✅ Transacción Webpay registrada en Odoo para orden {order_name} (ID {create_json['result']})"
                    )
                    return True

                print(f"⚠️ La creación de la transacción no devolvió resultado: {create_json}")
                return False

            print(f"❌ Error HTTP creando transacción: {create_response.text}")
            return False

        except Exception as e:
            print(f"❌ Error registrando transacción Webpay: {e}")
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
                            "id",
                            "name",
                            "state",
                            "amount_total",
                            "partner_id",
                            "date_order",
                            "invoice_status",
                            "note",
                            "order_line",
                            "currency_id",
                            "company_id",
                            "transaction_ids",
                            "partner_invoice_id",
                            "partner_shipping_id",
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
    
   
