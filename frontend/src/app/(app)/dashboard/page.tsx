import Link from 'next/link';
import { ArrowRight, Activity, FileCheck2, FileUp, ListChecks, AlertTriangle, TrendingUp } from 'lucide-react';
import ClaimVolumeChart from '@/components/ClaimVolumeChart';
import { API_V1_SERVER } from '@/lib/api';
import { formatCurrency, summarise, volumeByDay, type Claim } from '@/lib/claimStatus';

async function getClaims(): Promise<{ claims: Claim[]; reachable: boolean }> {
  try {
    const res = await fetch(`${API_V1_SERVER}/claims?limit=100`, { cache: 'no-store' });
    if (!res.ok) throw new Error(`API responded ${res.status}`);
    const page = await res.json();
    return { claims: page.items as Claim[], reachable: true };
  } catch (err) {
    console.error('Dashboard could not load claims:', err);
    return { claims: [], reachable: false };
  }
}

// Declared explicitly because getClaims() catches its own errors, which would
// otherwise swallow the signal Next uses to infer that this route is dynamic.
export const dynamic = 'force-dynamic';

export default async function DashboardPage() {
  const { claims, reachable } = await getClaims();
  const stats = summarise(claims);
  const volume = volumeByDay(claims);

  return (
    <div className="space-y-8">
      <header className="mb-10">
        <h1 className="text-4xl font-bold tracking-tight text-white mb-2">Dashboard</h1>
        <p className="text-slate-400 text-lg">
          {reachable
            ? `${stats.total} ${stats.total === 1 ? 'claim' : 'claims'} in the system.`
            : 'Claim data is currently unavailable.'}
        </p>
      </header>

      {!reachable && (
        <div className="border border-amber-500/30 bg-amber-500/5 p-4 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
          <div>
            <p className="text-amber-200 font-medium text-sm">Cannot reach the API</p>
            <p className="text-slate-400 text-sm mt-1">
              The dashboard shows no figures rather than stale ones. Check that the backend container is running.
            </p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <Stat
          icon={<Activity className="w-6 h-6 text-teal-400" />}
          label="In progress"
          value={stats.inProgress}
          note={stats.inProgress > 0 ? 'Being processed now' : 'Nothing queued'}
          live={stats.inProgress > 0}
        />
        <Stat
          icon={<FileCheck2 className="w-6 h-6 text-indigo-400" />}
          label="Audited"
          value={stats.audited}
          note="Adjudication complete"
        />
        <Stat
          icon={<ListChecks className="w-6 h-6 text-slate-300" />}
          label="Appeals generated"
          value={stats.appealsGenerated}
          note="Letters on file"
        />
        <Stat
          icon={<AlertTriangle className="w-6 h-6 text-rose-400" />}
          label="Needs attention"
          value={stats.needsAttention}
          note={stats.needsAttention > 0 ? 'Failed or unprocessed' : 'No failures'}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-6">
        <div className="glass-panel p-6 lg:col-span-2 flex flex-col">
          <div className="flex items-baseline justify-between mb-6">
            <h2 className="text-xl font-semibold text-white flex items-center">
              <TrendingUp className="w-5 h-5 mr-2 text-teal-400" /> Claim volume
            </h2>
            <span className="text-xs text-slate-500 uppercase tracking-wider">Last 14 days</span>
          </div>
          <ClaimVolumeChart data={volume} />
          <p className="text-xs text-slate-500 mt-4 pt-4 border-t border-white/10">
            Total billed across all claims:{' '}
            <span className="text-slate-300 font-medium tabular-nums">
              {formatCurrency(stats.totalBilled, claims[0]?.currency ?? 'INR')}
            </span>
          </p>
        </div>

        <div className="flex flex-col gap-6">
          <Action
            href="/upload"
            icon={<FileUp className="w-6 h-6 text-black" />}
            accent="bg-teal-500"
            hover="group-hover:text-teal-400"
            title="Upload claim"
            body="Submit a bill and policy to audit line by line."
          />
          <Action
            href="/claims"
            icon={<ListChecks className="w-6 h-6 text-black" />}
            accent="bg-indigo-500"
            hover="group-hover:text-indigo-400"
            title="Audit results"
            body="Review findings and generate appeals."
          />
        </div>
      </div>
    </div>
  );
}

function Stat({
  icon,
  label,
  value,
  note,
  live = false,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  note: string;
  live?: boolean;
}) {
  return (
    <div className="glass-panel p-6 flex flex-col">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-11 h-11 bg-[#111111] border border-white/10 flex items-center justify-center shrink-0">
          {icon}
        </div>
        <h2 className="text-sm font-medium text-slate-300">{label}</h2>
      </div>
      <p className="text-4xl font-bold text-white mt-auto tabular-nums">{value}</p>
      <p className="text-slate-500 text-xs mt-2 flex items-center">
        {live && <span className="w-1.5 h-1.5 rounded-full bg-teal-400 animate-pulse mr-2" />}
        {note}
      </p>
    </div>
  );
}

function Action({
  href,
  icon,
  accent,
  hover,
  title,
  body,
}: {
  href: string;
  icon: React.ReactNode;
  accent: string;
  hover: string;
  title: string;
  body: string;
}) {
  return (
    <Link href={href} className="block h-full">
      <div className="glass-panel p-6 hover:border-white/30 transition-colors group h-full flex flex-col">
        <div className="flex items-center justify-between mb-4">
          <div className={`w-12 h-12 ${accent} flex items-center justify-center`}>{icon}</div>
          <ArrowRight className={`w-6 h-6 text-slate-500 ${hover} transition-colors`} />
        </div>
        <h3 className="text-xl font-semibold text-white mb-2">{title}</h3>
        <p className="text-slate-400 text-sm">{body}</p>
      </div>
    </Link>
  );
}
