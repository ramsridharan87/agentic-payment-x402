from dataclasses import dataclass

from x402 import x402ClientSync
from x402.mechanisms.evm.exact.register import register_exact_evm_client
from x402.schemas.hooks import AbortResult, PaymentCreationContext

from ..audit import AuditLog

BASE_MAINNET = "eip155:8453"
USDC_DECIMALS = 6


def usd_to_atomic(usd: float, decimals: int = USDC_DECIMALS) -> int:
    return round(usd * (10**decimals))


def atomic_to_usd(atomic: int, decimals: int = USDC_DECIMALS) -> float:
    return atomic / (10**decimals)


@dataclass
class LastPayment:
    """Populated by the before-payment hook so the calling tool can attach the
    settlement's tx hash to the same amount/destination after the round trip."""

    amount_usd: float | None = None
    destination: str | None = None
    network: str | None = None


def build_x402_client(
    signer,
    audit: AuditLog,
    per_tx_cap_usd: float,
    daily_cap_usd: float,
    network: str = BASE_MAINNET,
) -> tuple[x402ClientSync, LastPayment]:
    """Build an x402 client wired to `signer`, enforcing hard spending caps in
    code (independent of whatever an agent reasons about) and logging every
    payment decision - allowed or blocked - to the audit log.

    Note: the CDP wallet itself also enforces a $2/transaction Wallet Policy
    server-side, so a bug here isn't the only line of defense.
    """
    client = x402ClientSync()
    register_exact_evm_client(client, signer, networks=network)
    last_payment = LastPayment()

    def before_payment(ctx: PaymentCreationContext) -> AbortResult | None:
        req = ctx.selected_requirements
        amount_usd = atomic_to_usd(int(req.get_amount()))

        if amount_usd > per_tx_cap_usd:
            audit.log(
                "payment_blocked",
                f"Blocked ${amount_usd:.4f} payment to {req.pay_to} - exceeds "
                f"per-transaction cap of ${per_tx_cap_usd:.2f}",
                amount_usd=amount_usd,
                destination=req.pay_to,
                network=str(req.network),
            )
            return AbortResult(reason="per_tx_cap_exceeded")

        spent_today = audit.spent_today_usd()
        if spent_today + amount_usd > daily_cap_usd:
            audit.log(
                "payment_blocked",
                f"Blocked ${amount_usd:.4f} payment to {req.pay_to} - would exceed "
                f"daily cap (${spent_today:.4f} already spent today, cap ${daily_cap_usd:.2f})",
                amount_usd=amount_usd,
                destination=req.pay_to,
                network=str(req.network),
            )
            return AbortResult(reason="daily_cap_exceeded")

        last_payment.amount_usd = amount_usd
        last_payment.destination = req.pay_to
        last_payment.network = str(req.network)
        return None

    client.on_before_payment_creation(before_payment)
    return client, last_payment
