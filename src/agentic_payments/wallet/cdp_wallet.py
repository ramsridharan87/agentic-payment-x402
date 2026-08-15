from decimal import Decimal

from cdp import CdpClient

DEFAULT_ACCOUNT_NAME = "agentic-payments-wallet"

# Native USDC on Base mainnet. Used to identify the USDC balance when the
# SDK doesn't return a token symbol for a given network.
BASE_USDC_CONTRACT = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"


async def get_or_create_wallet(cdp: CdpClient, name: str = DEFAULT_ACCOUNT_NAME):
    """Return the agent's EVM account, creating it on first run. Idempotent by name."""
    return await cdp.evm.get_or_create_account(name=name)


async def get_token_balances(account, network: str = "base") -> list[dict]:
    """Return every token balance held by the account on the given network."""
    result = await account.list_token_balances(network=network, page_size=50)
    balances = []
    for b in result.balances:
        decimals = getattr(b.amount, "decimals", 0)
        raw = int(b.amount.amount)
        amount = Decimal(raw) / (Decimal(10) ** decimals) if decimals else Decimal(raw)
        balances.append(
            {
                "contract_address": b.token.contract_address,
                "symbol": getattr(b.token, "symbol", None),
                "amount": amount,
            }
        )
    return balances


async def get_usdc_balance(account, network: str = "base") -> Decimal:
    """Return the account's USDC balance on the given network, or 0 if it holds none."""
    for b in await get_token_balances(account, network=network):
        is_usdc = (b["symbol"] or "").upper() == "USDC" or (
            b["contract_address"].lower() == BASE_USDC_CONTRACT.lower()
        )
        if is_usdc:
            return b["amount"]
    return Decimal(0)
