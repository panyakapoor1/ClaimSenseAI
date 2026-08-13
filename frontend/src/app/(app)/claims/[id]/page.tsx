import Link from 'next/link';
import { ArrowLeft, AlertTriangle, Quote } from 'lucide-react';
import GenerateAppealButton from '@/components/GenerateAppealButton';
import EvidencePanel, { type Evidence } from '@/components/EvidencePanel';
import RiskPanel, { type Risk, type RiskSignal } from '@/components/RiskPanel';
import ReviewHistory, { type Review } from '@/components/ReviewHistory';
import DecisionPanel from '@/components/DecisionPanel';
import { CAPABILITIES } from '@/lib/roles';
import { getSession } from '@/lib/session';
import { API_V1_SERVER } from '@/lib/api';
import { authHeaders } from '@/lib/session';
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
  risk: Risk | null;
  signals: RiskSignal[];
};

async function getClaimDetails(id: string): Promise<ClaimDetail | null> {
  try {
    const res = await fetch(`${API_V1_SERVER}/claims/${id}`, {
      headers: await authHeaders(),
      cache: 'no-store',
    });
    if (res.status === 404) return null;
    if (!res.ok) throw new Error(`API responded ${res.status}`);
    return await res.json();
  } catch (err) {
    console.error('Could not load claim:', err);
    return null;
  }
}

async function getEvidence(id: string): Promise<Evidence | null> {
  try {
    const res = await fetch(`${API_V1_SERVER}/claims/${id}/evidence`, {
      headers: await authHeaders(),
      cache: 'no-store',
    });
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.error('Could not load evidence:', err);
    return null;
  }
}

async function getReview(id: string): Promise<Review | null> {
  try {
    const res = await fetch(`${API_V1_SERVER}/claims/${id}/review`, {
      headers: await authHeaders(),
      cache: 'no-store',
    });
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.error('Could not load review history:', err);
    return null;
  }
}

