import Link from 'next/link';
import { ArrowRight, FileCheck2 } from 'lucide-react';
import { API_V1_SERVER } from '@/lib/api';
import { formatCurrency, presentStatus, TONE_CLASS, type Claim } from '@/lib/claimStatus';

export const dynamic = 'force-dynamic';

async function getClaims(): Promise<Claim[]> {
  try {
    const res = await fetch(`${API_V1_SERVER}/claims?limit=100`, { cache: 'no-store' });
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
    <div className="space-y-8">
      <header className="mb-10 flex items-end justify-between gap-6">
        <div>
          <h1 className="text-4xl font-bold tracking-tight text-white mb-2">Audit results</h1>
          <p className="text-slate-400 text-lg">
            Line-by-line findings for every claim, with the policy clause each verdict rests on.
          </p>
        </div>
        <Link href="/upload" className="btn-primary shrink-0">+ New audit</Link>
      </header>

      {claims.length === 0 ? (
        <div className="glass-panel p-12 text-center flex flex-col items-center">
          <FileCheck2 className="w-16 h-16 text-slate-600 mb-4" />
          <h2 className="text-xl font-medium text-slate-300 mb-2">No claims yet</h2>
          <p className="text-slate-500 max-w-md">
            Upload a hospital bill and the governing policy to run an audit, or load the demo
            claims with <code className="text-slate-400">python scripts/seed.py</code>.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {claims.map((claim) => {
            const status = presentStatus(claim.status);
            return (
              <Link key={claim.id} href={`/claims/${claim.id}`}>
                <div className="glass-panel p-6 hover:border-white/30 transition-colors group h-full flex flex-col">
                  <div className="flex justify-between items-start mb-4 gap-3">
                    <span className={`px-3 py-1 text-xs font-medium border ${TONE_CLASS[status.tone]}`}>
                      {status.label}
                    </span>
                    <ArrowRight className="w-5 h-5 text-slate-600 group-hover:text-teal-400 transition-colors shrink-0" />
                  </div>

                  <h3 className="text-lg font-medium text-white mb-1 font-mono tracking-tight">
                    {claim.reference}
                  </h3>

                  <div className="mt-auto pt-4 flex justify-between items-end">
                    <div>
                      <p className="text-slate-500 text-xs mb-1">Total billed</p>
                      <p className="text-xl font-semibold text-slate-200 tabular-nums">
                        {formatCurrency(claim.total_billed, claim.currency)}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-slate-500 text-xs mb-1">Received</p>
                      <p className="text-slate-400 text-sm tabular-nums">
                        {new Date(claim.created_at).toLocaleDateString()}
                      </p>
                    </div>
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
