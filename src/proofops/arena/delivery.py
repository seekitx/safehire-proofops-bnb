"""Read-only bridge from the signed hire path to frozen task acceptance.

No caller-uploaded verification flags, settlement instruction or payment claim.
Legacy deliveries without an anchored arena task hash fail closed.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from proofops.arena.models import TaskSpec, utcnow
from proofops.arena.planners import evaluate
from proofops.arena.providers import ProviderCatalog
from proofops.arena.store import parse_proposal
from proofops.decision.paid import BscReader
from proofops.services.live_erc8183 import live_delivery


async def accept_delivery(
    task: TaskSpec, job_id: int, agent_ref: str, catalog: ProviderCatalog,
    *, loader: Callable[..., Awaitable[dict[str, Any]]] = live_delivery,
    reader: BscReader | None = None,
) -> dict[str, Any]:
    provider = catalog.select(agent_ref, task.category)
    if type(job_id) is not int or not 0 < job_id < 2**256:
        raise ValueError("Invalid job ID")
    if not task.fresh():
        raise ValueError("Task snapshot expired; cannot issue a current acceptance")
    delivery = await loader(job_id=job_id)
    verification = delivery.get('verification', {})
    if (delivery.get('chain_id') != 56 or delivery.get('job_id') != job_id
            or not all(verification.get(key) is True for key in
                       ('valid', 'hash_matches', 'job_matches', 'chain_matches', 'contracts_match'))):
        raise ValueError("Delivery chain commitment was not verified")
    signed_task = delivery.get('task_spec', {})
    if (signed_task.get('erc8004_token_id') != provider.token_id
            or signed_task.get('service') != provider.skill_id
            or TaskSpec.model_validate(signed_task.get('arena_task')).task_hash != task.task_hash):
        raise ValueError("Signed hire does not bind this frozen Arena task and provider skill")
    # Content comes exclusively from the manifest retrieved and hash-checked by
    # live_delivery, never from the HTTP caller's proposal or a claimed hash.
    raw = verification.get('content')
    if not isinstance(raw, str):
        raise TypeError("Delivery contains no structured proposal")
    proposal = parse_proposal(raw)
    if (proposal.agent_ref != agent_ref or proposal.task_hash != task.task_hash
            or proposal.snapshot_hash != task.snapshot_hash):
        raise ValueError("Delivered proposal belongs to a different task, snapshot or provider")
    chain = reader or BscReader()
    if int(await chain.rpc('eth_chainId', []), 16) != 56:
        raise ValueError("Snapshot RPC chain mismatch")
    block = await chain.rpc('eth_getBlockByNumber', [hex(task.snapshot.block_number), False])
    if not isinstance(block, dict) or str(block.get('hash', '')).lower() != task.snapshot.block_hash.lower():
        raise ValueError("Snapshot block is missing or no longer canonical")
    block_age = utcnow().timestamp() - int(block['timestamp'], 16)
    if not -5 <= block_age <= task.limits.max_snapshot_age_seconds:
        raise ValueError("Onchain snapshot block is stale")
    identity = await chain.identity(provider.token_id, task.snapshot.block_hash)
    if identity.get('wallet', '').lower() != str(delivery.get('provider', '')).lower():
        raise ValueError("Registry wallet does not match the delivery provider")
    if (await chain.canonical_block_hash(task.snapshot.block_number)).lower() != task.snapshot.block_hash.lower():
        raise ValueError("Snapshot block changed during verification")
    report = evaluate(task, proposal)
    return {
        'schema_version': 'safehire-live-acceptance/1', 'verified_at': utcnow().isoformat(),
        'task_hash': task.task_hash, 'job_id': job_id, 'agent_ref': agent_ref,
        'raw_proposal': raw, 'delivery': delivery, 'acceptance': report,
        'delivery_commitment_verified': True, 'registry_wallet_at_snapshot_verified': True,
        'snapshot_block_verified': True, 'financial_inputs_authenticated': False,
        'payment_verified': False, 'settlement_authorized': False,
        'boundary': 'Trusted RPC and committed delivery observation. Financial inputs remain caller supplied; '
                    'constraint acceptance is not useful-work certification or permission to settle.',
    }
