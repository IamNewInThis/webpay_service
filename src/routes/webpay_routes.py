"""
🌐 Rutas de Webpay
==================
Define todos los endpoints relacionados con transacciones de Webpay Plus.
Maneja inicialización, confirmación y cancelación de transacciones.

🔒 Seguridad (Arquitectura Odoo Online):
- /init requiere ORIGEN VÁLIDO (dominio Odoo autorizado) - llamado desde frontend
- /commit (GET/POST) no requiere autenticación (llamado por Transbank)

⚠️ IMPORTANTE: En Odoo Online no puedes agregar endpoints backend ni guardar secretos.
   Todo el control de seguridad se hace en este middleware, que:
   1. Valida que las llamadas vengan del dominio Odoo autorizado
   2. Gestiona las claves API de Webpay de forma segura
   3. Actualiza Odoo vía JSON-RPC con credenciales seguras
"""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from src.services.webpay_service import WebpayService
from src.services.odoo_sales import OdooSalesService
from src.security import verify_api_key, verify_frontend_request
from src.client_config import ClientConfig, get_client_from_origin
from src.config import settings
from typing import Dict, Any, Optional
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# Crear router para agrupar las rutas de Webpay
webpay_router = APIRouter(prefix="/webpay", tags=["webpay"])


@webpay_router.post("/init")
async def init_webpay_transaction(
    request: Request,
    validation: Dict[str, Any] = Depends(verify_frontend_request)
) -> Dict[str, Any]:
    """
    🚀 Inicializa una nueva transacción Webpay
    
    🔒 Seguridad: Valida que el request venga del dominio Odoo autorizado
                 e identifica automáticamente al cliente
    
    Este endpoint es llamado desde el frontend de Odoo (JavaScript).
    NO requiere API Key porque el frontend no puede guardar secretos de forma segura.
    En su lugar, validamos que el origen sea un dominio Odoo autorizado.
    
    Headers opcionales (recomendados):
        X-Timestamp: Timestamp unix para prevenir replay attacks
    
    Body esperado:
    {
        "amount": 10000,
        "customer_name": "Juan Pérez",
        "order_date": "2025-10-19"
    }
    
    Returns:
        {
            "token": "abc123...",
            "url": "https://webpay3gint.transbank.cl/webpayserver/initTransaction"
        }
    """
    try:
        # Obtener configuración del cliente desde la validación
        client: ClientConfig = validation.get("client")
        
        if not client:
            return {"error": "Cliente no identificado"}
        
        # Validar primero que las credenciales de Odoo sigan funcionando
        odoo_service = OdooSalesService(client)
        if not odoo_service.authenticate():
            error_msg = "No se pudo autenticar con Odoo. Verifique credenciales del cliente."
            print(f"❌ {error_msg}")
            return {"error": error_msg, "message": "El flujo de Webpay se detiene porque Odoo no responde."}

        # Crear servicio de Webpay específico para este cliente
        webpay_service = WebpayService(client)
        
        # Extraer datos del request
        data = await request.json()
        amount = data.get("amount", 1000)
        customer_name = data.get("customer_name", "Cliente")
        order_date = data.get("order_date")
        order_name = data.get("order_name")
        
        print(f"💳 Iniciando transacción para cliente: {client.client_name}")
        print(f"   Cliente final: {customer_name}, Monto: ${amount}")
        
        # Crear transacción usando el servicio
        response = webpay_service.create_transaction(
            amount=amount,
            customer_name=customer_name,
            order_date=order_date,
            order_name=order_name
        )
        
        return response
        
    except Exception as e:
        print(f"❌ Error en /webpay/init: {str(e)}")
        return {"error": "Error interno del servidor", "message": str(e)}


