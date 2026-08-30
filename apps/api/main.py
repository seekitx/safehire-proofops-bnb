from __future__ import annotations

import secrets
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from proofops.domain.errors import (
    AdapterUnavailableError,
    DuplicateRequestError,
    RiskRejectedError,
    TaskTransitionError,
)
from proofops.domain.models import DataSource, ExecutionMode, LpPosition
from proofops.plugins.adversarial import Proposal
from proofops.services.bootstrap import Application, build_application
from proofops.services.browser_deployment import (
    base_deployment_plan,
    scoped_policy_creation_data,
)
from proofops.settings import Settings

EVM_ADDRESS_PATTERN = r"^0x[a-fA-F0-9]{40}$"


class CompareRequest(BaseModel):
    agent_ids: list[str] = Field(min_length=2, max_length=3)


class AgentInvokeRequest(BaseModel):
    input: dict[str, Any]


class LpSimulationRequest(BaseModel):
    current_price: float = Field(gt=0)
    lower_price: float = Field(gt=0)
    upper_price: float = Field(gt=0)
    realized_volatility_30d: float = Field(ge=0)
    fee_apr: float = Field(ge=0)
    liquidity_usd: float = Field(ge=0)
    estimated_rebalance_cost_usd: float = Field(ge=0)
    uncollected_fees_usd: float = Field(default=0, ge=0)
    notional_usd: float = Field(gt=0)


class WalletChallengeRequest(BaseModel):
    owner: str = Field(pattern=EVM_ADDRESS_PATTERN)


class WalletVerifyRequest(BaseModel):
    owner: str = Field(pattern=EVM_ADDRESS_PATTERN)
    message: str = Field(min_length=20, max_length=2000)
    signature: str = Field(pattern=r"^0x[a-fA-F0-9]+$")


class CreatePolicyRequest(BaseModel):
    owner: str = Field(pattern=EVM_ADDRESS_PATTERN)
    agent_id: str
    chain_id: Literal[56, 97] = 97
    allowed_targets: list[str] = Field(min_length=1, max_length=10)
    allowed_methods: list[str] = Field(min_length=1, max_length=10)
    max_value_usd: float = Field(gt=0, le=100_000)
    daily_value_usd: float = Field(gt=0, le=500_000)
    max_slippage_bps: int = Field(ge=0, le=500)
    ttl_minutes: int = Field(gt=0, le=1440)
    require_human_approval: bool = True


class HireAgentRequest(BaseModel):
    owner: str = Field(pattern=EVM_ADDRESS_PATTERN)
    chain_id: Literal[56, 97] = 97
    allowed_targets: list[str] = Field(min_length=1, max_length=10)
    allowed_methods: list[str] = Field(min_length=1, max_length=10)
    max_value_usd: float = Field(gt=0, le=100_000)
    daily_value_usd: float = Field(gt=0, le=500_000)
    max_slippage_bps: int = Field(ge=0, le=500)
    ttl_minutes: int = Field(default=60, gt=0, le=1440)
    request: dict[str, Any]
    idempotency_key: str = Field(min_length=8, max_length=128)


class CreateTaskRequest(BaseModel):
    agent_id: str
    policy_id: str
    request: dict[str, Any]
    idempotency_key: str = Field(min_length=8, max_length=128)


class SimulationResultRequest(BaseModel):
    result: dict[str, Any]


class ExecuteTaskRequest(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=128)
    chain_id: Literal[56, 97]
    target: str
    method: str
    value_usd: float = Field(ge=0)
    slippage_bps: int = Field(ge=0, le=1000)
    mode: ExecutionMode = ExecutionMode.DEMO
    source: DataSource = DataSource.DEMO_FIXTURE
    metadata: dict[str, Any] = Field(default_factory=dict)


class VerifyTransactionRequest(BaseModel):
    chain_id: Literal[56, 97]
    tx_hash: str = Field(pattern=r"^0x[a-fA-F0-9]{64}$")


class ScopedPolicyPlanRequest(BaseModel):
    owner: str = Field(pattern=EVM_ADDRESS_PATTERN)
    registry_address: str = Field(pattern=EVM_ADDRESS_PATTERN)
    expires_at: int = Field(gt=0)