export default async function ClaimDetailsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  // Fetched together: the requests are independent, and awaiting them in
  // sequence would multiply the page's time to first byte.
  const [claim, evidence, review, session] = await Promise.all([
    getClaimDetails(id),
    getEvidence(id),
    getReview(id),
    getSession(),
  ]);

  const canDecide = Boolean(session?.capabilities.includes(CAPABILITIES.decideClaims));

  if (!claim) {
    return (
      <div className="stamp-in flex flex-col items-center border border-dashed border-line-strong px-6 py-20 text-center">
        <AlertTriangle className="h-8 w-8 text-rejected" strokeWidth={1.4} />
        <h2 className="mt-5 text-lg font-semibold text-ink-900">Claim not found</h2>
        <p className="mt-2 max-w-md text-sm text-ink-700">
          This claim does not exist, or the API could not be reached.
        </p>
        <Link href="/claims" className="btn-ghost mt-7">
          Back to audit results
        </Link>
      </div>
    );
  }

  const status = presentStatus(claim.status);
  const disputed = claim.items.filter(
    (i) => i.audit && i.audit.status !== 'APPROVED',
  ).length;

  return (
    <div>
      <header className="stamp-in">
        <Link
          href="/claims"
          className="group inline-flex items-center gap-2 text-sm text-ink-500 transition-colors hover:text-ink-900"
        >
          <ArrowLeft className="h-4 w-4 transition-transform group-hover:-translate-x-0.5" />
          Audit results
        </Link>

        <div className="mt-6 flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div className="min-w-0">
            <p className="eyebrow">Claim</p>
            <h1 className="display mt-3 font-mono text-3xl text-ink-900 md:text-4xl">
              {claim.reference}
            </h1>
            {(claim.claimant_name || claim.provider_name) && (
              <p className="mt-3 text-sm text-ink-500">
                {[claim.claimant_name, claim.provider_name]
                  .filter(Boolean)
                  .join(' · ')}
              </p>
            )}
          </div>

          <div className="flex shrink-0 flex-wrap items-center gap-3">
            <span className={`chip ${TONE_CLASS[status.tone]}`}>{status.label}</span>
            {disputed > 0 && <GenerateAppealButton claimId={claim.id} />}
          </div>
        </div>

        {claim.failure_reason && (
          <div className="mt-6 flex items-start gap-3 border border-rejected-line bg-rejected-soft p-4">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-rejected" />
            <p className="text-sm text-rejected">{claim.failure_reason}</p>
          </div>
        )}

        <div className="mt-8 grid grid-cols-1 gap-px border border-line bg-line sm:grid-cols-3">
          <Figure label="Total billed">
            {formatCurrency(claim.total_billed, claim.currency)}
          </Figure>
          <Figure label="Allowed" tone={claim.total_approved !== null ? 'verified' : 'muted'}>
            {claim.total_approved !== null
              ? formatCurrency(claim.total_approved, claim.currency)
              : 'Not yet adjudicated'}
          </Figure>
          <Figure label="Disputed lines" tone={disputed > 0 ? 'rejected' : 'ink'}>
            {String(disputed)}
          </Figure>
        </div>
      </header>

      <div className="mt-10 space-y-6">
        <RiskPanel risk={claim.risk} signals={claim.signals} />
        {review && <ReviewHistory review={review} />}
        {evidence && <EvidencePanel evidence={evidence} />}
      </div>

      <section className="mt-12">
        <p className="eyebrow">Line items and findings</p>
        <div className="rule mt-4" />

        <div className="mt-6 space-y-4">
          {claim.items.map((item) => {
            const audit = item.audit;
            const style = audit ? ADJUDICATION[audit.status] : null;

            return (
              <article
                key={item.id}
                className={`panel border-l-[3px] p-6 ${
                  style ? style.accent : 'border-l-line-strong'
                }`}
              >
                <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-medium text-ink-900">{item.description}</h3>
                      <span className="chip border-line bg-mist text-ink-500">
                        {item.category}
                      </span>
                      {item.procedure_code && (
                        <span className="chip border-line bg-mist font-mono text-ink-500">
                          {item.procedure_code}
                        </span>
                      )}
                    </div>

                    <p className="mt-2 font-mono text-sm tabular-nums text-ink-500">
                      Billed{' '}
                      <span className="text-ink-900">
                        {formatCurrency(item.billed_amount, claim.currency)}
                      </span>
                      {audit?.capped_amount != null && (
                        <>
                          {' · allowed '}
                          <span className="text-capped">
                            {formatCurrency(audit.capped_amount, claim.currency)}
                          </span>
                        </>
                      )}
                    </p>
                  </div>

                  <span
                    className={`chip shrink-0 ${
                      style ? style.chip : 'border-line bg-mist text-ink-500'
                    }`}
                  >
                    {style ? style.label : 'Not yet audited'}
                  </span>
                </div>

                {audit && (
                  <div className="mt-5 border-t border-line pt-5">
                    <div className="flex items-baseline justify-between gap-4">
                      <p className="eyebrow">Reasoning</p>
                      {/* Labelled as the model's own view, because it is: the
                          figure is a self-assessment and is not calibrated. */}
                      <span className="font-mono text-[0.6875rem] tabular-nums text-ink-300">
                        self-rated {(audit.confidence * 100).toFixed(0)}%
                      </span>
                    </div>

                    <p className="mt-3 text-sm leading-relaxed text-ink-700">
                      {audit.reason}
                    </p>

                    {audit.policy_clause_cited ? (
                      <figure className="well mt-4 p-4">
                        <figcaption className="flex flex-wrap justify-between gap-3">
                          <span className="eyebrow">{audit.policy_clause_cited}</span>
                          {audit.page_number != null && (
                            <span className="eyebrow">Page {audit.page_number}</span>
                          )}
                        </figcaption>
                        {audit.original_clause_text && (
                          <blockquote className="mt-3 flex gap-2.5 text-sm leading-relaxed text-ink-900">
                            <Quote className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ink-300" />
                            <span>{audit.original_clause_text}</span>
                          </blockquote>
                        )}
                      </figure>
                    ) : (
                      <p className="mt-4 border border-dashed border-line-strong p-3 text-xs leading-relaxed text-ink-500">
                        No policy clause was matched to this line. The verdict rests
                        on the reasoning above alone.
                      </p>
                    )}

                    <DecisionPanel
                      claimId={claim.id}
                      itemId={item.id}
                      currentStatus={audit.status}
                      canDecide={canDecide}
                    />
                  </div>
                )}
              </article>
            );
          })}
        </div>
      </section>
    </div>
  );
}

function Figure({
  label,
  children,
  tone = 'ink',
}: {
  label: string;
  children: React.ReactNode;
  tone?: 'ink' | 'verified' | 'rejected' | 'muted';
}) {
  const toneClass = {
    ink: 'text-ink-900',
    verified: 'text-verified',
    rejected: 'text-rejected',
    muted: 'text-ink-300',
  }[tone];

  return (
    <div className="bg-surface p-5">
      <p className="eyebrow">{label}</p>
      <p className={`mt-3 font-mono text-xl tabular-nums ${toneClass}`}>{children}</p>
    </div>
  );
}
