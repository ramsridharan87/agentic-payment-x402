from typing import Any

from x402 import NoMatchingRequirementsError, PaymentAbortedError, x402ClientSync
from x402.http import x402HTTPClientSync
from x402.http.clients import x402_requests
from x402.http.clients.requests import PaymentError as X402RequestsPaymentError

from ..audit import AuditLog
from ..payments.x402_client import LastPayment


def fetch_paid_resource(
    url: str,
    client: x402ClientSync,
    audit: AuditLog,
    last_payment: LastPayment,
) -> dict[str, Any]:
    """Fetch a URL, automatically paying via x402 if it returns 402 Payment
    Required. This is the only function in the codebase that can move money -
    every call goes through the per-transaction and daily spending caps
    registered on `client` before any signature is produced."""
    http_client = x402HTTPClientSync(client)
    last_payment.amount_usd = None
    last_payment.destination = None
    last_payment.network = None

    try:
        with x402_requests(client) as session:
            response = session.get(url, timeout=30)
    except X402RequestsPaymentError as e:
        # The requests adapter wraps every create_payment_payload failure in
        # its own PaymentError; the real reason is on __cause__.
        cause = e.__cause__
        if isinstance(cause, PaymentAbortedError):
            return {"error": f"Payment blocked by spending guardrail: {cause.reason}"}
        if isinstance(cause, NoMatchingRequirementsError):
            audit.log(
                "payment_blocked",
                f"No compatible x402 payment method offered for {url}",
                resource_url=url,
            )
            return {"error": "This resource didn't offer a payment method this wallet supports."}
        audit.log("payment_failed", f"Payment failed for {url}: {e}", resource_url=url)
        return {"error": f"Payment failed: {e}"}

    if response.status_code >= 400:
        return {
            "error": f"Request failed with status {response.status_code}",
            "body": response.text[:1000],
        }

    try:
        settle_response = http_client.get_payment_settle_response(
            lambda name: response.headers.get(name)
        )
        audit.log(
            "payment_executed",
            f"Paid ${last_payment.amount_usd or 0:.4f} to {last_payment.destination} "
            f"for {url} (tx {settle_response.transaction})",
            amount_usd=last_payment.amount_usd,
            destination=last_payment.destination,
            resource_url=url,
            network=last_payment.network,
            tx_hash=settle_response.transaction,
        )
    except ValueError:
        pass  # resource was free - no payment was made

    return {"status": response.status_code, "body": response.text[:4000]}
