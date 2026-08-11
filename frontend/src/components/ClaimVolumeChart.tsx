'use client';

import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

type Point = { date: string; label: string; claims: number };

export default function ClaimVolumeChart({ data }: { data: Point[] }) {
  const hasVolume = data.some((d) => d.claims > 0);

  if (!hasVolume) {
    return (
      <div className="flex-1 min-h-[250px] flex items-center justify-center border border-dashed border-white/10">
        <p className="text-sm text-slate-500">No claims submitted in the last 14 days.</p>
      </div>
    );
  }

  return (
    <div className="flex-1 min-h-[250px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="claimVolume" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#2dd4bf" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#2dd4bf" stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis dataKey="label" stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} minTickGap={24} />
          <YAxis stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} allowDecimals={false} />
          <Tooltip
            contentStyle={{ backgroundColor: '#0f0f0f', border: '1px solid rgba(255,255,255,0.1)', color: '#fff' }}
            itemStyle={{ color: '#2dd4bf' }}
            formatter={(value) => [`${value}`, Number(value) === 1 ? 'claim' : 'claims']}
          />
          <Area type="monotone" dataKey="claims" stroke="#2dd4bf" strokeWidth={2} fillOpacity={1} fill="url(#claimVolume)" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
