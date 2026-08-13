'use client';

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer,
} from 'recharts';

type Point = { date: string; label: string; claims: number };

// Referenced as variables rather than literals so the chart follows the theme.
// SVG paint attributes accept var(), which is what lets recharts do this at all.
const INK = 'var(--color-ink-900)';
const AXIS = 'var(--color-ink-300)';
const GRID = 'var(--color-line)';
const SURFACE = 'var(--color-surface)';

/**
 * Claim volume over the trailing fortnight.
 *
 * One series, so no legend. The panel heading names it. The mark is ink rather
 * than a hue because colour in this interface is reserved for adjudication
 * status, and a volume trend is not a verdict.
 */
export default function ClaimVolumeChart({ data }: { data: Point[] }) {
  const hasVolume = data.some((d) => d.claims > 0);

  if (!hasVolume) {
    return (
      <div className="flex h-full min-h-[250px] items-center justify-center border border-dashed border-line">
        <p className="text-sm text-ink-500">No claims submitted in the last 14 days.</p>
      </div>
    );
  }

  return (
    <div className="h-full min-h-[250px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 8, left: -22, bottom: 0 }}>
          <defs>
            <linearGradient id="claimVolume" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={INK} stopOpacity={0.12} />
              <stop offset="100%" stopColor={INK} stopOpacity={0.01} />
            </linearGradient>
          </defs>

          {/* Recessive: horizontal only, so the eye reads magnitude without the
              grid competing with the mark. */}
          <CartesianGrid stroke={GRID} strokeDasharray="0" vertical={false} />

          <XAxis
            dataKey="label"
            stroke={AXIS}
            fontSize={11}
            fontFamily="var(--font-plex-mono)"
            tickLine={false}
            axisLine={false}
            minTickGap={26}
            dy={6}
          />
          <YAxis
            stroke={AXIS}
            fontSize={11}
            fontFamily="var(--font-plex-mono)"
            tickLine={false}
            axisLine={false}
            allowDecimals={false}
            width={44}
          />

          <Tooltip
            cursor={{ stroke: AXIS, strokeWidth: 1, strokeDasharray: '3 3' }}
            contentStyle={{
              background: SURFACE,
              border: `1px solid ${GRID}`,
              borderRadius: 2,
              boxShadow: '0 2px 10px rgb(21 22 26 / 0.06)',
              fontSize: 12,
              fontFamily: 'var(--font-plex-mono)',
              padding: '8px 10px',
            }}
            labelStyle={{ color: AXIS, marginBottom: 4 }}
            itemStyle={{ color: INK, padding: 0 }}
            formatter={(value) => [
              `${value}`,
              Number(value) === 1 ? 'claim' : 'claims',
            ]}
          />

          <Area
            type="monotone"
            dataKey="claims"
            stroke={INK}
            strokeWidth={2}
            fill="url(#claimVolume)"
            // A generous hover target, ringed in the surface colour so it reads
            // as sitting on top of the line rather than punched through it.
            activeDot={{ r: 4.5, fill: INK, stroke: SURFACE, strokeWidth: 2 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
