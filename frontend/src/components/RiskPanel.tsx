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

/**
 * The bands escalate rather than each taking their own hue: cleared, then two
 * weights of caution, then a filled block for critical. A reader should be able
 * to rank them without consulting a key.
 */
const BAND_STYLE: Record<string, string> = {
  LOW: 'border-verified-line bg-verified-soft text-verified',
  MEDIUM: 'border-capped-line bg-capped-soft text-capped',
  HIGH: 'border-rejected-line bg-rejected-soft text-rejected',
  // text-paper rather than text-white: the fill flips with the theme, so the
  // label has to flip with it or the filled band loses all contrast in dark.
  CRITICAL: 'border-rejected bg-rejected text-paper',
};

/**
 * The risk score, decomposed into the rules that produced it.
 *
 * The score is never shown on its own. A number an analyst cannot interrogate
 * is a number they have to either accept or ignore, and both are bad, so every
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
      <section className="panel p-6">
        <p className="eyebrow">Risk</p>
        <p className="mt-3 text-sm text-ink-500">
          Not scored yet. Risk is computed when the claim is adjudicated.
        </p>
      </section>
    );
  }

  const aggravating = signals.filter((s) => s.direction === 'AGGRAVATING');
  const mitigating = signals.filter((s) => s.direction === 'MITIGATING');
  const band = BAND_STYLE[risk.band] ?? BAND_STYLE.MEDIUM;

  return (
    <section className="panel p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="eyebrow">Risk</p>
          <p className="mt-3 text-sm text-ink-500">
            {risk.signal_count} {risk.signal_count === 1 ? 'rule' : 'rules'} fired on
            this claim
          </p>
        </div>

        <div className={`flex items-baseline gap-2 border px-4 py-2.5 ${band}`}>
          <span className="font-mono text-3xl tabular-nums leading-none">
            {risk.score.toFixed(0)}
          </span>
          <span className="font-mono text-xs opacity-70">/100</span>
          <span className="ml-2 font-mono text-[0.625rem] uppercase tracking-[0.16em]">
            {risk.band}
          </span>
        </div>
      </div>

      <div className="mt-7 space-y-7">
        {aggravating.length > 0 && (
          <div>
            <p className="eyebrow flex items-center gap-2">
              <TrendingUp className="h-3.5 w-3.5" /> Raises risk
            </p>
            <ul className="mt-4 space-y-4">
              {aggravating.map((signal) => (
                <SignalRow key={signal.code} signal={signal} />
              ))}
            </ul>
          </div>
        )}

        {mitigating.length > 0 && (
          <div>
            <p className="eyebrow flex items-center gap-2">
              <TrendingDown className="h-3.5 w-3.5" /> Lowers risk
            </p>
            <ul className="mt-4 space-y-4">
              {mitigating.map((signal) => (
                <SignalRow key={signal.code} signal={signal} />
              ))}
            </ul>
          </div>
        )}

        {signals.length === 0 && (
          <p className="flex items-center gap-2 text-sm text-ink-500">
            <ShieldCheck className="h-4 w-4 text-verified" />
            No rules fired on this claim.
          </p>
        )}
      </div>

      <p className="mt-7 border-t border-line pt-4 text-xs leading-relaxed text-ink-500">
        Signals are computed from the claim’s own data by a deterministic rules
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
        className={`w-11 shrink-0 text-right font-mono text-sm tabular-nums ${
          aggravating ? 'text-rejected' : 'text-verified'
        }`}
      >
        {signal.weight > 0 ? '+' : ''}
        {signal.weight.toFixed(0)}
      </span>

      <div className="min-w-0 flex-1">
        <p className="text-sm text-ink-900">{signal.title}</p>
        <p className="mt-0.5 text-xs leading-relaxed text-ink-500">{signal.detail}</p>
        {/* A proportional bar per contribution, so relative weight is visible
            without having to compare numbers by eye. */}
        <div className="mt-2 h-1 bg-mist">
          <div
            className={`h-full ${aggravating ? 'bg-rejected' : 'bg-verified'}`}
            style={{ width: `${width}%` }}
          />
        </div>
      </div>
    </li>
  );
}
