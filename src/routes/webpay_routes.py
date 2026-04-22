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

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from src.services.webpay_service import WebpayService
from src.services.odoo_sales import OdooSalesService
from src.services.odoo_invoices import OdooInvoicesService
from src.services.mongo_logger import mongo_logger
from src.security import verify_api_key, verify_frontend_request
from src.client_config import ClientConfig, get_client_from_origin
from src.config import settings
from typing import Dict, Any, List, Optional
from datetime import datetime
import os
import re
from dotenv import load_dotenv


def validate_order_name(order_name: str) -> tuple[bool, str]:
    """
    🔒 Valida que el nombre de la orden sea válido de Odoo y no un fallback temporal.

    Rechaza:
    - ORDER-{timestamp} (fallback del frontend cuando no encuentra el nombre real)
    - Nombres vacíos o None
    - Nombres que no parezcan órdenes válidas de Odoo

    Acepta:
    - SO00123, S00123 (Sale Orders)
    - PO00123 (Purchase Orders)
    - WH/OUT/00123 (Stock moves)
    - Otros formatos comunes de Odoo

    Returns:
        tuple: (es_valido: bool, mensaje_error: str)
    """
    if not order_name or not order_name.strip():
        return False, "El nombre de la orden está vacío"

    order_name = order_name.strip()

    # ❌ Rechazar patrón de fallback: ORDER-{timestamp}
    # Este patrón indica que el frontend no pudo obtener el nombre real de la orden
    if re.match(r'^ORDER-\d+$', order_name):
        return False, f"Nombre de orden inválido '{order_name}'. El frontend no pudo obtener el nombre real de la orden de Odoo."

    # ❌ Rechazar otros patrones de fallback comunes
    if order_name.startswith('ORDER-') or order_name.startswith('TEMP-') or order_name.startswith('TEST-'):
        return False, f"Nombre de orden temporal detectado: '{order_name}'. Debe ser una orden real de Odoo."

    # ✅ Validar que parezca una orden válida de Odoo
    # Patrones comunes: SO00123, S00123, PO00123, WH/OUT/00123, INV/2024/00001
    valid_patterns = [
        r'^S\d+$',           # S00123
        r'^SO\d+$',          # SO00123
        r'^PO\d+$',          # PO00123
        r'^WH/.+/\d+$',      # WH/OUT/00123
        r'^INV/.+/\d+$',     # INV/2024/00001
        r'^[A-Z]{2,4}\d+$',  # Otros códigos alfanuméricos
    ]

    for pattern in valid_patterns:
        if re.match(pattern, order_name, re.IGNORECASE):
            return True, ""

    # Si no coincide con ningún patrón conocido pero tampoco es un fallback,
    # lo aceptamos pero con una advertencia
    print(f"⚠️ Nombre de orden con formato no estándar: '{order_name}' - se acepta pero verificar")
    return True, ""

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

        # 🔒 VALIDACIÓN 1: Verificar que el order_name tenga formato válido
        is_valid, error_message = validate_order_name(order_name)
        if not is_valid:
            print(f"❌ VALIDACIÓN FORMATO FALLIDA: {error_message}")
            return {
                "error": "Nombre de orden inválido",
                "message": error_message,
                "code": "INVALID_ORDER_NAME",
                "received_order_name": order_name
            }

        # 🔒 VALIDACIÓN 2 (CRÍTICA): Verificar que la orden EXISTA en Odoo
        # Esta es la validación más importante - previene fraudes y manipulación del frontend
        print(f"🔎 Verificando que la orden '{order_name}' exista en Odoo...")
        odoo_order = odoo_service.get_order_by_name(order_name)

        if not odoo_order:
            error_msg = f"La orden '{order_name}' no existe en Odoo. No se puede procesar el pago."
            print(f"❌ VALIDACIÓN ODOO FALLIDA: {error_msg}")
            mongo_logger.log_error(
                event_type="INIT_ORDER_NOT_FOUND",
                client_id=client.client_id,
                error_message=error_msg,
                extra_data={"order_name": order_name, "amount": amount}
            )
            return {
                "error": "Orden no encontrada",
                "message": error_msg,
                "code": "ORDER_NOT_FOUND_IN_ODOO",
                "received_order_name": order_name
            }

        # Verificar que el monto coincida (tolerancia de 1 peso por redondeo)
        odoo_amount = int(odoo_order.get("amount_total", 0))
        if abs(odoo_amount - amount) > 1:
            error_msg = f"El monto no coincide. Frontend: ${amount}, Odoo: ${odoo_amount}"
            print(f"⚠️ VALIDACIÓN MONTO: {error_msg}")
            # No bloqueamos, pero registramos la discrepancia
            mongo_logger.log_error(
                event_type="INIT_AMOUNT_MISMATCH",
                client_id=client.client_id,
                error_message=error_msg,
                extra_data={"order_name": order_name, "frontend_amount": amount, "odoo_amount": odoo_amount}
            )
            # Usar el monto de Odoo como fuente de verdad
            amount = odoo_amount

        print(f"✅ Orden verificada en Odoo: {odoo_order['name']} (ID: {odoo_order['id']}, Monto: ${odoo_amount})")

        print(f"💳 Iniciando transacción para cliente: {client.client_name}")
        print(f"   Cliente final: {customer_name[:20]}..., Monto: ${amount}")
        print(f"   Orden: {order_name} ✅ (verificada en Odoo)")

        # Crear transacción usando el servicio
        response = webpay_service.create_transaction(
            amount=amount,
            customer_name=customer_name,
            order_date=order_date,
            order_name=order_name
        )

        # 📊 Registrar transacción en MongoDB
        if response.get("token"):
            mongo_logger.log_transaction_created(
                buy_order=response.get("buy_order", order_name),
                token_ws=response.get("token"),
                client_id=client.client_id,
                order_name=order_name,
                amount=amount
            )

        return response

    except Exception as e:
        print(f"❌ Error en /webpay/init: {str(e)}")
        # Registrar error en MongoDB
        mongo_logger.log_error(
            event_type="INIT",
            client_id=client.client_id if client else "unknown",
            error_message=str(e),
            extra_data={"order_name": order_name if 'order_name' in dir() else None}
        )
        return {"error": "Error interno del servidor", "message": str(e)}


