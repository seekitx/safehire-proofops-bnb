from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

from eth_abi.abi import encode
from eth_utils.address import to_checksum_address
from eth_utils.crypto import keccak

REGISTER_SIGNATURE = "register(bytes32,uint8,string,bytes32)"
REGISTER_SELECTOR = keccak(text=REGISTER_SIGNATURE)[:4]
SELLER_FUNDING_WEI = 50_000_000_000_000_000


def _creation_bytecode(project_root: Path, contract_name: str) -> str:
    path = (
        project_root
        / "contracts"
        / "artifacts"
        / "src"
        / f"{contract_name}.sol"
        / f"{contract_name}.json"
    )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"compiled artifact missing for {contract_name}; run npm run compile in contracts"
        ) from exc
    bytecode = payload.get("bytecode") if isinstance(payload, dict) else None
    if not isinstance(bytecode, str) or not bytecode.startswith("0x") or len(bytecode) < 4:
        raise ValueError(f"compiled artifact has invalid bytecode: {contract_name}")
    return bytecode


def _agent_wallet(project_root: Path) -> str:
    config_path = (
        project_root
        / "agent-studio"
        / "safehireagents"
        / "app"
        / "agent"
        / "studio.toml"
    )
    try:
        with config_path.open("rb") as handle:
            config = tomllib.load(handle)
        address = str(config["wallet"]["address"])
        return str(to_checksum_address(address))
    except (OSError, KeyError, TypeError, ValueError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(
            "Agent Studio wallet address is missing; create the seller wallet first"
        ) from exc


def base_deployment_plan(project_root: Path) -> dict[str, Any]:
    """Return unsigned BSC Testnet creation data for the no-argument contracts."""

    seller_wallet = _agent_wallet(project_root)
    transactions = []
    for contract_name in ("AgentRegistry", "EvidenceAnchor"):
        bytecode = _creation_bytecode(project_root, contract_name)
        transactions.append(
            {
                "contract_name": contract_name,
                "data": bytecode,
                "value": "0x0",
            }
        )
    return {
        "chain_id": 97,
        "network": "bsc-testnet",
        "funding": {
            "kind": "funding",
            "contract_name": "FundAgentWallet",
            "to": seller_wallet,
            "value": hex(SELLER_FUNDING_WEI),
            "value_wei": str(SELLER_FUNDING_WEI),
            "value_display": "0.05 tBNB",
        },
        "transactions": transactions,
        "policy_template": {
            "executor": "connected_wallet",
            "target": "deployed_AgentRegistry",
            "selector": f"0x{REGISTER_SELECTOR.hex()}",
            "selector_signature": REGISTER_SIGNATURE,
            "max_value_per_call_wei": "0",
            "max_total_value_wei": "0",
            "expires_in_seconds": 604800,
            "revocable": True,
        },
        "asset_boundary": {
            "gas_asset": "tBNB",
            "erc8183_hiring_asset": "U",
            "erc8183_hiring_price": "0.1",
            "strategy_assets": ["USDT", "USDC"],
            "deployment_spends_hiring_asset": False,
            "seller_wallet": seller_wallet,
        },
    }


def scoped_policy_creation_data(
    project_root: Path,
    *,
    owner: str,
    registry_address: str,
    expires_at: int,
) -> dict[str, Any]:
    """Build unsigned constructor data for a zero-value, revocable demo policy."""

    try:
        executor = to_checksum_address(owner)
        target = to_checksum_address(registry_address)
    except ValueError as exc:
        raise ValueError("owner and registry_address must be valid EVM addresses") from exc
    if expires_at <= 0:
        raise ValueError("expires_at must be a positive Unix timestamp")

    bytecode = _creation_bytecode(project_root, "ScopedExecutionPolicy")
    constructor_args = encode(
        ["address", "address[]", "bytes4[]", "uint256", "uint256", "uint64"],
        [executor, [target], [REGISTER_SELECTOR], 0, 0, expires_at],
    )
    return {
        "chain_id": 97,
        "network": "bsc-testnet",
        "contract_name": "ScopedExecutionPolicy",
        "data": f"{bytecode}{constructor_args.hex()}",
        "value": "0x0",
        "policy": {
            "owner": executor,
            "executor": executor,
            "allowed_targets": [target],
            "allowed_selectors": [f"0x{REGISTER_SELECTOR.hex()}"],
            "max_value_per_call_wei": "0",
            "max_total_value_wei": "0",
            "expires_at": expires_at,
            "require_human_approval": True,
            "revocable": True,
        },
    }
