import Link from 'next/link';
import { ArrowRight, FileCheck2, Clock, AlertCircle } from 'lucide-react';
import { API_URL_SERVER } from '@/lib/api';

export const dynamic = 'force-dynamic';

async function getClaims() {
  try {
    const res = await fetch(`${API_URL_SERVER}/claims/`, { cache: 'no-store' });
    if (!res.ok) throw new Error('Failed to fetch claims');
    return await res.json();
  } catch (err) {
    console.error(err);
    return [];
  }
}

export default async function ClaimsPage() {
  const claims = await getClaims();

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <header className="mb-10 flex items-center justify-between">
        <div>
          <h1 className="text-4xl font-bold tracking-tight text-white mb-2">
            Audit Results
          </h1>
          <p className="text-slate-400 text-lg">
            Review the status and detailed AI findings for your audited claims.
          </p>
        </div>
        <Link href="/upload" className="btn-primary">
          + New Audit
        </Link>
      </header>

      {claims.length === 0 ? (
        <div className="glass-panel p-12 text-center flex flex-col items-center">
          <FileCheck2 className="w-16 h-16 text-slate-600 mb-4" />
          <h2 className="text-xl font-medium text-slate-300 mb-2">No claims found</h2>
          <p className="text-slate-500 max-w-md">
            You haven't uploaded any claims yet. Upload a medical bill and insurance policy to get started.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {claims.map((claim: any) => (
            <Link key={claim.id} href={`/claims/${claim.id}`}>
              <div className="glass-panel p-6 border-slate-700/50 hover:border-teal-500/50 hover:bg-slate-800/80 transition-all cursor-pointer group h-full flex flex-col">
                <div className="flex justify-between items-start mb-4">
                  <div className={`px-3 py-1 rounded-full text-xs font-medium flex items-center
                    ${claim.status === 'COMPLETED' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 
                      claim.status === 'PENDING' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' : 
                      'bg-slate-500/10 text-slate-400 border border-slate-500/20'}`}
                  >
                    {claim.status === 'PENDING' && <Clock className="w-3 h-3 mr-1.5" />}
                    {claim.status === 'COMPLETED' && <FileCheck2 className="w-3 h-3 mr-1.5" />}
                    {claim.status}
                  </div>
                  <ArrowRight className="w-5 h-5 text-slate-600 group-hover:text-teal-400 transition-all group-hover:translate-x-1" />
                </div>
                
                <h3 className="text-lg font-medium text-white mb-1 truncate">
                  Claim #{claim.id.substring(0, 8)}...
                </h3>
                
                <div className="mt-auto pt-4 flex justify-between items-end">
                  <div>
                    <p className="text-slate-500 text-xs mb-1">Total Billed</p>
                    <p className="text-xl font-semibold text-slate-200">
                      ${claim.total_billed.toFixed(2)}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-slate-500 text-xs mb-1">Date</p>
                    <p className="text-slate-400 text-sm">
                      {new Date(claim.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
