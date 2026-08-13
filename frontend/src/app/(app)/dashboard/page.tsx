import Link from 'next/link';
import { ArrowRight, AlertTriangle } from 'lucide-react';
import ClaimVolumeChart from '@/components/ClaimVolumeChart';
import PageHeader from '@/components/PageHeader';
import { API_V1_SERVER } from '@/lib/api';
import { authHeaders, getSession } from '@/lib/session';
import { CAPABILITIES } from '@/lib/roles';
import { formatCurrency, summarise, volumeByDay, type Claim } from '@/lib/claimStatus';

async function getClaims(): Promise<{ claims: Claim[]; reachable: boolean }> {
  try {
    const res = await fetch(`${API_V1_SERVER}/claims?limit=100`, {
      headers: await authHeaders(),
      cache: 'no-store',
    });
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
  const [{ claims, reachable }, session] = await Promise.all([getClaims(), getSession()]);
  const stats = summarise(claims);
  const volume = volumeByDay(claims);

  // The shortcuts have to obey the same capabilities the navigation does.
  // Offering an auditor an upload card sends them to a page the server will
  // refuse. The rule is enforced either way, but advertising it is a lie.
  const canCreate = Boolean(session?.capabilities.includes(CAPABILITIES.createClaims));

  return (
    <div>
      <PageHeader
        eyebrow="Overview"
        title="Dashboard"
        description={
          reachable
            ? `${stats.total} ${stats.total === 1 ? 'claim' : 'claims'} in the system.`
            : 'Claim data is currently unavailable.'
        }
      />

      {!reachable && (
        <div className="stamp-in mt-8 flex items-start gap-3 border border-capped-line bg-capped-soft p-4">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-capped" />
          <div>
            <p className="text-sm font-medium text-capped">Cannot reach the API</p>
            <p className="mt-1 text-sm text-ink-700">
              The dashboard shows no figures rather than stale ones. Check that the
              backend container is running.
            </p>
          </div>
        </div>
      )}

      {/* Figures sit in one ruled block rather than four floating cards. They
          are a single reading, and separating them implies they are unrelated. */}
      <section className="stamp-in mt-10 grid grid-cols-2 gap-px border border-line bg-line md:grid-cols-4">
        <Stat
          label="In progress"
          value={stats.inProgress}
          note={stats.inProgress > 0 ? 'Being processed now' : 'Nothing queued'}
          live={stats.inProgress > 0}
        />
        <Stat label="Audited" value={stats.audited} note="Adjudication complete" />
        <Stat
          label="Appeals drafted"
          value={stats.appealsGenerated}
          note="Letters on file"
        />
        <Stat
          label="Needs attention"
          value={stats.needsAttention}
          note={stats.needsAttention > 0 ? 'Failed or unprocessed' : 'No failures'}
          attention={stats.needsAttention > 0}
        />
      </section>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <section className="panel flex flex-col p-6 lg:col-span-2">
          <div className="flex items-baseline justify-between gap-4">
            <h2 className="eyebrow">Claim volume</h2>
            <span className="eyebrow">Last 14 days</span>
          </div>

          <div className="mt-6 flex-1">
            <ClaimVolumeChart data={volume} />
          </div>

          <p className="mt-6 border-t border-line pt-4 text-sm text-ink-500">
            Total billed across all claims{' '}
            <span className="font-mono tabular-nums text-ink-900">
              {formatCurrency(stats.totalBilled, claims[0]?.currency ?? 'INR')}
            </span>
          </p>
        </section>

        <div className="flex flex-col gap-6">
          {canCreate && (
            <Action
              href="/upload"
              step="01"
              title="Upload a claim"
              body="Submit a bill and the governing policy to audit it line by line."
            />
          )}
          <Action
            href="/claims"
            step={canCreate ? '02' : '01'}
            title="Audit results"
            body="Review findings, check the cited clause, and draft an appeal."
          />
        </div>
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  note,
  live = false,
  attention = false,
}: {
  label: string;
  value: number;
  note: string;
  live?: boolean;
  attention?: boolean;
}) {
  return (
    <div className="bg-surface p-6">
      <p className="eyebrow">{label}</p>
      <p
        className={`display mt-5 text-4xl tabular-nums ${
          attention ? 'text-rejected' : 'text-ink-900'
        }`}
      >
        {value}
      </p>
      <p className="mt-2 flex items-center gap-2 text-xs text-ink-500">
        {live && (
          <span className="relative flex h-1.5 w-1.5 shrink-0">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-review opacity-60" />
            <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-review" />
          </span>
        )}
        {note}
      </p>
    </div>
  );
}

function Action({
  href,
  step,
  title,
  body,
}: {
  href: string;
  step: string;
  title: string;
  body: string;
}) {
  return (
    <Link
      href={href}
      className="panel group flex h-full flex-col p-6 transition-colors hover:border-ink-300"
    >
      <div className="flex items-start justify-between">
        <span className="font-mono text-xs tabular-nums text-ink-300">{step}</span>
        <ArrowRight className="h-4 w-4 text-ink-300 transition-all group-hover:translate-x-1 group-hover:text-ink-900" />
      </div>
      <h3 className="mt-6 text-lg font-semibold text-ink-900">{title}</h3>
      <p className="mt-2 text-sm leading-relaxed text-ink-700">{body}</p>
    </Link>
  );
}
