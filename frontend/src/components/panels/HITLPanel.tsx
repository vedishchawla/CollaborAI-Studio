import React from 'react';
import { Button } from '@/components/ui/button';
import {
  UserCheck,
  CheckCircle2,
  XCircle,
  Edit3,
  Clock,
  ShieldCheck,
  FileCheck,
  ChevronRight,
  AlertCircle,
} from 'lucide-react';
import { HITLCheckpoint } from '@/types/schema';
import { formatLocalTime } from '@/lib/utils';

interface HITLPanelProps {
  checkpoints: HITLCheckpoint[];
  onOpenCheckpointModal: (checkpoint: HITLCheckpoint) => void;
}

export const HITLPanel: React.FC<HITLPanelProps> = ({
  checkpoints = [],
  onOpenCheckpointModal,
}) => {
  const pendingCheckpoints = checkpoints.filter((c) => c.status === 'pending');
  const resolvedCheckpoints = checkpoints.filter((c) => c.status !== 'pending');

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'approved':
      case 'approve':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold flex items-center gap-1 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="w-3 h-3" /> Approved
          </span>
        );
      case 'modified':
      case 'modify':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold flex items-center gap-1 bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <Edit3 className="w-3 h-3" /> Modified
          </span>
        );
      case 'rejected':
      case 'reject':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold flex items-center gap-1 bg-rose-500/10 text-rose-400 border border-rose-500/20">
            <XCircle className="w-3 h-3" /> Rejected
          </span>
        );
      case 'pending':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold flex items-center gap-1 bg-primary/10 text-primary border border-primary/20 animate-pulse">
            <Clock className="w-3 h-3" /> Awaiting Review
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-muted text-muted-foreground">
            {status}
          </span>
        );
    }
  };

  return (
    <div className="space-y-4">
      {/* Experiment Header Banner */}
      <div className="p-3.5 rounded-lg border border-primary/20 bg-primary/5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold tracking-wider uppercase bg-primary/20 text-primary border border-primary/30">
            EXPERIMENT 2
          </span>
          <span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
            <UserCheck className="w-3.5 h-3.5 text-primary" />
            Human-in-the-Loop (HITL) Checkpoint & Approval Ledger
          </span>
        </div>
        <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
          <span>Total Gates: <strong className="text-foreground">{checkpoints.length}</strong></span>
          <span>•</span>
          <span>Pending: <strong className="text-foreground">{pendingCheckpoints.length}</strong></span>
          <span>•</span>
          <span>Approved: <strong className="text-foreground">{resolvedCheckpoints.length}</strong></span>
        </div>
      </div>

      {/* Pending Checkpoints Action Card */}
      {pendingCheckpoints.length > 0 && (
        <div className="space-y-2">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-primary block">
            Action Required ({pendingCheckpoints.length}):
          </span>
          {pendingCheckpoints.map((chk) => (
            <div
              key={chk.checkpoint_id}
              className="p-4 rounded-lg border border-primary/30 bg-primary/5 flex items-center justify-between gap-3"
            >
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono font-bold text-foreground">{chk.checkpoint_id}</span>
                  {getStatusBadge(chk.status)}
                </div>
                <h4 className="text-xs font-bold text-foreground">{chk.title}</h4>
                <p className="text-[11px] text-muted-foreground">{chk.description}</p>
              </div>
              <Button
                size="sm"
                onClick={() => onOpenCheckpointModal(chk)}
                className="shrink-0 flex items-center gap-1.5 text-xs font-semibold"
              >
                Review & Decide
                <ChevronRight className="w-3.5 h-3.5" />
              </Button>
            </div>
          ))}
        </div>
      )}

      {/* History Ledger */}
      <div className="space-y-2">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground block">
          Approval History & Provenance:
        </span>

        {checkpoints.length === 0 ? (
          <div className="p-8 text-center rounded-lg border border-dashed border-border bg-muted/20">
            <FileCheck className="w-8 h-8 text-muted-foreground mx-auto mb-2 opacity-60" />
            <p className="text-xs font-medium text-foreground">No checkpoint events logged yet.</p>
            <p className="text-[11px] text-muted-foreground mt-1">
              As the multi-agent pipeline proceeds, human approval gates (e.g. Findings Review, Final Sign-off) will record decision provenance here.
            </p>
          </div>
        ) : (
          checkpoints.map((chk) => (
            <div
              key={chk.checkpoint_id}
              className="p-3.5 rounded-lg border border-border bg-card/60 text-xs space-y-2"
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold text-foreground">{chk.checkpoint_id}</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground font-mono">
                    {chk.checkpoint_type}
                  </span>
                </div>
                {getStatusBadge(chk.status)}
              </div>

              <div>
                <h5 className="font-semibold text-foreground text-xs">{chk.title}</h5>
                {chk.description && (
                  <p className="text-[11px] text-muted-foreground mt-0.5">{chk.description}</p>
                )}
              </div>

              {chk.decision && (
                <div className="p-2.5 rounded bg-muted text-[11px] space-y-1">
                  <div className="flex items-center justify-between text-muted-foreground">
                    <span>Decided by: <strong className="text-foreground">{chk.decision.decided_by}</strong></span>
                    {chk.resolved_at && (
                      <time className="font-mono text-[10px]">
                        {formatLocalTime(chk.resolved_at, { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                      </time>
                    )}
                  </div>
                  {chk.decision.feedback && (
                    <p className="text-foreground italic">
                      &quot;{chk.decision.feedback}&quot;
                    </p>
                  )}
                  {chk.decision.modifications && (
                    <div className="mt-1 pt-1 border-t border-border/40">
                      <span className="text-[10px] font-semibold text-muted-foreground block">Injected Parameter Overrides:</span>
                      <pre className="text-[10px] font-mono text-primary">
                        {JSON.stringify(chk.decision.modifications, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
};

