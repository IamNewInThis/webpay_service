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
    
    🔒 Seguridad para Odoo Online:
    - Todas las claves sensibles (API_KEY, HMAC_SECRET) se mantienen en el middleware
    - Las credenciales de Odoo se usan solo para JSON-RPC
    - Token interno opcional para auditoría de requests
    """
    
    def __init__(self):
        """🚀 Inicializa la configuración de Odoo desde variables de entorno"""
        self.odoo_url = os.getenv("ODOO_URL")
        self.database = os.getenv("ODOO_DATABASE")
        self.username = os.getenv("ODOO_USERNAME")
        self.password = os.getenv("ODOO_PASSWORD")
        self.internal_token = os.getenv("INTERNAL_TOKEN")
        
        # 💳 Configuración de Webpay
        self.webpay_provider_id = int(os.getenv("WEBPAY_PROVIDER_ID"))
        self.webpay_payment_method_id = int(os.getenv("WEBPAY_PAYMENT_METHOD_ID"))
        
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
        Intenta confirmar la orden; si Odoo lanza UserError por stock, fuerza el estado 'sale'.
        """
        if not self.uid:
            if not self.authenticate():
                return False

        try:
            print(f"💳 Intentando confirmar orden {order_id} con datos de pago...")

            # === 1️⃣ Intentar confirmar la orden ===
            confirm_payload = {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "service": "object",
                    "method": "execute_kw",
                    "args": [
                        self.database, self.uid, self.password,
                        "sale.order", "action_confirm",
                        [[order_id]]
                    ]
                },
                "id": 4
            }

            confirm_response = self.session.post(f"{self.odoo_url}/jsonrpc", json=confirm_payload)
            confirm_result = confirm_response.json()

            # === 2️⃣ Si hay error (stock o rutas), forzamos el estado manualmente ===
            if "error" in confirm_result:
                error_block = confirm_result.get("error", {})
                error_msg = error_block.get("message") or ""
                data_block = error_block.get("data") or {}
                detailed_msg = ""
                if isinstance(data_block, dict):
                    detailed_msg = data_block.get("message") or data_block.get("debug") or ""
                combined_error_msg = f"{error_msg} - {detailed_msg}" if detailed_msg else error_msg
                print(f"⚠️ Error confirmando orden {order_id}: {combined_error_msg}")

                normalized_msg = combined_error_msg.lower()
                stock_keywords = ("reabastecimiento", "stock", "no se encontró", "no se encontro")

                # Si el error proviene de stock/rules => forzar estado sale
                if any(keyword in normalized_msg for keyword in stock_keywords):
                    print("🔁 Forzando estado 'sale' por error de stock...")
                    force_payload = {
                        "jsonrpc": "2.0",
                        "method": "call",
                        "params": {
                            "service": "object",
                            "method": "execute_kw",
                            "args": [
                                self.database, self.uid, self.password,
                                "sale.order", "write",
                                [[order_id], {"state": "sale"}]
                            ]
                        },
                        "id": 5
                    }
                    force_response = self.session.post(f"{self.odoo_url}/jsonrpc", json=force_payload)
                    force_json = force_response.json() if force_response.ok else {}
                    if force_json.get("result"):
                        print(f"✅ Orden {order_id} forzada a estado 'sale'")
                    else:
                        print(f"⚠️ No se pudo forzar el estado manualmente: {force_json}")
                        return False
                else:
                    return False

            # === 3️⃣ Registrar nota del pago ===
            note_payload = {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "service": "object",
                    "method": "execute_kw",
                    "args": [
                        self.database, self.uid, self.password,
                        "sale.order", "write",
                        [
                            [order_id],
                            {"note": f"Pago procesado vía Webpay - Orden: {payment_data.get('buy_order', 'N/A')}"}
                        ]
                    ]
                },
                "id": 6
            }

            note_response = self.session.post(f"{self.odoo_url}/jsonrpc", json=note_payload)
            note_json = note_response.json() if note_response.ok else {}
            if note_json.get("result"):
                print(f"✅ Nota de pago agregada a orden {order_id}")
            else:
                print(f"⚠️ No se pudo registrar la nota de pago: {note_json}")
            return True

        except Exception as e:
            print(f"❌ Error general al actualizar pago: {e}")
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

    def register_webpay_transaction(
        self,
        order_id: int,
        order_name: str,
        amount: float,
        status: str = "done",
        payment_data: Optional[Dict[str, Any]] = None,
        order_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        💳 Crea o actualiza una transacción Webpay vinculada a la orden usando el provider/método configurado en Odoo.
        Provider hardcodeado (ID=22) y método de pago (ID=217) según configuración del cliente.
        """
        if not self.uid:
            if not self.authenticate():
                return False

        try:
            try:
                order_ref = int(order_id)
            except (TypeError, ValueError):
                print(f"❌ order_id inválido para transacción Webpay: {order_id}")
                return False

            try:
                normalized_amount = float(amount)
            except (TypeError, ValueError):
                normalized_amount = 0.0

            payment_data = payment_data or {}
            provider_id = self.webpay_provider_id
            payment_method_id = self.webpay_payment_method_id
            provider_code = payment_data.get("provider_code") or "webpay"
            payment_data.update(
                {
                    "provider_id": provider_id,
                    "payment_method_id": payment_method_id,
                    "provider_code": provider_code,
                }
            )

            reference = order_name

            order_info = order_data or self.get_order_by_id(order_ref)
            if not order_info:
                print(f"❌ No se pudieron obtener datos de la orden {order_ref}")
                return False

            def _extract_id(field: Any) -> Optional[int]:
                if isinstance(field, list) and field:
                    return field[0]
                if isinstance(field, int):
                    return field
                return None

            partner_id = _extract_id(order_info.get("partner_id"))
            partner_name = (
                order_info["partner_id"][1]
                if isinstance(order_info.get("partner_id"), list)
                and len(order_info["partner_id"]) > 1
                else None
            )
            currency_id = _extract_id(order_info.get("currency_id"))
            company_id = _extract_id(order_info.get("company_id"))

            domain = [
                ["provider_id", "=", provider_id],
                ["reference", "=", reference],
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
            existing_ids = search_response.json().get("result") or []

            tx_vals: Dict[str, Any] = {
                "amount": normalized_amount,
                "provider_id": provider_id,
                "provider_code": provider_code,
                "reference": reference,
                "state": status,
                "payment_method_id": payment_method_id,
                "is_post_processed": True,
            }

            if partner_id:
                tx_vals["partner_id"] = partner_id
            if partner_name:
                tx_vals["partner_name"] = partner_name
            
            # 💰 Currency_id es obligatorio - usar de la orden o valor por defecto
            if currency_id:
                tx_vals["currency_id"] = currency_id
            else:
                # Fallback: usar CLP (peso chileno) como moneda por defecto
                print("⚠️ currency_id no encontrado en orden, usando CLP por defecto")
                clp_currency_id = self._get_clp_currency_id()
                if clp_currency_id:
                    tx_vals["currency_id"] = clp_currency_id
                else:
                    # Último recurso: usar ID 1 (usualmente USD en instalaciones base)
                    print("⚠️ No se pudo obtener CLP, usando currency_id=1 por defecto")
                    tx_vals["currency_id"] = 1
                    
            if company_id:
                tx_vals["company_id"] = company_id

            authorization_code = payment_data.get("authorization_code")
            session_id = payment_data.get("session_id") or payment_data.get("buy_order")
            
            if authorization_code:
                tx_vals["provider_reference"] = str(authorization_code)
            payment_status = payment_data.get("status")
            if payment_status:
                tx_vals["state_message"] = str(payment_status)
            
            response_code = payment_data.get("response_code")
            if response_code is not None:
                suffix = f" RC:{response_code}"
                tx_vals["state_message"] = f"{tx_vals.get('state_message', '')}{suffix}".strip()

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
                    self._link_transaction_to_order(order_ref, tx_id)
                    print(f"✅ Transacción Webpay actualizada para orden {order_name} (ID {tx_id})")
                    return True

                print(f"⚠️ No se pudo actualizar la transacción Webpay: {write_response.text}")
                return False

            print("ℹ️ Creando nueva transacción Webpay en Odoo")
            tx_vals["provider_id"] = provider_id
            tx_vals["payment_method_id"] = payment_method_id

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
                tx_id = create_json.get("result")
                if tx_id:
                    self._link_transaction_to_order(order_ref, tx_id)
                    print(
                        f"✅ Transacción Webpay registrada en Odoo para orden {order_name} (ID {tx_id})"
                    )
                    return True

                print(f"⚠️ La creación de la transacción no devolvió resultado: {create_json}")
                return False

            print(f"❌ Error HTTP creando transacción: {create_response.text}")
            return False

        except Exception as e:
            print(f"❌ Error registrando transacción Webpay: {e}")
            return False

    def _link_transaction_to_order(self, order_id: int, transaction_id: int) -> None:
        """
        Asocia la payment.transaction a la sale.order para que Odoo muestre la confirmación correcta.
        """
        try:
            payload = {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "service": "object",
                    "method": "execute_kw",
                    "args": [
                        self.database,
                        self.uid,
                        self.password,
                        "sale.order",
                        "write",
                        [[order_id], {"transaction_ids": [(4, transaction_id)]}],
                    ],
                },
                "id": 12,
            }

            response = self.session.post(f"{self.odoo_url}/jsonrpc", json=payload)
            if response.ok and response.json().get("result"):
                print(f"🔗 Transacción {transaction_id} enlazada con orden {order_id}")
            else:
                print(
                    f"⚠️ No se pudo enlazar transacción {transaction_id} a orden {order_id}: {response.text}"
                )
        except Exception as e:
            print(f"⚠️ Error enlazando transacción {transaction_id} con orden {order_id}: {e}")

    def _get_clp_currency_id(self) -> Optional[int]:
        """
        💰 Obtiene el ID de la moneda CLP (peso chileno) desde Odoo
        
        Returns:
            ID de la moneda CLP o None si no se encuentra
        """
        if not self.uid:
            if not self.authenticate():
                return None
        
        try:
            payload = {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "service": "object",
                    "method": "execute_kw",
                    "args": [
                        self.database, self.uid, self.password,
                        "res.currency", "search",
                        [[["name", "=", "CLP"]]],
                        {"limit": 1}
                    ]
                },
                "id": 13
            }
            
            response = self.session.post(f"{self.odoo_url}/jsonrpc", json=payload)
            if response.ok:
                result = response.json()
                currency_ids = result.get("result", [])
                if currency_ids:
                    clp_id = currency_ids[0]
                    print(f"💰 Moneda CLP encontrada con ID: {clp_id}")
                    return clp_id
                else:
                    print("⚠️ Moneda CLP no encontrada en Odoo")
                    return None
            else:
                print(f"❌ Error buscando moneda CLP: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error obteniendo moneda CLP: {str(e)}")
            return None

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
    
   
