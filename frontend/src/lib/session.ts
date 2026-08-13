import 'server-only';

import { cookies } from 'next/headers';

import { API_V1_SERVER } from './api';
import type { Session } from './roles';

export const SESSION_COOKIE = 'claimsense_session';

/**
 * Forward the browser's session cookie to the API as a bearer token.
 *
 * Server Components run inside the frontend container and call the API at
 * `http://fastapi:8000`, a different host from the one that set the cookie, so
 * the browser's cookie is never attached automatically. Reading it here and
 * sending it as `Authorization` is what carries the caller's identity across
 * that hop. Without this, every server-rendered page would be anonymous.
 */
export async function authHeaders(): Promise<Record<string, string>> {
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * The signed-in user, or null.
 *
 * Asks the API rather than decoding the token here: the server is the authority
 * on whether a session is still valid, and a deactivated account must stop
 * working immediately rather than when its token happens to expire.
 */
export async function getSession(): Promise<Session | null> {
  const headers = await authHeaders();
  if (!headers.Authorization) return null;

  try {
    const res = await fetch(`${API_V1_SERVER}/auth/me`, {
      headers,
      cache: 'no-store',
    });
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.error('Could not resolve session:', err);
    return null;
  }
}