class DebateRequest(BaseModel):
    title: str = "SafeHire / ProofOps"
    problem: str = "Users cannot verify which DeFi agent deserves scoped access to money."
    user_path: list[str] = Field(
        default_factory=lambda: [
            "compare",
            "evidence",
            "simulate",
            "set_limits",
            "hire",
            "receipt",
            "revoke",
        ]
    )
    sponsor_integrations: list[str] = Field(
        default_factory=lambda: [
            "BNB Agent Studio / ERC-8183",
            "PancakeSwap",
            "TermiX benchmarks",
        ]
    )
    architecture: str = "modular_monolith_plus_isolated_execution_gateway"
    safety_controls: list[str] = Field(
        default_factory=lambda: [
            "deterministic risk gate",
            "allowlist",
            "spend cap",
            "expiry",
            "idempotency",
            "human approval",
            "kill switch",
        ]
    )
    evidence_plan: list[str] = Field(
        default_factory=lambda: [
            "tx hash",
            "contract address",
            "raw benchmark outputs",
            "hash-chain ledger",
            "source labels",
            "failure-path screenshots",
        ]
    )
    estimated_days: float = 9.0
    uses_generic_chat: bool = False
    deterministic_scoring: bool = True
    live_bsc_plan: bool = True
    fixture_labeling: bool = True


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    application = await build_application(Settings())
    app.state.application = application
    try:
        yield
    finally:
        await application.close()


app = FastAPI(
    title="SafeHire / ProofOps API",
    version="0.2.0",
    description="Verifiable, permissioned DeFi agent marketplace for BNB Chain",
    lifespan=lifespan,
)
settings = Settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Admin-Key",
        "X-Request-ID",
    ],
)


@app.middleware("http")
async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
    started = time.perf_counter()
    request_id = request.headers.get("x-request-id") or f"req_{uuid.uuid4().hex[:20]}"
    try:
        content_length = int(request.headers.get("content-length", "0") or 0)
    except ValueError:
        content_length = 1_000_001
    if content_length > 1_000_000:
        return JSONResponse(
            status_code=413,
            content={"error": "payload_too_large", "request_id": request_id},
        )
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-Ms"] = f"{(time.perf_counter() - started) * 1000:.2f}"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


def get_application(request: Request) -> Application:
    application: Application = request.app.state.application
    return application


ApplicationDep = Annotated[Application, Depends(get_application)]
AuthorizationHeader = Annotated[str | None, Header(alias="Authorization")]
AdminKeyHeader = Annotated[str | None, Header(alias="X-Admin-Key")]


def _session_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="wallet_session_required")
    return authorization.removeprefix("Bearer ").strip()


def _require_wallet(
    application: Application, authorization: str | None, *, owner: str | None = None
) -> str:
    try:
        return application.wallet_auth.require_session(_session_token(authorization), owner=owner)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def _require_admin(application: Application, x_admin_key: str | None) -> None:
    expected = application.settings.admin_api_key
    if expected in {"", "change-me-before-deploy"}:
        if application.settings.app_env == "production":
            raise HTTPException(status_code=503, detail="admin_key_not_configured")
        return
    if not x_admin_key or not secrets.compare_digest(x_admin_key, expected):
        raise HTTPException(status_code=401, detail="invalid_admin_key")


@app.exception_handler(KeyError)
async def not_found_handler(_request: Request, exc: KeyError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"error": "not_found", "message": str(exc)})


@app.exception_handler(ValueError)
async def value_error_handler(_request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error": "validation_error", "message": str(exc)},
    )


@app.exception_handler(AdapterUnavailableError)
async def adapter_unavailable_handler(
    _request: Request, exc: AdapterUnavailableError
) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"error": "upstream_unavailable", "message": str(exc)},
    )


@app.exception_handler(DuplicateRequestError)
async def duplicate_handler(_request: Request, exc: DuplicateRequestError) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={"error": "duplicate_request", "message": str(exc)},
    )


@app.exception_handler(RiskRejectedError)
async def risk_conflict_handler(_request: Request, exc: RiskRejectedError) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={"error": type(exc).__name__, "message": str(exc)},
    )


@app.exception_handler(TaskTransitionError)
async def transition_conflict_handler(_request: Request, exc: TaskTransitionError) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={"error": type(exc).__name__, "message": str(exc)},
    )


@app.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
async def ready(application: ApplicationDep) -> dict[str, Any]:
    ledger = application.harness.resolve("evidence.ledger").verify()
    return {
        "status": "ready" if ledger["valid"] else "degraded",
        "ledger": ledger,
    }


@app.get("/api/runtime")
async def runtime(application: ApplicationDep) -> dict[str, Any]:
    return {
        "app_env": application.settings.app_env,
        "execution_mode": application.settings.execution_mode,
        "execution_adapter": application.settings.execution_adapter,
        "public_base_url": application.settings.public_base_url,
        "github_repo_url": application.settings.github_repo_url,
        "wallet_auth_required": True,
        "mainnet_enabled": application.settings.allow_bsc_mainnet,
    }


