/**
 * CollaborAI TypeScript Schemas - mirroring backend Pydantic models
 */

export interface Constraint {
  constraint_id: string;
  category: 'timeline' | 'budget' | 'compliance' | 'technical' | 'operational' | 'risk' | 'strategic';
  description: string;
  is_hard_constraint: boolean;
  threshold_value?: string;
}

export interface Task {
  task_id: string;
  workstream_id: string;
  assigned_agent: string;
  objective: string;
  required_inputs: string[];
  status: 'pending' | 'in_progress' | 'completed' | 're_evaluating';
}

export interface Workstream {
  workstream_id: string;
  title: string;
  domain: string;
  required_expertise: string;
  tasks: Task[];
}

export interface Assertion {
  dimension:
    | 'timeline_weeks'
    | 'budget_usd'
    | 'compliance_status'
    | 'feasibility_score'
    | 'risk_level'
    | 'market_demand'
    | 'operational_complexity'
    | 'performance_impact'
    | 'other';
  dimension_label?: string;
  value: any;
  unit?: string;
  is_flexible: boolean;
  acceptable_range?: any[];
}

export interface Finding {
  finding_id: string;
  run_id: string;
  agent_name: string;
  topic: string;
  claim: string;
  assertions: Assertion[];
  assumptions: string[];
  confidence: number;
  evidence: Record<string, any>;
  dependencies: string[];
  status: 'active' | 'stale' | 'revised' | 'retracted';
  created_at: string;
  revised_at?: string;
}

export interface Conflict {
  conflict_id: string;
  run_id: string;
  agents_involved: string[];
  incompatible_finding_ids: string[];
  conflict_type:
    | 'timeline_mismatch'
    | 'budget_exceeded'
    | 'regulatory_violation'
    | 'risk_appetite_clash'
    | 'architectural_incompatibility'
    | 'resource_contention'
    | 'general_contradiction';
  description: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  status: 'detected' | 'negotiating' | 'resolved' | 'escalated';
  resolution_summary?: string;
}

export interface NegotiationProposal {
  proposal_id: string;
  proposing_agent: string;
  round_number: number;
  compromise_statement: string;
  concessions_made: string[];
  impact_on_own_domain: string;
}

export interface NegotiationRound {
  round_id: string;
  conflict_id: string;
  round_number: number;
  proposals: NegotiationProposal[];
  compromise_achieved: boolean;
  synthesis_statement?: string;
  resolved_findings_updates?: Record<string, any>[];
}

export interface StaleAssumption {
  assumption_id: string;
  finding_id: string;
  invalidating_finding_id: string;
  reason: string;
  impacted_agent: string;
  re_evaluation_required: boolean;
  resolved: boolean;
}

export interface EscalationOption {
  option_id: string;
  title: string;
  description: string;
  trade_offs: string[];
  estimated_impact: string;
}

export interface HumanEscalation {
  escalation_id: string;
  run_id: string;
  conflict_id: string;
  reason: string;
  options: EscalationOption[];
  human_decision?: {
    selected_option_id: string;
    custom_guidance?: string;
  };
  status: 'pending' | 'resolved';
  escalated_at: string;
  resolved_at?: string;
}

export interface AttributedClaim {
  claim_id: string;
  statement: string;
  source_finding_ids: string[];
  contributing_agents: string[];
  confidence_score: number;
  rationale: string;
}

export interface FinalRecommendation {
  executive_summary: string;
  strategic_verdict: 'GO' | 'GO_WITH_CONDITIONS' | 'DEFER' | 'NO_GO' | 'ALTERNATIVE_SELECTED';
  phased_roadmap: {
    phase: string;
    duration: string;
    actions: string[];
    owner: string;
  }[];
  risk_mitigation_plan: {
    risk: string;
    severity: string;
    mitigation: string;
    monitoring: string;
  }[];
  attributed_claims: AttributedClaim[];
}

export interface AgentStatus {
  agent_name: string;
  role: string;
  state: 'idle' | 'thinking' | 'posting_finding' | 'debating' | 'resolved' | 'waiting_human' | 're_evaluating' | 'error';
  last_action: string;
  active_task_id?: string;
  color_theme?: string;
  avatar_icon?: string;
  updated_at: string;
}

