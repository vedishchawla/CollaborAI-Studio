import React from 'react';
import {
  ShieldCheck,
  ShieldAlert,
  CheckCircle2,
  AlertTriangle,
  Sparkles,
  Bot,
  Wrench,
  Target,
} from 'lucide-react';
import {
  OrchestratorVerification,
  FindingVerification,
} from '@/types/schema';

interface VerificationGuardPanelProps {
  orchestratorVerification?: OrchestratorVerification | null | undefined;
  findingVerifications: FindingVerification[];
}

export const VerificationGuardPanel: React.FC<VerificationGuardPanelProps> = ({
  orchestratorVerification,
  findingVerifications = [],
}) => {
  const avgScore =
    findingVerifications.length > 0
      ? Math.round(
          (findingVerifications.reduce((acc, v) => acc + (v.grounding_score || 0), 0) /
            findingVerifications.length) *
            100,
        )
      : orchestratorVerification
      ? Math.round(orchestratorVerification.grounding_score * 100)
      : 0;

  return (
    <div className="space-y-4">
      {/* Header Banner */}
      <div className="p-3.5 rounded-lg border border-amber-500/20 bg-amber-500/5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold tracking-wider uppercase bg-amber-500/20 text-amber-400 border border-amber-500/30">
            GUARD AGENT
          </span>
          <span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-amber-400" />
            Anti-Hallucination & Output Verification Guard
          </span>
        </div>

        {(orchestratorVerification || findingVerifications.length > 0) && (
          <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
            <span>
              Grounding Score: <strong className="text-foreground">{avgScore}%</strong>
            </span>
            <span>•</span>
            <span>
              Findings Audited: <strong className="text-foreground">{findingVerifications.length}</strong>
            </span>
          </div>
        )}
      </div>

      {/* Section 1: Top-Level Orchestrator Guard Audit */}
      <div className="rounded-lg border border-border bg-card/60 p-4 space-y-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Bot className="w-4 h-4 text-primary" />
            <h4 className="text-xs font-semibold text-foreground">
              1. Top-Level Orchestrator Decomposition Audit
            </h4>
          </div>
          {orchestratorVerification && (
            <span
              className={`px-2 py-0.5 rounded text-[10px] font-semibold flex items-center gap-1 ${
                orchestratorVerification.is_valid && !orchestratorVerification.hallucination_detected
                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                  : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
              }`}
            >
              {orchestratorVerification.is_valid && !orchestratorVerification.hallucination_detected ? (
                <CheckCircle2 className="w-3 h-3" />
              ) : (
                <AlertTriangle className="w-3 h-3" />
              )}
              {Math.round(orchestratorVerification.grounding_score * 100)}% Grounded
            </span>
          )}
        </div>

        {!orchestratorVerification ? (
          <p className="text-xs text-muted-foreground">
            Start a deliberation run to verify the top-level orchestrator&apos;s dynamic agent decomposition and domain coverage.
          </p>
        ) : (
          <div className="space-y-3 text-xs">
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              <div className="p-2.5 rounded bg-muted/60 border border-border">
                <span className="text-[10px] text-muted-foreground block">Initial Orchestrator Agents</span>
                <strong className="text-sm font-mono text-foreground">
                  {orchestratorVerification.initial_agent_count}
                </strong>
              </div>
              <div className="p-2.5 rounded bg-muted/60 border border-border">
                <span className="text-[10px] text-muted-foreground block">Verified Active Agents</span>
                <strong className="text-sm font-mono text-foreground">
                  {orchestratorVerification.verified_agent_count}
                </strong>
              </div>
              <div className="p-2.5 rounded bg-muted/60 border border-border col-span-2 sm:col-span-1">
                <span className="text-[10px] text-muted-foreground block">Auto-Injected Missing</span>
                <strong className="text-sm font-mono text-foreground">
                  {orchestratorVerification.added_missing_agents.length}
                </strong>
              </div>
            </div>

            <div>
              <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider block mb-1.5">
                Verified Specialist Team
              </span>
              <div className="flex flex-wrap gap-1.5">
                {orchestratorVerification.verified_agents.map((agent) => {
                  const wasAdded = orchestratorVerification.added_missing_agents.includes(agent);
                  return (
                    <span
                      key={agent}
                      className={`px-2 py-0.5 rounded text-[11px] font-mono border ${
                        wasAdded
                          ? 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                          : 'bg-muted text-foreground border-border'
                      }`}
                    >
                      {agent}
                      {wasAdded ? ' (Guard Added)' : ''}
                    </span>
                  );
                })}
              </div>
            </div>

            {orchestratorVerification.flagged_issues.length > 0 && (
              <div className="p-2.5 rounded bg-amber-500/10 border border-amber-500/20 text-amber-300 space-y-1">
                <span className="text-[10px] font-semibold uppercase tracking-wider block">
                  Guard Corrections / Notes
                </span>
                <ul className="list-disc list-inside text-[11px]">
                  {orchestratorVerification.flagged_issues.map((issue, idx) => (
                    <li key={idx}>{issue}</li>
                  ))}
                </ul>
              </div>
            )}

            <p className="text-xs text-muted-foreground leading-relaxed bg-muted/40 p-2.5 rounded border border-border/60">
              {orchestratorVerification.rationale}
            </p>
          </div>
        )}
      </div>

      {/* Section 2: Per-Agent Finding Output Verification */}
      <div className="space-y-2.5">
        <h4 className="text-xs font-semibold text-foreground flex items-center gap-2 px-0.5">
          <Sparkles className="w-3.5 h-3.5 text-amber-400" />
          2. Specialist Agent Output Verification ({findingVerifications.length})
        </h4>

        {findingVerifications.length === 0 ? (
          <div className="p-6 text-center rounded-lg border border-dashed border-border bg-muted/20">
            <ShieldAlert className="w-7 h-7 text-muted-foreground mx-auto mb-2 opacity-60" />
            <p className="text-xs font-medium text-foreground">No specialist findings audited yet.</p>
            <p className="text-[11px] text-muted-foreground mt-1">
              After specialists execute, the Guard Agent verifies every finding against MCP tool evidence and goal constraints.
            </p>
          </div>
        ) : (
          findingVerifications.map((verif) => {
            const isVerified = verif.verdict === 'verified';
            const isCorrected = verif.verdict === 'auto_corrected';

            return (
              <div
                key={verif.verification_id}
                className="rounded-lg border border-border bg-card/60 p-3.5 text-xs space-y-2.5"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[11px] font-bold text-primary bg-accent px-2 py-0.5 rounded border border-primary/30">
                      {verif.finding_id}
                    </span>
                    <span className="font-semibold text-foreground">{verif.agent_name}</span>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-mono text-muted-foreground">
                      {Math.round(verif.grounding_score * 100)}% grounded
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider flex items-center gap-1 ${
                        isVerified
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                          : isCorrected
                          ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                          : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                      }`}
                    >
                      {isVerified ? (
                        <CheckCircle2 className="w-3 h-3" />
                      ) : (
                        <AlertTriangle className="w-3 h-3" />
                      )}
                      {verif.verdict.replace('_', ' ')}
                    </span>
                  </div>
                </div>

                <div className="flex flex-wrap gap-2 text-[11px]">
                  <span
                    className={`px-2 py-0.5 rounded border flex items-center gap-1 ${
                      verif.mcp_evidence_aligned
                        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                        : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                    }`}
                  >
                    <Wrench className="w-3 h-3" />
                    MCP Evidence: {verif.mcp_evidence_aligned ? 'Aligned' : 'Mismatch'}
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded border flex items-center gap-1 ${
                      verif.goal_aligned
                        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                        : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                    }`}
                  >
                    <Target className="w-3 h-3" />
                    Goal Scope: {verif.goal_aligned ? 'Aligned' : 'Drift'}
                  </span>
                </div>

                {verif.issues_found.length > 0 && (
                  <div className="p-2 rounded bg-amber-500/10 border border-amber-500/20 text-amber-300 text-[11px]">
                    <strong>Issues Caught:</strong> {verif.issues_found.join(' | ')}
                  </div>
                )}

                {verif.corrected_claim && (
                  <div className="p-2 rounded bg-muted border border-border text-[11px] text-foreground">
                    <strong className="text-amber-400 block mb-0.5">Auto-Corrected Claim:</strong>
                    {verif.corrected_claim}
                  </div>
                )}

                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  {verif.rationale}
                </p>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
