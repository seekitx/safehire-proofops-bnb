from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from proofops.agents.engines import ENGINE_BY_CATEGORY
from proofops.agents.service import EXAMPLE_INPUTS
from proofops.decision.market import CATEGORIES, SnapshotCache, compare_market, project_market
from proofops.domain.models import AgentCategory
from proofops.services.live_agent_market import live_agent_market


class DecisionCompareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent_ids: list[str] = Field(min_length=2, max_length=3)


class PreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: AgentCategory
    input: dict[str, Any]


def make_router(root: Path, cache: SnapshotCache | None = None) -> APIRouter:
    router = APIRouter(prefix="/api/decision", tags=["Evidence-first decision desk"])
    source = cache or SnapshotCache(lambda: live_agent_market(root))

    @router.get("/market")
    async def market(category: AgentCategory | None = None, q: str = "") -> dict[str, Any]:
        if len(q) > 100:
            raise HTTPException(422, "Search query is limited to 100 characters")
        projected = project_market(await source.get())
        if category:
            projected["listings"] = [row for row in projected["listings"] if row["category"] == category.value]
        if q.strip():
            term = q.strip().casefold()
            projected["listings"] = [row for row in projected["listings"] if
                term in f"{row['name']} {row['description']} {row['operator_label']}".casefold()]
        return projected

    @router.post("/compare")
    async def compare(request: DecisionCompareRequest) -> dict[str, Any]:
        try:
            return compare_market(project_market(await source.get()), request.agent_ids)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.get("/examples")
    async def examples() -> dict[str, Any]:
        return {"evidence_mode": "synthetic_examples", "network_activity": False,
                "examples": {category.value: value for category, value in EXAMPLE_INPUTS.items()},
                "category_requirements": CATEGORIES}

    @router.post("/preview")
    async def preview(request: PreviewRequest) -> dict[str, Any]:
        # No external calls, approvals, signatures, or execution. Inputs are not evidence.
        try:
            if len(json.dumps(request.input, allow_nan=False)) > 16000:
                raise ValueError("Preview input is limited to 16,000 characters")
            result = ENGINE_BY_CATEGORY[request.category]().invoke(request.input).to_dict()
        except (ValueError, TypeError, OverflowError) as exc:
            raise HTTPException(422, str(exc)) from exc
        return {"evidence_mode": "caller_supplied_simulation", "network_activity": False,
                "trade_executed": False, "result": result}

    return router
