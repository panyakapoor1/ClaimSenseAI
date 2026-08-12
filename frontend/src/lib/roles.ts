/**
 * Session shapes and the capability vocabulary.
 *
 * Deliberately free of server-only imports. `lib/session.ts` uses `next/headers`,
 * which cannot be pulled into a client bundle — so the pieces a Client Component
 * needs (types, labels, capability names) live here instead.
 *
 * These names mirror `services/auth.py`. The server is the authority; this copy
 * exists only so the UI can hide controls a role cannot use.
 */

export type Role = 'ANALYST' | 'SENIOR_ANALYST' | 'ADMIN' | 'AUDITOR';

export type SessionUser = {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  organization_id: string;
};

export type Session = {
  user: SessionUser;
  capabilities: string[];
};

export const CAPABILITIES = {
  readClaims: 'claims:read',
  createClaims: 'claims:create',
  runAnalysis: 'claims:analyse',
  decideClaims: 'claims:decide',
  managePolicies: 'policies:manage',
  administer: 'system:administer',
} as const;

export const ROLE_LABELS: Record<Role, string> = {
  ANALYST: 'Analyst',
  SENIOR_ANALYST: 'Senior Analyst',
  ADMIN: 'Administrator',
  AUDITOR: 'Auditor',
};

export function can(session: Session | null, capability: string): boolean {
  return Boolean(session?.capabilities.includes(capability));
}
