import requests

from ..payments.x402_client import atomic_to_usd

DISCOVERY_URL = "https://api.cdp.coinbase.com/platform/v2/x402/discovery/search"


def search_bazaar(
    query: str,
    max_usd_price: float | None = None,
    network: str = "base",
    limit: int = 5,
) -> list[dict]:
    """Search Coinbase's x402 Bazaar for real pay-per-call endpoints matching
    `query`. Free - this only looks up what's available and its price, it
    does not pay for or call anything. No CDP API key required (public)."""
    params: dict[str, str | int] = {"query": query, "network": network, "limit": limit}
    if max_usd_price is not None:
        params["maxUsdPrice"] = f"{max_usd_price:.2f}"

    response = requests.get(DISCOVERY_URL, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()

    results = []
    for item in data.get("resources", []):
        accepts = item.get("accepts") or [{}]
        terms = accepts[0]
        # Bazaar's `network` filter is a relevance hint, not a hard filter -
        # it can still return non-EVM (e.g. Solana) results. Drop anything
        # this wallet's EVM-only signer couldn't actually pay for.
        if not str(terms.get("network", "")).startswith("eip155"):
            continue
        price_usd = None
        if terms.get("amount"):
            price_usd = atomic_to_usd(int(terms["amount"]))
        results.append(
            {
                "resource": item.get("resource"),
                "description": item.get("description"),
                "service_name": item.get("serviceName"),
                "price_usd": price_usd,
                "network": terms.get("network"),
                "pay_to": terms.get("payTo"),
            }
        )
    return results
