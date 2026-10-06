"""Base-only EIP-191 wallet proofs; services own challenges and nonce consumption."""

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx
from eth_abi import encode
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_keys.exceptions import BadSignature
from eth_utils import is_address, keccak, to_checksum_address

__all__ = ["BaseWalletVerifier", "CounterfactualValidator", "WalletProofError"]

_BASE_CHAINS = frozenset({8453, 84532})
_ERC6492_SUFFIX = bytes.fromhex("6492" * 16)
_ERC1271_MAGIC = bytes.fromhex("1626ba7e")


class WalletProofError(ValueError):
    """The wallet proof could not be established on the configured Base chain."""


@dataclass(frozen=True)
class CounterfactualValidator:
    """Operator-reviewed ERC-6492 universal validator and expected runtime code hash."""

    address: str
    code_hash: bytes

    def __post_init__(self) -> None:
        if (
            not is_address(self.address)
            or not isinstance(self.code_hash, bytes)
            or len(self.code_hash) != 32
        ):
            raise ValueError("Invalid counterfactual validator configuration")


class BaseWalletVerifier:
    """Read-only verifier using one server-configured Base RPC endpoint.

    RPC URL and optional validator are trusted operator configuration, never proof
    fields. The validator must implement isValidSig(address,bytes32,bytes), including
    ERC-6492 factory simulation. Its runtime code hash is checked at the same block
    as verification. Services must bind challenges to purpose, subject, chain,
    address and a single-use expiring nonce before accepting this result.
    """

    def __init__(
        self,
        *,
        chain_id: int,
        rpc_url: str,
        client: httpx.AsyncClient,
        counterfactual_validator: CounterfactualValidator | None = None,
    ) -> None:
        if type(chain_id) is not int or chain_id not in _BASE_CHAINS:
            raise ValueError("Configure Base mainnet (8453) or Sepolia (84532)")
        url = httpx.URL(rpc_url)
        if url.scheme not in {"http", "https"} or not url.host:
            raise ValueError("Invalid Base RPC URL")
        self._chain_id = chain_id
        self._rpc_url = rpc_url
        self._client = client
        self._validator = counterfactual_validator

    async def _rpc(self, method: str, params: list[Any]) -> Any:
        response = await self._client.post(
            self._rpc_url,
            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
            timeout=5.0,
            follow_redirects=False,
        )
        response.raise_for_status()
        body = response.json()
        if (
            not isinstance(body, dict)
            or body.get("jsonrpc") != "2.0"
            or type(body.get("id")) is not int
            or body["id"] != 1
            or "error" in body
            or "result" not in body
        ):
            raise WalletProofError("Invalid Base RPC response")
        return body["result"]

    @staticmethod
    def _bytes(value: Any) -> bytes:
        if not isinstance(value, str) or not value.startswith("0x"):
            raise WalletProofError("Invalid Base RPC data")
        return bytes.fromhex(value[2:])

    @staticmethod
    def _quantity(value: Any) -> int:
        if not isinstance(value, str) or not value.startswith("0x") or len(value) < 3:
            raise WalletProofError("Invalid Base RPC quantity")
        result = int(value, 16)
        if value != hex(result):
            raise WalletProofError("Noncanonical Base RPC quantity")
        return result

    async def verify_personal_signature(
        self, *, address: str, message: str, signature: bytes, chain_id: int
    ) -> str:
        """Return the checksum signer only when this exact proof verifies on Base.

        The explicit chain_id must come from the service's validated challenge,
        including the SIWE chain field when applicable. This does not parse SIWE
        or grant a session, enrollment or payout authorization by itself.
        """
        if type(chain_id) is not int or chain_id != self._chain_id:
            raise WalletProofError("Proof chain must match configured Base chain")
        if not is_address(address) or not isinstance(message, str) or not message:
            raise WalletProofError("Invalid wallet challenge")
        if not isinstance(signature, bytes) or not 0 < len(signature) <= 16384:
            raise WalletProofError("Invalid wallet signature size")
        try:
            message_bytes = message.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise WalletProofError("Invalid wallet challenge encoding") from exc
        if len(message_bytes) > 16384:
            raise WalletProofError("Invalid wallet challenge size")
        signer = to_checksum_address(address)
        signable = encode_defunct(text=message)
        digest = keccak(b"\x19" + signable.version + signable.header + signable.body)
        try:
            async with asyncio.timeout(15):
                if self._quantity(await self._rpc("eth_chainId", [])) != self._chain_id:
                    raise WalletProofError("RPC is not the configured Base chain")
                block = hex(self._quantity(await self._rpc("eth_blockNumber", [])))
                # ERC-6492 detection precedes code checks and EOA recovery.
                if signature.endswith(_ERC6492_SUFFIX):
                    validator = self._validator
                    if validator is None:
                        raise WalletProofError(
                            "Counterfactual verification is not configured"
                        )
                    code = self._bytes(
                        await self._rpc("eth_getCode", [validator.address, block])
                    )
                    if not code or keccak(code) != validator.code_hash:
                        raise WalletProofError(
                            "Untrusted counterfactual validator code"
                        )
                    data = keccak(text="isValidSig(address,bytes32,bytes)")[
                        :4
                    ] + encode(
                        ["address", "bytes32", "bytes"], [signer, digest, signature]
                    )
                    target = validator.address
                    expected = (1).to_bytes(32, "big")
                else:
                    code = self._bytes(await self._rpc("eth_getCode", [signer, block]))
                    if not code:
                        if (
                            len(signature) != 65
                            or Account.recover_message(signable, signature=signature)
                            != signer
                        ):
                            raise WalletProofError("Invalid EOA signature")
                        return signer
                    data = _ERC1271_MAGIC + encode(
                        ["bytes32", "bytes"], [digest, signature]
                    )
                    target = signer
                    expected = _ERC1271_MAGIC + bytes(28)
                result = self._bytes(
                    await self._rpc(
                        "eth_call",
                        [
                            {
                                "to": target,
                                "data": "0x" + data.hex(),
                                "gas": "0x4c4b40",
                            },
                            block,
                        ],
                    )
                )
                if result != expected:
                    raise WalletProofError("Contract wallet rejected the signature")
                return signer
        except WalletProofError:
            raise
        except (
            httpx.HTTPError,
            BadSignature,
            ValueError,
            TypeError,
            OverflowError,
            TimeoutError,
        ) as exc:
            raise WalletProofError("Wallet proof could not be verified") from exc
