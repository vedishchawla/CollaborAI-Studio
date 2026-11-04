import {
  SharedState,
  ScenarioPreset,
  SpecialistProfile,
  Constraint,
  BenchmarkResponse,
  MCPTool,
  MCPToolResult,
  HITLCheckpoint,
  HITLConfig,
  CheckpointDecision,
} from '../types/schema';

const API_BASE = '/api';

export async function fetchScenarios(): Promise<ScenarioPreset[]> {
  const res = await fetch(`${API_BASE}/scenarios`);
  if (!res.ok) throw new Error('Failed to load scenarios');
  return res.json();
}

export async function fetchSpecialists(): Promise<SpecialistProfile[]> {
  const res = await fetch(`${API_BASE}/runs/roster/specialists`);
  if (!res.ok) throw new Error('Failed to load specialists');
  return res.json();
}

export async function createRun(params: {
  goal: string;
  constraints?: Constraint[];
  scenario_id?: string;
  simulation_mode?: boolean;
  hitl_config?: HITLConfig;
  enable_mcp_tools?: boolean;
}): Promise<SharedState> {
  const res = await fetch(`${API_BASE}/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to start run');
  }
  const data = await res.json();
  return data.state;
}

export async function fetchRun(runId: string): Promise<SharedState> {
  const res = await fetch(`${API_BASE}/runs/${runId}`);
  if (!res.ok) throw new Error('Failed to fetch run');
  const data = await res.json();
  return data.state;
}

export async function submitEscalation(params: {
  runId: string;
  escalationId: string;
  selectedOptionId: string;
  customGuidance?: string;
}): Promise<SharedState> {
  const res = await fetch(`${API_BASE}/runs/${params.runId}/escalate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      escalation_id: params.escalationId,
      selected_option_id: params.selectedOptionId,
      custom_guidance: params.customGuidance,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to submit escalation');
  }
  const data = await res.json();
  return data.state;
}

export async function runBenchmark(runId: string): Promise<BenchmarkResponse> {
  const res = await fetch(`${API_BASE}/runs/${runId}/benchmark`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error('Failed to generate benchmark');
  return res.json();
}

// ── MCP Tool APIs ────────────────────────────────────────────────────────────

export async function fetchMCPTools(category?: string): Promise<{ tools: MCPTool[]; total_count: number }> {
  const url = category ? `${API_BASE}/mcp/tools?category=${encodeURIComponent(category)}` : `${API_BASE}/mcp/tools`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch MCP tools');
  return res.json();
}

export async function invokeMCPTool(params: {
  tool_name: string;
  arguments?: Record<string, any>;
  requesting_agent?: string;
  run_id?: string;
}): Promise<MCPToolResult> {
  const res = await fetch(`${API_BASE}/mcp/invoke`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to invoke MCP tool');
  }
  const data = await res.json();
  return data.result;
}

export async function fetchRunMCPTools(runId: string): Promise<{ run_id: string; mcp_tools_used: any[]; total_invocations: number }> {
  const res = await fetch(`${API_BASE}/mcp/runs/${runId}/tools`);
  if (!res.ok) throw new Error('Failed to fetch run tool usage');
  return res.json();
}

// ── HITL Checkpoint APIs ─────────────────────────────────────────────────────

export async function fetchCheckpoints(runId: string): Promise<{ run_id: string; checkpoints: HITLCheckpoint[]; summary: any }> {
  const res = await fetch(`${API_BASE}/hitl/runs/${runId}/checkpoints`);
  if (!res.ok) throw new Error('Failed to fetch checkpoints');
  return res.json();
}

export async function fetchPendingCheckpoints(runId: string): Promise<{ run_id: string; pending_checkpoints: HITLCheckpoint[]; total_pending: number }> {
  const res = await fetch(`${API_BASE}/hitl/runs/${runId}/pending`);
  if (!res.ok) throw new Error('Failed to fetch pending checkpoints');
  return res.json();
}

export async function submitCheckpointDecision(params: {
  checkpointId: string;
  decision: 'approve' | 'reject' | 'modify' | 'skip';
  feedback?: string;
  modifications?: Record<string, any>;
  decidedBy?: string;
}): Promise<HITLCheckpoint> {
  const res = await fetch(`${API_BASE}/hitl/checkpoints/${params.checkpointId}/decide`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      decision: params.decision,
      feedback: params.feedback,
      modifications: params.modifications,
      decided_by: params.decidedBy || 'human_operator',
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to submit checkpoint decision');
  }
  const data = await res.json();
  return data.checkpoint;
}
