"""Fail-closed verification for task-bound ERC-8183 provider quotes.

The helpers in this module only verify data and read chain state. They never
hold a private key, request an approval, or broadcast a transaction.
"""
from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import asdict, dataclass
from typing import Any, TypeAlias

import httpx
from eth_abi.abi import encode
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_utils.address import to_checksum_address
from eth_utils.crypto import keccak

RpcCall: TypeAlias = Callable[[str, list[Any]], Awaitable[Any]]

ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")
HASH = re.compile(r"^0x[0-9a-fA-F]{64}$")
SIGNATURE = re.compile(r"^0x[0-9a-fA-F]{130}$")
EIP1271_MAGIC = "0x1626ba7e"


class QuoteVerificationError(ValueError):
    """A quote could not be cryptographically bound to the requested job."""


@dataclass(frozen=True)
class VerifiedQuote:
    chain_id: int
    provider: str
    price_raw: str
    payment_token: str
    verifying_contract: str
    estimated_completion_seconds: int
    quote_expires_at: int
    signature_method: str
    request_hash: str
    response_hash: str
    negotiation_hash: str
    job_description: str

    def to_dict(self) -> dict[str, Any]:
        return {"valid": True, **asdict(self)}


def canonical_json(value: Any) -> str:
    """Return the one JSON representation used for hashes and on-chain text."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def canonical_keccak(value: Any) -> str:
    return f"0x{keccak(text=canonical_json(value)).hex()}"


def response_hash_content(response: Mapping[str, Any]) -> dict[str, Any]:
    """Exclude envelope-only signature fields from the provider response hash."""
    return {
        str(key): value
        for key, value in response.items()
        if key not in {"provider_sig", "response_hash", "negotiation_hash"}
    }


def build_description_content(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """Build the exact job description content signed by the provider."""
    request = envelope.get("request")
    response = envelope.get("response")
    if not isinstance(request, Mapping) or not isinstance(response, Mapping):
        raise QuoteVerificationError("negotiation request and response must be JSON objects")
    terms = response.get("terms")
    if not isinstance(terms, Mapping):
        raise QuoteVerificationError("negotiated terms must be a JSON object")
    task = request.get("task_description")
    if not isinstance(task, str) or not task:
        raise QuoteVerificationError("negotiation is missing the canonical task description")
    job_terms = {
        str(key): value for key, value in terms.items() if key not in {"price", "currency"}
    }
    return {
        "version": 1,
        "negotiated_at": response.get("negotiated_at"),
        "quote_expires_at": response.get("quote_expires_at"),
        "task": task,
        "terms": job_terms,
        "price": terms.get("price"),
        "currency": terms.get("currency"),
        "chain_id": envelope.get("chain_id"),
        "verifying_contract": envelope.get("verifying_contract"),
    }



def sdk_description_content(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """Pinned BNB SDK format, only when sanitization would preserve every byte.

    Source: bnbagent-sdk bab27109237d509c780a36cf831dcfce70aabafe,
    python/bnbagent/erc8183/negotiation.py::_build_description_content.
    Evaluation flags are not signed by this format and are never trusted here.
    """
    content = build_description_content(envelope)
    terms = content["terms"]
    signed_keys = {"deliverables", "quality_standards", "success_criteria"}
    content["terms"] = {key: value for key, value in terms.items() if key in signed_keys}
    if not content["terms"].get("success_criteria"):
        content["terms"].pop("success_criteria", None)
    content["verifying_contract"] = to_checksum_address(content["verifying_contract"])
    strings = [content["task"], content["terms"].get("deliverables"),
               content["terms"].get("quality_standards")]
    criteria = content["terms"].get("success_criteria", [])
    if not isinstance(criteria, list):
        raise QuoteVerificationError("SDK success criteria must be a list")
    strings.extend(criteria)
    for value in strings:
        if (not isinstance(value, str) or not value.isascii() or "[" in value or "]" in value
                or any(ord(char) < 32 and char not in "\t\n" for char in value)):
            raise QuoteVerificationError("SDK sanitization would change the signed task or terms; refused")
    return content

def find_named_value(value: Any, name: str, *, _depth: int = 0) -> Any:
    """Find a named value in a bounded JSON tree without following object graphs."""
    if _depth > 12:
        return None
    if isinstance(value, Mapping):
        if name in value:
            return value[name]
        for child in value.values():
            found = find_named_value(child, name, _depth=_depth + 1)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value[:100]:
            found = find_named_value(child, name, _depth=_depth + 1)
            if found is not None:
                return found
    return None


def find_negotiation_envelope(value: Any, *, _depth: int = 0) -> dict[str, Any] | None:
    """Locate a complete negotiation envelope in a bounded A2A response."""
    if _depth > 12:
        return None
    if isinstance(value, Mapping):
        required = {
            "request",
            "request_hash",
            "response",
            "response_hash",
            "chain_id",
            "verifying_contract",
            "negotiation_hash",
            "provider_sig",
        }
        if required.issubset(value):
            return {str(key): item for key, item in value.items()}
        for child in value.values():
            found = find_negotiation_envelope(child, _depth=_depth + 1)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value[:100]:
            found = find_negotiation_envelope(child, _depth=_depth + 1)
            if found is not None:
                return found
    return None


async def _default_rpc(rpc_url: str, method: str, params: list[Any]) -> Any:
    async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
        response = await client.post(
            rpc_url,
            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        )
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict) or payload.get("error") is not None or "result" not in payload:
        raise QuoteVerificationError(f"RPC did not return a result for {method}")
    return payload["result"]


async def _read_chain_context(
    *, rpc_url: str, rpc_call: RpcCall | None, expected_chain_id: int
) -> tuple[RpcCall, int]:
    async def call(method: str, params: list[Any]) -> Any:
        if rpc_call is not None:
            return await rpc_call(method, params)
        return await _default_rpc(rpc_url, method, params)

    chain_raw = await call("eth_chainId", [])
    block = await call("eth_getBlockByNumber", ["latest", False])
    if not isinstance(chain_raw, str) or not isinstance(block, Mapping):
        raise QuoteVerificationError("RPC returned an invalid chain context")
    timestamp_raw = block.get("timestamp")
    if not isinstance(timestamp_raw, str):
        raise QuoteVerificationError("RPC latest block is missing its timestamp")
    try:
        chain_id = int(chain_raw, 16)
        timestamp = int(timestamp_raw, 16)
    except ValueError as exc:
        raise QuoteVerificationError("RPC returned malformed chain numbers") from exc
    if chain_id != expected_chain_id or timestamp <= 0:
        raise QuoteVerificationError("RPC returned invalid chain numbers")
    return call, timestamp


def _eip191_digest(text: str) -> bytes:
    raw = text.encode("utf-8")
    return keccak(b"\x19Ethereum Signed Message:\n" + str(len(raw)).encode("ascii") + raw)


async def _verify_signature(
    *,
    provider: str,
    negotiation_hash: str,
    signature: str,
    call: RpcCall,
) -> str:
    if not ADDRESS.fullmatch(provider):
        raise QuoteVerificationError("provider is not an EVM address")
    if not HASH.fullmatch(negotiation_hash) or not SIGNATURE.fullmatch(signature):
        raise QuoteVerificationError("provider signature fields are malformed")
    code = await call("eth_getCode", [provider, "latest"])
    if not isinstance(code, str) or not code.startswith("0x"):
        raise QuoteVerificationError("RPC returned malformed provider bytecode")
    if code not in {"0x", "0x0", "0x00"}:
        digest = _eip191_digest(negotiation_hash)
        calldata = keccak(text="isValidSignature(bytes32,bytes)")[:4] + encode(
            ["bytes32", "bytes"],
            [digest, bytes.fromhex(signature[2:])],
        )
        result = await call("eth_call", [{"to": provider, "data": f"0x{calldata.hex()}"}, "latest"])
        if not isinstance(result, str) or not result.lower().startswith(EIP1271_MAGIC):
            raise QuoteVerificationError("ERC-1271 provider signature is invalid")
        return "eip1271"
    try:
        recovered = Account.recover_message(
            encode_defunct(text=negotiation_hash), signature=signature
        )
    except (TypeError, ValueError) as exc:
        raise QuoteVerificationError("EOA provider signature is invalid") from exc
    if recovered.lower() != provider.lower():
        raise QuoteVerificationError("provider signature does not match the quoted provider")
    return "eip191"


def _validated_description(
    description: Mapping[str, Any],
    *,
    expected_chain_id: int,
    expected_verifying_contract: str,
    expected_payment_token: str,
    expected_price_raw: int,
    chain_timestamp: int,
    require_current_quote: bool = True,
) -> tuple[dict[str, Any], str, str]:
    content = {
        str(key): value
        for key, value in description.items()
        if key not in {"negotiation_hash", "provider_sig"}
    }
    if content.get("version") != 1:
        raise QuoteVerificationError("unsupported signed job-description version")
    if content.get("chain_id") != expected_chain_id:
        raise QuoteVerificationError("quote is bound to a different chain")
    contract = content.get("verifying_contract")
    currency = content.get("currency")
    if not isinstance(contract, str) or contract.lower() != expected_verifying_contract.lower():
        raise QuoteVerificationError("quote is bound to a different ERC-8183 contract")
    if not isinstance(currency, str) or currency.lower() != expected_payment_token.lower():
        raise QuoteVerificationError("quote uses an unexpected payment token")
    price = content.get("price")
    if isinstance(price, bool) or not isinstance(price, (int, str)):
        raise QuoteVerificationError("quote price is not an unsigned raw integer")
    price_text = str(price)
    if not price_text.isascii() or not price_text.isdigit() or int(price_text) != expected_price_raw:
        raise QuoteVerificationError("quote price does not match the reviewed fixed price")
    negotiated_at = content.get("negotiated_at")
    expires_at = content.get("quote_expires_at")
    if not isinstance(negotiated_at, int) or isinstance(negotiated_at, bool):
        raise QuoteVerificationError("quote negotiation time is invalid")
    if not isinstance(expires_at, int) or isinstance(expires_at, bool):
        raise QuoteVerificationError("quote expiry is invalid")
    if negotiated_at > chain_timestamp + 30 or (require_current_quote and expires_at <= chain_timestamp):
        raise QuoteVerificationError("quote is not currently valid at the latest chain timestamp")
    if expires_at <= negotiated_at or expires_at - negotiated_at > 86_400:
        raise QuoteVerificationError("quote validity window is invalid")
    task = content.get("task")
    terms = content.get("terms")
    if not isinstance(task, str) or not isinstance(terms, Mapping):
        raise QuoteVerificationError("signed description is missing its task or terms")
    try:
        parsed_task = json.loads(task)
    except json.JSONDecodeError as exc:
        raise QuoteVerificationError("signed task is not valid canonical JSON") from exc
    if not isinstance(parsed_task, dict) or canonical_json(parsed_task) != task:
        raise QuoteVerificationError("signed task is not canonical JSON")
    negotiation_hash = description.get("negotiation_hash")
    signature = description.get("provider_sig")
    if not isinstance(negotiation_hash, str) or negotiation_hash != canonical_keccak(content):
        raise QuoteVerificationError("negotiation hash does not match the signed job description")
    if not isinstance(signature, str):
        raise QuoteVerificationError("signed job description is missing the provider signature")
    return content, negotiation_hash, signature


async def verify_negotiation_envelope(
    *,
    envelope: Mapping[str, Any],
    expected_request: Mapping[str, Any],
    provider: str,
    expected_chain_id: int,
    expected_verifying_contract: str,
    expected_payment_token: str,
    expected_price_raw: int,
    rpc_url: str,
    rpc_call: RpcCall | None = None,
    quote_format: str = "safehire-v2",
) -> VerifiedQuote:
    """Verify request/response hashes, current validity and provider signature."""
    if quote_format not in {"safehire-v2", "bnbagent-sdk-v1"}:
        raise QuoteVerificationError("unreviewed provider quote format")
    request = envelope.get("request")
    response = envelope.get("response")
    if not isinstance(request, Mapping) or not isinstance(response, Mapping):
        raise QuoteVerificationError("negotiation envelope is incomplete")
    if canonical_json(request) != canonical_json(expected_request):
        raise QuoteVerificationError("provider quote does not bind the exact requested task")
    request_hash = envelope.get("request_hash")
    response_hash = envelope.get("response_hash")
    if request_hash != canonical_keccak(request):
        raise QuoteVerificationError("negotiation request hash mismatch")
    response_content = response_hash_content(response)
    if quote_format == "bnbagent-sdk-v1":
        # SDK assigns negotiated_at after computing response_hash. The timestamp
        # is nevertheless bound by negotiation_hash + provider_sig below.
        response_content.pop("negotiated_at", None)
    if response_hash != canonical_keccak(response_content):
        raise QuoteVerificationError("negotiation response hash mismatch")
    if response.get("accepted") is not True:
        raise QuoteVerificationError("provider did not accept the requested job")
    requested_terms = request.get("terms")
    response_terms = response.get("terms")
    if not isinstance(requested_terms, Mapping) or not isinstance(response_terms, Mapping):
        raise QuoteVerificationError("negotiation terms are missing")
    if quote_format == "bnbagent-sdk-v1" and (set(requested_terms) - {"deliverables", "quality_standards", "success_criteria", "evaluation_required", "evaluator_type"}
            or requested_terms.get("evaluation_required", True) is not True
            or requested_terms.get("evaluator_type", "uma_oov3") != "uma_oov3"):
        raise QuoteVerificationError("SDK quote contains unreviewed unsigned metadata")
    for key, value in requested_terms.items():
        if response_terms.get(key) != value:
            raise QuoteVerificationError("provider changed a requested non-price term")
    description_content = sdk_description_content(envelope) if quote_format == "bnbagent-sdk-v1" else build_description_content(envelope)
    negotiation_hash = envelope.get("negotiation_hash")
    signature = envelope.get("provider_sig")
    if not isinstance(negotiation_hash, str) or negotiation_hash != canonical_keccak(description_content):
        raise QuoteVerificationError("negotiation hash mismatch")
    if not isinstance(signature, str):
        raise QuoteVerificationError("provider signature is missing")
    description = {
        **description_content,
        "negotiation_hash": negotiation_hash,
        "provider_sig": signature,
    }
    call, chain_timestamp = await _read_chain_context(rpc_url=rpc_url, rpc_call=rpc_call, expected_chain_id=expected_chain_id)
    _validated_description(
        description,
        expected_chain_id=expected_chain_id,
        expected_verifying_contract=expected_verifying_contract,
        expected_payment_token=expected_payment_token,
        expected_price_raw=expected_price_raw,
        chain_timestamp=chain_timestamp,
    )
    signature_method = await _verify_signature(
        provider=provider,
        negotiation_hash=negotiation_hash,
        signature=signature,
        call=call,
    )
    completion = response.get("estimated_completion_seconds")
    if not isinstance(completion, int) or isinstance(completion, bool) or not 1 <= completion <= 604_800:
        raise QuoteVerificationError("estimated completion time is invalid")
    expires_at = description_content["quote_expires_at"]
    assert isinstance(expires_at, int)
    assert isinstance(request_hash, str)
    assert isinstance(response_hash, str)
    return VerifiedQuote(
        chain_id=expected_chain_id,
        provider=provider,
        price_raw=str(expected_price_raw),
        payment_token=expected_payment_token,
        verifying_contract=expected_verifying_contract,
        estimated_completion_seconds=completion,
        quote_expires_at=expires_at,
        signature_method=signature_method,
        request_hash=request_hash,
        response_hash=response_hash,
        negotiation_hash=negotiation_hash,
        job_description=canonical_json(description),
    )


async def verify_job_description(
    *,
    description: Mapping[str, Any],
    provider: str,
    expected_chain_id: int,
    expected_verifying_contract: str,
    expected_payment_token: str,
    expected_price_raw: int,
    rpc_url: str,
    rpc_call: RpcCall | None = None,
    require_current_quote: bool = True,
) -> dict[str, Any]:
    """Re-verify the signed description read back from an on-chain job."""
    call, chain_timestamp = await _read_chain_context(rpc_url=rpc_url, rpc_call=rpc_call, expected_chain_id=expected_chain_id)
    _, negotiation_hash, signature = _validated_description(
        description,
        expected_chain_id=expected_chain_id,
        expected_verifying_contract=expected_verifying_contract,
        expected_payment_token=expected_payment_token,
        expected_price_raw=expected_price_raw,
        chain_timestamp=chain_timestamp,
        require_current_quote=require_current_quote,
    )
    signature_method = await _verify_signature(
        provider=provider,
        negotiation_hash=negotiation_hash,
        signature=signature,
        call=call,
    )
    return {
        "valid": True,
        "provider": provider,
        "signature_method": signature_method,
        "negotiation_hash": negotiation_hash,
    }
