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
  OPEN: 'border-capped-line bg-capped-soft text-capped',
  IN_PROGRESS: 'border-review-line bg-review-soft text-review',
  RESOLVED: 'border-verified-line bg-verified-soft text-verified',
  CLOSED: 'border-line bg-mist text-ink-500',
};

/**
 * What people have done to this claim.
 *
 * An override shows what it overrode. The model's verdict is not erased by
 * someone disagreeing with it, and that pairing is the whole value of the record.
 */
export default function ReviewHistory({ review }: { review: Review }) {
  const { decisions, investigations } = review;

  if (decisions.length === 0 && investigations.length === 0) return null;

  return (
    <section className="panel p-6">
      <p className="eyebrow">Human review</p>

      {decisions.length > 0 && (
        /* A ruled timeline: the left hairline is what makes a list of actions
           read as a sequence rather than as unrelated events. */
        <ol className="mt-6 space-y-5 border-l border-line pl-5">
          {decisions.map((decision) => (
            <li key={decision.id} className="relative">
              <span className="absolute -left-[1.4375rem] top-1 flex h-3.5 w-3.5 items-center justify-center bg-surface">
                {decision.overrides_ai ? (
                  <GitBranch className="h-3.5 w-3.5 text-capped" strokeWidth={1.8} />
                ) : (
                  <UserCheck className="h-3.5 w-3.5 text-ink-300" strokeWidth={1.8} />
                )}
              </span>

              <p className="text-sm text-ink-900">
                {ACTION_LABEL[decision.action] ?? decision.action}
                {decision.decided_by && (
                  <span className="text-ink-500"> · {decision.decided_by}</span>
                )}
              </p>

              {decision.overrides_ai && decision.previous_ai_outcome && (
                <p className="mt-1 text-xs text-capped">
                  The AI had decided {decision.previous_ai_outcome.toLowerCase()}.
                </p>
              )}

              {decision.reason && (
                <p className="mt-1.5 text-sm leading-relaxed text-ink-700">
                  {decision.reason}
                </p>
              )}

              <p className="mt-1.5 font-mono text-xs tabular-nums text-ink-300">
                {new Date(decision.created_at).toLocaleString()}
              </p>
            </li>
          ))}
        </ol>
      )}

      {investigations.length > 0 && (
        <div className="mt-6 space-y-3">
          {investigations.map((investigation) => (
            <div key={investigation.id} className="well p-4">
              <div className="flex items-start justify-between gap-4">
                <p className="text-sm font-medium text-ink-900">
                  {investigation.title}
                </p>
                <span
                  className={`chip shrink-0 ${
                    INVESTIGATION_TONE[investigation.status] ?? INVESTIGATION_TONE.OPEN
                  }`}
                >
                  {investigation.status.replace('_', ' ').toLowerCase()}
                </span>
              </div>

              <p className="mt-2 text-xs text-ink-500">
                Opened by {investigation.opened_by ?? 'unknown'}
                {investigation.assigned_to && ` · assigned to ${investigation.assigned_to}`}
              </p>

              {investigation.notes.length > 0 && (
                <ul className="mt-4 space-y-3 border-l border-line-strong pl-4">
                  {investigation.notes.map((note) => (
                    <li key={note.id} className="flex gap-2">
                      <MessageSquare
                        className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ink-300"
                        strokeWidth={1.8}
                      />
                      <div>
                        <p className="text-sm leading-relaxed text-ink-700">
                          {note.body}
                        </p>
                        <p className="mt-1 font-mono text-xs text-ink-300">
                          {note.author ?? 'unknown'} ·{' '}
                          {new Date(note.created_at).toLocaleString()}
                        </p>
                      </div>
                    </li>
                  ))}
                </ul>
              )}

              {investigation.resolution && (
                <p className="mt-4 border-t border-line pt-3 text-sm text-verified">
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
