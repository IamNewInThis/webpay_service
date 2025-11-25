"""
Rutas del servicio Webpay.

Expone los endpoints `POST /webpay/init` y `/webpay/commit` (GET/POST) que la
aplicación principal importa como `webpay_router`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field, validator

from src.security import verify_api_key, verify_frontend_request
from src.services.odoo_sales import OdooSalesService
from src.services.webpay_service import WebpayService
from src.tenants import TenantConfig, tenant_manager


class WebpayInitRequest(BaseModel):
    """Payload recibido al inicializar una transacción."""

    amount: int = Field(..., gt=0, description="Monto total en pesos chilenos")
    customer_name: Optional[str] = Field(None, description="Nombre del comprador")
    order_date: Optional[str] = Field(
        None, description="Fecha de la orden en formato YYYY-MM-DD"
    )
    tenant_id: Optional[str] = Field(
        None, description="Forzar tenant específico (opcional)"
    )

    @validator("order_date")
    def _validate_order_date(cls, value: Optional[str]) -> Optional[str]:
        if not value:
            return value
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("order_date debe usar el formato YYYY-MM-DD") from exc
        return value


webpay_router = APIRouter(prefix="/webpay", tags=["webpay"])
webpay_service = WebpayService()


@webpay_router.post("/init", dependencies=[Depends(verify_api_key)])
async def init_transaction(
    payload: WebpayInitRequest,
    _security_ctx: Dict[str, Any] = Depends(verify_frontend_request),
) -> Dict[str, Any]:
    """
    Crea una transacción en Webpay Plus para el tenant detectado por origen.
    """
    tenant = _resolve_tenant(payload.tenant_id, _security_ctx.get("tenant"))

    try:
        result = webpay_service.create_transaction(
            amount=payload.amount,
            customer_name=payload.customer_name,
            order_date=payload.order_date,
            tenant=tenant,
        )
    except Exception as exc:  # pragma: no cover - FastAPI captura el detalle
        raise HTTPException(
            status_code=500, detail=f"No se pudo iniciar la transacción: {exc}"
        ) from exc

    return {
        "success": True,
        "tenant_id": tenant.id,
        "token": result.get("token"),
        "session_id": result.get("session_id"),
        "buy_order": result.get("buy_order"),
        "redirect_url": result.get("url"),
        "return_url": webpay_service.return_url,
        "webpay_response": result,
    }


@webpay_router.get("/commit")
async def commit_transaction_get(
    token_ws: Optional[str] = None,
    tbk_token: Optional[str] = None,
    tbk_orden_compra: Optional[str] = None,
    tbk_id_sesion: Optional[str] = None,
) -> JSONResponse:
    """
    Endpoint auxiliar para pruebas (GET). Devuelve el resultado en JSON.
    """
    commit_result = await _finalize_commit_flow(
        token_ws=token_ws,
        tbk_token=tbk_token,
        tbk_buy_order=tbk_orden_compra,
        tbk_session=tbk_id_sesion,
    )
    return JSONResponse(commit_result)


@webpay_router.post("/commit")
async def commit_transaction_post(
    token_ws: Optional[str] = Form(None),
    tbk_token: Optional[str] = Form(None),
    tbk_orden_compra: Optional[str] = Form(None),
    tbk_id_sesion: Optional[str] = Form(None),
) -> RedirectResponse:
    """
    Recibe la confirmación de Webpay (POST). Redirige al frontend del tenant.
    """
    commit_result = await _finalize_commit_flow(
        token_ws=token_ws,
        tbk_token=tbk_token,
        tbk_buy_order=tbk_orden_compra,
        tbk_session=tbk_id_sesion,
    )
    return RedirectResponse(commit_result["redirect_url"], status_code=303)


def _resolve_tenant(
    requested_id: Optional[str], fallback: Optional[TenantConfig]
) -> TenantConfig:
    if requested_id:
        tenant = tenant_manager.get_tenant_by_id(requested_id)
        if not tenant:
            raise HTTPException(
                status_code=404,
                detail=f"Tenant '{requested_id}' no está configurado",
            )
        return tenant
    if fallback:
        return fallback
    return tenant_manager.default_tenant


async def _finalize_commit_flow(
    token_ws: Optional[str],
    tbk_token: Optional[str],
    tbk_buy_order: Optional[str],
    tbk_session: Optional[str],
) -> Dict[str, Any]:
    tenant = tenant_manager.tenant_from_session(tbk_session) or tenant_manager.default_tenant

    if not token_ws:
        status = "cancelled" if tbk_token else "error"
        redirect_url = _build_redirect_url(tenant, status, tbk_buy_order)
        return {
            "success": False,
            "status": status,
            "redirect_url": redirect_url,
            "transaction": None,
        }

    try:
        transaction = webpay_service.commit_transaction(token_ws)
    except Exception as exc:  # pragma: no cover - dependemos del SDK
        print(f"❌ Error confirmando token {token_ws}: {exc}")
        redirect_url = _build_redirect_url(tenant, "error", tbk_buy_order)
        return {
            "success": False,
            "status": "error",
            "redirect_url": redirect_url,
            "transaction": None,
        }

    tenant = _tenant_from_transaction(transaction, tenant)
    success = webpay_service.is_transaction_successful(transaction)
    status = "success" if success else "rejected"

    if success:
        _sync_transaction_with_odoo(tenant, transaction, success)

    redirect_url = _build_redirect_url(
        tenant, status, transaction.get("buy_order") or tbk_buy_order
    )
    return {
        "success": success,
        "status": status,
        "redirect_url": redirect_url,
        "transaction": transaction,
    }


def _tenant_from_transaction(
    transaction: Dict[str, Any], fallback: TenantConfig
) -> TenantConfig:
    tenant_id = transaction.get("tenant_id")
    if tenant_id:
        tenant = tenant_manager.get_tenant_by_id(tenant_id)
        if tenant:
            return tenant

    session_id = transaction.get("session_id")
    if session_id:
        tenant = tenant_manager.tenant_from_session(session_id)
        if tenant:
            return tenant

    return fallback


def _build_redirect_url(
    tenant: TenantConfig, status: str, buy_order: Optional[str]
) -> str:
    if status == "success" and buy_order:
        return tenant.build_success_url(buy_order)
    return tenant.build_payment_status_url(status)


def _sync_transaction_with_odoo(
    tenant: TenantConfig, transaction: Dict[str, Any], success: bool
) -> None:
    """
    Envía los datos del commit a Odoo para actualizar la orden y registrar la transacción.
    """
    try:
        order_context = _parse_buy_order(transaction.get("buy_order"))
        order_amount = transaction.get("amount") or order_context.get("amount")
        try:
            normalized_amount = int(order_amount) if order_amount is not None else 0
        except (TypeError, ValueError):
            normalized_amount = 0

        odoo_service = OdooSalesService(tenant.odoo)
        order = odoo_service.find_order_by_criteria(
            customer_name=order_context.get("customer_hint") or "",
            amount=normalized_amount,
            order_date=order_context.get("order_date") or "",
        )

        if not order:
            print("⚠️ No se encontró una orden que coincida con el buy_order recibido")
            return

        payment_payload = _build_payment_payload(transaction)
        odoo_service.update_order_payment_status(order["id"], payment_payload)
        odoo_service.register_webpay_transaction(
            order_id=order["id"],
            order_name=order.get("name") or transaction.get("buy_order") or "Webpay",
            amount=normalized_amount or transaction.get("amount") or 0,
            status="done" if success else "error",
            payment_data=payment_payload,
            order_data=order,
        )
    except Exception as exc:  # pragma: no cover - integra servicios externos
        print(f"⚠️ Error sincronizando la transacción con Odoo: {exc}")


def _parse_buy_order(buy_order: Optional[str]) -> Dict[str, Optional[Any]]:
    if not buy_order:
        return {"customer_hint": None, "amount": None, "order_date": None}

    parts = buy_order.split("_")
    if len(parts) < 3:
        return {
            "customer_hint": buy_order.replace("-", " ").strip(),
            "amount": None,
            "order_date": None,
        }

    amount = None
    try:
        amount = int(parts[1])
    except (TypeError, ValueError):
        pass

    return {
        "customer_hint": parts[0].replace("-", " ").strip() or None,
        "amount": amount,
        "order_date": _format_date_token(parts[2]),
    }


def _format_date_token(token: Optional[str]) -> Optional[str]:
    if not token:
        return None

    digits = "".join(ch for ch in token if ch.isdigit())
    if len(digits) == 8:
        return f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]}"
    if len(digits) == 6:
        return f"20{digits[0:2]}-{digits[2:4]}-{digits[4:6]}"
    return None


def _build_payment_payload(transaction: Dict[str, Any]) -> Dict[str, Any]:
    card_detail = transaction.get("card_detail") or {}
    return {
        "buy_order": transaction.get("buy_order"),
        "session_id": transaction.get("session_id"),
        "status": transaction.get("status"),
        "response_code": transaction.get("response_code"),
        "authorization_code": transaction.get("authorization_code"),
        "payment_type_code": transaction.get("payment_type_code"),
        "card_number": card_detail.get("card_number"),
        "accounting_date": transaction.get("accounting_date"),
        "transaction_date": transaction.get("transaction_date"),
    }
