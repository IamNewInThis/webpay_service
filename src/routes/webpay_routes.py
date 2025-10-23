"""
🌐 Rutas de Webpay
==================
Define todos los endpoints relacionados con transacciones de Webpay Plus.
Maneja inicialización, confirmación y cancelación de transacciones.
"""

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from src.services.webpay_service import WebpayService
from src.services.odoo_sales import OdooSalesService
from typing import Dict, Any
from datetime import datetime

# Crear router para agrupar las rutas de Webpay
webpay_router = APIRouter(prefix="/webpay", tags=["webpay"])

# Instanciar servicios
webpay_service = WebpayService()
odoo_service = OdooSalesService()


@webpay_router.post("/init")
async def init_webpay_transaction(request: Request) -> Dict[str, Any]:
    """
    🚀 Inicializa una nueva transacción Webpay
    
    Recibe los datos del pago desde el frontend y crea una transacción
    en el sistema de Webpay Plus de Transbank.
    
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
        # Extraer datos del request
        data = await request.json()
        amount = data.get("amount", 1000)
        customer_name = data.get("customer_name", "Cliente")
        order_date = data.get("order_date")
        
        print(f"💳 Iniciando transacción - Cliente: {customer_name}, Monto: ${amount}")
        
        # Crear transacción usando el servicio
        response = webpay_service.create_transaction(
            amount=amount,
            customer_name=customer_name,
            order_date=order_date
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
            return RedirectResponse(
                url="https://tecnogrow-webpay.odoo.com/shop/payment?status=cancelled"
            )
        
        # Confirmar transacción
        result = webpay_service.commit_transaction(token)
        
        # Si la transacción es exitosa, intentar actualizar orden en Odoo
        if webpay_service.is_transaction_successful(result):
            # Intentar encontrar y actualizar la orden correspondiente en Odoo
            await _process_successful_payment(result)

            # Buscar la orden en Odoo con find_order_by_criteria

            # Despues de obtenerla marcar el estado como 'sale'
            
            redirect_url = (
                f"https://tecnogrow-webpay.odoo.com/shop/confirmation"
                f"?status=success&order={result['buy_order']}"
            )
            print(f"✅ POST - Redirigiendo a confirmación: {result['buy_order']}")
        else:
            redirect_url = "https://tecnogrow-webpay.odoo.com/shop/payment?status=rejected"
            print("❌ POST - Transacción rechazada")
        
        return RedirectResponse(url=redirect_url)
        
    except Exception as e:
        print(f"❌ Error en POST /webpay/commit: {str(e)}")
        return RedirectResponse(
            url="https://tecnogrow-webpay.odoo.com/shop/payment?status=error"
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
        
        if not token:
            # Verificar si es una cancelación (tiene TBK_TOKEN pero no token_ws)
            if "TBK_TOKEN" in params:
                print("❌ GET - Usuario canceló la transacción")
                return RedirectResponse(
                    url="https://tecnogrow-webpay.odoo.com/shop/payment?status=cancelled"
                )
            else:
                print("⚠️ GET - Sin tokens válidos")
                return RedirectResponse(
                    url="https://tecnogrow-webpay.odoo.com/shop/payment?status=error"
                )
        
        # Procesar transacción con token_ws
        result = webpay_service.commit_transaction(token)
        
        # Si la transacción es exitosa, intentar actualizar orden en Odoo
        if webpay_service.is_transaction_successful(result):
            # Intentar encontrar y actualizar la orden correspondiente en Odoo
            await _process_successful_payment(result)
            
            redirect_url = (
                f"https://tecnogrow-webpay.odoo.com/shop/confirmation"
                f"?status=success&order={result['buy_order']}"
            )
            print(f"✅ GET - Redirigiendo a confirmación: {result['buy_order']}")
        else:
            redirect_url = "https://tecnogrow-webpay.odoo.com/shop/payment?status=rejected"
            print("❌ GET - Transacción rechazada")
        
        return RedirectResponse(url=redirect_url)
        
    except Exception as e:
        print(f"❌ Error en GET /webpay/commit: {str(e)}")
        return RedirectResponse(
            url="https://tecnogrow-webpay.odoo.com/shop/payment?status=error"
        )


async def _process_successful_payment(payment_result: Dict[str, Any]) -> None:
    """
    🔄 Procesa un pago exitoso e intenta actualizar la orden en Odoo
    
    Extrae información del buy_order para encontrar la orden correspondiente
    en Odoo y actualizar su estado de pago.
    
    Args:
        payment_result: Resultado de la transacción de Webpay
    """
    try:
        buy_order = payment_result.get("buy_order", "") or ""
        raw_amount = payment_result.get("amount", 0)
        try:
            amount = int(float(raw_amount))
        except (TypeError, ValueError):
            amount = 0
        
        # Extraer datos del buy_order (formato: {customer_name}_{amount}_{date})
        parts = buy_order.split("_")
        if len(parts) >= 3:
            customer_name = parts[0].replace("-", " ").title()  # Reconvertir espacios
            order_date = parts[2]  # Formato YYYYMMDD
            
            # Convertir fecha a formato YYYY-MM-DD
            try:
                formatted_date = datetime.strptime(order_date, "%Y%m%d").strftime("%Y-%m-%d")
            except ValueError:
                formatted_date = datetime.utcnow().strftime("%Y-%m-%d")
            
            print(f"🔍 Buscando orden en Odoo - Cliente: {customer_name}, Monto: {amount}, Fecha: {formatted_date}")
            
            # Buscar orden en Odoo por criterios
            order = odoo_service.find_order_by_criteria(
                customer_name=customer_name,
                amount=amount,
                order_date=formatted_date
            )
            
            if order:
                # Actualizar estado de la orden
                success = odoo_service.update_order_payment_status(
                    order_id=order["id"],
                    payment_data=payment_result
                )
                
                if success:
                    print(f"✅ Orden {order['name']} actualizada exitosamente en Odoo")
                else:
                    print(f"❌ Error actualizando orden {order['name']} en Odoo")

                tx_status = (
                    "done"
                    if payment_result.get("status") == "AUTHORIZED"
                    or payment_result.get("response_code") == 0
                    else "error"
                )
                registered = odoo_service.register_webpay_transaction(
                    order_id=order["id"],
                    order_name=order["name"],
                    amount=amount,
                    status=tx_status,
                    payment_data=payment_result,
                )

                if registered:
                    print(
                        f"✅ Transacción Webpay registrada para orden {order['name']} con estado {tx_status}"
                    )
                else:
                    print(
                        f"⚠️ No se pudo registrar la transacción Webpay para orden {order['name']}"
                    )
            else:
                print("⚠️ No se encontró orden correspondiente en Odoo")
        else:
            print(f"⚠️ Formato de buy_order inválido: {buy_order}")
            
    except Exception as e:
        print(f"❌ Error procesando pago exitoso: {str(e)}")
        # No levantamos la excepción para que el pago continue normalmente
