from __future__ import annotations

from proofops.domain.errors import TaskTransitionError
from proofops.domain.models import TaskState

ALLOWED_TRANSITIONS: dict[TaskState, frozenset[TaskState]] = {
    TaskState.DRAFT: frozenset({TaskState.SIMULATED, TaskState.REVOKED}),
    TaskState.SIMULATED: frozenset({TaskState.APPROVAL_REQUIRED, TaskState.REVOKED}),
    TaskState.APPROVAL_REQUIRED: frozenset({TaskState.APPROVED, TaskState.REVOKED}),
    TaskState.APPROVED: frozenset({TaskState.EXECUTING, TaskState.REVOKED}),
    TaskState.EXECUTING: frozenset({TaskState.SUCCEEDED, TaskState.FAILED}),
    TaskState.SUCCEEDED: frozenset({TaskState.REVOKED}),
    TaskState.FAILED: frozenset({TaskState.APPROVED, TaskState.REVOKED}),
    TaskState.REVOKED: frozenset(),
}


def require_transition(current: TaskState, target: TaskState) -> None:
    if target not in ALLOWED_TRANSITIONS[current]:
        raise TaskTransitionError(f"invalid task transition: {current.value} -> {target.value}")
