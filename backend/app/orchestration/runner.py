"""Execution Runner & Event Broadcaster for CollaborAI.

Manages run lifecycles, drives the state graph, broadcasts WebSocket events,
and coordinates Human-in-the-Loop escalation pauses and resumes.
"""

from __future__ import annotations
import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from sqlalchemy import select

from ..config import settings
from ..db.session import AsyncSessionLocal
from ..db.models import RunModel, FindingModel, ConflictModel, EventModel
from ..schemas.state import SharedState, ExecutionEvent, Constraint
from ..llm import get_llm_provider
from .state_graph import CoordinationStateGraph
from ..hitl.checkpoint import HITLCheckpointManager, HITLCheckpointConfig, CheckpointDecision
from ..mcp.client import MCPToolClient

logger = logging.getLogger("collaborai.orchestration.runner")


class RunOrchestrator:
    """Manages active runs, step execution, persistence, and WebSocket broadcasting."""

    def __init__(self):
        self._active_states: Dict[str, SharedState] = {}
        self._listeners: Dict[str, List[Callable[[ExecutionEvent], None]]] = {}
        self._hitl_managers: Dict[str, HITLCheckpointManager] = {}
        self._mcp_clients: Dict[str, MCPToolClient] = {}

    def subscribe(self, run_id: str, callback: Callable[[ExecutionEvent], None]) -> None:
        """Register a callback for WebSocket streaming."""
        if run_id not in self._listeners:
            self._listeners[run_id] = []
        self._listeners[run_id].append(callback)

    def unsubscribe(self, run_id: str, callback: Callable[[ExecutionEvent], None]) -> None:
        """Unregister a WebSocket callback."""
        if run_id in self._listeners and callback in self._listeners[run_id]:
            self._listeners[run_id].remove(callback)

    def _broadcast(self, event: ExecutionEvent) -> None:
        """Send event to all registered listeners."""
        for cb in self._listeners.get(event.run_id, []):
            try:
                cb(event)
            except Exception as e:
                logger.error("Error in event callback: %s", e)

    def get_state(self, run_id: str) -> Optional[SharedState]:
        """Fetch current in-memory state of a run."""
        return self._active_states.get(run_id)

    def get_hitl_manager(self, run_id: str) -> Optional[HITLCheckpointManager]:
        """Fetch HITL checkpoint manager for a run."""
        return self._hitl_managers.get(run_id)

    def get_all_hitl_managers(self) -> Dict[str, HITLCheckpointManager]:
        """Fetch all registered HITL managers."""
        return self._hitl_managers

    async def create_and_start_run(
        self,
        goal: str,
        constraints: Optional[List[Constraint]] = None,
        simulation_mode: Optional[bool] = None,
        run_id: Optional[str] = None,
        hitl_config: Optional[Any] = None,
        enable_mcp_tools: bool = True
    ) -> SharedState:
        """Initialize and launch an asynchronous multi-agent coordination run."""
        rid = run_id or f"run-{uuid.uuid4().hex[:8]}"
        state = SharedState(
            run_id=rid,
            goal=goal,
            constraints=constraints or [],
            hitl_enabled=True if hitl_config is None or getattr(hitl_config, "enabled", True) else False
        )
        self._active_states[rid] = state

        # Configure HITL Manager
        if hitl_config:
            chk_cfg = HITLCheckpointConfig(
                enable_findings_review=getattr(hitl_config, "enable_findings_review", False),
                enable_pre_negotiation_approval=getattr(hitl_config, "enable_pre_negotiation_approval", False),
                enable_post_negotiation_review=getattr(hitl_config, "enable_post_negotiation_review", False),
                enable_pre_synthesis_approval=getattr(hitl_config, "enable_pre_synthesis_approval", False),
                auto_approve_timeout=getattr(hitl_config, "auto_approve_timeout", None),
            )
        else:
            chk_cfg = HITLCheckpointConfig()
        hitl_mgr = HITLCheckpointManager(config=chk_cfg)
        self._hitl_managers[rid] = hitl_mgr

        # Configure MCP Client
        mcp_client = MCPToolClient() if enable_mcp_tools else None
        if mcp_client:
            self._mcp_clients[rid] = mcp_client

        # Save initial run in DB
        async with AsyncSessionLocal() as session:
            db_run = RunModel(
                id=rid,
                goal=goal,
                constraints=[c.model_dump() for c in state.constraints],
                status="running",
                state_json=state.model_dump(mode="json")
            )
            session.add(db_run)
            await session.commit()

        # Emit RUN_STARTED event
        start_event = ExecutionEvent(
            event_id=f"EVT-{uuid.uuid4().hex[:8]}",
            run_id=rid,
            event_type="RUN_STARTED",
            title="CollaborAI Multi-Agent Run Initiated",
            data={
                "goal": goal,
                "constraints_count": len(state.constraints),
                "mcp_tools_enabled": enable_mcp_tools,
                "hitl_enabled": state.hitl_enabled,
            }
        )
        state.execution_events.append(start_event)
        self._broadcast(start_event)

        # Launch background execution task
        asyncio.create_task(
            self._execute_pipeline(
                rid,
                simulation_mode=simulation_mode,
                enable_mcp_tools=enable_mcp_tools
            )
        )
        return state

    async def _execute_pipeline(
        self,
        run_id: str,
        simulation_mode: Optional[bool] = None,
        enable_mcp_tools: bool = True
    ) -> None:
        """Drive the state machine sequentially through the PS-27 stages."""
        state = self._active_states.get(run_id)
        if not state:
            return

        is_sim = simulation_mode if simulation_mode is not None else settings.SIMULATION_MODE
        llm = get_llm_provider(force_simulation=is_sim)
        mcp_client = self._mcp_clients.get(run_id) or (MCPToolClient() if enable_mcp_tools else None)
        hitl_mgr = self._hitl_managers.get(run_id) or HITLCheckpointManager()
        graph = CoordinationStateGraph(
            llm_provider=llm,
            mcp_client=mcp_client,
            hitl_manager=hitl_mgr,
            enable_mcp_tools=enable_mcp_tools
        )

        try:
            # 1. Goal Decomposition
            state = await graph.decompose_goal_node(state, event_callback=self._broadcast)

            # 2. Specialist Execution
            state = await graph.execute_specialists_node(state, event_callback=self._broadcast)

            # HITL Checkpoint: findings_review
            if state.hitl_enabled and hitl_mgr.should_checkpoint("findings_review"):
                await self._pause_for_checkpoint(
                    state, hitl_mgr,
                    checkpoint_type="findings_review",
                    title="Review Specialist Findings",
                    description=f"{len(state.findings)} specialist findings posted. Approve to proceed to conflict detection.",
                    stage="after_specialist_execution",
                    payload={"findings_count": len(state.findings)}
                )
                return

            # 3. Conflict Detection
            state = await graph.detect_conflicts_node(state, event_callback=self._broadcast)

            # 4. Multi-Agent Negotiation
            if state.conflicts:
                # HITL Checkpoint: pre_negotiation_approval
                if state.hitl_enabled and hitl_mgr.should_checkpoint("pre_negotiation_approval"):
                    await self._pause_for_checkpoint(
                        state, hitl_mgr,
                        checkpoint_type="pre_negotiation_approval",
                        title="Approve Negotiation Protocol",
                        description=f"{len(state.conflicts)} conflicts detected. Approve negotiation parameters.",
                        stage="pre_negotiation",
                        payload={"conflicts_count": len(state.conflicts)}
                    )
                    return

                state = await graph.negotiate_conflicts_node(state, event_callback=self._broadcast)

                # Check if execution paused for Human-in-the-Loop Escalation
                if state.is_paused_for_human:
                    logger.info("Run %s paused awaiting human escalation response.", run_id)
                    await self._persist_state(state, status="paused_for_human")
                    return

                # HITL Checkpoint: post_negotiation_review
                if state.hitl_enabled and hitl_mgr.should_checkpoint("post_negotiation_review"):
                    await self._pause_for_checkpoint(
                        state, hitl_mgr,
                        checkpoint_type="post_negotiation_review",
                        title="Review Negotiation Outcomes",
                        description=f"{len(state.negotiations)} negotiation rounds concluded. Review compromise.",
                        stage="post_negotiation",
                        payload={"negotiations_count": len(state.negotiations)}
                    )
                    return

            # 5. Stale Assumption Detection & Re-evaluation
            state = await graph.stale_assumption_check_node(state, event_callback=self._broadcast)

            # 6. Goal Consistency Check
            state = await graph.goal_consistency_node(state, event_callback=self._broadcast)

            # HITL Checkpoint: pre_synthesis_approval
            if state.hitl_enabled and hitl_mgr.should_checkpoint("pre_synthesis_approval"):
                await self._pause_for_checkpoint(
                    state, hitl_mgr,
                    checkpoint_type="pre_synthesis_approval",
                    title="Approve Final Strategic Synthesis",
                    description="Deliberation complete. Sign off to generate final executive recommendation and roadmap.",
                    stage="pre_synthesis",
                    payload={"findings_count": len(state.findings), "conflicts_count": len(state.conflicts)}
                )
                return

            # 7. Final Synthesis & Attribution
            state = await graph.synthesis_node(state, event_callback=self._broadcast)

            # Mark Completed
            comp_event = ExecutionEvent(
                event_id=f"EVT-{uuid.uuid4().hex[:8]}",
                run_id=run_id,
                event_type="RUN_COMPLETED",
                title="CollaborAI Deliberation Finished Successfully",
                data={"verdict": state.final_recommendation.strategic_verdict if state.final_recommendation else "COMPLETED"}
            )
            state.execution_events.append(comp_event)
            self._broadcast(comp_event)

            await self._persist_state(state, status="completed")

        except Exception as e:
            logger.exception("Error executing multi-agent pipeline for run %s: %s", run_id, e)
            state.error = str(e)
            fail_event = ExecutionEvent(
                event_id=f"EVT-{uuid.uuid4().hex[:8]}",
                run_id=run_id,
                event_type="RUN_FAILED",
                title="Execution Pipeline Error",
                data={"error": str(e)}
            )
            state.execution_events.append(fail_event)
            self._broadcast(fail_event)
            await self._persist_state(state, status="failed")

    async def _pause_for_checkpoint(
        self,
        state: SharedState,
        hitl_mgr: HITLCheckpointManager,
        checkpoint_type: str,
        title: str,
        description: str,
        stage: str,
        payload: Dict[str, Any]
    ) -> None:
        """Create a blocking HITL checkpoint and pause pipeline."""
        checkpoint = hitl_mgr.create_checkpoint(
            run_id=state.run_id,
            checkpoint_type=checkpoint_type,
            title=title,
            description=description,
            stage=stage,
            payload=payload,
            is_blocking=True
        )
        state.hitl_checkpoints.append(checkpoint.model_dump(mode="json"))
        state.is_paused_for_hitl = True
        state.active_hitl_checkpoint_id = checkpoint.checkpoint_id

        pause_event = ExecutionEvent(
            event_id=f"EVT-{uuid.uuid4().hex[:8]}",
            run_id=state.run_id,
            event_type="HITL_PAUSED",
            title=f"HITL Checkpoint: {title}",
            data=checkpoint.model_dump(mode="json")
        )
        state.execution_events.append(pause_event)
        self._broadcast(pause_event)
        await self._persist_state(state, status="paused_for_hitl")

    async def resume_from_checkpoint(
        self,
        run_id: str,
        checkpoint_id: str,
        decision: CheckpointDecision
    ) -> SharedState:
        """Resume deliberation pipeline after a human decision on a checkpoint."""
        state = self._active_states.get(run_id)
        if not state:
            raise ValueError(f"Run {run_id} not found.")

        state.is_paused_for_hitl = False
        state.active_hitl_checkpoint_id = None

        # Update checkpoint in state record
        for chk in state.hitl_checkpoints:
            if chk.get("checkpoint_id") == checkpoint_id:
                chk["status"] = decision.decision
                chk["decision"] = decision.model_dump(mode="json")
                chk["resolved_at"] = datetime.utcnow().isoformat()

        resumed_event = ExecutionEvent(
            event_id=f"EVT-{uuid.uuid4().hex[:8]}",
            run_id=run_id,
            event_type="HITL_RESUMED",
            title=f"HITL Checkpoint Resolved: {decision.decision.upper()}",
            data={"checkpoint_id": checkpoint_id, "decision": decision.decision, "feedback": decision.feedback}
        )
        state.execution_events.append(resumed_event)
        self._broadcast(resumed_event)

        # Determine which stage to resume from
        hitl_mgr = self._hitl_managers.get(run_id)
        chk = hitl_mgr.get_checkpoint(checkpoint_id) if hitl_mgr else None
        stage = chk.stage if chk else "pre_synthesis"

        is_sim = settings.SIMULATION_MODE
        llm = get_llm_provider(force_simulation=is_sim)
        mcp_client = self._mcp_clients.get(run_id)
        graph = CoordinationStateGraph(
            llm_provider=llm,
            mcp_client=mcp_client,
            hitl_manager=hitl_mgr,
            enable_mcp_tools=bool(mcp_client)
        )

        asyncio.create_task(self._continue_pipeline_after_checkpoint(state, graph, stage, decision))
        return state

    async def _continue_pipeline_after_checkpoint(
        self,
        state: SharedState,
        graph: CoordinationStateGraph,
        stage: str,
        decision: CheckpointDecision
    ) -> None:
        """Continue execution from the paused checkpoint stage."""
        try:
            # If rejected, adjust or re-synthesize with feedback
            if decision.decision == "reject" and decision.feedback:
                state.goal += f" (Human Revision Guidance: {decision.feedback})"

            if stage == "after_specialist_execution":
                state = await graph.detect_conflicts_node(state, event_callback=self._broadcast)
                if state.conflicts:
                    state = await graph.negotiate_conflicts_node(state, event_callback=self._broadcast)
                state = await graph.stale_assumption_check_node(state, event_callback=self._broadcast)
                state = await graph.goal_consistency_node(state, event_callback=self._broadcast)
                state = await graph.synthesis_node(state, event_callback=self._broadcast)

            elif stage == "pre_negotiation":
                state = await graph.negotiate_conflicts_node(state, event_callback=self._broadcast)
                state = await graph.stale_assumption_check_node(state, event_callback=self._broadcast)
                state = await graph.goal_consistency_node(state, event_callback=self._broadcast)
                state = await graph.synthesis_node(state, event_callback=self._broadcast)

            elif stage in ("post_negotiation", "pre_synthesis"):
                state = await graph.synthesis_node(state, event_callback=self._broadcast)

            # Deliberation finished
            comp_event = ExecutionEvent(
                event_id=f"EVT-{uuid.uuid4().hex[:8]}",
                run_id=state.run_id,
                event_type="RUN_COMPLETED",
                title="CollaborAI Deliberation Finished Successfully",
                data={"verdict": state.final_recommendation.strategic_verdict if state.final_recommendation else "COMPLETED"}
            )
            state.execution_events.append(comp_event)
            self._broadcast(comp_event)
            await self._persist_state(state, status="completed")

        except Exception as e:
            logger.exception("Error continuing pipeline after checkpoint for run %s: %s", state.run_id, e)
            await self._persist_state(state, status="failed")

    async def resume_escalated_run(
        self,
        run_id: str,
        escalation_id: str,
        selected_option_id: str,
        custom_guidance: Optional[str] = None
    ) -> SharedState:
        """Resume execution following human escalation decision."""
        state = self._active_states.get(run_id)
        if not state:
            raise ValueError(f"Run {run_id} not found.")

        # Find escalation record
        for esc in state.escalations:
            if esc.escalation_id == escalation_id:
                esc.status = "resolved"
                esc.human_decision = {
                    "selected_option_id": selected_option_id,
                    "custom_guidance": custom_guidance
                }
                esc.resolved_at = datetime.utcnow()

        state.is_paused_for_human = False

        resumed_event = ExecutionEvent(
            event_id=f"EVT-{uuid.uuid4().hex[:8]}",
            run_id=run_id,
            event_type="RUN_RESUMED",
            title="Human Decision Injected - Deliberation Resumed",
            data={"option": selected_option_id, "guidance": custom_guidance}
        )
        state.execution_events.append(resumed_event)
        self._broadcast(resumed_event)

        # Run synthesis to incorporate human decision
        llm = get_llm_provider()
        graph = CoordinationStateGraph(llm_provider=llm)
        asyncio.create_task(self._finish_after_escalation(state, graph))

        return state

    async def _finish_after_escalation(self, state: SharedState, graph: CoordinationStateGraph) -> None:
        """Complete synthesis following human escalation injection."""
        state = await graph.synthesis_node(state, event_callback=self._broadcast)
        comp_event = ExecutionEvent(
            event_id=f"EVT-{uuid.uuid4().hex[:8]}",
            run_id=state.run_id,
            event_type="RUN_COMPLETED",
            title="CollaborAI Deliberation Finished Following Human Input",
            data={"verdict": state.final_recommendation.strategic_verdict if state.final_recommendation else "COMPLETED"}
        )
        state.execution_events.append(comp_event)
        self._broadcast(comp_event)
        await self._persist_state(state, status="completed")

    async def _persist_state(self, state: SharedState, status: str) -> None:
        """Persist state updates to SQLite/database."""
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(RunModel).where(RunModel.id == state.run_id))
                db_run = result.scalar_one_or_none()
                if db_run:
                    db_run.status = status
                    db_run.state_json = state.model_dump(mode="json")
                    if status == "completed":
                        db_run.completed_at = datetime.utcnow()
                    await session.commit()
        except Exception as e:
            logger.error("Failed to persist run state for %s: %s", state.run_id, e)


# Global orchestrator singleton
orchestrator = RunOrchestrator()
