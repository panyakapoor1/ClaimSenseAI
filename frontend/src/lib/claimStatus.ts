export type Claim = {
  id: string;
  status: string;
  total_billed: number;
  created_at: string;
};

/**
 * Claim statuses grouped by what an analyst actually does about them.
 *
 * The backend writes these as free-form strings today; P1 replaces them with a
 * Postgres enum driven by an explicit state machine. Until then this module is
 * the single place that knows the vocabulary.
 */
export const IN_PROGRESS = ['PENDING', 'EXTRACTED'];
export const AUDITED = ['AUDIT_COMPLETE', 'APPEAL_GENERATED', 'NO_APPEAL_NEEDED'];
export const NEEDS_ATTENTION = ['FAILED', 'LLM_UNAVAILABLE'];

export type ClaimStats = {
  total: number;
  inProgress: number;
  audited: number;
  appealsGenerated: number;
  needsAttention: number;
  totalBilled: number;
};

export function summarise(claims: Claim[]): ClaimStats {
  return {
    total: claims.length,
    inProgress: claims.filter((c) => IN_PROGRESS.includes(c.status)).length,
    audited: claims.filter((c) => AUDITED.includes(c.status)).length,
    appealsGenerated: claims.filter((c) => c.status === 'APPEAL_GENERATED').length,
    needsAttention: claims.filter((c) => NEEDS_ATTENTION.includes(c.status)).length,
    totalBilled: claims.reduce((sum, c) => sum + (c.total_billed ?? 0), 0),
  };
}

/**
 * Claims per day for the trailing `days` window, including days with none.
 *
 * Gaps are emitted as zero rather than skipped, so the x-axis stays a real
 * calendar and a quiet week reads as quiet instead of compressing away.
 */
export function volumeByDay(claims: Claim[], days = 14) {
  const buckets = new Map<string, number>();
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    buckets.set(d.toISOString().slice(0, 10), 0);
  }

  for (const claim of claims) {
    const key = new Date(claim.created_at).toISOString().slice(0, 10);
    if (buckets.has(key)) buckets.set(key, buckets.get(key)! + 1);
  }

  return Array.from(buckets, ([date, claims]) => ({
    date,
    label: new Date(date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
    claims,
  }));
}
