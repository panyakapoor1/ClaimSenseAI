export type Claim = {
  id: string;
  reference: string;
  status: ClaimStatus;
  total_billed: number;
  currency: string;
  created_at: string;
};

/**
 * The claim lifecycle, mirroring the `claim_status` enum in the database.
 *
 * Previously these were unconstrained strings on both sides, and the UI checked
 * for a 'COMPLETED' status the backend never wrote, so every finished claim
 * fell through to the default badge.
 */
export const CLAIM_STATUSES = [
  'RECEIVED', 'EXTRACTING', 'EXTRACTED', 'AUDITING', 'AUDIT_COMPLETE',
  'APPEAL_GENERATED', 'NO_APPEAL_NEEDED', 'CLOSED', 'FAILED', 'LLM_UNAVAILABLE',
] as const;

export type ClaimStatus = (typeof CLAIM_STATUSES)[number];

export const IN_PROGRESS: ClaimStatus[] = ['RECEIVED', 'EXTRACTING', 'EXTRACTED', 'AUDITING'];
export const AUDITED: ClaimStatus[] = ['AUDIT_COMPLETE', 'APPEAL_GENERATED', 'NO_APPEAL_NEEDED', 'CLOSED'];
export const NEEDS_ATTENTION: ClaimStatus[] = ['FAILED', 'LLM_UNAVAILABLE'];

type Presentation = { label: string; tone: 'progress' | 'done' | 'attention' };

const PRESENTATION: Record<ClaimStatus, Presentation> = {
  RECEIVED: { label: 'Received', tone: 'progress' },
  EXTRACTING: { label: 'Reading bill', tone: 'progress' },
  EXTRACTED: { label: 'Bill parsed', tone: 'progress' },
  AUDITING: { label: 'Auditing', tone: 'progress' },
  AUDIT_COMPLETE: { label: 'Audit complete', tone: 'done' },
  APPEAL_GENERATED: { label: 'Appeal drafted', tone: 'done' },
  NO_APPEAL_NEEDED: { label: 'No appeal needed', tone: 'done' },
  CLOSED: { label: 'Closed', tone: 'done' },
  FAILED: { label: 'Failed', tone: 'attention' },
  LLM_UNAVAILABLE: { label: 'AI unavailable', tone: 'attention' },
};

export function presentStatus(status: string): Presentation {
  return PRESENTATION[status as ClaimStatus] ?? { label: status, tone: 'attention' };
}

/**
 * Chip styling per tone.
 *
 * Colour in this interface only ever means status, so these four palettes are
 * the whole of the chroma budget, and nothing decorative may borrow them.
 */
export const TONE_CLASS: Record<Presentation['tone'], string> = {
  progress: 'bg-review-soft text-review border-review-line',
  done: 'bg-verified-soft text-verified border-verified-line',
  attention: 'bg-rejected-soft text-rejected border-rejected-line',
};

/** Per-line adjudication outcomes, mirroring the `adjudication_status` enum. */
export type AdjudicationStatus = 'APPROVED' | 'CAPPED' | 'REJECTED' | 'NEEDS_REVIEW';

export const ADJUDICATION: Record<AdjudicationStatus, { label: string; accent: string; chip: string }> = {
  APPROVED: {
    label: 'Approved',
    accent: 'border-l-verified',
    chip: 'bg-verified-soft text-verified border-verified-line',
  },
  CAPPED: {
    label: 'Capped',
    accent: 'border-l-capped',
    chip: 'bg-capped-soft text-capped border-capped-line',
  },
  REJECTED: {
    label: 'Rejected',
    accent: 'border-l-rejected',
    chip: 'bg-rejected-soft text-rejected border-rejected-line',
  },
  NEEDS_REVIEW: {
    label: 'Needs review',
    accent: 'border-l-review',
    chip: 'bg-review-soft text-review border-review-line',
  },
};

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

export function formatCurrency(amount: number, currency = 'INR') {
  return new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency,
    maximumFractionDigits: 0,
  }).format(amount);
}
