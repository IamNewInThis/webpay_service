"""
📊 MongoDB Transaction Logger
=============================
Servicio para registrar transacciones y eventos en MongoDB.
Proporciona logging persistente para auditoría y recuperación de pagos.

Funcionalidades:
- Registro de transacciones Webpay (init, commit, error)
- Seguimiento de sincronización con Odoo
- Índices optimizados para consultas
- Manejo graceful si MongoDB no está disponible
"""

from datetime import datetime, timezone
from typing import Dict, Any, Optional
from src.config import settings
import traceback


class MongoLogService:
    """
    🗄️ Servicio de logging en MongoDB

    Registra todas las transacciones y eventos importantes del sistema.
    Diseñado para ser resiliente: si MongoDB falla, no afecta el flujo principal.
    """

    _instance = None
    _client = None
    _db = None
    _collection = None
    _initialized = False

    def __new__(cls):
        """Patrón Singleton"""
        if cls._instance is None:
            cls._instance = super(MongoLogService, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """Inicializa la conexión a MongoDB (solo la primera vez)"""
        if not self._initialized and settings.MONGO_ENABLED:
            self._connect()
            self._initialized = True

    def _connect(self) -> bool:
        """
        🔌 Establece conexión con MongoDB

        Returns:
            bool: True si la conexión fue exitosa
        """
        if not settings.MONGO_URI:
            print("⚠️ MONGO_URI no configurado - logging en MongoDB deshabilitado")
            return False

        try:
            from pymongo import MongoClient, ASCENDING, DESCENDING
            from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
            import certifi

            # Configuración de conexión para MongoDB
            tls_params = {
                'serverSelectionTimeoutMS': 10000,
                'connectTimeoutMS': 10000,
                'socketTimeoutMS': 10000,
                'retryWrites': True,
            }
            
            if settings.MONGO_TLS_ALLOW_INVALID:
                # Para Render: desactivar verificación SSL
                tls_params['tls'] = True
                tls_params['tlsAllowInvalidCertificates'] = True
            else:
                # Para VPS/producción: usar certificados válidos
                tls_params['tls'] = True
                tls_params['tlsCAFile'] = certifi.where()
            
            # Conectar con configuración optimizada
            self._client = MongoClient(
                settings.MONGO_URI,
                **tls_params
            )

            # Verificar conexión
            self._client.admin.command('ping')

            self._db = self._client[settings.MONGO_DATABASE]
            self._collection = self._db[settings.MONGO_COLLECTION]

            # Crear índices para consultas eficientes
            self._create_indexes()

            print(f"✅ MongoDB conectado: {settings.MONGO_DATABASE}/{settings.MONGO_COLLECTION}")
            return True

        except ImportError:
            print("⚠️ pymongo no instalado - ejecuta: pip install pymongo")
            return False
        except Exception as e:
            print(f"⚠️ Error conectando a MongoDB: {str(e)}")
            return False

    def _create_indexes(self) -> None:
        """
        📑 Crea índices para optimizar consultas
        """
        try:
            from pymongo import ASCENDING, DESCENDING

            # Índice por token_ws (búsqueda exacta)
            self._collection.create_index("token_ws", unique=True, sparse=True)

            # Índice por buy_order (búsqueda de transacciones)
            self._collection.create_index("buy_order")

            # Índice por client_id + created_at (consultas por cliente)
            self._collection.create_index([
                ("client_id", ASCENDING),
                ("created_at", DESCENDING)
            ])

            # Índice por status + odoo_synced (encontrar pagos no sincronizados)
            self._collection.create_index([
                ("status", ASCENDING),
                ("odoo_synced", ASCENDING)
            ])

            # Índice por created_at (consultas por fecha)
            self._collection.create_index("created_at")

            # TTL index opcional - eliminar logs después de 90 días
            # self._collection.create_index("created_at", expireAfterSeconds=7776000)

            print("📑 Índices de MongoDB creados/verificados")

        except Exception as e:
            print(f"⚠️ Error creando índices: {str(e)}")

    def _is_connected(self) -> bool:
        """Verifica si hay conexión activa"""
        return self._collection is not None

    def log_transaction_init(
        self,
        client_id: str,
        order_name: str,
        amount: int,
        customer_name: str,
        token_ws: Optional[str] = None,
        buy_order: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        📝 Registra el inicio de una transacción

        Args:
            client_id: ID del tenant
            order_name: Nombre de la orden en Odoo (ej: S00123)
            amount: Monto en CLP
            customer_name: Nombre del cliente
            token_ws: Token de Webpay (si ya se tiene)
            buy_order: Código de orden para Webpay
            extra_data: Datos adicionales

        Returns:
            str: ID del documento insertado o None si falla
        """
        if not self._is_connected():
            return None

        try:
            doc = {
                "event_type": "TRANSACTION_INIT",
                "client_id": client_id,
                "order_name": order_name,
                "amount": amount,
                "customer_name": customer_name,
                "token_ws": token_ws,
                "buy_order": buy_order,
                "status": "PENDING",
                "odoo_synced": False,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }

            if extra_data:
                doc["extra_data"] = extra_data

            result = self._collection.insert_one(doc)
            print(f"📝 Log INIT registrado: {order_name} -> {result.inserted_id}")
            return str(result.inserted_id)

        except Exception as e:
            print(f"⚠️ Error registrando log INIT: {str(e)}")
            return None

    def log_transaction_created(
        self,
        buy_order: str,
        token_ws: str,
        client_id: str,
        order_name: str,
        amount: int,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        📝 Registra que la transacción fue creada en Webpay

        Se llama después de recibir respuesta exitosa de Webpay.create()
        """
        if not self._is_connected():
            return None

        try:
            doc = {
                "event_type": "TRANSACTION_CREATED",
                "token_ws": token_ws,
                "buy_order": buy_order,
                "client_id": client_id,
                "order_name": order_name,
                "amount": amount,
                "status": "CREATED",
                "odoo_synced": False,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }

            if extra_data:
                doc["extra_data"] = extra_data

            result = self._collection.insert_one(doc)
            print(f"📝 Log CREATED registrado: {buy_order} token={token_ws[:20]}...")
            return str(result.inserted_id)

        except Exception as e:
            print(f"⚠️ Error registrando log CREATED: {str(e)}")
            return None

    def log_transaction_commit(
        self,
        token_ws: str,
        transbank_response: Dict[str, Any],
        client_id: str,
        odoo_order_id: Optional[int] = None,
        odoo_order_name: Optional[str] = None,
        odoo_synced: bool = False,
        odoo_transaction_id: Optional[int] = None,
        error: Optional[str] = None
    ) -> bool:
        """
        📝 Registra el resultado del commit de una transacción

        Args:
            token_ws: Token de la transacción
            transbank_response: Respuesta completa de Transbank
            client_id: ID del tenant
            odoo_order_id: ID de la orden en Odoo (si se encontró)
            odoo_order_name: Nombre de la orden en Odoo
            odoo_synced: Si se sincronizó correctamente con Odoo
            odoo_transaction_id: ID del payment.transaction en Odoo
            error: Mensaje de error si hubo problemas

        Returns:
            bool: True si se registró correctamente
        """
        if not self._is_connected():
            return False

        try:
            # Extraer datos de la respuesta de Transbank
            status = transbank_response.get("status", "UNKNOWN")
            response_code = transbank_response.get("response_code")
            buy_order = transbank_response.get("buy_order", "")
            amount = transbank_response.get("amount", 0)
            authorization_code = transbank_response.get("authorization_code")
            transaction_date = transbank_response.get("transaction_date")

            doc = {
                "event_type": "TRANSACTION_COMMIT",
                "token_ws": token_ws,
                "buy_order": buy_order,
                "client_id": client_id,
                "order_name": odoo_order_name,
                "order_id": odoo_order_id,
                "amount": amount,
                "status": status,
                "transbank": {
                    "response_code": response_code,
                    "authorization_code": authorization_code,
                    "transaction_date": transaction_date,
                    "full_response": transbank_response
                },
                "odoo_synced": odoo_synced,
                "odoo_transaction_id": odoo_transaction_id,
                "error": error,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }

            # Intentar actualizar si existe, sino insertar
            result = self._collection.update_one(
                {"token_ws": token_ws},
                {"$set": doc},
                upsert=True
            )

            status_emoji = "✅" if status == "AUTHORIZED" else "❌"
            sync_emoji = "🔄" if odoo_synced else "⚠️"
            print(f"📝 Log COMMIT registrado: {buy_order} {status_emoji} {status} {sync_emoji} odoo_synced={odoo_synced}")

            return True

        except Exception as e:
            print(f"⚠️ Error registrando log COMMIT: {str(e)}")
            return False

    def update_odoo_sync_status(
        self,
        token_ws: str,
        odoo_synced: bool,
        odoo_order_id: Optional[int] = None,
        odoo_transaction_id: Optional[int] = None,
        error: Optional[str] = None
    ) -> bool:
        """
        🔄 Actualiza el estado de sincronización con Odoo

        Útil para actualizar después de reintentos de sincronización.
        """
        if not self._is_connected():
            return False

        try:
            update_data = {
                "odoo_synced": odoo_synced,
                "updated_at": datetime.now(timezone.utc)
            }

            if odoo_order_id:
                update_data["order_id"] = odoo_order_id
            if odoo_transaction_id:
                update_data["odoo_transaction_id"] = odoo_transaction_id
            if error:
                update_data["error"] = error

            result = self._collection.update_one(
                {"token_ws": token_ws},
                {"$set": update_data}
            )

            return result.modified_count > 0

        except Exception as e:
            print(f"⚠️ Error actualizando sync status: {str(e)}")
            return False

    def get_unsynced_transactions(self, client_id: Optional[str] = None) -> list:
        """
        🔍 Obtiene transacciones autorizadas pero no sincronizadas con Odoo

        Útil para recuperación manual o automática de pagos perdidos.

        Args:
            client_id: Filtrar por cliente específico (opcional)

        Returns:
            Lista de transacciones pendientes de sincronizar
        """
        if not self._is_connected():
            return []

        try:
            query = {
                "status": "AUTHORIZED",
                "odoo_synced": False
            }

            if client_id:
                query["client_id"] = client_id

            cursor = self._collection.find(query).sort("created_at", -1)
            return list(cursor)

        except Exception as e:
            print(f"⚠️ Error obteniendo transacciones no sincronizadas: {str(e)}")
            return []

    def get_transaction_by_token(self, token_ws: str) -> Optional[Dict[str, Any]]:
        """
        🔍 Busca una transacción por su token
        """
        if not self._is_connected():
            return None

        try:
            return self._collection.find_one({"token_ws": token_ws})
        except Exception as e:
            print(f"⚠️ Error buscando transacción: {str(e)}")
            return None

    def get_transaction_by_order(self, buy_order: str) -> Optional[Dict[str, Any]]:
        """
        🔍 Busca una transacción por su buy_order
        """
        if not self._is_connected():
            return None

        try:
            return self._collection.find_one({"buy_order": buy_order})
        except Exception as e:
            print(f"⚠️ Error buscando transacción: {str(e)}")
            return None

    def log_error(
        self,
        event_type: str,
        client_id: str,
        error_message: str,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        ❌ Registra un error
        """
        if not self._is_connected():
            return False

        try:
            doc = {
                "event_type": f"ERROR_{event_type}",
                "client_id": client_id,
                "status": "ERROR",
                "error": error_message,
                "stack_trace": traceback.format_exc(),
                "created_at": datetime.now(timezone.utc),
            }

            if extra_data:
                doc["extra_data"] = extra_data

            self._collection.insert_one(doc)
            print(f"📝 Log ERROR registrado: {event_type} - {error_message[:50]}...")
            return True

        except Exception as e:
            print(f"⚠️ Error registrando log ERROR: {str(e)}")
            return False


# 🌟 Instancia global del logger (Singleton)
mongo_logger = MongoLogService()
