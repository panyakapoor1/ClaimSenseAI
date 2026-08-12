import { TrendingUp, TrendingDown, ShieldCheck } from 'lucide-react';

export type RiskSignal = {
  code: string;
  title: string;
  detail: string;
  direction: 'AGGRAVATING' | 'MITIGATING';
  weight: number;
};

export type Risk = {
  score: number;
  band: string;
  signal_count: number;
};

const BAND_STYLE: Record<string, string> = {
  LOW: 'text-emerald-300 border-emerald-500/30 bg-emerald-500/5',
  MEDIUM: 'text-amber-300 border-amber-500/30 bg-amber-500/5',
  HIGH: 'text-orange-300 border-orange-500/30 bg-orange-500/5',
  CRITICAL: 'text-rose-300 border-rose-500/30 bg-rose-500/5',
};

/**
 * The risk score, decomposed into the rules that produced it.
 *
 * The score is never shown on its own. A number an analyst cannot interrogate
 * is a number they have to either accept or ignore, and both are bad — so every
 * contribution is listed with the observation behind it.
 */
export default function RiskPanel({
  risk,
  signals,
}: {
  risk: Risk | null;
  signals: RiskSignal[];
}) {
  if (!risk) {
    return (
      <section className="glass-panel p-6">
        <h2 className="text-xl font-semibold text-white mb-2">Risk</h2>
        <p className="text-sm text-slate-500">
          Not scored yet. Risk is computed when the claim is adjudicated.
        </p>
      </section>
    );
  }

  const aggravating = signals.filter((s) => s.direction === 'AGGRAVATING');
  const mitigating = signals.filter((s) => s.direction === 'MITIGATING');
  const band = BAND_STYLE[risk.band] ?? BAND_STYLE.MEDIUM;

  return (
    <section className="glass-panel p-6">
      <div className="flex items-start justify-between gap-6 mb-6 flex-wrap">
        <div>
          <h2 className="text-xl font-semibold text-white mb-1">Risk</h2>
          <p className="text-sm text-slate-500">
            {risk.signal_count} {risk.signal_count === 1 ? 'rule' : 'rules'} fired on this claim
          </p>
        </div>

        <div className={`px-4 py-2 border ${band} flex items-baseline gap-2`}>
          <span className="text-3xl font-bold tabular-nums">{risk.score.toFixed(0)}</span>
          <span className="text-sm opacity-70">/ 100</span>
          <span className="text-xs uppercase tracking-wider ml-2">{risk.band}</span>
        </div>
      </div>

      {/* A proportional bar per contribution, so relative weight is visible
          without having to compare numbers by eye. */}
      <div className="space-y-4">
        {aggravating.length > 0 && (
          <div>
            <h3 className="text-xs uppercase tracking-wider text-slate-500 mb-3 flex items-center gap-2">
              <TrendingUp className="w-3.5 h-3.5" /> Raises risk
            </h3>
            <ul className="space-y-3">
              {aggravating.map((signal) => (
                <SignalRow key={signal.code} signal={signal} />
              ))}
            </ul>
          </div>
        )}

        {mitigating.length > 0 && (
          <div className="pt-2">
            <h3 className="text-xs uppercase tracking-wider text-slate-500 mb-3 flex items-center gap-2">
              <TrendingDown className="w-3.5 h-3.5" /> Lowers risk
            </h3>
            <ul className="space-y-3">
              {mitigating.map((signal) => (
                <SignalRow key={signal.code} signal={signal} />
              ))}
            </ul>
          </div>
        )}

        {signals.length === 0 && (
          <p className="text-sm text-slate-500 flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            No rules fired on this claim.
          </p>
        )}
      </div>

      <p className="text-xs text-slate-600 mt-6 pt-4 border-t border-white/10">
        Signals are computed from the claim's own data by a deterministic rules
        engine. The weights are a stated policy, not learned parameters.
      </p>
    </section>
  );
}

function SignalRow({ signal }: { signal: RiskSignal }) {
  const aggravating = signal.direction === 'AGGRAVATING';
  // Bar width relative to the heaviest weight in the rule set.
  const width = Math.min(100, (Math.abs(signal.weight) / 26) * 100);

  return (
    <li className="flex gap-4">
      <span
        className={`w-12 shrink-0 text-sm font-semibold tabular-nums text-right ${
          aggravating ? 'text-rose-300' : 'text-emerald-300'
        }`}
      >
        {signal.weight > 0 ? '+' : ''}
        {signal.weight.toFixed(0)}
      </span>

      <div className="min-w-0 flex-1">
        <p className="text-sm text-slate-200">{signal.title}</p>
        <p className="text-xs text-slate-500 mt-0.5">{signal.detail}</p>
        <div className="h-0.5 bg-white/5 mt-2">
          <div
            className={`h-full ${aggravating ? 'bg-rose-500/60' : 'bg-emerald-500/60'}`}
            style={{ width: `${width}%` }}
          />
        </div>
      </div>
    </li>
  );
}
