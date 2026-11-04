"""Human-in-the-Loop (HITL) Module for CollaborAI.

Provides configurable checkpoint gates, human review queues, and approval
workflows that allow human operators to inspect, approve, reject, or modify
agent outputs at critical stages of the multi-agent deliberation pipeline.
"""

from .checkpoint import HITLCheckpointManager, HITLCheckpoint, CheckpointDecision

__all__ = [
    "HITLCheckpointManager",
    "HITLCheckpoint",
    "CheckpointDecision",
]
