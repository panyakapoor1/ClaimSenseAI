import Link from 'next/link';
import { ArrowLeft, FileCheck2, AlertTriangle, FileText, CheckCircle2 } from 'lucide-react';
import GenerateAppealButton from '@/components/GenerateAppealButton';

async function getClaimDetails(id: string) {
  try {
    const res = await fetch(`http://localhost:8000/audit-results/${id}`, { cache: 'no-store' });
    if (!res.ok) {
      if (res.status === 404) return null;
      throw new Error('Failed to fetch claim details');
    }
    return await res.json();
  } catch (err) {
    console.error(err);
    return null;
  }
}

export default async function ClaimDetailsPage({ params }: { params: { id: string } }) {
  const claim = await getClaimDetails(params.id);

  if (!claim) {
    return (
      <div className="glass-panel p-12 text-center flex flex-col items-center">
        <AlertTriangle className="w-16 h-16 text-rose-500 mb-4" />
        <h2 className="text-xl font-medium text-slate-300 mb-2">Claim Not Found</h2>
        <p className="text-slate-500 mb-6">The claim you are looking for does not exist or has not been fully processed yet.</p>
        <Link href="/claims" className="btn-secondary">Back to Claims</Link>
      </div>
    );
  }

  const hasRejectedItems = claim.items.some((item: any) => item.audit?.status === 'REJECTED');

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <header className="mb-8">
        <Link href="/claims" className="inline-flex items-center text-slate-400 hover:text-teal-400 transition-colors mb-4 text-sm font-medium">
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Audit Results
        </Link>
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-white mb-2 flex items-center">
              Claim <span className="text-slate-500 ml-3 text-2xl font-normal">#{claim.claim_id.substring(0,8)}</span>
            </h1>
            <p className="text-slate-400">
              Total Billed: <span className="text-slate-200 font-semibold">${claim.total_billed.toFixed(2)}</span>
            </p>
          </div>
          
          <div className="flex items-center gap-3">
            <div className={`px-4 py-2 rounded-lg text-sm font-medium flex items-center
              ${claim.claim_status === 'COMPLETED' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 
                'bg-amber-500/10 text-amber-400 border border-amber-500/20'}`}
            >
              {claim.claim_status === 'COMPLETED' && <FileCheck2 className="w-4 h-4 mr-2" />}
              Status: {claim.claim_status}
            </div>
            
            {hasRejectedItems && (
              <GenerateAppealButton claimId={claim.claim_id} />
            )}
          </div>
        </div>
      </header>

      <div className="space-y-6">
        <h2 className="text-xl font-semibold text-white">Line Items & Audit Findings</h2>
        
        {claim.items.map((item: any) => {
          const isRejected = item.audit?.status === 'REJECTED';
          const isApproved = item.audit?.status === 'APPROVED';
          const isPending = !item.audit || item.audit.status === 'PENDING';

          return (
            <div 
              key={item.item_id} 
              className={`glass-panel p-6 border-l-4 transition-all
                ${isRejected ? 'border-l-rose-500' : isApproved ? 'border-l-emerald-500' : 'border-l-amber-500'}
              `}
            >
              <div className="flex flex-col md:flex-row justify-between md:items-start gap-4 mb-4">
                <div>
                  <div className="flex items-center gap-3 mb-2">
                    <span className="text-lg font-medium text-white">{item.description}</span>
                    <span className="px-2.5 py-0.5 rounded-full bg-slate-800 border border-slate-700 text-slate-300 text-xs">
                      {item.category}
                    </span>
                  </div>
                  <p className="text-slate-400 text-sm">Billed Amount: <span className="text-slate-200 font-semibold">${item.billed_amount.toFixed(2)}</span></p>
                </div>

                <div className={`shrink-0 px-3 py-1.5 rounded-lg text-sm font-semibold flex items-center
                  ${isRejected ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20' : 
                    isApproved ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 
                    'bg-amber-500/10 text-amber-400 border border-amber-500/20'}`}
                >
                  {isRejected && <AlertTriangle className="w-4 h-4 mr-1.5" />}
                  {isApproved && <CheckCircle2 className="w-4 h-4 mr-1.5" />}
                  {item.audit?.status || 'PENDING'}
                </div>
              </div>

              {!isPending && item.audit?.reason && (
                <div className="mt-4 pt-4 border-t border-slate-800">
                  <h4 className="text-slate-300 font-medium mb-2 flex items-center text-sm">
                    <FileText className="w-4 h-4 mr-2 text-slate-500" />
                    AI Auditor Reasoning
                  </h4>
                  <p className="text-slate-400 text-sm leading-relaxed mb-4">
                    {item.audit.reason}
                  </p>
                  
                  {item.audit.policy_clause_cited && (
                    <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-800">
                      <p className="text-xs text-slate-500 uppercase tracking-wider font-semibold mb-2 flex justify-between">
                        <span>Cited Policy Clause</span>
                        <span>Page {item.audit.page_number}</span>
                      </p>
                      <p className="text-indigo-200/80 text-sm font-serif italic">
                        "{item.audit.policy_clause_cited}"
                      </p>
                    </div>
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