def _get_doc_type_from_log(token_ws: str) -> str:
    """Consulta MongoDB para saber si el token corresponde a una factura o venta."""
    try:
        log = mongo_logger.get_transaction_by_token(token_ws)
        if log and isinstance(log.get("extra_data"), dict):
            return log["extra_data"].get("doc_type", "venta")
    except Exception:
        pass
    return "venta"


@webpay_router.post("/init-factura")
async def init_factura_transaction(
    request: Request,
    validation: Dict[str, Any] = Depends(verify_frontend_request),
) -> Dict[str, Any]:
    """
    Inicializa una transacción Webpay para pago de facturas (Pago Express).

    Body esperado:
    {
        "invoice_ids": [123, 456],
        "amount": 50000,
        "customer_name": "Juan Pérez",
        "rut": "12.345.678-9"
    }

    Returns:
        {"token": "...", "url": "..."}
    """
    client: Optional[ClientConfig] = None
    try:
        client = validation.get("client")
        if not client:
            return {"error": "Cliente no identificado"}

        data = await request.json()
        invoice_ids: List[int] = data.get("invoice_ids", [])
        amount = int(data.get("amount", 0))
        customer_name = str(data.get("customer_name", "Cliente"))
        rut = str(data.get("rut", ""))

        if not invoice_ids or amount <= 0:
            return {"error": "Se requieren invoice_ids y amount válidos"}

        # Validar facturas en Odoo
        invoices_service = OdooInvoicesService(client)
        if not invoices_service.authenticate():
            return {"error": "No se pudo conectar con Odoo"}

        invoices = invoices_service.get_invoices_by_ids(invoice_ids)
        if not invoices:
            return {
                "error": "No se encontraron las facturas en Odoo",
                "code": "INVOICES_NOT_FOUND",
            }

        # Verificar que todas las facturas estén publicadas y pendientes de pago
        invalid = [
            inv for inv in invoices
            if inv.get("state") != "posted"
            or inv.get("payment_state") not in ("not_paid", "partial")
        ]
        if invalid:
            invalid_names = [inv.get("name", inv["id"]) for inv in invalid]
            return {
                "error": "Algunas facturas no están disponibles para pago",
                "code": "INVALID_INVOICE_STATE",
                "facturas": invalid_names,
            }

        # Usar monto real de Odoo como fuente de verdad
        total_residual = round(sum(inv.get("amount_residual", 0) for inv in invoices))
        if abs(total_residual - amount) > 1:
            print(f"⚠️ Monto frontend ${amount} vs Odoo ${total_residual} — usando Odoo")
            mongo_logger.log_error(
                event_type="INIT_FACTURA_AMOUNT_MISMATCH",
                client_id=client.client_id,
                error_message=f"Frontend: ${amount}, Odoo: ${total_residual}",
                extra_data={"invoice_ids": invoice_ids},
            )
            amount = total_residual

        # buy_order: nombre de la primera factura (Webpay acepta hasta 26 chars)
        primary_name = invoices[0].get("name", f"FAC-{invoice_ids[0]}")

        # Codificar invoice_ids en session_id para recuperarlos en el commit
        # sin depender de MongoDB. Formato: "F:123|456|789" (máx 61 chars de Transbank)
        encoded_session = "F:" + "|".join(str(i) for i in invoice_ids)
        if len(encoded_session) > 61:
            return {
                "error": "Demasiadas facturas seleccionadas. Paga en grupos más pequeños.",
                "code": "TOO_MANY_INVOICES",
            }

        print(f"🧾 Iniciando pago express para {len(invoices)} factura(s) — ${amount} — {primary_name}")

        webpay_service = WebpayService(client)
        response = webpay_service.create_transaction(
            amount=amount,
            customer_name=customer_name,
            order_date=None,
            order_name=primary_name,
            session_id=encoded_session,
        )

        if response.get("token"):
            mongo_logger.log_transaction_created(
                buy_order=response.get("buy_order", primary_name),
                token_ws=response["token"],
                client_id=client.client_id,
                order_name=primary_name,
                amount=amount,
                extra_data={
                    "doc_type": "factura",
                    "invoice_ids": invoice_ids,
                    "rut": rut,
                },
            )

        return response

    except Exception as e:
        print(f"❌ Error en /webpay/init-factura: {e}")
        mongo_logger.log_error(
            event_type="INIT_FACTURA",
            client_id=client.client_id if client else "unknown",
            error_message=str(e),
        )
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
        
        # 🔍 1. IDENTIFICAR CLIENTE ANTES DEL COMMIT
        # Intentar desde referer
        origin = request.headers.get("referer", "")
        client = get_client_from_origin(origin) if origin else None
        
        # Si no hay referer, usar el primer cliente activo (fallback)
        if not client:
            print("⚠️ No se pudo identificar cliente desde referer, usando fallback")
            from src.client_config import client_loader
            active_clients = client_loader.get_active_clients()
            client = active_clients[0] if active_clients else None
        
        if not client:
            print("❌ No hay clientes activos configurados")
            return RedirectResponse(url="/shop/payment?status=error")
        
        print(f"🔍 Cliente identificado para commit: {client.client_name}")
        
        # 🔧 2. CREAR WEBPAY SERVICE CON LA CONFIGURACIÓN DEL CLIENTE
        webpay_service = WebpayService(client)
        
        # ✅ 3. HACER COMMIT CON EL SERVICIO CORRECTO
        result = webpay_service.commit_transaction(token)

        odoo_url = client.odoo.url
        doc_type = "factura" if str(result.get("session_id", "")).startswith("F:") else "venta"

        if webpay_service.is_transaction_successful(result):
            if doc_type == "factura":
                await _process_successful_invoice_payment(result, client, token)
                redirect_url = (
                    f"{odoo_url}/pago-express"
                    f"?status=exitoso&ref={result.get('buy_order', '')}"
                )
                print(f"✅ POST - Pago de factura confirmado: {result.get('buy_order')}")
            else:
                odoo_service = OdooSalesService(client)
                await _process_successful_payment(result, odoo_service, client, token_ws=token)
                redirect_url = (
                    f"{odoo_url}/shop/confirmation"
                    f"?status=success&order={result['buy_order']}"
                )
                print(f"✅ POST - Redirigiendo a confirmación: {result['buy_order']}")
        else:
            mongo_logger.log_transaction_commit(
                token_ws=token,
                transbank_response=result,
                client_id=client.client_id,
                odoo_synced=False,
                error="Transacción rechazada por Webpay"
            )
            if doc_type == "factura":
                redirect_url = f"{odoo_url}/pago-express?status=rechazado"
            else:
                redirect_url = f"{odoo_url}/shop/payment?status=rejected"
            print(f"❌ POST - Transacción rechazada (doc_type={doc_type})")

        return RedirectResponse(url=redirect_url)

    except Exception as e:
        print(f"❌ Error en POST /webpay/commit: {str(e)}")
        mongo_logger.log_error(
            event_type="COMMIT_POST",
            client_id=client.client_id if client else "unknown",
            error_message=str(e)
        )
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
        
        # 🔍 1. IDENTIFICAR CLIENTE ANTES DEL COMMIT
        # Intentar desde referer
        origin = request.headers.get("referer", "")
        client = get_client_from_origin(origin) if origin else None
        
        # Si no hay referer, usar el primer cliente activo (fallback)
        if not client:
            print("⚠️ No se pudo identificar cliente desde referer, usando fallback")
            from src.client_config import client_loader
            active_clients = client_loader.get_active_clients()
            client = active_clients[0] if active_clients else None
        
        if not client:
            print("❌ No hay clientes activos configurados")
            return RedirectResponse(url="/shop/payment?status=error")
        
        print(f"🔍 Cliente identificado para commit: {client.client_name}")
        
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
        
        # 🔧 2. CREAR WEBPAY SERVICE CON LA CONFIGURACIÓN DEL CLIENTE
        webpay_service = WebpayService(client)
        
        # ✅ 3. HACER COMMIT CON EL SERVICIO CORRECTO
        result = webpay_service.commit_transaction(token)

        doc_type = "factura" if str(result.get("session_id", "")).startswith("F:") else "venta"

        if webpay_service.is_transaction_successful(result):
            if doc_type == "factura":
                await _process_successful_invoice_payment(result, client, token)
                redirect_url = (
                    f"{odoo_url}/pago-express"
                    f"?status=exitoso&ref={result.get('buy_order', '')}"
                )
                print(f"✅ GET - Pago de factura confirmado: {result.get('buy_order')}")
            else:
                odoo_service = OdooSalesService(client)
                await _process_successful_payment(result, odoo_service, client, token_ws=token)
                redirect_url = (
                    f"{odoo_url}/shop/confirmation"
                    f"?status=success&order={result['buy_order']}"
                )
                print(f"✅ GET - Redirigiendo a confirmación: {result['buy_order']}")
        else:
            mongo_logger.log_transaction_commit(
                token_ws=token,
                transbank_response=result,
                client_id=client.client_id,
                odoo_synced=False,
                error="Transacción rechazada por Webpay"
            )
            if doc_type == "factura":
                redirect_url = f"{odoo_url}/pago-express?status=rechazado"
            else:
                redirect_url = f"{odoo_url}/shop/payment?status=rejected"
            print(f"❌ GET - Transacción rechazada (doc_type={doc_type})")

        return RedirectResponse(url=redirect_url)

    except Exception as e:
        print(f"❌ Error en GET /webpay/commit: {str(e)}")
        mongo_logger.log_error(
            event_type="COMMIT_GET",
            client_id=client.client_id if client else "unknown",
            error_message=str(e)
        )
        from src.client_config import client_loader
        active_clients = client_loader.get_active_clients()
        fallback_url = active_clients[0].odoo.url if active_clients else "http://localhost:8000"
        return RedirectResponse(
            url=f"{fallback_url}/shop/payment?status=error"
        )


