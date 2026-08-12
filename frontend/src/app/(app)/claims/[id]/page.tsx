import Link from 'next/link';
import { ArrowLeft, AlertTriangle, FileText, Quote } from 'lucide-react';
import GenerateAppealButton from '@/components/GenerateAppealButton';
import { API_V1_SERVER } from '@/lib/api';
import {
  ADJUDICATION,
  formatCurrency,
  presentStatus,
  TONE_CLASS,
  type AdjudicationStatus,
} from '@/lib/claimStatus';

export const dynamic = 'force-dynamic';

type Finding = {
  status: AdjudicationStatus;
  reason: string;
  policy_clause_cited: string | null;
  original_clause_text: string | null;
  page_number: number | null;
  confidence: number;
  capped_amount: number | null;
};

type Item = {
  id: string;
  category: string;
  description: string;
  billed_amount: number;
  allowed_amount: number | null;
  procedure_code: string | null;
  audit: Finding | null;
};

type RiskSignal = {
  code: string;
  title: string;
  detail: string;
  direction: 'AGGRAVATING' | 'MITIGATING';
  weight: number;
};

type ClaimDetail = {
  id: string;
  reference: string;
  status: string;
  total_billed: number;
  total_approved: number | null;
  currency: string;
  claimant_name: string | null;
  provider_name: string | null;
  failure_reason: string | null;
  items: Item[];
  risk: { score: number; band: string; signal_count: number } | null;
  signals: RiskSignal[];
};

async function getClaimDetails(id: string): Promise<ClaimDetail | null> {
  try {
    const res = await fetch(`${API_V1_SERVER}/claims/${id}`, { cache: 'no-store' });
    if (res.status === 404) return null;
    if (!res.ok) throw new Error(`API responded ${res.status}`);
    return await res.json();
  } catch (err) {
    console.error('Could not load claim:', err);
    return null;
  }
}

export default async function ClaimDetailsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const claim = await getClaimDetails(id);

  if (!claim) {
    return (
      <div className="glass-panel p-12 text-center flex flex-col items-center">
        <AlertTriangle className="w-16 h-16 text-rose-500 mb-4" />
        <h2 className="text-xl font-medium text-slate-300 mb-2">Claim not found</h2>
        <p className="text-slate-500 mb-6">
          This claim does not exist, or the API could not be reached.
        </p>
        <Link href="/claims" className="btn-secondary">Back to audit results</Link>
      </div>
    );
  }

  const status = presentStatus(claim.status);
  const disputed = claim.items.filter(
    (i) => i.audit && i.audit.status !== 'APPROVED',
  ).length;

  return (
    <div className="space-y-8">
      <header className="mb-8">
        <Link
          href="/claims"
          className="inline-flex items-center text-slate-400 hover:text-teal-400 transition-colors mb-4 text-sm font-medium"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to audit results
        </Link>

        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-white mb-3 font-mono">
              {claim.reference}
            </h1>
            <div className="flex flex-wrap gap-x-8 gap-y-2 text-sm">
              <span className="text-slate-400">
                Billed{' '}
                <span className="text-slate-100 font-semibold tabular-nums">
                  {formatCurrency(claim.total_billed, claim.currency)}
                </span>
              </span>
              {claim.total_approved !== null && (
                <span className="text-slate-400">
                  Allowed{' '}
                  <span className="text-emerald-300 font-semibold tabular-nums">
                    {formatCurrency(claim.total_approved, claim.currency)}
                  </span>
                </span>
              )}
              <span className="text-slate-400">
                Disputed lines <span className="text-slate-100 font-semibold tabular-nums">{disputed}</span>
              </span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <span className={`px-4 py-2 text-sm font-medium border ${TONE_CLASS[status.tone]}`}>
              {status.label}
            </span>
            {disputed > 0 && <GenerateAppealButton claimId={claim.id} />}
          </div>
        </div>
      </header>

      <div className="space-y-6">
        <h2 className="text-xl font-semibold text-white">Line items and findings</h2>

        {claim.items.map((item) => {
          const audit = item.audit;
          const style = audit ? ADJUDICATION[audit.status] : null;

          return (
            <div
              key={item.id}
              className={`glass-panel p-6 border-l-4 ${style ? style.accent : 'border-l-slate-700'}`}
            >
              <div className="flex flex-col md:flex-row justify-between md:items-start gap-4 mb-4">
                <div>
                  <div className="flex items-center flex-wrap gap-3 mb-2">
                    <span className="text-lg font-medium text-white">{item.description}</span>
                    <span className="px-2.5 py-0.5 bg-white/5 border border-white/10 text-slate-300 text-xs">
                      {item.category}
                    </span>
                    {item.procedure_code && (
                      <span className="px-2.5 py-0.5 bg-white/5 border border-white/10 text-slate-400 text-xs font-mono">
                        {item.procedure_code}
                      </span>
                    )}
                  </div>
                  <p className="text-slate-400 text-sm tabular-nums">
                    Billed{' '}
                    <span className="text-slate-100 font-semibold">
                      {formatCurrency(item.billed_amount, claim.currency)}
                    </span>
                    {audit?.capped_amount != null && (
                      <>
                        {' · '}allowed{' '}
                        <span className="text-amber-300 font-semibold">
                          {formatCurrency(audit.capped_amount, claim.currency)}
                        </span>
                      </>
                    )}
                  </p>
                </div>

                <span
                  className={`shrink-0 px-3 py-1.5 text-sm font-semibold border ${
                    style ? style.chip : 'bg-white/5 text-slate-400 border-white/10'
                  }`}
                >
                  {style ? style.label : 'Not yet audited'}
                </span>
              </div>

              {audit && (
                <div className="mt-4 pt-4 border-t border-white/10">
                  <h4 className="text-slate-300 font-medium mb-2 flex items-center justify-between text-sm">
                    <span className="flex items-center">
                      <FileText className="w-4 h-4 mr-2 text-slate-500" />
                      Reasoning
                    </span>
                    <span className="text-xs text-slate-500 tabular-nums">
                      confidence {(audit.confidence * 100).toFixed(0)}%
                    </span>
                  </h4>
                  <p className="text-slate-400 text-sm leading-relaxed mb-4">{audit.reason}</p>

                  {audit.policy_clause_cited ? (
                    <div className="bg-black/40 p-4 border border-white/10">
                      <p className="text-xs text-slate-500 uppercase tracking-wider font-semibold mb-2 flex justify-between gap-4">
                        <span>{audit.policy_clause_cited}</span>
                        {audit.page_number != null && <span>Page {audit.page_number}</span>}
                      </p>
                      {audit.original_clause_text && (
                        <p className="text-slate-300 text-sm leading-relaxed flex gap-2">
                          <Quote className="w-4 h-4 text-slate-600 shrink-0 mt-0.5" />
                          <span>{audit.original_clause_text}</span>
                        </p>
                      )}
                    </div>
                  ) : (
                    <p className="text-xs text-slate-500 border border-dashed border-white/10 p-3">
                      No policy clause was matched to this line. The verdict rests on the
                      reasoning above alone.
                    </p>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
