"""Tests for HITL Checkpoint Manager and Human-in-the-Loop Workflows."""

import pytest
from app.hitl.checkpoint import (
    HITLCheckpointManager,
    HITLCheckpointConfig,
    HITLCheckpoint,
    CheckpointDecision,
)


class TestHITLCheckpointManager:
    def _make_manager(self, **kwargs) -> HITLCheckpointManager:
        config = HITLCheckpointConfig(**kwargs)
        return HITLCheckpointManager(config=config)

    def test_create_checkpoint(self):
        mgr = self._make_manager()
        chk = mgr.create_checkpoint(
            run_id="run-001",
            checkpoint_type="findings_review",
            title="Review Specialist Findings",
            description="Please review the 4 specialist findings before conflict detection.",
            stage="after_specialist_execution",
            payload={"findings_count": 4},
        )
        assert chk.checkpoint_id.startswith("HITL-")
        assert chk.status == "pending"
        assert chk.is_blocking is True

    def test_resolve_checkpoint_approve(self):
        mgr = self._make_manager()
        chk = mgr.create_checkpoint(
            run_id="run-001",
            checkpoint_type="findings_review",
            title="Review Findings",
        )
        decision = CheckpointDecision(
            checkpoint_id=chk.checkpoint_id,
            decision="approve",
            feedback="Looks good, proceed.",
        )
        resolved = mgr.resolve_checkpoint(chk.checkpoint_id, decision)
        assert resolved.status == "approve"
        assert resolved.decision is not None
        assert resolved.decision.feedback == "Looks good, proceed."

    def test_resolve_checkpoint_reject(self):
        mgr = self._make_manager()
        chk = mgr.create_checkpoint(
            run_id="run-001",
            checkpoint_type="pre_synthesis_approval",
            title="Approve Synthesis",
        )
        decision = CheckpointDecision(
            checkpoint_id=chk.checkpoint_id,
            decision="reject",
            feedback="The financial analysis seems incomplete. Re-run the financial specialist.",
        )
        resolved = mgr.resolve_checkpoint(chk.checkpoint_id, decision)
        assert resolved.status == "reject"

    def test_resolve_checkpoint_modify(self):
        mgr = self._make_manager()
        chk = mgr.create_checkpoint(
            run_id="run-001",
            checkpoint_type="post_negotiation_review",
            title="Review Negotiation",
        )
        decision = CheckpointDecision(
            checkpoint_id=chk.checkpoint_id,
            decision="modify",
            feedback="Adjust the timeline to 12 weeks instead of 8.",
            modifications={"timeline_weeks": 12},
        )
        resolved = mgr.resolve_checkpoint(chk.checkpoint_id, decision)
        assert resolved.status == "modify"
        assert resolved.decision.modifications["timeline_weeks"] == 12

    def test_pending_checkpoints(self):
        mgr = self._make_manager()
        mgr.create_checkpoint(run_id="run-001", checkpoint_type="findings_review", title="R1")
        mgr.create_checkpoint(run_id="run-001", checkpoint_type="pre_synthesis_approval", title="R2")
        assert mgr.has_pending_checkpoints("run-001") is True
        assert len(mgr.get_pending_checkpoints("run-001")) == 2

    def test_resolve_clears_pending(self):
        mgr = self._make_manager()
        chk = mgr.create_checkpoint(run_id="run-001", checkpoint_type="findings_review", title="R1")
        decision = CheckpointDecision(checkpoint_id=chk.checkpoint_id, decision="approve")
        mgr.resolve_checkpoint(chk.checkpoint_id, decision)
        assert mgr.has_pending_checkpoints("run-001") is False

    def test_double_resolve_raises(self):
        mgr = self._make_manager()
        chk = mgr.create_checkpoint(run_id="run-001", checkpoint_type="findings_review", title="R1")
        decision = CheckpointDecision(checkpoint_id=chk.checkpoint_id, decision="approve")
        mgr.resolve_checkpoint(chk.checkpoint_id, decision)
        with pytest.raises(ValueError, match="already resolved"):
            mgr.resolve_checkpoint(chk.checkpoint_id, decision)

    def test_should_checkpoint_config(self):
        mgr = self._make_manager(
            enable_findings_review=True,
            enable_pre_synthesis_approval=True,
            enable_pre_negotiation_approval=False,
        )
        assert mgr.should_checkpoint("findings_review") is True
        assert mgr.should_checkpoint("pre_synthesis_approval") is True
        assert mgr.should_checkpoint("pre_negotiation_approval") is False

    def test_summary(self):
        mgr = self._make_manager()
        chk1 = mgr.create_checkpoint(run_id="run-001", checkpoint_type="findings_review", title="R1")
        chk2 = mgr.create_checkpoint(run_id="run-001", checkpoint_type="pre_synthesis_approval", title="R2")
        mgr.resolve_checkpoint(chk1.checkpoint_id, CheckpointDecision(checkpoint_id=chk1.checkpoint_id, decision="approve"))
        summary = mgr.get_summary("run-001")
        assert summary["total"] == 2
        assert summary["pending"] == 1
        assert summary["approved"] == 1

    def test_filter_by_run_id(self):
        mgr = self._make_manager()
        mgr.create_checkpoint(run_id="run-001", checkpoint_type="findings_review", title="R1")
        mgr.create_checkpoint(run_id="run-002", checkpoint_type="findings_review", title="R2")
        assert len(mgr.get_all_checkpoints("run-001")) == 1
        assert len(mgr.get_all_checkpoints("run-002")) == 1
        assert len(mgr.get_all_checkpoints()) == 2

    def test_nonexistent_checkpoint_raises(self):
        mgr = self._make_manager()
        with pytest.raises(ValueError, match="not found"):
            mgr.resolve_checkpoint(
                "HITL-FAKE",
                CheckpointDecision(checkpoint_id="HITL-FAKE", decision="approve")
            )

