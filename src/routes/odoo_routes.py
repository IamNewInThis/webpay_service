"""
📦 Rutas de integración con Odoo
================================
Define endpoints para interactuar con el ERP Odoo.
Permite consultar órdenes, actualizar estados y sincronizar datos.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
from src.services.odoo_sales import OdooSalesService
from pydantic import BaseModel

# Crear router para agrupar las rutas de Odoo
odoo_router = APIRouter(prefix="/odoo", tags=["odoo"])

# Instanciar el servicio de Odoo
odoo_service = OdooSalesService()

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
