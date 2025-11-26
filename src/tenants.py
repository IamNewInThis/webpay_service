"""
🤝 Gestión multi-tenant
======================
Define las estructuras y helpers para soportar múltiples clientes
utilizando el mismo microservicio. Cada tenant define su set de
orígenes permitidos y credenciales de Odoo.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from fnmatch import fnmatch
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

# Asegura que las variables del .env estén disponibles
load_dotenv()


@dataclass
class OdooCredentials:
    """Credenciales necesarias para hablar con una instancia de Odoo."""

    base_url: str
    database: str
    username: str
    password: str

    def __post_init__(self) -> None:
        self.base_url = (self.base_url or "").rstrip("/")

    @property
    def success_url(self) -> str:
        return f"{self.base_url}/shop/confirmation"

    @property
    def payment_url(self) -> str:
        return f"{self.base_url}/shop/payment"


@dataclass
class WebpayConfig:
    """Configura las credenciales Webpay para un tenant específico."""

    commerce_code: str
    api_key: str
    environment: str = "TEST"
    provider_id: Optional[int] = None
    payment_method_id: Optional[int] = None

    def is_production(self) -> bool:
        env = (self.environment or "TEST").upper()
        return env in {"PROD", "PRODUCTION", "LIVE"}


@dataclass
class TenantConfig:
    """Configuración completa de un tenant/cliente."""

    id: str
    name: str
    origins: List[str]
    odoo: OdooCredentials
    metadata: Dict[str, str] = field(default_factory=dict)
    webpay: Optional[WebpayConfig] = None

    def __post_init__(self) -> None:
        safe_id = re.sub(r"[^0-9a-z\-]", "", (self.id or "").lower())
        self.id = safe_id or "tenant"
        self.origins = [
            (origin or "").rstrip("/")
            for origin in self.origins
            if origin
        ]

    def matches_origin(self, origin: Optional[str]) -> bool:
        """Valida si el origen recibido pertenece al tenant."""
        if not origin:
            return False

        normalized = origin.rstrip("/").lower()
        for pattern in self.origins:
            pattern_normalized = pattern.rstrip("/").lower()
            if "*" in pattern_normalized:
                if fnmatch(normalized, pattern_normalized):
                    return True
            elif normalized == pattern_normalized:
                return True
        return False

    def build_success_url(self, buy_order: str) -> str:
        return f"{self.odoo.success_url}?status=success&order={buy_order}"

    def build_payment_status_url(self, status: str) -> str:
        return f"{self.odoo.payment_url}?status={status}"


class TenantManager:
    """
    Mantiene el listado de tenants y helpers para encontrarlos según origen
    o session_id. Si no se define TENANT_CONFIGS, utiliza el .env tradicional.
    """

    SESSION_SEPARATOR = "__"

    def __init__(self) -> None:
        self._tenants = self._load_from_env()
        if not self._tenants:
            self._tenants = [self._build_fallback_tenant()]
        self._lookup: Dict[str, TenantConfig] = {tenant.id: tenant for tenant in self._tenants}

    def _load_from_env(self) -> List[TenantConfig]:
        raw = os.getenv("TENANT_CONFIGS") or ""
        if not raw.strip():
            return []

        tenants: List[TenantConfig] = []
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            print(f"⚠️ Error leyendo TENANT_CONFIGS: {exc}")
            return tenants

        for entry in data:
            try:
                webpay_cfg = self._build_webpay_config(entry.get("webpay"))
                tenant = TenantConfig(
                    id=entry.get("id") or entry.get("slug") or entry.get("name") or "tenant",
                    name=entry.get("name") or entry.get("id") or "Tenant",
                    origins=entry.get("origins") or [],
                    odoo=OdooCredentials(
                        base_url=entry["odoo"]["url"],
                        database=entry["odoo"]["database"],
                        username=entry["odoo"]["username"],
                        password=entry["odoo"]["password"],
                    ),
                    metadata=entry.get("metadata") or {},
                    webpay=webpay_cfg,
                )
                tenants.append(tenant)
            except KeyError as exc:
                print(f"⚠️ Configuración incompleta para un tenant: {exc}")

        return tenants

    def _build_fallback_tenant(self) -> TenantConfig:
        """Genera un tenant 'default' basado en las variables clásicas del .env."""
        fallback_origin = os.getenv("ODOO_URL", "").rstrip("/")
        extra_origins = [
            origin.strip()
            for origin in os.getenv("DEFAULT_ORIGINS", "").split(",")
            if origin.strip()
        ]
        origins = [origin for origin in [fallback_origin, "http://localhost:8000"] + extra_origins if origin]

        return TenantConfig(
            id="default",
            name="Default",
            origins=origins,
            odoo=OdooCredentials(
                base_url=fallback_origin,
                database=os.getenv("ODOO_DATABASE", ""),
                username=os.getenv("ODOO_USERNAME", ""),
                password=os.getenv("ODOO_PASSWORD", ""),
            ),
            webpay=self._build_webpay_config(
                {
                    "commerce_code": os.getenv("WEBPAY_COMMERCE_CODE"),
                    "api_key": os.getenv("WEBPAY_API_KEY"),
                    "environment": os.getenv("WEBPAY_ENVIRONMENT"),
                    "provider_id": os.getenv("WEBPAY_PROVIDER_ID"),
                    "payment_method_id": os.getenv("WEBPAY_PAYMENT_METHOD_ID"),
                }
            ),
        )

    def _build_webpay_config(self, entry: Optional[Any]) -> Optional["WebpayConfig"]:
        if not entry:
            return None

        if hasattr(entry, "commerce_code"):
            commerce_code = entry.commerce_code
            api_key = entry.api_key
            environment = getattr(entry, "environment", None)
            provider_id = getattr(entry, "provider_id", None)
            payment_method_id = getattr(entry, "payment_method_id", None)
        elif isinstance(entry, dict):
            commerce_code = entry.get("commerce_code") or entry.get("commerceCode")
            api_key = entry.get("api_key") or entry.get("apiKey")
            environment = entry.get("environment")
            provider_id = entry.get("provider_id") or entry.get("providerId")
            payment_method_id = entry.get("payment_method_id") or entry.get("paymentMethodId")
        else:
            return None

        if not commerce_code or not api_key:
            return None

        return WebpayConfig(
            commerce_code=str(commerce_code),
            api_key=str(api_key),
            environment=(environment or "TEST").upper(),
            provider_id=self._to_int(provider_id),
            payment_method_id=self._to_int(payment_method_id),
        )

    @staticmethod
    def _to_int(value: Optional[Any]) -> Optional[int]:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @property
    def tenants(self) -> List[TenantConfig]:
        return self._tenants

    @property
    def default_tenant(self) -> TenantConfig:
        return self._tenants[0]

    def all_allowed_origins(self) -> List[str]:
        origins = []
        for tenant in self._tenants:
            origins.extend(tenant.origins)
        return sorted(set(origin for origin in origins if origin))

    def get_tenant_by_origin(self, origin: Optional[str]) -> Optional[TenantConfig]:
        for tenant in self._tenants:
            if tenant.matches_origin(origin):
                return tenant
        return None

    def get_tenant_by_id(self, tenant_id: Optional[str]) -> Optional[TenantConfig]:
        if not tenant_id:
            return None
        return self._lookup.get(tenant_id)

    def build_session_id(self, tenant: TenantConfig, raw_session: str) -> str:
        """
        Codifica el session_id incluyendo el tenant para poder identificar
        a qué cliente pertenece en los callbacks de Webpay.
        """
        safe_session = re.sub(r"[^0-9a-zA-Z\-]", "", raw_session)
        session = f"{tenant.id}{self.SESSION_SEPARATOR}{safe_session}"
        return session[:60]  # Límite seguro para Webpay

    def tenant_from_session(self, session_id: Optional[str]) -> Optional[TenantConfig]:
        if not session_id:
            return None
        parts = session_id.split(self.SESSION_SEPARATOR, 1)
        if not parts:
            return None
        tenant_id = parts[0]
        return self.get_tenant_by_id(tenant_id)


# Instancia global utilizada en el resto del proyecto
tenant_manager = TenantManager()
