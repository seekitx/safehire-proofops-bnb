from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
from eth_utils.crypto import keccak

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = PROJECT_ROOT / "evidence" / "pancakeswap" / "live-benefit-report.json"
RPC_URL = "https://bsc-dataseed.bnbchain.org"

# Current BSC addresses from PancakeSwap's official V3 address page.
FACTORY = "0x0BFbCF9fa4f9C56B0F40a671Ad40E0805A091865"
QUOTER_V2 = "0xB048Bbc1Ee6b733FFfCFb9e9CeF7375518e25997"
SOURCE_URL = "https://developer.pancakeswap.finance/contracts/v3/addresses"

# Canonical BSC WBNB and Binance-Peg USDT. Both use 18 decimals.
WBNB = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
USDT = "0x55d398326f99059fF775485246999027B3197955"
AMOUNT_IN_RAW = 10**17  # 0.1 WBNB
FEE_TIERS = (100, 500, 2500, 10000)


def _selector(signature: str) -> str:
    return keccak(text=signature)[:4].hex()


def _word_address(value: str) -> str:
    return value.lower().removeprefix("0x").zfill(64)


def _word_int(value: int) -> str:
    return hex(value)[2:].zfill(64)


async def _rpc(
    client: httpx.AsyncClient,
    method: str,
    params: list[Any],
) -> Any:
    response = await client.post(
        RPC_URL,
        json={"jsonrpc": "2.0", "id": method, "method": method, "params": params},
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or payload.get("error") or "result" not in payload:
        raise ValueError(f"BSC RPC rejected {method}")
    return payload["result"]


def _decode_words(raw: str) -> list[int]:
    if not isinstance(raw, str) or not raw.startswith("0x"):
        raise ValueError("invalid eth_call response")
    body = raw[2:]
    if len(body) % 64:
        raise ValueError("misaligned eth_call response")
    return [int(body[index : index + 64], 16) for index in range(0, len(body), 64)]


async def capture() -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20) as client:
        chain_id = int(await _rpc(client, "eth_chainId", []), 16)
        if chain_id != 56:
            raise ValueError("RPC is not BSC mainnet")
        block_number = int(await _rpc(client, "eth_blockNumber", []), 16)
        block_tag = hex(block_number)

        quotes: list[dict[str, Any]] = []
        for fee in FEE_TIERS:
            pool_call = (
                "0x"
                + _selector("getPool(address,address,uint24)")
                + _word_address(WBNB)
                + _word_address(USDT)
                + _word_int(fee)
            )
            pool_raw = await _rpc(
                client,
                "eth_call",
                [{"to": FACTORY, "data": pool_call}, block_tag],
            )
            pool = "0x" + str(pool_raw)[-40:]
            if int(pool, 16) == 0:
                continue

            quote_call = (
                "0x"
                + _selector(
                    "quoteExactInputSingle((address,address,uint256,uint24,uint160))"
                )
                + _word_address(WBNB)
                + _word_address(USDT)
                + _word_int(AMOUNT_IN_RAW)
                + _word_int(fee)
                + _word_int(0)
            )
            quote_raw = await _rpc(
                client,
                "eth_call",
                [{"to": QUOTER_V2, "data": quote_call}, block_tag],
            )
            words = _decode_words(quote_raw)
            if len(words) < 4:
                raise ValueError("PancakeSwap QuoterV2 returned an incomplete response")
            amount_out = Decimal(words[0]) / Decimal(10**18)
            quotes.append(
                {
                    "fee_hundredths_of_bip": fee,
                    "fee_percent": str(Decimal(fee) / Decimal(10_000)),
                    "pool_address": pool,
                    "pool_url": f"https://bscscan.com/address/{pool}",
                    "amount_out_raw": str(words[0]),
                    "amount_out_usdt": str(amount_out),
                    "initialized_ticks_crossed": words[2],
                    "quoter_gas_estimate": words[3],
                }
            )

    if len(quotes) < 2:
        raise ValueError("fewer than two viable direct PancakeSwap V3 pools were quoted")
    best = max(quotes, key=lambda item: Decimal(str(item["amount_out_usdt"])))
    baseline = next(
        (item for item in quotes if item["fee_hundredths_of_bip"] == 500),
        sorted(quotes, key=lambda item: Decimal(str(item["amount_out_usdt"])), reverse=True)[1],
    )
    improvement = Decimal(str(best["amount_out_usdt"])) - Decimal(
        str(baseline["amount_out_usdt"])
    )
    improvement_bps = improvement / Decimal(str(baseline["amount_out_usdt"])) * 10_000

    report = {
        "schema_version": "1.0",
        "evidence_mode": "live",
        "beneficiary": "trader",
        "network": "bsc-mainnet",
        "chain_id": 56,
        "observed_block": block_number,
        "observed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "source_url": SOURCE_URL,
        "source": "pancakeswap_v3_factory_and_quoter_v2_same_block_rpc",
        "contracts": {
            "factory": FACTORY,
            "quoter_v2": QUOTER_V2,
        },
        "input": {
            "token_in": WBNB,
            "token_out": USDT,
            "amount_in_raw": str(AMOUNT_IN_RAW),
            "amount_in_display": "0.1 WBNB",
        },
        "quotes": quotes,
        "decision": {
            "selected_fee_hundredths_of_bip": best["fee_hundredths_of_bip"],
            "selected_pool": best["pool_address"],
            "selected_amount_out_usdt": best["amount_out_usdt"],
            "baseline_fee_hundredths_of_bip": baseline["fee_hundredths_of_bip"],
            "baseline_amount_out_usdt": baseline["amount_out_usdt"],
            "improvement_usdt": str(improvement),
            "improvement_bps": str(improvement_bps.quantize(Decimal("0.0001"))),
        },
        "measurable_benefit": (
            f"At BSC block {block_number}, comparing direct PancakeSwap V3 fee tiers "
            f"selected the {Decimal(int(best['fee_hundredths_of_bip'])) / Decimal(10_000)}% "
            f"pool over the 0.05% baseline and improved the read-only 0.1 WBNB quote by "
            f"{improvement} USDT ({improvement_bps.quantize(Decimal('0.0001'))} bps)."
        ),
        "risk_boundary": (
            "This is a same-block read-only QuoterV2 comparison, not a trade or profit promise. "
            "It excludes transaction gas and later price movement; execution still needs a fresh "
            "quote, user slippage limit, deadline, allowance review and wallet confirmation."
        ),
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return report


if __name__ == "__main__":
    result = asyncio.run(capture())
    print(json.dumps(result["decision"], indent=2, ensure_ascii=False))
