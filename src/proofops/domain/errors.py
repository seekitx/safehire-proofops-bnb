class ProofOpsError(Exception):
    """Base exception for semantic, transport-neutral application errors."""


class ValidationError(ProofOpsError):
    pass


class PluginError(ProofOpsError):
    pass


class PluginDependencyError(PluginError):
    pass


class PluginLifecycleError(PluginError):
    pass


class EvidenceIntegrityError(ProofOpsError):
    pass


class RiskRejectedError(ProofOpsError):
    pass


class TaskTransitionError(ProofOpsError):
    pass


class DuplicateRequestError(ProofOpsError):
    pass


class AdapterUnavailableError(ProofOpsError):
    pass