@app.get("/api/network")
async def network_status(application: ApplicationDep, chain_id: int = 97) -> dict[str, Any]:
    return await application.network.status(chain_id)


def _require_development(application: Application) -> None:
    if application.settings.app_env == "production":
        raise HTTPException(status_code=404, detail="not_found")


@app.get("/api/dev/contracts/deployment-plan")
async def contract_deployment_plan(application: ApplicationDep) -> dict[str, Any]:
    _require_development(application)
    return base_deployment_plan(Path.cwd())


@app.post("/api/dev/contracts/scoped-policy-plan")
async def scoped_policy_plan(
    body: ScopedPolicyPlanRequest, application: ApplicationDep
) -> dict[str, Any]:
    _require_development(application)
    return scoped_policy_creation_data(
        Path.cwd(),
        owner=body.owner,
        registry_address=body.registry_address,
        expires_at=body.expires_at,
    )


@app.get("/api/sources/readiness")
async def official_source_readiness(application: ApplicationDep) -> dict[str, Any]:
    return await application.official_sources.readiness()


@app.get("/api/sources/8004scan/agents")
async def official_agents(
    application: ApplicationDep,
    chain_id: int = 97,
    limit: int = 20,
) -> dict[str, Any]:
    return await application.official_sources.scan8004_agents(chain_id=chain_id, limit=limit)


@app.get("/api/sources/venus/pools")
async def venus_pools(application: ApplicationDep, chain_id: int = 56) -> dict[str, Any]:
    return await application.official_sources.venus_pools(chain_id=chain_id)


@app.get("/api/sources/lista/vaults")
async def lista_vaults(application: ApplicationDep, limit: int = 20) -> dict[str, Any]:
    return await application.official_sources.lista_vaults(limit=limit)


@app.get("/api/sources/pancakeswap/positions/{position_id}")
async def pancake_position(position_id: str, application: ApplicationDep) -> dict[str, Any]:
    return await application.official_sources.pancake_position(position_id)


@app.post("/api/network/verify-transaction")
async def verify_transaction(
    body: VerifyTransactionRequest, application: ApplicationDep
) -> dict[str, Any]:
    return await application.network.verify_transaction(body.chain_id, body.tx_hash)


@app.post("/api/auth/challenge")
async def wallet_challenge(
    body: WalletChallengeRequest, application: ApplicationDep
) -> dict[str, str]:
    return application.wallet_auth.challenge(body.owner)


@app.post("/api/auth/verify")
async def wallet_verify(body: WalletVerifyRequest, application: ApplicationDep) -> dict[str, str]:
    return application.wallet_auth.verify(
        owner=body.owner, message=body.message, signature=body.signature
    )


@app.get("/api/plugins")
async def plugins(application: ApplicationDep) -> dict[str, Any]:
    return {"plugins": application.harness.list_plugins()}


@app.get("/api/agents")
async def list_agents(application: ApplicationDep, category: str | None = None) -> dict[str, Any]:
    return {"agents": application.marketplace.list_agents(category)}


@app.get("/api/agents/{agent_id}")
async def get_agent(agent_id: str, application: ApplicationDep) -> dict[str, Any]:
    return application.marketplace.get_agent(agent_id)


@app.get("/agents/{agent_id}")
async def get_agent_card(agent_id: str, application: ApplicationDep) -> dict[str, Any]:
    return application.agents.card(agent_id)


@app.post("/agents/{agent_id}")
@app.post("/api/agents/{agent_id}/invoke")
async def invoke_agent(
    agent_id: str, body: AgentInvokeRequest, application: ApplicationDep
) -> dict[str, Any]:
    return application.agents.invoke(agent_id, body.input)


@app.post("/api/compare")
async def compare(body: CompareRequest, application: ApplicationDep) -> dict[str, Any]:
    return application.marketplace.compare(body.agent_ids)


@app.post("/api/simulations/lp-guardian")
async def simulate_lp(body: LpSimulationRequest, application: ApplicationDep) -> dict[str, Any]:
    policy = application.harness.resolve("pancake.lp_guardian")
    position = LpPosition(
        current_price=body.current_price,
        lower_price=body.lower_price,
        upper_price=body.upper_price,
        realized_volatility_30d=body.realized_volatility_30d,
        fee_apr=body.fee_apr,
        liquidity_usd=body.liquidity_usd,
        estimated_rebalance_cost_usd=body.estimated_rebalance_cost_usd,
        uncollected_fees_usd=body.uncollected_fees_usd,
    )
    result = policy.simulate(position, body.notional_usd)
    application.harness.resolve("evidence.ledger").append(
        kind="lp_simulation", source="api", payload=result.to_dict()
    )
    return {
        "source": "caller_supplied",
        "simulation": result.to_dict(),
    }


