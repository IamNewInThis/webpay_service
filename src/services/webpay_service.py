"""
🏦 Servicio de Webpay Plus
========================
Maneja toda la lógica de negocio relacionada con transacciones de Webpay Plus.
Abstrae la configuración y operaciones del SDK de Transbank.
Soporta múltiples clientes con configuración dinámica.
"""

import re
import os
from datetime import datetime
from typing import Dict, Any, Optional

from transbank.common.integration_api_keys import IntegrationApiKeys
from transbank.common.integration_commerce_codes import IntegrationCommerceCodes
from transbank.common.integration_type import IntegrationType
from transbank.common.options import WebpayOptions
from transbank.webpay.webpay_plus.transaction import Transaction

from src.config import settings
from src.client_config import ClientConfig


class WebpayService:
    """
    🔧 Servicio para manejar transacciones Webpay Plus
    
    Encapsula toda la configuración y operaciones del SDK de Transbank,
    proporcionando una interfaz limpia para inicializar y confirmar transacciones.
    Soporta configuración dinámica por cliente (TEST, CERTIFICATION, PRODUCTION).
    """
    
    def __init__(self, client_config: Optional[ClientConfig] = None):
        """
        🚀 Inicializa la configuración de Webpay
        
        Args:
            client_config: Configuración del cliente. Si es None, usa modo TEST por defecto.
        """
        if client_config and client_config.webpay:
            # Configuración específica del cliente
            webpay_config = client_config.webpay
            integration_type = webpay_config.integration_type.upper()
            
            if integration_type == "TEST":
                self.commerce_code = IntegrationCommerceCodes.WEBPAY_PLUS
                self.api_key = IntegrationApiKeys.WEBPAY
                self.integration_type = IntegrationType.TEST
                print(f"🔧 WebpayService inicializado para {client_config.client_name} en modo TEST")
                
            elif integration_type == "CERTIFICATION":
                if not webpay_config.commerce_code or not webpay_config.api_key:
                    raise ValueError(f"commerce_code y api_key requeridos para CERTIFICATION")
                self.commerce_code = webpay_config.commerce_code
                self.api_key = webpay_config.api_key
                self.integration_type = IntegrationType.TEST  # CERTIFICATION usa TEST environment
                print(f"🔧 WebpayService inicializado para {client_config.client_name} en modo CERTIFICATION")
                
            elif integration_type == "PRODUCTION":
                if not webpay_config.commerce_code or not webpay_config.api_key:
                    raise ValueError(f"commerce_code y api_key requeridos para PRODUCTION")
                self.commerce_code = webpay_config.commerce_code
                self.api_key = webpay_config.api_key
                self.integration_type = IntegrationType.LIVE
                print(f"🔧 WebpayService inicializado para {client_config.client_name} en modo PRODUCTION")
                
            else:
                raise ValueError(f"integration_type inválido: {integration_type}. Usa TEST, CERTIFICATION o PRODUCTION")
        else:
            # Modo por defecto: TEST
            self.commerce_code = IntegrationCommerceCodes.WEBPAY_PLUS
            self.api_key = IntegrationApiKeys.WEBPAY
            self.integration_type = IntegrationType.TEST
            print("🔧 WebpayService inicializado en modo TEST (sin cliente)")
        
        self.options = WebpayOptions(
            self.commerce_code, 
            self.api_key, 
            self.integration_type
        )
        print(f"🧩 DEBUG CONFIG → integration_type={self.integration_type} commerce_code={self.commerce_code} api_key_len={len(self.api_key) if self.api_key else 0}")

    
    def create_transaction(self, amount: int, customer_name: str = None, order_date: str = None) -> Dict[str, Any]:
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
            session_id = f"S-{abs(hash((buy_order, normalized_amount))) % 1000000}"

            # Generar identificadores únicos para la transacción
            # URL de retorno donde Webpay enviará la respuesta
            return_url = settings.WEBPAY_RETURN_URL
            
            # Crear transacción usando el SDK de Transbank
            tx = Transaction(self.options)
            response = tx.create(buy_order, session_id, normalized_amount, return_url)

            print(f"📤 Enviando create() → buy_order={buy_order} session_id={session_id} amount={normalized_amount} return_url={return_url}")
            print(f"📤 DEBUG REQUEST → commerce_code={self.commerce_code} integration_type={self.integration_type} api_key_prefix={self.api_key[:6] if self.api_key else 'NONE'}")


            # Enriquecer respuesta original para facilitar auditoría
            response.update(
                {
                    "buy_order": buy_order,
                    "session_id": session_id,
                    "customer_name": customer_label.replace("-", " "),
                    "order_date": order_date_str,
                }
            )
            
            print(f"🔸 Transacción creada - Orden: {buy_order}, Monto: ${normalized_amount}")
            print(f"🔸 Token: {response.get('token', 'N/A')}")
            
            return response
            
        except Exception as e:
            print(f"🛑 CREATE ERROR DETAIL → type={type(e)} message={str(e)}")

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
            tx = Transaction(self.options)
            result = tx.commit(token)
            
            # Log detallado del resultado
            status = result.get("status")
            response_code = result.get("response_code")
            buy_order = result.get("buy_order")
            amount = result.get("amount")
            
            print(f"✅ Transacción confirmada - Orden: {buy_order}")
            print(f"🔍 Status: {status}, Response Code: {response_code}")
            print(f"💰 Monto: ${amount}")
            print(f"📩 Enviando commit() → token={token}")
            print(f"📩 DEBUG REQUEST → commerce_code={self.commerce_code} integration_type={self.integration_type}")

            
            return result
            
        except Exception as e:
            print(f"🛑 COMMIT ERROR DETAIL → type={type(e)} message={str(e)}")
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
