from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Callable

import httpx

from proofops.domain.canonical import sha256_hex
from proofops.domain.errors import AdapterUnavailableError
from proofops.domain.models import DataSource, ExecutionIntent, ExecutionMode, ExecutionReceipt


class ExecutionAdapter(ABC):
    @abstractmethod
    async def execute(self, intent: ExecutionIntent) -> ExecutionReceipt:
        raise NotImplementedError


class DemoExecutionAdapter(ExecutionAdapter):
    async def execute(self, intent: ExecutionIntent) -> ExecutionReceipt:
        await asyncio.sleep(0)
        synthetic_hash = "0x" + sha256_hex(intent.to_dict())
        return ExecutionReceipt(
            task_id=intent.task_id,
            success=True,
            mode=ExecutionMode.DEMO,
            tx_hash=synthetic_hash,
            chain_id=intent.chain_id,
            gas_used=0,
            cost_usd=0.0,
            source=DataSource.DEMO_FIXTURE,
            result={
                "status": "simulated_demo_execution",
                "warning": "This is not a blockchain transaction and cannot satisfy the live evidence gate.",
                "target": intent.target,
                "method": intent.method,
            },
        )


class DisabledOnchainAdapter(ExecutionAdapter):
    def __init__(self, reason: str) -> None:
        self.reason = reason

    async def execute(self, intent: ExecutionIntent) -> ExecutionReceipt:
        raise AdapterUnavailableError(self.reason)


class RemoteAgentExecutionAdapter(ExecutionAdapter):
    """Calls a deployed Agent Studio-compatible endpoint.

    The remote Agent owns signing and ERC-8183/x402 concerns. SafeHire sends only
    the already-approved task and scoped policy metadata; it never accepts a
    private key.
    """

    def __init__(
        self,
        *,
        endpoint_resolver: Callable[[str], str],
        auth_token: str = "",
        timeout_seconds: float = 30,
    ) -> None:
        self._endpoint_resolver = endpoint_resolver
        self._auth_token = auth_token
        self._timeout = timeout_seconds

    async def execute(self, intent: ExecutionIntent) -> ExecutionReceipt:
        endpoint = self._endpoint_resolver(intent.agent_id)
        if not endpoint.startswith("https://"):
            raise AdapterUnavailableError("remote onchain agent endpoint must use HTTPS")
        headers = {"Content-Type": "application/json"}
        if self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"
        payload = {
            "task_id": intent.task_id,
            "request": dict(intent.metadata.get("request", {})),
            "execution": {
                "chain_id": intent.chain_id,
                "target": intent.target,
                "method": intent.method,
                "value_usd": intent.value_usd,
                "slippage_bps": intent.slippage_bps,
                "deadline": intent.deadline.isoformat(),
                "policy_id": intent.metadata.get("policy_id"),
            },
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(endpoint, json=payload, headers=headers)
                response.raise_for_status()
                result = response.json()
        except Exception as exc:
            raise AdapterUnavailableError(
                f"remote agent execution failed: {type(exc).__name__}"
            ) from exc
        if not isinstance(result, dict):
            raise AdapterUnavailableError("remote agent returned a non-object response")
        tx_hash = result.get("txHash") or result.get("tx_hash")
        success = bool(result.get("success")) and isinstance(tx_hash, str)
        source = DataSource.TESTNET_EVIDENCE if intent.chain_id == 97 else DataSource.LIVE_ONCHAIN
        return ExecutionReceipt(
            task_id=intent.task_id,
            success=success,
            mode=intent.mode,
            tx_hash=str(tx_hash) if tx_hash else None,
            chain_id=intent.chain_id,
            gas_used=int(result["gas_used"]) if result.get("gas_used") else None,
            cost_usd=float(result["cost_usd"]) if result.get("cost_usd") else None,
            source=source,
            result=result,
            error_code=None if success else "missing_verified_transaction",
            error_message=(
                None
                if success
                else "Remote agent did not return success=true with a transaction hash"
            ),
        )
