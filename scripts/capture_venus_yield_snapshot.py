from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = PROJECT_ROOT / "evidence" / "venus" / "stablecoin-yield-snapshot.json"
SOURCE_URL = "https://api.venus.io/markets"
SOURCE_DOC = (
    "https://github.com/VenusProtocol/venus-protocol-documentation/blob/main/services/api.md"
)
CORE_POOL = "0xfD36E2c2a6789Db23113685031d7F16329158384"
SYMBOLS = ("USDT", "USDC", "FDUSD")


def _decimal(raw: Any, field: str) -> Decimal:
    try:
        return Decimal(str(raw))
    except Exception as exc:  # Decimal raises more than one input exception.
        raise ValueError(f"Venus returned an invalid {field}") from exc


async def capture() -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            SOURCE_URL,
            params={"chainId": "56", "limit": "100"},
            headers={"accept-version": "next"},
        )
        response.raise_for_status()
        payload = response.json()

    rows = payload.get("result") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise TypeError("Venus markets response has no result list")

    markets: list[dict[str, Any]] = []
    for symbol in SYMBOLS:
        candidates = [
            row
            for row in rows
            if isinstance(row, dict)
            and str(row.get("chainId")) == "56"
            and str(row.get("underlyingSymbol")) == symbol
            and str(row.get("poolComptrollerAddress", "")).lower() == CORE_POOL.lower()
            and row.get("isListed") is True
            and row.get("isPriceInvalid") is False
        ]
        if len(candidates) != 1:
            raise ValueError(f"expected one healthy core-pool {symbol} market")
        row = candidates[0]
        supply_apy = _decimal(row.get("supplyApy"), f"{symbol}.supplyApy")
        supply_usd = _decimal(
            row.get("totalSupplyUnderlyingCents"),
            f"{symbol}.totalSupplyUnderlyingCents",
        ) / Decimal(100)
        liquidity_usd = _decimal(row.get("liquidityCents"), f"{symbol}.liquidityCents") / Decimal(
            100
        )
        markets.append(
            {
                "protocol": f"Venus Core {symbol}",
                "symbol": symbol,
                "market_address": row["address"],
                "market_url": f"https://bscscan.com/address/{row['address']}",
                "gross_supply_apy_percent": str(supply_apy),
                "total_supplied_usd": str(supply_usd),
                "available_liquidity_usd": str(liquidity_usd),
                "listed": True,
                "price_valid": True,
                "paused_actions_bitmap": int(row.get("pausedActionsBitmap", -1)),
                "last_calculated_block": int(row.get("lastCalculatedXvsAccruedBlockNumber", 0)),
            }
        )

    report = {
        "schema_version": "1.0",
        "evidence_mode": "live",
        "network": "bsc-mainnet",
        "chain_id": 56,
        "observed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "source_url": SOURCE_URL,
        "source_documentation": SOURCE_DOC,
        "api_version": "next",
        "pool_comptroller": CORE_POOL,
        "markets": markets,
        "risk_boundary": (
            "Venus describes this API as indexed data that can lag the chain. This snapshot is "
            "suitable for a recorded comparison input, not for transaction simulation, account "
            "health, pause-state enforcement, or a profit promise."
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
    print(json.dumps(result["markets"], indent=2, ensure_ascii=False))
