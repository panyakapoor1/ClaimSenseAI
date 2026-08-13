import Link from 'next/link';
import { FileText, ArrowRight } from 'lucide-react';
import PageHeader from '@/components/PageHeader';
import { API_V1_SERVER } from '@/lib/api';
import { authHeaders } from '@/lib/session';
import { formatCurrency, type Claim } from '@/lib/claimStatus';

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

export default async function AppealsListPage() {
  const claims = await getClaims();

  // Only claims that actually have a letter. The previous version listed every
  // claim as though each had an appeal, so most rows led to an empty page.
  const drafted = claims.filter((claim) => claim.status === 'APPEAL_GENERATED');

  return (
    <div>
      <PageHeader
        eyebrow="Correspondence"
        title="Appeals"
        description="Letters drafted against the clause used to reject each disputed charge."
      />

      {drafted.length === 0 ? (
        <div className="stamp-in mt-10 flex flex-col items-center border border-dashed border-line-strong px-6 py-20 text-center">
          <FileText className="h-8 w-8 text-ink-300" strokeWidth={1.4} />
          <h2 className="mt-5 text-lg font-semibold text-ink-900">
            No appeals drafted yet
          </h2>
          <p className="mt-2 max-w-md text-sm leading-relaxed text-ink-700">
            An appeal is drafted from a claim that has disputed lines. Open an
            audited claim and draft one from there.
          </p>
          <Link href="/claims" className="btn mt-7">
            Go to audit results
          </Link>
        </div>
      ) : (
        <section className="stamp-in mt-10">
          <div className="hidden grid-cols-[1fr_9rem_7rem_1.5rem] gap-4 border-b border-line pb-3 md:grid">
            <span className="eyebrow">Claim</span>
            <span className="eyebrow text-right">Total billed</span>
            <span className="eyebrow text-right">Received</span>
            <span />
          </div>

          {drafted.map((claim) => (
            <Link
              key={claim.id}
              href={`/appeals/${claim.id}`}
              className="group grid grid-cols-1 gap-2 border-b border-line px-1 py-4 transition-colors hover:bg-mist md:grid-cols-[1fr_9rem_7rem_1.5rem] md:items-center md:gap-4"
            >
              <span className="font-mono text-sm text-ink-900">{claim.reference}</span>

              <span className="font-mono text-sm tabular-nums text-ink-900 md:text-right">
                {formatCurrency(claim.total_billed, claim.currency)}
              </span>

              <span className="font-mono text-sm tabular-nums text-ink-500 md:text-right">
                {new Date(claim.created_at).toLocaleDateString()}
              </span>

              <ArrowRight className="hidden h-4 w-4 text-ink-300 transition-all group-hover:translate-x-0.5 group-hover:text-ink-900 md:block" />
            </Link>
          ))}
        </section>
      )}
    </div>
  );
}
