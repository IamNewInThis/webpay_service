"""
🏦 Servicio de Webpay Plus
========================
Maneja toda la lógica de negocio relacionada con transacciones de Webpay Plus.
Abstrae la configuración y operaciones del SDK de Transbank.
"""

import os
import re
import time
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

from transbank.common.integration_api_keys import IntegrationApiKeys
from transbank.common.integration_commerce_codes import IntegrationCommerceCodes
from transbank.common.integration_type import IntegrationType
from transbank.common.options import WebpayOptions
from transbank.webpay.webpay_plus.transaction import Transaction

from src.config import settings
from src.tenants import TenantConfig, tenant_manager


class WebpayService:
    """
    🔧 Servicio para manejar transacciones Webpay Plus
    
    Encapsula toda la configuración y operaciones del SDK de Transbank,
    proporcionando una interfaz limpia para inicializar y confirmar transacciones.
    """
    
    def __init__(self):
        """🚀 Inicializa la configuración base de Webpay (modo TEST por defecto)"""
        default_commerce = os.getenv("WEBPAY_COMMERCE_CODE") or IntegrationCommerceCodes.WEBPAY_PLUS
        default_api_key = os.getenv("WEBPAY_API_KEY") or IntegrationApiKeys.WEBPAY
        default_env = os.getenv("WEBPAY_ENVIRONMENT", "TEST")

        self.default_options = WebpayOptions(
            default_commerce,
            default_api_key,
            self._map_integration_type(default_env),
        )
        self.return_url = settings.WEBPAY_RETURN_URL
        self._options_cache: Dict[str, WebpayOptions] = {}
        self._token_cache: Dict[str, Dict[str, Any]] = {}
        print("🔧 WebpayService inicializado (multi-tenant ready)")
    
    def create_transaction(
        self,
        amount: int,
        customer_name: str | None = None,
        order_date: str | None = None,
        tenant: Optional[TenantConfig] = None,
    ) -> Dict[str, Any]:
        """
        💳 Crea una nueva transacción en Webpay
        
        Args:
            amount: Monto en pesos chilenos (entero)
            customer_name: Nombre del cliente (opcional)
            order_date: Fecha de la orden (opcional)
            
        Returns:
            Dict con 'token' y 'url' para redireccionar al usuario
        """
        try:
            try:
                normalized_amount = int(float(amount))
            except (TypeError, ValueError):
                normalized_amount = 0

            # 🔤 Preparar identificadores reutilizables para el commit
            customer_label = self._sanitize_customer_name(customer_name)
            order_date_str = self._normalize_order_date(order_date)
            date_token = order_date_str.replace("-", "")

            buy_order = self._build_buy_order(customer_label, normalized_amount, date_token)
            tenant = tenant or tenant_manager.default_tenant
            raw_session = f"S-{abs(hash((buy_order, normalized_amount))) % 1000000}"
            session_id = tenant_manager.build_session_id(tenant, raw_session)
            options = self._get_options_for_tenant(tenant)
            
            # Crear transacción usando el SDK de Transbank
            tx = Transaction(options)
            response = tx.create(buy_order, session_id, normalized_amount, self.return_url)

            # Enriquecer respuesta original para facilitar auditoría
            response.update(
                {
                    "buy_order": buy_order,
                    "session_id": session_id,
                    "customer_name": customer_label.replace("-", " "),
                    "order_date": order_date_str,
                    "tenant_id": tenant.id,
                }
            )

            token = response.get("token")
            if token:
                self._remember_token(token, tenant, options)
            else:
                print("⚠️ Respuesta de Webpay sin token - no se pudo registrar cache")
            
            print(f"🔸 Transacción creada - Orden: {buy_order}, Monto: ${normalized_amount}")
            print(f"🔸 Token: {response.get('token', 'N/A')}")
            
            return response
            
        except Exception as e:
            print(f"❌ Error creando transacción: {str(e)}")
            raise e
    
    def commit_transaction(self, token: str) -> Dict[str, Any]:
        """
        ✅ Confirma una transacción usando el token de Webpay
        
        Args:
            token: Token ws devuelto por Webpay después del pago
            
        Returns:
            Dict con el resultado de la transacción (status, buy_order, amount, etc.)
        """
        try:
            options, cached_tenant = self._options_for_token(token)
            tx = Transaction(options)
            result = tx.commit(token)
            if cached_tenant:
                result["tenant_id"] = cached_tenant.id
            
            # Log detallado del resultado
            status = result.get("status")
            response_code = result.get("response_code")
            buy_order = result.get("buy_order")
            amount = result.get("amount")
            
            print(f"✅ Transacción confirmada - Orden: {buy_order}")
            print(f"🔍 Status: {status}, Response Code: {response_code}")
            print(f"💰 Monto: ${amount}")
            
            return result
            
        except Exception as e:
            print(f"❌ Error confirmando transacción: {str(e)}")
            raise e
    
    def is_transaction_successful(self, transaction_result: Dict[str, Any]) -> bool:
        """
        🎯 Determina si una transacción fue exitosa
        
        Args:
            transaction_result: Resultado devuelto por commit_transaction
            
        Returns:
            True si la transacción fue autorizada exitosamente
        """
        status = transaction_result.get("status")
        response_code = transaction_result.get("response_code")
        
        # Una transacción es exitosa si está AUTHORIZED o tiene response_code 0
        is_success = status == "AUTHORIZED" or response_code == 0
        
        print(f"🎯 Transacción {'EXITOSA' if is_success else 'FALLIDA'}")
        return is_success

    def _sanitize_customer_name(self, customer_name: str | None) -> str:
        """
        Genera un identificador seguro y compacto para el nombre del cliente.
        """
        if not customer_name:
            return "cliente"

        cleaned = re.sub(r"[^0-9A-Za-z\s-]", "", customer_name).strip()
        cleaned = re.sub(r"\s+", "-", cleaned)
        cleaned = cleaned or "cliente"

        # Limitar longitud para respetar restricciones de Webpay (máx. 26 caracteres en total)
        return cleaned[:12].lower()

    def _normalize_order_date(self, order_date: str | None) -> str:
        """
        Normaliza la fecha a formato YYYY-MM-DD.
        """
        try:
            if order_date:
                parsed = datetime.strptime(order_date, "%Y-%m-%d")
            else:
                parsed = datetime.utcnow()
        except ValueError:
            parsed = datetime.utcnow()
        return parsed.strftime("%Y-%m-%d")

    def _build_buy_order(self, customer_label: str, amount: int, date_token: str) -> str:
        """
        Construye un buy_order reversible para poder identificar la orden en Odoo.
        """
        base_buy_order = f"{customer_label}_{amount}_{date_token}"

        if len(base_buy_order) <= 26:
            return base_buy_order

        # Ajustar longitud del nombre para respetar la restricción total.
        static_length = len(str(amount)) + len(date_token) + 2  # guiones bajos
        available_for_name = max(1, 26 - static_length)
        trimmed_name = customer_label[:available_for_name]
        adjusted_buy_order = f"{trimmed_name}_{amount}_{date_token}"

        if len(adjusted_buy_order) <= 26:
            return adjusted_buy_order

        # Fallback defensivo: usar hash pero mantener los tres componentes legibles.
        hashed_suffix = abs(hash(base_buy_order)) % 1000000
        compact_date = date_token[-6:] if len(date_token) >= 6 else date_token
        hashed_str = str(hashed_suffix)
        hashed_buy_order = f"w{hashed_str}_{amount}_{compact_date}"

        if len(hashed_buy_order) <= 26:
            return hashed_buy_order

        overflow = len(hashed_buy_order) - 26
        if overflow >= len(hashed_str):
            trimmed_hash = hashed_str[: max(1, len(hashed_str) - 1)]
        else:
            trimmed_hash = hashed_str[: len(hashed_str) - overflow]

        adjusted = f"w{trimmed_hash}_{amount}_{compact_date}"
        return adjusted[:26]

    def _remember_token(self, token: str, tenant: TenantConfig, options: WebpayOptions) -> None:
        self._token_cache[token] = {
            "tenant_id": tenant.id,
            "options": options,
            "created_at": time.time(),
        }

    def _options_for_token(self, token: str) -> Tuple[WebpayOptions, Optional[TenantConfig]]:
        data = self._token_cache.pop(token, None)
        if not data:
            return self.default_options, None
        tenant = tenant_manager.get_tenant_by_id(data.get("tenant_id"))
        return data.get("options", self.default_options), tenant

    def _get_options_for_tenant(self, tenant: TenantConfig) -> WebpayOptions:
        if not tenant or not tenant.webpay:
            return self.default_options

        cached = self._options_cache.get(tenant.id)
        if cached:
            return cached

        integration_type = self._map_integration_type(tenant.webpay.environment)
        options = WebpayOptions(tenant.webpay.commerce_code, tenant.webpay.api_key, integration_type)
        self._options_cache[tenant.id] = options
        return options

    @staticmethod
    def _map_integration_type(environment: Optional[str]) -> IntegrationType:
        env = (environment or "TEST").upper()
        if env in {"PROD", "PRODUCTION", "LIVE"}:
            return IntegrationType.LIVE
        return IntegrationType.TEST