@webpay_router.post("/commit")
async def commit_webpay_transaction_post(request: Request) -> RedirectResponse:
    """
    ✅ Confirma una transacción Webpay (método POST)
    
    Endpoint que recibe la respuesta de Webpay cuando el usuario completa
    el pago exitosamente. Webpay envía el token_ws via POST form data.
    
    Form data esperado:
        token_ws: Token de la transacción
    
    Returns:
        Redirección a la página de confirmación o error según el resultado
    """
    try:
        # Extraer token del formulario
        form = await request.form()
        token = form.get("token_ws")
        
        if not token:
            print("⚠️ POST sin token_ws - Posible cancelación")
            # Sin token, no podemos identificar el cliente, usar primera config activa
            from src.client_config import client_loader
            active_clients = client_loader.get_active_clients()
            fallback_url = active_clients[0].odoo.url if active_clients else "http://localhost:8000"
            return RedirectResponse(
                url=f"{fallback_url}/shop/payment?status=cancelled"
            )
        
        # Identificar cliente primero (para crear servicio con su configuración)
        # Por ahora usamos servicio sin cliente para commit, ya que no tenemos el cliente todavía
        temp_webpay_service = WebpayService()  # Servicio temporal para commit
        result = temp_webpay_service.commit_transaction(token)
        
        # Identificar cliente desde el buy_order
        client = _identify_client_from_result(result)
        
        if not client:
            print("⚠️ No se pudo identificar cliente desde transacción")
            from src.client_config import client_loader
            active_clients = client_loader.get_active_clients()
            client = active_clients[0] if active_clients else None
        
        if not client:
            return RedirectResponse(url="/shop/payment?status=error")
        
        odoo_url = client.odoo.url
        
        # Si la transacción es exitosa, intentar actualizar orden en Odoo
        if temp_webpay_service.is_transaction_successful(result):
            # Crear servicio de Odoo específico para este cliente
            odoo_service = OdooSalesService(client)
            
            # Intentar encontrar y actualizar la orden correspondiente en Odoo
            await _process_successful_payment(result, odoo_service, client)
            
            redirect_url = (
                f"{odoo_url}/shop/confirmation"
                f"?status=success&order={result['buy_order']}"
            )
            print(f"✅ POST - Redirigiendo a confirmación: {result['buy_order']}")
        else:
            redirect_url = f"{odoo_url}/shop/payment?status=rejected"
            print("❌ POST - Transacción rechazada")
        
        return RedirectResponse(url=redirect_url)
        
    except Exception as e:
        print(f"❌ Error en POST /webpay/commit: {str(e)}")
        # Intentar obtener un cliente para redirección
        from src.client_config import client_loader
        active_clients = client_loader.get_active_clients()
        fallback_url = active_clients[0].odoo.url if active_clients else "http://localhost:8000"
        return RedirectResponse(
            url=f"{fallback_url}/shop/payment?status=error"
        )


@webpay_router.get("/commit")
async def commit_webpay_transaction_get(request: Request) -> RedirectResponse:
    """
    🔄 Maneja respuestas de Webpay vía GET
    
    Webpay a veces envía la respuesta como GET con parámetros en la URL.
    Esto puede suceder tanto para transacciones exitosas como cancelaciones.
    
    Query params esperados:
        - token_ws: Para transacciones exitosas/fallidas
        - TBK_TOKEN: Para cancelaciones del usuario
        - TBK_ORDEN_COMPRA: Orden de compra (en cancelaciones)
        - TBK_ID_SESION: ID de sesión (en cancelaciones)
    
    Returns:
        Redirección apropiada según el tipo de respuesta
    """
    try:
        params = dict(request.query_params)
        print(f"📥 GET /webpay/commit - Params: {params}")
        
        token = params.get("token_ws")
        
        # Obtener cliente (intentar desde referer si está disponible)
        origin = request.headers.get("referer", "")
        client = get_client_from_origin(origin) if origin else None
        
        if not client:
            from src.client_config import client_loader
            active_clients = client_loader.get_active_clients()
            client = active_clients[0] if active_clients else None
        
        if not client:
            return RedirectResponse(url="/shop/payment?status=error")
        
        odoo_url = client.odoo.url
        
        if not token:
            # Verificar si es una cancelación (tiene TBK_TOKEN pero no token_ws)
            if "TBK_TOKEN" in params:
                print("❌ GET - Usuario canceló la transacción")
                return RedirectResponse(
                    url=f"{odoo_url}/shop/payment?status=cancelled"
                )
            else:
                print("⚠️ GET - Sin tokens válidos")
                return RedirectResponse(
                    url=f"{odoo_url}/shop/payment?status=error"
                )
        
        # Procesar transacción con token_ws
        # Crear servicio temporal de Webpay para commit (sin cliente específico aún)
        temp_webpay_service = WebpayService()
        result = temp_webpay_service.commit_transaction(token)
        
        # Identificar cliente desde el resultado
        client_from_result = _identify_client_from_result(result)
        if client_from_result:
            client = client_from_result
            odoo_url = client.odoo.url
        
        # Si la transacción es exitosa, intentar actualizar orden en Odoo
        if temp_webpay_service.is_transaction_successful(result):
            # Crear servicio de Odoo específico para este cliente
            odoo_service = OdooSalesService(client)
            
            # Intentar encontrar y actualizar la orden correspondiente en Odoo
            await _process_successful_payment(result, odoo_service, client)
            
            redirect_url = (
                f"{odoo_url}/shop/confirmation"
                f"?status=success&order={result['buy_order']}"
            )
            print(f"✅ GET - Redirigiendo a confirmación: {result['buy_order']}")
        else:
            redirect_url = f"{odoo_url}/shop/payment?status=rejected"
            print("❌ GET - Transacción rechazada")
        
        return RedirectResponse(url=redirect_url)
        
    except Exception as e:
        print(f"❌ Error en GET /webpay/commit: {str(e)}")
        from src.client_config import client_loader
        active_clients = client_loader.get_active_clients()
        fallback_url = active_clients[0].odoo.url if active_clients else "http://localhost:8000"
        return RedirectResponse(
            url=f"{fallback_url}/shop/payment?status=error"
        )


def _identify_client_from_result(payment_result: Dict[str, Any]) -> Optional[ClientConfig]:
    """
    🔍 Intenta identificar al cliente desde el resultado del pago
    
    Extrae información del buy_order y busca qué cliente corresponde.
    Esto es útil en callbacks donde no tenemos el Origin header.
    
    Args:
        payment_result: Resultado de la transacción de Webpay
        
    Returns:
        ClientConfig del cliente identificado o None
    """
    try:
        buy_order = payment_result.get("buy_order", "") or ""
        
        # TODO: Si en el futuro necesitas diferenciar clientes por buy_order,
        # puedes agregar un prefijo al buy_order que incluya el client_id
        # Por ejemplo: "tecnogrow_Juan-Perez_10000_20251119"
        
        # Por ahora, si solo hay un cliente activo, usarlo
        from src.client_config import client_loader
        active_clients = client_loader.get_active_clients()
        
        if len(active_clients) == 1:
            return active_clients[0]
        
        # Si hay múltiples clientes, necesitarías lógica adicional
        # para identificar cuál es basándote en el buy_order
        print(f"⚠️ Múltiples clientes activos, no se puede identificar desde buy_order: {buy_order}")
        return None
        
    except Exception as e:
        print(f"❌ Error identificando cliente: {str(e)}")
        return None

async def _process_successful_payment(
    payment_result: Dict[str, Any],
    odoo_service: OdooSalesService,
    client: ClientConfig
) -> None:
    """
    🔄 Procesa un pago exitoso e intenta actualizar la orden en Odoo
    usando DIRECTAMENTE el buy_order como name de sale.order.
    """
    try:
        # === Datos base de la transacción ===
        buy_order = payment_result.get("buy_order", "") or ""
        raw_amount = payment_result.get("amount", 0)

        try:
            amount = int(float(raw_amount))
        except (TypeError, ValueError):
            amount = 0

        print(f"🔎 Procesando pago exitoso → buy_order={buy_order}, amount={amount}")

        # === 1️⃣ Buscar la orden EXACTA en Odoo por name ===
        print(f"🔎 Buscando orden exacta en Odoo name='{buy_order}'")
        order = odoo_service.get_order_by_name(buy_order)

        if not order:
            print(f"❌ No se encontró en Odoo la orden '{buy_order}'")
            return

        print(f"✅ Orden encontrada → ID={order['id']} name={order['name']} state={order['state']}")

        # === 2️⃣ Confirmar la orden o forzar estado "sale" ===
        success = odoo_service.update_order_payment_status(
            order_id=order["id"],
            payment_data=payment_result
        )

        if not success:
            print(f"❌ No se pudo confirmar la orden {order['name']}")
            return

        print(f"💚 Orden {order['name']} confirmada correctamente en Odoo")

        # === 3️⃣ Determinar estado de transacción ===
        tx_status = (
            "done"
            if payment_result.get("status") == "AUTHORIZED"
            or payment_result.get("response_code") == 0
            else "error"
        )

        # === 4️⃣ Registrar transacción Webpay en Odoo ===
        registered = odoo_service.register_webpay_transaction(
            order_id=order["id"],
            order_name=order["name"],
            amount=order["amount_total"],
            status=tx_status,
            payment_data=payment_result,
            order_data=order,
        )

        if registered:
            print(f"💳 Transacción Webpay registrada exitosamente en Odoo para {order['name']}")
        else:
            print(f"⚠️ No se pudo registrar la transacción Webpay en Odoo")

    except Exception as e:
        print(f"❌ Error procesando pago exitoso: {str(e)}")
