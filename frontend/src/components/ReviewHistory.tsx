import { UserCheck, GitBranch, MessageSquare } from 'lucide-react';

type Decision = {
  id: string;
  action: string;
  reason: string;
  previous_ai_outcome: string | null;
  overrides_ai: boolean;
  decided_by: string | null;
  created_at: string;
};

type Note = { id: string; body: string; author: string | null; created_at: string };

type Investigation = {
  id: string;
  title: string;
  status: string;
  resolution: string | null;
  opened_by: string | null;
  assigned_to: string | null;
  notes: Note[];
};

export type Review = {
  decisions: Decision[];
  investigations: Investigation[];
};

const ACTION_LABEL: Record<string, string> = {
  APPROVE: 'Approved',
  REJECT: 'Rejected',
  OVERRIDE: 'Overrode the AI',
  ESCALATE: 'Escalated',
  REQUEST_EVIDENCE: 'Requested evidence',
  CONFIRM_FRAUD: 'Confirmed fraud',
  MARK_FALSE_POSITIVE: 'Marked a false positive',
};

const INVESTIGATION_TONE: Record<string, string> = {
  OPEN: 'text-amber-300 border-amber-500/25',
  IN_PROGRESS: 'text-sky-300 border-sky-500/25',
  RESOLVED: 'text-emerald-300 border-emerald-500/25',
  CLOSED: 'text-slate-400 border-white/15',
};

/**
 * What people have done to this claim.
 *
 * An override shows what it overrode. The model's verdict is not erased by
 * someone disagreeing with it — that pairing is the whole value of the record.
 */
export default function ReviewHistory({ review }: { review: Review }) {
  const { decisions, investigations } = review;

  if (decisions.length === 0 && investigations.length === 0) return null;

  return (
    <section className="glass-panel p-6">
      <h2 className="text-xl font-semibold text-white mb-5">Human review</h2>

      {decisions.length > 0 && (
        <ul className="space-y-3 mb-6">
          {decisions.map((decision) => (
            <li key={decision.id} className="flex gap-3">
              <span className="shrink-0 mt-0.5">
                {decision.overrides_ai ? (
                  <GitBranch className="w-4 h-4 text-amber-400" />
                ) : (
                  <UserCheck className="w-4 h-4 text-slate-500" />
                )}
              </span>

              <div className="min-w-0">
                <p className="text-sm text-slate-200">
                  {ACTION_LABEL[decision.action] ?? decision.action}
                  {decision.decided_by && (
                    <span className="text-slate-500"> · {decision.decided_by}</span>
                  )}
                </p>

                {decision.overrides_ai && decision.previous_ai_outcome && (
                  <p className="text-xs text-amber-200/80 mt-0.5">
                    The AI had decided {decision.previous_ai_outcome.toLowerCase()}.
                  </p>
                )}

                {decision.reason && (
                  <p className="text-xs text-slate-400 mt-1">{decision.reason}</p>
                )}

                <p className="text-xs text-slate-600 mt-1 tabular-nums">
                  {new Date(decision.created_at).toLocaleString()}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}

      {investigations.length > 0 && (
        <div className="space-y-3">
          {investigations.map((investigation) => (
            <div key={investigation.id} className="border border-white/10 bg-black/40 p-4">
              <div className="flex items-start justify-between gap-4 mb-2">
                <p className="text-sm text-slate-200">{investigation.title}</p>
                <span
                  className={`shrink-0 text-xs border px-2 py-0.5 ${
                    INVESTIGATION_TONE[investigation.status] ?? INVESTIGATION_TONE.OPEN
                  }`}
                >
                  {investigation.status.replace('_', ' ').toLowerCase()}
                </span>
              </div>

              <p className="text-xs text-slate-500">
                Opened by {investigation.opened_by ?? 'unknown'}
                {investigation.assigned_to && ` · assigned to ${investigation.assigned_to}`}
              </p>

              {investigation.notes.length > 0 && (
                <ul className="mt-3 space-y-2 border-l border-white/10 pl-3">
                  {investigation.notes.map((note) => (
                    <li key={note.id} className="flex gap-2">
                      <MessageSquare className="w-3.5 h-3.5 text-slate-600 shrink-0 mt-0.5" />
                      <div>
                        <p className="text-xs text-slate-300">{note.body}</p>
                        <p className="text-xs text-slate-600 mt-0.5">
                          {note.author ?? 'unknown'} ·{' '}
                          {new Date(note.created_at).toLocaleString()}
                        </p>
                      </div>
                    </li>
                  ))}
                </ul>
              )}

              {investigation.resolution && (
                <p className="text-xs text-emerald-200/80 mt-3 pt-3 border-t border-white/10">
                  Resolved: {investigation.resolution}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
