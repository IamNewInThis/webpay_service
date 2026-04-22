# src/services/odoo_invoices.py
"""
Servicio de Odoo Invoices (Facturas)
Maneja búsqueda de facturas y registro de pagos via account.payment.register.
"""

import requests
from typing import Any, Dict, List, Optional
from datetime import date
from dotenv import load_dotenv
from src.client_config import ClientConfig

load_dotenv()


class OdooInvoicesService:

    def __init__(self, client_config: ClientConfig):
        self.odoo_url = client_config.odoo.url
        self.database = client_config.odoo.database
        self.username = client_config.odoo.username
        self.password = client_config.odoo.password
        self.invoice_journal_id: Optional[int] = getattr(client_config.webpay, "invoice_journal_id", None)
        self.client_id = client_config.client_id
        self.client_name = client_config.client_name
        self.uid: Optional[int] = None
        self.session = requests.Session()
        print(f"🧾 OdooInvoicesService inicializado para: {self.client_name}")

    def authenticate(self) -> bool:
        payload = {
            "jsonrpc": "2.0", "method": "call",
            "params": {
                "service": "common", "method": "authenticate",
                "args": [self.database, self.username, self.password, {}],
            },
            "id": 1,
        }
        try:
            resp = self.session.post(f"{self.odoo_url}/jsonrpc", json=payload)
            if resp.ok:
                result = resp.json()
                if result.get("result"):
                    self.uid = result["result"]
                    print(f"✅ OdooInvoicesService autenticado. UID: {self.uid}")
                    return True
            print("❌ OdooInvoicesService: autenticación fallida")
            return False
        except Exception as e:
            print(f"❌ Error autenticando OdooInvoicesService: {e}")
            return False

    def _rpc(self, model: str, method: str, args: list, kw: Optional[dict] = None, rpc_id: int = 1) -> Any:
        """Wrapper para llamadas execute_kw a Odoo."""
        if not self.uid and not self.authenticate():
            raise RuntimeError("No autenticado con Odoo")
        rpc_args = [self.database, self.uid, self.password, model, method, args]
        if kw is not None:
            rpc_args.append(kw)
        payload = {
            "jsonrpc": "2.0", "method": "call",
            "params": {"service": "object", "method": "execute_kw", "args": rpc_args},
            "id": rpc_id,
        }
        resp = self.session.post(f"{self.odoo_url}/jsonrpc", json=payload)
        if not resp.ok:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        result = resp.json()
        if "error" in result:
            err = result["error"]
            msg = (err.get("data") or {}).get("message") or err.get("message", str(err))
            raise RuntimeError(f"Odoo: {msg}")
        return result.get("result")

    # ─── Consultas ───────────────────────────────────────────────────────────

    INVOICE_FIELDS = [
        "id", "name", "state", "payment_state",
        "amount_total", "amount_residual",
        "partner_id", "currency_id", "company_id",
        "invoice_date", "invoice_date_due",
        "l10n_latam_document_type_id",
    ]

    def get_invoice_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Busca una factura publicada por su nombre."""
        try:
            results = self._rpc(
                "account.move", "search_read",
                [[["name", "=", name], ["move_type", "=", "out_invoice"]]],
                {"fields": self.INVOICE_FIELDS, "limit": 1},
                rpc_id=20,
            )
            return results[0] if results else None
        except Exception as e:
            print(f"❌ Error buscando factura '{name}': {e}")
            return None

    def get_invoices_by_ids(self, invoice_ids: List[int]) -> List[Dict[str, Any]]:
        """Obtiene facturas de cliente (out_invoice) por sus IDs."""
        if not invoice_ids:
            return []
        try:
            return self._rpc(
                "account.move", "search_read",
                [[["id", "in", invoice_ids], ["move_type", "=", "out_invoice"]]],
                {"fields": self.INVOICE_FIELDS},
                rpc_id=21,
            ) or []
        except Exception as e:
            print(f"❌ Error obteniendo facturas {invoice_ids}: {e}")
            return []

    # ─── Registro de pago ────────────────────────────────────────────────────

    def register_invoice_payment(
        self,
        invoice_ids: List[int],
        amount: float,
        payment_data: Dict[str, Any],
    ) -> bool:
        """
        Registra el pago de una o varias facturas usando account.payment.register.

        Crea el pago y lo reconcilia automáticamente con las facturas indicadas,
        cambiando su payment_state a in_payment o paid.
        """
        if not invoice_ids:
            return False

        try:
            today = date.today().isoformat()
            auth_code = payment_data.get("authorization_code", "")
            buy_order = payment_data.get("buy_order", "")
            communication = f"Webpay {auth_code}" if auth_code else f"Pago Express {buy_order}"

            ctx = {
                "active_model": "account.move",
                "active_ids": invoice_ids,
                "active_id": invoice_ids[0],
            }

            # 1. Obtener valores por defecto del wizard
            print(f"🧾 Obteniendo defaults para payment.register — facturas {invoice_ids}")
            defaults = self._rpc(
                "account.payment.register", "default_get",
                [["payment_date", "amount", "journal_id", "currency_id",
                  "partner_id", "payment_type", "partner_type",
                  "company_id", "communication"]],
                {"context": ctx},
                rpc_id=22,
            )
            if not defaults:
                print("❌ No se obtuvieron defaults del wizard account.payment.register")
                return False

            # 2. Armar vals sobreescribiendo con datos reales
            wizard_vals = dict(defaults)
            wizard_vals["amount"] = float(amount)
            wizard_vals["payment_date"] = today
            wizard_vals["communication"] = communication

            # journal_id: config explícita > default de Odoo > búsqueda fallback
            if self.invoice_journal_id:
                wizard_vals["journal_id"] = self.invoice_journal_id
            elif not wizard_vals.get("journal_id"):
                fallback_journal = self._find_payment_journal()
                if fallback_journal:
                    wizard_vals["journal_id"] = fallback_journal
                    print(f"⚠️ journal_id no configurado, usando fallback ID={fallback_journal}")
                else:
                    print("❌ No se encontró ningún diario de pago. Configura invoice_journal_id en clients.yaml")
                    return False

            # 3. Crear el wizard
            wizard_id = self._rpc(
                "account.payment.register", "create",
                [wizard_vals],
                {"context": ctx},
                rpc_id=23,
            )
            if not wizard_id:
                print("❌ No se pudo crear el wizard account.payment.register")
                return False

            print(f"💳 Wizard de pago creado (ID {wizard_id}), ejecutando...")

            # 4. Crear pagos y reconciliar con facturas
            self._rpc(
                "account.payment.register", "action_create_payments",
                [[wizard_id]],
                {"context": ctx},
                rpc_id=24,
            )

            print(f"✅ Pago registrado para facturas {invoice_ids} — {communication}")
            return True

        except Exception as e:
            print(f"❌ Error registrando pago en facturas {invoice_ids}: {e}")
            return False

    def _find_payment_journal(self) -> Optional[int]:
        """Busca el primer diario de tipo banco o caja disponible como fallback."""
        try:
            results = self._rpc(
                "account.journal", "search",
                [[["type", "in", ["bank", "cash"]]]],
                {"limit": 1, "order": "sequence asc"},
                rpc_id=25,
            )
            if results:
                print(f"🔍 Diario de pago encontrado automáticamente: ID={results[0]}")
                return results[0]
            return None
        except Exception as e:
            print(f"⚠️ Error buscando diario de pago: {e}")
            return None
