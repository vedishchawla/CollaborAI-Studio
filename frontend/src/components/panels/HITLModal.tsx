import React, { useState } from 'react';
import { Dialog, DialogContent, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import {
  UserCheck,
  CheckCircle,
  XCircle,
  Edit3,
  AlertTriangle,
  Clock,
  ShieldAlert,
  ArrowRight,
  Sparkles,
  HelpCircle,
  FileCheck,
} from 'lucide-react';
import { HITLCheckpoint } from '@/types/schema';

interface HITLModalProps {
  checkpoint: HITLCheckpoint | null;
  isOpen: boolean;
  isSubmitting: boolean;
  onSubmitDecision: (params: {
    checkpointId: string;
    decision: 'approve' | 'reject' | 'modify' | 'skip';
    feedback?: string;
    modifications?: Record<string, any>;
  }) => void;
  onClose: () => void;
}

export const HITLModal: React.FC<HITLModalProps> = ({
  checkpoint,
  isOpen,
  isSubmitting,
  onSubmitDecision,
  onClose,
}) => {
  const [selectedDecision, setSelectedDecision] = useState<'approve' | 'modify' | 'reject'>('approve');
  const [feedback, setFeedback] = useState<string>('');
  const [modificationsText, setModificationsText] = useState<string>('{\n  "timeline_weeks": 12,\n  "contingency_budget_percent": 15\n}');

  if (!isOpen || !checkpoint) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting) return;

    let parsedModifications = undefined;
    if (selectedDecision === 'modify') {
      try {
        parsedModifications = JSON.parse(modificationsText);
      } catch (err) {
        alert('Invalid JSON in modifications field');
        return;
      }
    }

    if (selectedDecision === 'reject' && !feedback.trim()) {
      alert('Please provide feedback explaining why this checkpoint is being rejected so agents can revise.');
      return;
    }

    onSubmitDecision({
      checkpointId: checkpoint.checkpoint_id,
      decision: selectedDecision,
      feedback: feedback.trim() || undefined,
      modifications: parsedModifications,
    });
  };

  const getCheckpointBadge = (type: string) => {
    switch (type) {
      case 'findings_review':
        return 'Specialist Findings Gate';
      case 'pre_negotiation_approval':
        return 'Pre-Negotiation Alignment Gate';
      case 'post_negotiation_review':
        return 'Negotiation Outcome Gate';
      case 'pre_synthesis_approval':
        return 'Final Recommendation Sign-Off';
      default:
        return 'Human Approval Gate';
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent className="max-w-2xl bg-card border border-border p-0 overflow-hidden shadow-2xl">
        {/* Modal Header */}
        <div className="p-6 border-b border-border bg-muted/40">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center text-primary shrink-0">
              <UserCheck className="w-5 h-5" />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[10px] font-mono font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-primary/20 text-primary border border-primary/30">
                  {getCheckpointBadge(checkpoint.checkpoint_type)}
                </span>
                <span className="text-xs font-mono text-muted-foreground">{checkpoint.checkpoint_id}</span>
              </div>
              <DialogTitle className="text-base font-bold text-foreground">
                {checkpoint.title}
              </DialogTitle>
              <DialogDescription className="text-xs text-muted-foreground mt-1">
                {checkpoint.description || 'Deliberation has paused for human review before proceeding to the next stage.'}
              </DialogDescription>
            </div>
          </div>
        </div>

        {/* Experiment Context Banner */}
        <div className="px-6 py-2.5 bg-primary/5 border-b border-border text-[11px] text-muted-foreground flex items-center justify-between">
          <span className="font-medium text-foreground flex items-center gap-1.5">
            <FileCheck className="w-3.5 h-3.5 text-primary" />
            Human-in-the-Loop (HITL) Checkpoint Gate
          </span>
          <span>Stage: <strong className="text-foreground">{checkpoint.stage}</strong></span>
        </div>

        {/* Context Payload Preview */}
        {checkpoint.payload && Object.keys(checkpoint.payload).length > 0 && (
          <div className="px-6 py-3 border-b border-border bg-muted/20">
            <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider block mb-1">
              Checkpoint Deliberation Context:
            </span>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {Object.entries(checkpoint.payload).map(([key, val]) => (
                <div key={key} className="p-2 rounded bg-card border border-border text-xs">
                  <span className="text-[10px] text-muted-foreground block capitalize">{key.replace(/_/g, ' ')}</span>
                  <span className="font-semibold text-foreground">{String(val)}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Decision Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground block">
            Select Your Steering Action:
          </label>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
            {/* Option 1: Approve */}
            <div
              onClick={() => setSelectedDecision('approve')}
              className={`p-3.5 rounded-lg border cursor-pointer transition-all ${
                selectedDecision === 'approve'
                  ? 'bg-emerald-500/10 border-emerald-500 ring-2 ring-emerald-500/20'
                  : 'bg-card border-border hover:border-border'
              }`}
            >
              <div className="flex items-center gap-2 mb-1">
                <CheckCircle className={`w-4 h-4 ${selectedDecision === 'approve' ? 'text-emerald-400' : 'text-muted-foreground'}`} />
                <span className="text-xs font-bold text-foreground">Approve</span>
              </div>
              <p className="text-[11px] text-muted-foreground">
                Sign off on current stage and allow agents to proceed autonomously.
              </p>
            </div>

            {/* Option 2: Modify */}
            <div
              onClick={() => setSelectedDecision('modify')}
              className={`p-3.5 rounded-lg border cursor-pointer transition-all ${
                selectedDecision === 'modify'
                  ? 'bg-amber-500/10 border-amber-500 ring-2 ring-amber-500/20'
                  : 'bg-card border-border hover:border-border'
              }`}
            >
              <div className="flex items-center gap-2 mb-1">
                <Edit3 className={`w-4 h-4 ${selectedDecision === 'modify' ? 'text-amber-400' : 'text-muted-foreground'}`} />
                <span className="text-xs font-bold text-foreground">Modify</span>
              </div>
              <p className="text-[11px] text-muted-foreground">
                Inject custom constraints, parameters, or guidance before continuing.
              </p>
            </div>

            {/* Option 3: Reject */}
            <div
              onClick={() => setSelectedDecision('reject')}
              className={`p-3.5 rounded-lg border cursor-pointer transition-all ${
                selectedDecision === 'reject'
                  ? 'bg-rose-500/10 border-rose-500 ring-2 ring-rose-500/20'
                  : 'bg-card border-border hover:border-border'
              }`}
            >
              <div className="flex items-center gap-2 mb-1">
                <XCircle className={`w-4 h-4 ${selectedDecision === 'reject' ? 'text-rose-400' : 'text-muted-foreground'}`} />
                <span className="text-xs font-bold text-foreground">Reject</span>
              </div>
              <p className="text-[11px] text-muted-foreground">
                Reject findings/compromise and require agents to re-evaluate with feedback.
              </p>
            </div>
          </div>

          {/* Conditional Input: Modification JSON */}
          {selectedDecision === 'modify' && (
            <div className="space-y-1">
              <label className="text-[11px] font-semibold text-muted-foreground block">
                Parameter Overrides (JSON):
              </label>
              <textarea
                value={modificationsText}
                onChange={(e) => setModificationsText(e.target.value)}
                rows={3}
                className="w-full p-2.5 rounded-md bg-muted border border-border font-mono text-xs text-foreground outline-none focus:border-amber-400"
              />
            </div>
          )}

          {/* Feedback Input */}
          <div className="space-y-1">
            <label className="text-[11px] font-semibold text-muted-foreground block">
              {selectedDecision === 'reject' ? 'Revision Instructions (Required):' : 'Executive Guidance / Feedback (Optional):'}
            </label>
            <textarea
              placeholder={
                selectedDecision === 'reject'
                  ? 'Explain why this output is unacceptable and what specific changes agents must make...'
                  : 'Add any nuance or strategic directives for the agents...'
              }
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              rows={2}
              className="w-full p-2.5 rounded-md bg-muted border border-border text-xs text-foreground outline-none focus:border-primary placeholder:text-muted-foreground"
            />
          </div>

          {/* Actions */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-border">
            <Button
              type="button"
              variant="ghost"
              onClick={onClose}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              Decide Later
            </Button>
            <Button
              type="submit"
              disabled={isSubmitting}
              className={`text-xs font-bold flex items-center gap-2 ${
                selectedDecision === 'approve'
                  ? 'bg-emerald-600 hover:bg-emerald-500 text-white'
                  : selectedDecision === 'modify'
                  ? 'bg-amber-600 hover:bg-amber-500 text-white'
                  : 'bg-rose-600 hover:bg-rose-500 text-white'
              }`}
            >
              <UserCheck className="w-4 h-4" />
              {isSubmitting ? 'Recording Decision...' : 'Inject Human Decision & Resume'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
};

