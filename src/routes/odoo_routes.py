# src/routes/odoo_routes.py
"""
📦 Rutas de integración con Odoo
================================
Define endpoints para interactuar con el ERP Odoo.
Permite consultar órdenes, actualizar estados y sincronizar datos.
Creación de payments.

🔒 Seguridad: Todos los endpoints requieren API Key válida.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Dict, Any, Optional
from src.services.odoo_sales import OdooSalesService
from src.tenants import tenant_manager
from src.security import verify_api_key, verify_hmac_dependency
from pydantic import BaseModel

# Crear router para agrupar las rutas de Odoo
odoo_router = APIRouter(
    prefix="/odoo", 
    tags=["odoo"],
    dependencies=[Depends(verify_api_key)]  # 🔒 Proteger todas las rutas con API Key
)

# Instanciar el servicio de Odoo usando el tenant por defecto (o .env tradicional)
_default_tenant = tenant_manager.default_tenant
odoo_service = OdooSalesService(
    credentials=_default_tenant.odoo,
    webpay_config=_default_tenant.webpay,
)

class OrderStatusUpdate(BaseModel):
    """📝 Modelo para actualización de estado de orden"""
    status: str

@odoo_router.get("/orders/search")
async def search_orders(
    customer_name: Optional[str] = Query(None, description="Nombre del cliente"),
    amount: Optional[int] = Query(None, description="Monto de la orden"),
    order_date: Optional[str] = Query(None, description="Fecha de la orden (YYYY-MM-DD)")
) -> Dict[str, Any]:
    """
    🔎 Busca órdenes por criterios específicos
    
    Permite buscar órdenes usando diferentes filtros como
    nombre del cliente, monto y fecha de la orden.
    
    Query Parameters:
        customer_name: Nombre del cliente (búsqueda parcial)
        amount: Monto exacto de la orden
        order_date: Fecha de la orden en formato YYYY-MM-DD
    
    Returns:
        Orden encontrada o información de no encontrada
    """
    try:
        # Validar que al menos un criterio sea proporcionado
        if not any([customer_name, amount, order_date]):
            raise HTTPException(
                status_code=400,
                detail="Debe proporcionar al menos un criterio de búsqueda"
            )
        
        order = odoo_service.find_order_by_criteria(
            customer_name=customer_name,
            amount=amount,
            order_date=order_date
        )
        
        if order:
            return {
                "success": True,
                "found": True,
                "order": order
            }
        else:
            return {
                "success": True,
                "found": False,
                "message": "No se encontró orden con los criterios especificados"
            }
            
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error buscando órdenes: {str(e)}"
        )

@odoo_router.get("/orders/{order_id}")
async def get_order_details(order_id: int) -> Dict[str, Any]:
    """
    � Obtiene detalles de una orden específica
    
    Consulta información completa de una orden particular
    incluyendo líneas de orden, estado de pago, etc.
    
    Path Parameters:
        order_id: ID de la orden en Odoo
    
    Returns:
        Información detallada de la orden
    """
    try:
        order = odoo_service.get_order_by_id(order_id)
        if not order:
            raise HTTPException(
                status_code=404,
                detail=f"Orden {order_id} no encontrada"
            )
        
        return {
            "success": True,
            "order": order
        }
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo orden {order_id}: {str(e)}"
        )

@odoo_router.put("/orders/{order_identifier}/status")
async def update_order_status(order_identifier: str, status_data: OrderStatusUpdate) -> Dict[str, Any]:
    """
    🔄 Actualiza el estado de una orden (por ID o por código)
    """
    try:
        # Detectar si el identificador es numérico o código de orden
        if order_identifier.isdigit():
            order_id = int(order_identifier)
            updated = odoo_service.update_order_payment_status(order_id, {
                "buy_order": f"Manual_Update_{order_id}",
                "status": status_data.status,
            })
        else:
            updated = odoo_service.update_order_status_by_name(order_identifier, status_data.status)

        if not updated:
            raise HTTPException(
                status_code=404,
                detail=f"Orden '{order_identifier}' no encontrada o no se pudo actualizar",
            )

        return {
            "success": True,
            "message": f"Estado de la orden '{order_identifier}' actualizado a '{status_data.status}'",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error actualizando orden '{order_identifier}': {str(e)}",
        )

@odoo_router.get("/health")
async def check_odoo_connection() -> Dict[str, Any]:
    """
    🏥 Verifica la conexión con Odoo
    
    Endpoint de health check para verificar que la conexión
    con el ERP Odoo esté funcionando correctamente.
    
    Returns:
        Estado de la conexión y información básica
    """
    try:
        # Intentar autenticarse para verificar conexión
        authenticated = odoo_service.authenticate()
        
        if authenticated:
            # Obtener información básica para confirmar que todo funciona
            orders = odoo_service.get_recent_orders(limit=1)
            
            return {
                "status": "healthy",
                "connected": True,
                "database": odoo_service.database,
                "user": odoo_service.username,
                "orders_accessible": len(orders) >= 0  # True si podemos acceder
            }
        else:
            return {
                "status": "unhealthy",
                "connected": False,
                "error": "No se pudo autenticar con Odoo"
            }
            
    except Exception as e:
        return {
            "status": "unhealthy",
            "connected": False,
            "error": str(e)
        }

class PaymentCreateRequest(BaseModel):
    """🧾 Modelo para crear transacciones de pago manuales"""
    order_id: int
    order_name: str
    amount: float
    status: Optional[str] = "done"
    payment_data: Optional[Dict[str, Any]] = None


@odoo_router.post("/payments/create", dependencies=[Depends(verify_hmac_dependency)])
async def create_payment_transaction(data: PaymentCreateRequest) -> Dict[str, Any]:
    """
    💳 Crea una transacción de pago en Odoo manualmente (modo Odoo Online).
    Incluye automáticamente el partner_id desde la orden.
    
    🔒 Seguridad: Requiere API Key + HMAC signature válida

    Request body:
    - order_id: ID de la orden (int)
    - order_name: Nombre de la orden (string)
    - amount: Monto del pago
    - status: Estado del pago (por defecto "done")
    - payment_data: Información adicional (opcional)
    
    Headers requeridos:
    - X-API-Key: API Key válida
    - X-Signature: Firma HMAC del body
    - X-Timestamp: Timestamp unix de la request
    """
    try:
        if not odoo_service.uid:
            odoo_service.authenticate()

        order = odoo_service.get_order_by_id(data.order_id)
        if not order:
            raise HTTPException(
                status_code=404,
                detail=f"Orden {data.order_id} no encontrada en Odoo",
            )

        payment_payload = data.payment_data or {}
        tx_status = data.status or "done"

        success = odoo_service.register_webpay_transaction(
            order_id=data.order_id,
            order_name=order["name"],
            amount=data.amount,
            status=tx_status,
            payment_data=payment_payload,
            order_data=order,
        )

        if not success:
            raise HTTPException(
                status_code=500,
                detail=f"No se pudo crear la transacción para la orden {order['name']}",
            )

        return {
            "success": True,
            "message": f"Transacción Webpay registrada para la orden {order['name']}",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error creando transacción de pago: {str(e)}",
        )