async def _process_successful_invoice_payment(
    payment_result: Dict[str, Any],
    client: ClientConfig,
    token_ws: Optional[str] = None,
) -> None:
    """
    Procesa un pago exitoso de facturas (Pago Express).
    Registra el pago en Odoo via account.payment.register y reconcilia las facturas.
    """
    odoo_synced = False
    error_message = None

    try:
        # Recuperar invoice_ids desde session_id de Webpay (fuente primaria, no depende de MongoDB)
        invoice_ids: List[int] = []
        session_id = payment_result.get("session_id", "")
        if isinstance(session_id, str) and session_id.startswith("F:"):
            try:
                invoice_ids = [int(x) for x in session_id[2:].split("|") if x.isdigit()]
            except Exception:
                pass

        # Fallback: intentar desde MongoDB si session_id no trajo IDs
        if not invoice_ids and token_ws:
            mongo_log = mongo_logger.get_transaction_by_token(token_ws)
            if mongo_log and isinstance(mongo_log.get("extra_data"), dict):
                invoice_ids = mongo_log["extra_data"].get("invoice_ids", [])
                if invoice_ids:
                    print("⚠️ invoice_ids recuperados desde MongoDB (fallback)")

        if not invoice_ids:
            error_message = "No se pudieron recuperar los invoice_ids (session_id inválido y MongoDB sin datos)"
            print(f"❌ {error_message}")
            mongo_logger.log_transaction_commit(
                token_ws=token_ws or "",
                transbank_response=payment_result,
                client_id=client.client_id,
                odoo_synced=False,
                error=error_message,
            )
            return

        amount = payment_result.get("amount", 0)
        buy_order = payment_result.get("buy_order", "")
        print(f"🧾 Registrando pago en facturas {invoice_ids} — ${amount} — {buy_order}")

        invoices_service = OdooInvoicesService(client)
        odoo_synced = invoices_service.register_invoice_payment(
            invoice_ids=invoice_ids,
            amount=float(amount),
            payment_data=payment_result,
        )

        if not odoo_synced:
            error_message = f"No se pudo registrar el pago en las facturas {invoice_ids}"
            print(f"❌ {error_message}")

        mongo_logger.log_transaction_commit(
            token_ws=token_ws or "",
            transbank_response=payment_result,
            client_id=client.client_id,
            odoo_synced=odoo_synced,
            error=error_message,
        )

    except Exception as e:
        error_message = str(e)
        print(f"❌ Error procesando pago de facturas: {error_message}")
        mongo_logger.log_transaction_commit(
            token_ws=token_ws or "",
            transbank_response=payment_result,
            client_id=client.client_id,
            odoo_synced=False,
            error=error_message,
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
    client: ClientConfig,
    token_ws: Optional[str] = None
) -> None:
    """
    🔄 Procesa un pago exitoso e intenta actualizar la orden en Odoo
    usando DIRECTAMENTE el buy_order como name de sale.order.
    """
    odoo_synced = False
    odoo_order_id = None
    odoo_order_name = None
    odoo_transaction_id = None
    error_message = None

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
            error_message = f"No se encontró en Odoo la orden '{buy_order}'"
            print(f"❌ {error_message}")
            # Registrar en MongoDB aunque no se encontró la orden
            mongo_logger.log_transaction_commit(
                token_ws=token_ws or "",
                transbank_response=payment_result,
                client_id=client.client_id,
                odoo_synced=False,
                error=error_message
            )
            return

        odoo_order_id = order["id"]
        odoo_order_name = order["name"]
        print(f"✅ Orden encontrada → ID={order['id']} name={order['name']} state={order['state']}")

        # === 2️⃣ Confirmar la orden o forzar estado "sale" ===
        success = odoo_service.update_order_payment_status(
            order_id=order["id"],
            payment_data=payment_result
        )

        if not success:
            error_message = f"No se pudo confirmar la orden {order['name']}"
            print(f"❌ {error_message}")
            mongo_logger.log_transaction_commit(
                token_ws=token_ws or "",
                transbank_response=payment_result,
                client_id=client.client_id,
                odoo_order_id=odoo_order_id,
                odoo_order_name=odoo_order_name,
                odoo_synced=False,
                error=error_message
            )
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
            odoo_synced = True
            odoo_transaction_id = registered if isinstance(registered, int) else None
            print(f"💳 Transacción Webpay registrada exitosamente en Odoo para {order['name']}")
        else:
            error_message = "No se pudo registrar la transacción Webpay en Odoo"
            print(f"⚠️ {error_message}")

        # 📊 Registrar commit en MongoDB
        mongo_logger.log_transaction_commit(
            token_ws=token_ws or "",
            transbank_response=payment_result,
            client_id=client.client_id,
            odoo_order_id=odoo_order_id,
            odoo_order_name=odoo_order_name,
            odoo_synced=odoo_synced,
            odoo_transaction_id=odoo_transaction_id,
            error=error_message
        )

    except Exception as e:
        error_message = str(e)
        print(f"❌ Error procesando pago exitoso: {error_message}")
        # Registrar error en MongoDB
        mongo_logger.log_transaction_commit(
            token_ws=token_ws or "",
            transbank_response=payment_result,
            client_id=client.client_id,
            odoo_order_id=odoo_order_id,
            odoo_order_name=odoo_order_name,
            odoo_synced=False,
            error=error_message
        )
