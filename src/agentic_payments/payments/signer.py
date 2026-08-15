import asyncio
from typing import Any

from cdp import CdpClient

from ..wallet.cdp_wallet import DEFAULT_ACCOUNT_NAME


class CdpEvmSigner:
    """Bridges x402's ClientEvmSigner protocol to a CDP-managed account.

    The raw private key never leaves CDP's custody or enters this process:
    every signature is produced by calling CDP's sign_typed_data API, which
    signs server-side and returns only the resulting signature bytes.

    x402 calls sign_typed_data synchronously (even from its async client), so
    each call opens a short-lived CdpClient and drives it with asyncio.run().
    This is safe as long as it's never called from inside an already-running
    event loop (true for the sync agent/tool-use loop this project uses).
    """

    def __init__(self, address: str, account_name: str = DEFAULT_ACCOUNT_NAME) -> None:
        self._address = address
        self._account_name = account_name

    @property
    def address(self) -> str:
        return self._address

    def sign_typed_data(
        self,
        domain: Any,
        types: dict[str, list[Any]],
        primary_type: str,
        message: dict[str, Any],
    ) -> bytes:
        return asyncio.run(self._sign_async(domain, types, primary_type, message))

    async def _sign_async(
        self,
        domain: Any,
        types: dict[str, list[Any]],
        primary_type: str,
        message: dict[str, Any],
    ) -> bytes:
        domain_dict = {
            "name": domain.name,
            "version": domain.version,
            "chainId": domain.chain_id,
            "verifyingContract": domain.verifying_contract,
        }
        types_dict = {
            type_name: [{"name": f.name, "type": f.type} for f in fields]
            for type_name, fields in types.items()
        }

        async with CdpClient() as cdp:
            account = await cdp.evm.get_or_create_account(name=self._account_name)
            signature = await account.sign_typed_data(
                domain=domain_dict,
                types=types_dict,
                primary_type=primary_type,
                message=message,
            )

        if isinstance(signature, (bytes, bytearray)):
            return bytes(signature)
        return bytes.fromhex(signature.removeprefix("0x"))
