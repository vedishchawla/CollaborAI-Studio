"""HITL Checkpoint Manager — Configurable approval gates in the deliberation pipeline.

Enables human operators to:
1. Review specialist findings before conflict detection
2. Approve/reject/modify negotiation outcomes
3. Provide mid-deliberation guidance
4. Gate the final synthesis with human sign-off
"""

from __future__ import annotations
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger("collaborai.hitl.checkpoint")


class CheckpointDecision(BaseModel):
    """Human decision at a HITL checkpoint."""
    checkpoint_id: str = Field(description="ID of the checkpoint being resolved")
    decision: Literal["approve", "reject", "modify", "skip"] = Field(
        description="Human's decision on this checkpoint"
    )
    feedback: Optional[str] = Field(default=None, description="Optional human feedback or guidance")
    modifications: Optional[Dict[str, Any]] = Field(
        default=None, description="Specific modifications if decision is 'modify'"
    )
    decided_by: str = Field(default="human_operator", description="Identity of the decision-maker")
    decided_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class HITLCheckpoint(BaseModel):
    """A checkpoint in the deliberation pipeline requiring human review."""
    checkpoint_id: str = Field(description="Unique checkpoint ID e.g. 'HITL-CHK-001'")
    run_id: str = Field(description="Associated deliberation run ID")
    checkpoint_type: Literal[
        "findings_review",
        "pre_negotiation_approval",
        "post_negotiation_review",
        "pre_synthesis_approval",
        "custom_gate"
    ] = Field(description="Type of checkpoint")
    title: str = Field(description="Human-readable title")
    description: str = Field(default="", description="What the human needs to review")
    stage: str = Field(default="", description="Pipeline stage e.g. 'after_specialist_execution'")
    payload: Dict[str, Any] = Field(
        default_factory=dict, description="Context data for human review (findings, proposals, etc.)"
    )
    status: Literal["pending", "approved", "rejected", "modified", "skipped", "auto_approved"] = Field(
        default="pending"
    )
    decision: Optional[CheckpointDecision] = Field(default=None, description="Human decision once resolved")
    is_blocking: bool = Field(default=True, description="Whether pipeline pauses until resolved")
    auto_approve_timeout_seconds: Optional[int] = Field(
        default=None,
        description="If set, auto-approve after this many seconds if no human response"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None


class HITLCheckpointConfig(BaseModel):
    """Configuration for which checkpoints are enabled in a run."""
    enable_findings_review: bool = Field(
        default=False,
        description="Pause after specialist execution for human to review findings"
    )
    enable_pre_negotiation_approval: bool = Field(
        default=False,
        description="Require human approval before starting negotiation"
    )
    enable_post_negotiation_review: bool = Field(
        default=False,
        description="Review negotiation outcomes before proceeding"
    )
    enable_pre_synthesis_approval: bool = Field(
        default=True,
        description="Gate final synthesis with human approval"
    )
    auto_approve_timeout: Optional[int] = Field(
        default=None,
        description="Auto-approve checkpoints after N seconds if no response"
    )


class HITLCheckpointManager:
    """Manages HITL checkpoints throughout the deliberation lifecycle."""

    def __init__(self, config: Optional[HITLCheckpointConfig] = None):
        self.config = config or HITLCheckpointConfig()
        self._checkpoints: Dict[str, HITLCheckpoint] = {}
        self._pending_queue: List[str] = []

    @property
    def checkpoints(self) -> Dict[str, HITLCheckpoint]:
        return self._checkpoints

    def create_checkpoint(
        self,
        run_id: str,
        checkpoint_type: str,
        title: str,
        description: str = "",
        stage: str = "",
        payload: Optional[Dict[str, Any]] = None,
        is_blocking: bool = True,
    ) -> HITLCheckpoint:
        """Create a new checkpoint and add it to the pending queue."""
        checkpoint_id = f"HITL-{uuid.uuid4().hex[:8].upper()}"
        checkpoint = HITLCheckpoint(
            checkpoint_id=checkpoint_id,
            run_id=run_id,
            checkpoint_type=checkpoint_type,
            title=title,
            description=description,
            stage=stage,
            payload=payload or {},
            is_blocking=is_blocking,
            auto_approve_timeout_seconds=self.config.auto_approve_timeout,
        )
        self._checkpoints[checkpoint_id] = checkpoint
        if is_blocking:
            self._pending_queue.append(checkpoint_id)
        logger.info("HITL checkpoint created: %s (%s) for run %s", checkpoint_id, checkpoint_type, run_id)
        return checkpoint

    def resolve_checkpoint(
        self,
        checkpoint_id: str,
        decision: CheckpointDecision
    ) -> HITLCheckpoint:
        """Resolve a pending checkpoint with a human decision."""
        checkpoint = self._checkpoints.get(checkpoint_id)
        if not checkpoint:
            raise ValueError(f"Checkpoint {checkpoint_id} not found")
        if checkpoint.status != "pending":
            raise ValueError(f"Checkpoint {checkpoint_id} already resolved (status={checkpoint.status})")

        checkpoint.decision = decision
        checkpoint.status = decision.decision  # "approve", "reject", "modify", "skip"
        checkpoint.resolved_at = datetime.now(timezone.utc)

        if checkpoint_id in self._pending_queue:
            self._pending_queue.remove(checkpoint_id)

        logger.info(
            "HITL checkpoint resolved: %s → %s (feedback: %s)",
            checkpoint_id, decision.decision, decision.feedback or "none"
        )
        return checkpoint

    def has_pending_checkpoints(self, run_id: Optional[str] = None) -> bool:
        """Check if there are unresolved blocking checkpoints."""
        for chk_id in self._pending_queue:
            chk = self._checkpoints.get(chk_id)
            if chk and chk.status == "pending" and chk.is_blocking:
                if run_id is None or chk.run_id == run_id:
                    return True
        return False

    def get_pending_checkpoints(self, run_id: Optional[str] = None) -> List[HITLCheckpoint]:
        """Get all pending checkpoints, optionally filtered by run."""
        pending = []
        for chk_id in self._pending_queue:
            chk = self._checkpoints.get(chk_id)
            if chk and chk.status == "pending":
                if run_id is None or chk.run_id == run_id:
                    pending.append(chk)
        return pending

    def get_checkpoint(self, checkpoint_id: str) -> Optional[HITLCheckpoint]:
        return self._checkpoints.get(checkpoint_id)

    def get_all_checkpoints(self, run_id: Optional[str] = None) -> List[HITLCheckpoint]:
        """Return all checkpoints for a run."""
        chks = list(self._checkpoints.values())
        if run_id:
            chks = [c for c in chks if c.run_id == run_id]
        return sorted(chks, key=lambda c: c.created_at)

    def should_checkpoint(self, checkpoint_type: str) -> bool:
        """Check if a given checkpoint type is enabled in the current config."""
        mapping = {
            "findings_review": self.config.enable_findings_review,
            "pre_negotiation_approval": self.config.enable_pre_negotiation_approval,
            "post_negotiation_review": self.config.enable_post_negotiation_review,
            "pre_synthesis_approval": self.config.enable_pre_synthesis_approval,
        }
        return mapping.get(checkpoint_type, False)

    def get_summary(self, run_id: Optional[str] = None) -> Dict[str, Any]:
        """Get summary statistics for checkpoints."""
        chks = self.get_all_checkpoints(run_id)
        return {
            "total": len(chks),
            "pending": sum(1 for c in chks if c.status == "pending"),
            "approved": sum(1 for c in chks if c.status == "approved"),
            "rejected": sum(1 for c in chks if c.status == "rejected"),
            "modified": sum(1 for c in chks if c.status == "modified"),
            "skipped": sum(1 for c in chks if c.status == "skipped"),
        }
