'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { AlertTriangle, Check, Loader2, ShieldAlert, X } from 'lucide-react';

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

  const agreeing = currentStatus === 'APPROVED' ? 'APPROVE' : 'REJECT';
  const opposite = currentStatus === 'APPROVED' ? 'REJECTED' : 'APPROVED';

  return (
    <div className="mt-4 pt-4 border-t border-white/10">
      {error && (
        <p className="text-xs text-rose-300 mb-3 flex items-start gap-2">
          <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
          {error}
        </p>
      )}

      {reasonFor ? (
        <div className="space-y-2">
          <label className="text-xs text-slate-400 block">
            {reasonFor === 'OVERRIDE'
              ? `Why are you changing this to ${opposite.toLowerCase()}?`
              : 'Reason'}
          </label>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={2}
            autoFocus
            className="glass-input w-full text-sm p-2"
            placeholder="Recorded against your name on the claim's history."
          />
          <div className="flex gap-2">
            <button
              onClick={() =>
                submit(reasonFor, reasonFor === 'OVERRIDE' ? opposite : undefined)
              }
              disabled={!reason.trim() || pending !== null}
              className="btn-primary text-xs py-1.5 px-3 disabled:opacity-40"
            >
              {pending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Save decision'}
            </button>
            <button
              onClick={() => {
                setReasonFor(null);
                setReason('');
                setError(null);
              }}
              className="text-xs text-slate-400 hover:text-slate-200 px-3"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          <Button
            onClick={() => submit(agreeing)}
            busy={pending === agreeing}
            icon={<Check className="w-3.5 h-3.5" />}
            label="Agree with AI"
            tone="text-emerald-300 border-emerald-500/25 hover:bg-emerald-500/10"
          />
          <Button
            onClick={() => setReasonFor('OVERRIDE')}
            icon={<X className="w-3.5 h-3.5" />}
            label={`Override to ${opposite.toLowerCase()}`}
            tone="text-amber-300 border-amber-500/25 hover:bg-amber-500/10"
          />
          <Button
            onClick={() => setReasonFor('CONFIRM_FRAUD')}
            icon={<ShieldAlert className="w-3.5 h-3.5" />}
            label="Confirm fraud"
            tone="text-rose-300 border-rose-500/25 hover:bg-rose-500/10"
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
      className={`inline-flex items-center gap-1.5 text-xs border px-2.5 py-1.5 transition-colors disabled:opacity-40 ${tone}`}
    >
      {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : icon}
      {label}
    </button>
  );
}
