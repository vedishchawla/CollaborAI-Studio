"""HITL (Human-in-the-Loop) API Routes for CollaborAI.

Exposes endpoints for managing HITL checkpoints: listing pending approvals,
submitting decisions, and querying checkpoint history.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..hitl.checkpoint import CheckpointDecision, HITLCheckpoint
from ..orchestration.runner import orchestrator

router = APIRouter(prefix="/api/hitl", tags=["Human-in-the-Loop"])


class HITLCheckpointResponse(BaseModel):
    checkpoint: HITLCheckpoint


class HITLPendingResponse(BaseModel):
    run_id: str
    pending_checkpoints: List[HITLCheckpoint]
    total_pending: int


class HITLAllCheckpointsResponse(BaseModel):
    run_id: str
    checkpoints: List[HITLCheckpoint]
    summary: Dict[str, Any]


class HITLDecisionRequest(BaseModel):
    decision: str = Field(description="approve, reject, modify, or skip")
    feedback: Optional[str] = None
    modifications: Optional[Dict[str, Any]] = None
    decided_by: str = "human_operator"


@router.get("/runs/{run_id}/checkpoints", response_model=HITLAllCheckpointsResponse)
async def list_checkpoints(run_id: str):
    """List all HITL checkpoints for a deliberation run."""
    hitl_mgr = orchestrator.get_hitl_manager(run_id)
    if not hitl_mgr:
        raise HTTPException(status_code=404, detail="Run not found or HITL not enabled")

    checkpoints = hitl_mgr.get_all_checkpoints(run_id)
    summary = hitl_mgr.get_summary(run_id)
    return HITLAllCheckpointsResponse(
        run_id=run_id, checkpoints=checkpoints, summary=summary
    )


@router.get("/runs/{run_id}/pending", response_model=HITLPendingResponse)
async def get_pending_checkpoints(run_id: str):
    """Get all pending HITL checkpoints awaiting human decision."""
    hitl_mgr = orchestrator.get_hitl_manager(run_id)
    if not hitl_mgr:
        raise HTTPException(status_code=404, detail="Run not found or HITL not enabled")

    pending = hitl_mgr.get_pending_checkpoints(run_id)
    return HITLPendingResponse(
        run_id=run_id, pending_checkpoints=pending, total_pending=len(pending)
    )


@router.post("/checkpoints/{checkpoint_id}/decide", response_model=HITLCheckpointResponse)
async def submit_checkpoint_decision(checkpoint_id: str, req: HITLDecisionRequest):
    """Submit a human decision for a pending HITL checkpoint."""
    # Find the correct HITL manager across all runs
    hitl_mgr = None
    run_id = None
    for rid, mgr in orchestrator.get_all_hitl_managers().items():
        chk = mgr.get_checkpoint(checkpoint_id)
        if chk:
            hitl_mgr = mgr
            run_id = rid
            break

    if not hitl_mgr:
        raise HTTPException(status_code=404, detail=f"Checkpoint '{checkpoint_id}' not found")

    try:
        decision = CheckpointDecision(
            checkpoint_id=checkpoint_id,
            decision=req.decision,
            feedback=req.feedback,
            modifications=req.modifications,
            decided_by=req.decided_by,
        )
        resolved = hitl_mgr.resolve_checkpoint(checkpoint_id, decision)

        # Resume pipeline if this was the last blocking checkpoint
        if run_id and not hitl_mgr.has_pending_checkpoints(run_id):
            await orchestrator.resume_from_checkpoint(run_id, checkpoint_id, decision)

        return HITLCheckpointResponse(checkpoint=resolved)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