export interface ExecutionEvent {
  event_id: string;
  run_id: string;
  event_type: string;
  agent_name?: string;
  title: string;
  data: Record<string, any>;
  timestamp: string;
}

export interface SpecialistProfile {
  agent_name: string;
  role_title: string;
  domain: string;
  system_instruction: string;
  color_theme: string;
  avatar_icon: string;
  is_dynamic: boolean;
}

// ── MCP Tool Interfaces ──────────────────────────────────────────────────────

export interface MCPToolParameter {
  name: string;
  type: 'string' | 'number' | 'boolean' | 'object' | 'array';
  description: string;
  required: boolean;
  default?: any;
}

export interface MCPTool {
  name: string;
  description: string;
  category: 'research' | 'calculation' | 'data_retrieval' | 'document_analysis' | 'domain_lookup' | 'system';
  parameters: MCPToolParameter[];
  is_enabled: boolean;
}

export interface MCPToolResult {
  call_id: string;
  tool_name: string;
  status: 'success' | 'error' | 'timeout';
  result: any;
  error_message?: string;
  execution_time_ms: number;
  timestamp: string;
}

export interface MCPToolCall {
  call_id: string;
  tool_name: string;
  arguments: Record<string, any>;
  requesting_agent: string;
  run_id: string;
  timestamp: string;
}

// ── HITL Checkpoint Interfaces ──────────────────────────────────────────────

export interface CheckpointDecision {
  checkpoint_id: string;
  decision: 'approve' | 'reject' | 'modify' | 'skip';
  feedback?: string;
  modifications?: Record<string, any>;
  decided_by: string;
  decided_at: string;
}

export interface HITLCheckpoint {
  checkpoint_id: string;
  run_id: string;
  checkpoint_type: 'findings_review' | 'pre_negotiation_approval' | 'post_negotiation_review' | 'pre_synthesis_approval' | 'custom_gate';
  title: string;
  description: string;
  stage: string;
  payload: Record<string, any>;
  status: 'pending' | 'approved' | 'rejected' | 'modified' | 'skipped' | 'auto_approved';
  decision?: CheckpointDecision;
  is_blocking: boolean;
  auto_approve_timeout_seconds?: number;
  created_at: string;
  resolved_at?: string;
}

export interface HITLConfig {
  enabled: boolean;
  enable_findings_review: boolean;
  enable_pre_negotiation_approval: boolean;
  enable_post_negotiation_review: boolean;
  enable_pre_synthesis_approval: boolean;
  auto_approve_timeout?: number;
}

export interface SharedState {
  run_id: string;
  goal: string;
  constraints: Constraint[];
  workstreams: Workstream[];
  tasks: Task[];
  active_specialists: SpecialistProfile[];
  findings: Finding[];
  agent_statuses: Record<string, AgentStatus>;
  conflicts: Conflict[];
  negotiations: NegotiationRound[];
  stale_assumptions: StaleAssumption[];
  escalations: HumanEscalation[];
  final_recommendation?: FinalRecommendation;
  execution_events: ExecutionEvent[];
  mcp_tool_calls: MCPToolResult[];
  mcp_tools_summary?: Record<string, any>;
  hitl_checkpoints: HITLCheckpoint[];
  is_paused_for_hitl: boolean;
  active_hitl_checkpoint_id?: string;
  hitl_enabled: boolean;
  iteration_count: number;
  max_negotiation_rounds: number;
  is_paused_for_human: boolean;
  is_completed: boolean;
  error?: string;
}

export interface ScenarioPreset {
  scenario_id: string;
  title: string;
  category: string;
  description: string;
  default_goal: string;
  default_constraints: Constraint[];
  suggested_specialists: string[];
}

export interface BenchmarkResponse {
  run_id: string;
  goal: string;
  single_llm_verdict: string;
  single_llm_summary: string;
  single_llm_missed_conflicts: string[];
  multi_agent_verdict: string;
  multi_agent_conflicts_surfaced: number;
  multi_agent_negotiations_completed: number;
  depth_score_single_llm: number;
  depth_score_multi_agent: number;
  analysis_comparison: string;
}
