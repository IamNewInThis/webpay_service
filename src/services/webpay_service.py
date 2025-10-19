"""
🏦 Servicio de Webpay Plus
========================
Maneja toda la lógica de negocio relacionada con transacciones de Webpay Plus.
Abstrae la configuración y operaciones del SDK de Transbank.
"""

from transbank.webpay.webpay_plus.transaction import Transaction
from transbank.common.integration_commerce_codes import IntegrationCommerceCodes
from transbank.common.integration_api_keys import IntegrationApiKeys
from transbank.common.options import WebpayOptions
from transbank.common.integration_type import IntegrationType
from typing import Dict, Any


class WebpayService:
    """
    🔧 Servicio para manejar transacciones Webpay Plus
    
    Encapsula toda la configuración y operaciones del SDK de Transbank,
    proporcionando una interfaz limpia para inicializar y confirmar transacciones.
    """
    
    def __init__(self):
        """🚀 Inicializa la configuración de Webpay en modo TEST"""
        self.commerce_code = IntegrationCommerceCodes.WEBPAY_PLUS
        self.api_key = IntegrationApiKeys.WEBPAY
        self.integration_type = IntegrationType.TEST
        self.options = WebpayOptions(
            self.commerce_code, 
            self.api_key, 
            self.integration_type
        )
        print("🔧 WebpayService inicializado en modo TEST")
    
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
            # Generar identificadores únicos para la transacción
            buy_order = f"O-{abs(hash(str(amount) + str(customer_name))) % 1000000}"
            session_id = f"S-{abs(hash(buy_order)) % 1000000}"
            
            # URL de retorno donde Webpay enviará la respuesta
            return_url = "https://webpay-service.onrender.com/webpay/commit"
            
            # Crear transacción usando el SDK de Transbank
            tx = Transaction(self.options)
            response = tx.create(buy_order, session_id, amount, return_url)
            
            print(f"🔸 Transacción creada - Orden: {buy_order}, Monto: ${amount}")
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