@app.post("/api/permissions")
async def create_policy(
    body: CreatePolicyRequest,
    application: ApplicationDep,
    authorization: AuthorizationHeader = None,
) -> dict[str, Any]:
    _require_wallet(application, authorization, owner=body.owner)
    application.marketplace.get_agent(body.agent_id)
    policy = application.tasks.create_policy(
        owner=body.owner,
        agent_id=body.agent_id,
        chain_id=body.chain_id,
        allowed_targets=tuple(body.allowed_targets),
        allowed_methods=tuple(body.allowed_methods),
        max_value_usd=body.max_value_usd,
        daily_value_usd=body.daily_value_usd,
        max_slippage_bps=body.max_slippage_bps,
        ttl_minutes=body.ttl_minutes,
        require_human_approval=body.require_human_approval,
    )
    return policy.to_dict()


@app.get("/api/permissions")
async def list_policies(
    application: ApplicationDep,
    authorization: AuthorizationHeader = None,
) -> dict[str, Any]:
    owner = _require_wallet(application, authorization)
    return {
        "policies": [policy.to_dict() for policy in application.tasks.list_policies(owner=owner)]
    }


@app.post("/api/permissions/{policy_id}/revoke")
async def revoke_policy(
    policy_id: str,
    application: ApplicationDep,
    authorization: AuthorizationHeader = None,
) -> dict[str, Any]:
    current = application.tasks.get_policy(policy_id)
    _require_wallet(application, authorization, owner=current.owner)
    return application.tasks.revoke_policy(policy_id).to_dict()


@app.post("/api/agents/{agent_id}/hire")
async def hire_agent(
    agent_id: str,
    body: HireAgentRequest,
    application: ApplicationDep,
    authorization: AuthorizationHeader = None,
) -> dict[str, Any]:
    _require_wallet(application, authorization, owner=body.owner)
    application.marketplace.get_agent(agent_id)
    policy = application.tasks.create_policy(
        owner=body.owner,
        agent_id=agent_id,
        chain_id=body.chain_id,
        allowed_targets=tuple(body.allowed_targets),
        allowed_methods=tuple(body.allowed_methods),
        max_value_usd=body.max_value_usd,
        daily_value_usd=body.daily_value_usd,
        max_slippage_bps=body.max_slippage_bps,
        ttl_minutes=body.ttl_minutes,
        require_human_approval=True,
    )
    task = application.tasks.create_task(
        agent_id=agent_id,
        policy_id=policy.policy_id,
        request=body.request,
        idempotency_key=body.idempotency_key,
    )
    agent_result = application.agents.invoke(agent_id, body.request)
    task = application.tasks.simulate(task.task_id, agent_result)
    return {
        "policy": policy.to_dict(),
        "task": task.to_dict(),
        "agent_result": agent_result,
        "next_action": "approve",
    }


@app.post("/api/tasks")
async def create_task(
    body: CreateTaskRequest,
    application: ApplicationDep,
    authorization: AuthorizationHeader = None,
) -> dict[str, Any]:
    policy = application.tasks.get_policy(body.policy_id)
    _require_wallet(application, authorization, owner=policy.owner)
    return application.tasks.create_task(
        agent_id=body.agent_id,
        policy_id=body.policy_id,
        request=body.request,
        idempotency_key=body.idempotency_key,
    ).to_dict()


