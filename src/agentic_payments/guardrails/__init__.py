import os
from dataclasses import dataclass


@dataclass(frozen=True)
class SpendingPolicy:
    per_tx_cap_usd: float
    daily_cap_usd: float

    @classmethod
    def from_env(cls) -> "SpendingPolicy":
        return cls(
            per_tx_cap_usd=float(os.environ.get("PAYMENT_PER_TX_CAP_USD", "0.03")),
            daily_cap_usd=float(os.environ.get("PAYMENT_DAILY_CAP_USD", "10")),
        )
