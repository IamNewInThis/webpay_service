"""
🏪 Rutas de Odoo
================
Endpoints para integración con Odoo ERP.
Maneja sincronización de órdenes, clientes y estado de transacciones.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from src.services.odoo_sales import OdooSalesService
from typing import Dict, Any, Optional

# Crear router para agrupar las rutas de Odoo
odoo_router = APIRouter(prefix="/odoo", tags=["odoo"])

# Instanciar el servicio de Odoo (cuando esté implementado)
# odoo_service = OdooSalesService()


@odoo_router.get("/health")
async def odoo_health_check() -> Dict[str, str]:
    """
    🏥 Verifica la conectividad con Odoo
    
    Endpoint simple para verificar que el servicio puede comunicarse
    con la instancia de Odoo configurada.
    
    Returns:
        {"status": "ok", "message": "Conexión con Odoo operativa"}
    """
    # TODO: Implementar verificación real de conexión con Odoo
    return {
        "status": "ok", 
        "message": "Servicio Odoo disponible (pendiente implementación)"
    }


@odoo_router.post("/sync-order")
async def sync_order_with_odoo(request: Request) -> JSONResponse:
    """
    🔄 Sincroniza una orden de compra con Odoo
    
    Recibe datos de una transacción completada y actualiza
    el estado correspondiente en Odoo ERP.
    
    Body esperado:
    {
        "buy_order": "O-123456",
        "transaction_id": "abc123...",
        "amount": 10000,
        "status": "AUTHORIZED",
        "customer_name": "Juan Pérez"
    }
    
    Returns:
        {"status": "success", "odoo_order_id": 12345}
    """
    try:
        data = await request.json()
        buy_order = data.get("buy_order")
        
        print(f"🔄 Sincronizando orden {buy_order} con Odoo")
        
        # TODO: Implementar lógica de sincronización real
        # order_id = odoo_service.update_order_status(data)
        
        return JSONResponse({
            "status": "success",
            "message": f"Orden {buy_order} sincronizada",
            "odoo_order_id": None  # TODO: Retornar ID real de Odoo
        })
        
    except Exception as e:
        print(f"❌ Error sincronizando con Odoo: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


@odoo_router.get("/orders/{order_id}")
async def get_order_from_odoo(order_id: str) -> JSONResponse:
    """
    📋 Obtiene detalles de una orden desde Odoo
    
    Busca una orden específica en Odoo y retorna sus detalles.
    Útil para verificar el estado de órdenes y matching de transacciones.
    
    Args:
        order_id: ID de la orden en Odoo o buy_order de Webpay
        
    Returns:
        {"order": {...}, "status": "found"} o {"status": "not_found"}
    """
    try:
        print(f"📋 Buscando orden {order_id} en Odoo")
        
        # TODO: Implementar búsqueda real en Odoo
        # order_data = odoo_service.get_order(order_id)
        
        return JSONResponse({
            "status": "pending_implementation",
            "order_id": order_id,
            "message": "Búsqueda en Odoo pendiente de implementación"
        })
        
    except Exception as e:
        print(f"❌ Error buscando orden en Odoo: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )
