import Link from 'next/link';
import { FileText, ArrowRight } from 'lucide-react';

async function getClaims() {
  try {
    const res = await fetch('http://localhost:8000/claims/', { cache: 'no-store' });
    if (!res.ok) throw new Error('Failed to fetch claims');
    return await res.json();
  } catch (err) {
    console.error(err);
    return [];
  }
}

export default async function AppealsListPage() {
  const claims = await getClaims();

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <header className="mb-10">
        <h1 className="text-4xl font-bold tracking-tight text-white mb-2">
          Generated Appeals
        </h1>
        <p className="text-slate-400 text-lg">
          Select a claim to view its associated appeal documents.
        </p>
      </header>

      {claims.length === 0 ? (
        <div className="glass-panel p-12 text-center flex flex-col items-center">
          <FileText className="w-16 h-16 text-slate-600 mb-4" />
          <h2 className="text-xl font-medium text-slate-300 mb-2">No claims found</h2>
          <p className="text-slate-500 max-w-md">
            You don't have any claims yet.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {claims.map((claim: any) => (
            <Link key={claim.id} href={`/appeals/${claim.id}`}>
              <div className="glass-panel p-6 border-slate-700/50 hover:border-indigo-500/50 hover:bg-slate-800/80 transition-all cursor-pointer group h-full flex flex-col">
                <div className="flex justify-between items-start mb-4">
                  <div className="px-3 py-1 rounded-full text-xs font-medium bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 flex items-center">
                    <FileText className="w-3 h-3 mr-1.5" />
                    Appeal Doc
                  </div>
                  <ArrowRight className="w-5 h-5 text-slate-600 group-hover:text-indigo-400 transition-all group-hover:translate-x-1" />
                </div>
                
                <h3 className="text-lg font-medium text-white mb-1 truncate">
                  Appeal for Claim #{claim.id.substring(0, 8)}...
                </h3>
                
                <div className="mt-auto pt-4 flex justify-between items-end">
                  <div>
                    <p className="text-slate-500 text-xs mb-1">Claim Status</p>
                    <p className="text-sm font-semibold text-slate-200">
                      {claim.status}
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
