import Link from 'next/link';
import { ArrowRight, FileCheck2 } from 'lucide-react';
import PageHeader from '@/components/PageHeader';
import { API_V1_SERVER } from '@/lib/api';
import { authHeaders } from '@/lib/session';
import { formatCurrency, presentStatus, TONE_CLASS, type Claim } from '@/lib/claimStatus';

export const dynamic = 'force-dynamic';

async function getClaims(): Promise<Claim[]> {
  try {
    const res = await fetch(`${API_V1_SERVER}/claims?limit=100`, {
      headers: await authHeaders(),
      cache: 'no-store',
    });
    if (!res.ok) throw new Error(`API responded ${res.status}`);
    return (await res.json()).items;
  } catch (err) {
    console.error('Could not load claims:', err);
    return [];
  }
}

export default async function ClaimsPage() {
  const claims = await getClaims();

  return (
    <div>
      <PageHeader
        eyebrow="Adjudication"
        title="Audit results"
        description="Line-by-line findings for every claim, with the policy clause each verdict rests on."
        actions={
          <Link href="/upload" className="btn">
            New audit
          </Link>
        }
      />

      {claims.length === 0 ? (
        <div className="stamp-in mt-10 flex flex-col items-center border border-dashed border-line-strong px-6 py-20 text-center">
          <FileCheck2 className="h-8 w-8 text-ink-300" strokeWidth={1.4} />
          <h2 className="mt-5 text-lg font-semibold text-ink-900">No claims yet</h2>
          <p className="mt-2 max-w-md text-sm leading-relaxed text-ink-700">
            Upload a hospital bill and the governing policy to run an audit, or load
            the demo claims with{' '}
            <code className="font-mono text-ink-900">python scripts/seed.py</code>.
          </p>
          <Link href="/upload" className="btn mt-7">
            Upload a claim
          </Link>
        </div>
      ) : (
        /* A ruled register rather than a grid of cards: claims are rows in a
           ledger, and a row lets the eye compare references and figures down a
           column instead of hunting across tiles. */
        <section className="stamp-in mt-10">
          <div className="hidden grid-cols-[1fr_10rem_9rem_7rem_1.5rem] gap-4 border-b border-line pb-3 md:grid">
            <span className="eyebrow">Reference</span>
            <span className="eyebrow">Status</span>
            <span className="eyebrow text-right">Total billed</span>
            <span className="eyebrow text-right">Received</span>
            <span />
          </div>

          {claims.map((claim) => {
            const status = presentStatus(claim.status);

            return (
              <Link
                key={claim.id}
                href={`/claims/${claim.id}`}
                className="group grid grid-cols-1 gap-2 border-b border-line px-1 py-4 transition-colors hover:bg-mist md:grid-cols-[1fr_10rem_9rem_7rem_1.5rem] md:items-center md:gap-4"
              >
                <span className="font-mono text-sm text-ink-900">
                  {claim.reference}
                </span>

                <span>
                  <span className={`chip ${TONE_CLASS[status.tone]}`}>
                    {status.label}
                  </span>
                </span>

                <span className="font-mono text-sm tabular-nums text-ink-900 md:text-right">
                  {formatCurrency(claim.total_billed, claim.currency)}
                </span>

                <span className="font-mono text-sm tabular-nums text-ink-500 md:text-right">
                  {new Date(claim.created_at).toLocaleDateString()}
                </span>

                <ArrowRight className="hidden h-4 w-4 text-ink-300 transition-all group-hover:translate-x-0.5 group-hover:text-ink-900 md:block" />
              </Link>
            );
          })}
        </section>
      )}
    </div>
  );
}
