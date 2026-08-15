# Usage: python scripts/wallet_status.py
#
# Creates (or confirms) the agent's CDP wallet and prints its address and
# token balances on Base mainnet. Run it once to get a funding address,
# then again after sending USDC to confirm the balance landed.

import asyncio

from dotenv import load_dotenv

from agentic_payments.net import force_ipv4

force_ipv4()

from cdp import CdpClient  # noqa: E402  (must import after force_ipv4)

from agentic_payments.wallet.cdp_wallet import (  # noqa: E402
    get_or_create_wallet,
    get_token_balances,
    get_usdc_balance,
)

load_dotenv()

NETWORK = "base"


async def main():
    async with CdpClient() as cdp:
        account = await get_or_create_wallet(cdp)
        print(f"Wallet address: {account.address}")
        print(f"Network: {NETWORK}")

        balances = await get_token_balances(account, network=NETWORK)
        if not balances:
            print("No token balances yet - fund this address with USDC on Base to continue.")
        else:
            for b in balances:
                label = b["symbol"] or b["contract_address"]
                print(f"  {label}: {b['amount']}")

        usdc = await get_usdc_balance(account, network=NETWORK)
        print(f"USDC balance: {usdc}")


if __name__ == "__main__":
    asyncio.run(main())