@app.get("/api/tasks")
async def list_tasks(
    application: ApplicationDep,
    authorization: AuthorizationHeader = None,
    policy_id: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    owner = _require_wallet(application, authorization)
    allowed_policy_ids = {
        policy.policy_id for policy in application.tasks.list_policies(owner=owner)
    }
    if policy_id and policy_id not in allowed_policy_ids:
        raise HTTPException(status_code=403, detail="policy_not_owned")
    tasks = application.tasks.list_tasks(policy_id=policy_id, limit=limit)
    return {"tasks": [task.to_dict() for task in tasks if task.policy_id in allowed_policy_ids]}


@app.get("/api/tasks/{task_id}")
async def get_task(
    task_id: str,
    application: ApplicationDep,
    authorization: AuthorizationHeader = None,
) -> dict[str, Any]:
    task = application.tasks.get_task(task_id)
    policy = application.tasks.get_policy(task.policy_id)
    _require_wallet(application, authorization, owner=policy.owner)
    return task.to_dict()


@app.post("/api/tasks/{task_id}/simulate")
async def simulate_task(
    task_id: str,
    body: SimulationResultRequest,
    application: ApplicationDep,
    authorization: AuthorizationHeader = None,
) -> dict[str, Any]:
    task = application.tasks.get_task(task_id)
    policy = application.tasks.get_policy(task.policy_id)
    _require_wallet(application, authorization, owner=policy.owner)
    return application.tasks.simulate(task_id, body.result).to_dict()


@app.post("/api/tasks/{task_id}/approve")
async def approve_task(
    task_id: str,
    application: ApplicationDep,
    authorization: AuthorizationHeader = None,
) -> dict[str, Any]:
    task = application.tasks.get_task(task_id)
    policy = application.tasks.get_policy(task.policy_id)
    _require_wallet(application, authorization, owner=policy.owner)
    return application.tasks.approve(task_id).to_dict()


@app.post("/api/tasks/{task_id}/execute")
async def execute_task(
    task_id: str,
    body: ExecuteTaskRequest,
    application: ApplicationDep,
    authorization: AuthorizationHeader = None,
) -> dict[str, Any]:
    task = application.tasks.get_task(task_id)
    policy = application.tasks.get_policy(task.policy_id)
    _require_wallet(application, authorization, owner=policy.owner)
    metadata = {**body.metadata, "request": dict(task.request)}
    return (
        await application.tasks.execute(
            task_id,
            idempotency_key=body.idempotency_key,
            chain_id=body.chain_id,
            target=body.target,
            method=body.method,
            value_usd=body.value_usd,
            slippage_bps=body.slippage_bps,
            mode=body.mode,
            source=body.source,
            metadata=metadata,
        )
    ).to_dict()


@app.post("/api/tasks/{task_id}/revoke")
async def revoke_task(
    task_id: str,
    application: ApplicationDep,
    authorization: AuthorizationHeader = None,
) -> dict[str, Any]:
    task = application.tasks.get_task(task_id)
    policy = application.tasks.get_policy(task.policy_id)
    _require_wallet(application, authorization, owner=policy.owner)
    return application.tasks.revoke_task(task_id).to_dict()


@app.post("/api/benchmarks/run")
async def run_benchmarks(
    application: ApplicationDep,
    x_admin_key: AdminKeyHeader = None,
) -> dict[str, Any]:
    _require_admin(application, x_admin_key)
    runner = application.harness.resolve("benchmark.runner")
    return {"results": [item.to_dict() for item in runner.run_all()]}


@app.post("/api/debate/run")
async def run_debate(
    body: DebateRequest,
    application: ApplicationDep,
    x_admin_key: AdminKeyHeader = None,
) -> dict[str, Any]:
    _require_admin(application, x_admin_key)
    council = application.harness.resolve("design.council")
    proposal = Proposal(
        title=body.title,
        problem=body.problem,
        user_path=tuple(body.user_path),
        sponsor_integrations=tuple(body.sponsor_integrations),
        architecture=body.architecture,
        safety_controls=tuple(body.safety_controls),
        evidence_plan=tuple(body.evidence_plan),
        estimated_days=body.estimated_days,
        uses_generic_chat=body.uses_generic_chat,
        deterministic_scoring=body.deterministic_scoring,
        live_bsc_plan=body.live_bsc_plan,
        fixture_labeling=body.fixture_labeling,
    )
    result: dict[str, Any] = council.review(proposal).to_dict()
    return result


@app.get("/api/evidence/verify")
async def verify_evidence(application: ApplicationDep) -> dict[str, Any]:
    result: dict[str, Any] = application.harness.resolve("evidence.ledger").verify()
    return result


@app.get("/api/submission/validate")
async def validate_submission(application: ApplicationDep) -> dict[str, Any]:
    return application.submission.run()


WEB_ROOT = Path(__file__).resolve().parents[1] / "web"
app.mount("/assets", StaticFiles(directory=WEB_ROOT / "assets"), name="assets")


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(WEB_ROOT / "index.html")


@app.get("/dev/deploy-testnet", include_in_schema=False)
async def deploy_testnet_page(application: ApplicationDep) -> FileResponse:
    _require_development(application)
    return FileResponse(WEB_ROOT / "deploy-testnet.html")
