from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from transbank.webpay.webpay_plus.transaction import Transaction
from transbank.common.integration_commerce_codes import IntegrationCommerceCodes
from transbank.common.integration_api_keys import IntegrationApiKeys
from transbank.common.options import WebpayOptions
from transbank.common.integration_type import IntegrationType

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://tecnogrow-webpay.odoo.com",
        "https://*.odoo.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

commerce_code = IntegrationCommerceCodes.WEBPAY_PLUS
api_key = IntegrationApiKeys.WEBPAY
integration_type = IntegrationType.TEST

options = WebpayOptions(commerce_code, api_key, integration_type)

@app.post("/webpay/init")
async def webpay_init(request: Request):
    data = await request.json()
    amount = data.get("amount", 1000)
    buy_order = f"O-{abs(hash(amount)) % 1000000}"
    session_id = f"S-{abs(hash(buy_order)) % 1000000}"

    # ⬇️ Volver a tu backend, no directamente a Odoo
    return_url = "https://webpay-service.onrender.com/webpay/commit"

    tx = Transaction(options)
    response = tx.create(buy_order, session_id, amount, return_url)
    print("🔸 Transacción creada:", response)
    return response

@app.post("/webpay/commit")
async def webpay_commit(request: Request):
    form = await request.form()
    token = form.get("token_ws")
    tx = Transaction(options)

    try:
        result = tx.commit(token)
        print("✅ Resultado commit:", result)

        # ⚙️ Lógica de retorno
        if result.get("response_code") == 0:
            # Éxito
            redirect_url = (
                f"https://tecnogrow-webpay.odoo.com/shop/confirmation"
                f"?status=success&order={result['buy_order']}"
            )
        else:
            # Rechazado o anulado
            redirect_url = "https://tecnogrow-webpay.odoo.com/shop/payment?status=cancelled"

        return RedirectResponse(url=redirect_url)

    except Exception as e:
        print("❌ Error en commit:", e)
        return RedirectResponse("https://tecnogrow-webpay.odoo.com/shop/payment?status=error")
