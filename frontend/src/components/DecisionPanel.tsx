'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { AlertTriangle, ArrowUpRight, Check, Loader2, ShieldAlert, X } from 'lucide-react';

import { API_V1, readError } from '@/lib/api';

type Action =
  | 'APPROVE'
  | 'REJECT'
  | 'OVERRIDE'
  | 'ESCALATE'
  | 'REQUEST_EVIDENCE'
  | 'CONFIRM_FRAUD'
  | 'MARK_FALSE_POSITIVE';

/**
 * Controls for deciding a single line item.
 *
 * Only rendered for a caller who holds the capability; the server enforces the
 * same rule independently, so hiding a control is a courtesy rather than a
 * security boundary.
 *
 * Overriding requires a written reason, because the record of *why* someone
 * disagreed with the model is the part that has value six months later.
 */
export default function DecisionPanel({
  claimId,
  itemId,
  currentStatus,
  canDecide,
}: {
  claimId: string;
  itemId: string;
  currentStatus: string | null;
  canDecide: boolean;
}) {
  const router = useRouter();
  const [pending, setPending] = useState<Action | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reasonFor, setReasonFor] = useState<Action | null>(null);
  const [reason, setReason] = useState('');

  if (!canDecide) return null;

  const submit = async (action: Action, overrideStatus?: string) => {
    setPending(action);
    setError(null);

    try {
      const res = await fetch(`${API_V1}/claims/${claimId}/decisions`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action,
          claim_item_id: itemId,
          reason,
          override_status: overrideStatus ?? null,
        }),
      });

      if (!res.ok) throw new Error(await readError(res, 'Could not record the decision.'));

      setReason('');
      setReasonFor(null);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not record the decision.');
    } finally {
      setPending(null);
    }
  };

  /**
   * Which action means "I agree with the model" for this verdict.
   *
   * Only two of the model's four outcomes have an action that expresses
   * agreement. REJECT lands the item on REJECTED, so offering it as agreement
   * with a CAPPED or NEEDS_REVIEW finding would record the wrong verdict. A
   * capped line was partly allowed, not refused. Those get escalation instead,
   * which is the honest move: the reviewer has nothing to sign off with.
   */
  const agreeAction: Action | null =
    currentStatus === 'APPROVED'
      ? 'APPROVE'
      : currentStatus === 'REJECTED'
        ? 'REJECT'
        : null;

  const opposite = currentStatus === 'APPROVED' ? 'REJECTED' : 'APPROVED';

  // Only APPROVE is accepted without one; the server rejects the rest outright.
  const REASON_REQUIRED: Action[] = [
    'OVERRIDE',
    'REJECT',
    'CONFIRM_FRAUD',
    'MARK_FALSE_POSITIVE',
    'ESCALATE',
  ];

  const REASON_PROMPT: Partial<Record<Action, string>> = {
    OVERRIDE: `Why are you changing this to ${opposite.toLowerCase()}?`,
    REJECT: 'Why do you agree with this rejection?',
    CONFIRM_FRAUD: 'What makes this fraudulent?',
    ESCALATE: 'Why does this need a second opinion?',
  };

  /** Straight through when no reason is needed, otherwise open the box. */
  const start = (action: Action) => {
    if (REASON_REQUIRED.includes(action)) {
      setReasonFor(action);
      setError(null);
    } else {
      submit(action);
    }
  };

  return (
    <div className="mt-5 border-t border-line pt-5">
      {error && (
        <p className="mb-3 flex items-start gap-2 text-xs text-rejected">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          {error}
        </p>
      )}

      {reasonFor ? (
        <div>
          <label className="eyebrow block" htmlFor={`reason-${itemId}`}>
            {REASON_PROMPT[reasonFor] ?? 'Reason'}
          </label>
          <textarea
            id={`reason-${itemId}`}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={2}
            autoFocus
            className="field mt-3"
            placeholder="Recorded against your name on the claim’s history."
          />
          <div className="mt-3 flex items-center gap-2">
            <button
              onClick={() =>
                submit(reasonFor, reasonFor === 'OVERRIDE' ? opposite : undefined)
              }
              disabled={!reason.trim() || pending !== null}
              className="btn px-4 py-2 text-xs"
            >
              {pending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                'Save decision'
              )}
            </button>
            <button
              onClick={() => {
                setReasonFor(null);
                setReason('');
                setError(null);
              }}
              className="px-3 py-2 text-xs text-ink-500 transition-colors hover:text-ink-900"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          {agreeAction ? (
            <Button
              onClick={() => start(agreeAction)}
              busy={pending === agreeAction}
              icon={<Check className="h-3.5 w-3.5" />}
              label="Agree with AI"
              tone="border-verified-line bg-verified-soft text-verified hover:border-verified"
            />
          ) : (
            <Button
              onClick={() => start('ESCALATE')}
              busy={pending === 'ESCALATE'}
              icon={<ArrowUpRight className="h-3.5 w-3.5" />}
              label="Escalate"
              tone="border-review-line bg-review-soft text-review hover:border-review"
            />
          )}
          <Button
            onClick={() => start('OVERRIDE')}
            icon={<X className="h-3.5 w-3.5" />}
            label={`Override to ${opposite.toLowerCase()}`}
            tone="border-capped-line bg-capped-soft text-capped hover:border-capped"
          />
          <Button
            onClick={() => start('CONFIRM_FRAUD')}
            icon={<ShieldAlert className="h-3.5 w-3.5" />}
            label="Confirm fraud"
            tone="border-rejected-line bg-rejected-soft text-rejected hover:border-rejected"
          />
        </div>
      )}
    </div>
  );
}

function Button({
  onClick,
  label,
  icon,
  tone,
  busy = false,
}: {
  onClick: () => void;
  label: string;
  icon: React.ReactNode;
  tone: string;
  busy?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={busy}
      className={`inline-flex items-center gap-1.5 rounded-[2px] border px-2.5 py-1.5 text-xs font-medium transition-colors disabled:opacity-40 ${tone}`}
    >
      {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : icon}
      {label}
    </button>
  );
}
