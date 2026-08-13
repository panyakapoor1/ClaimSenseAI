// Server Components run inside the frontend container, where `localhost` is the
// frontend itself, so they must reach the API over the compose network.
const SERVER_ORIGIN = process.env.API_URL_INTERNAL ?? 'http://fastapi:8000';

// Client Components run in the browser, which reaches the API on the host port.
const BROWSER_ORIGIN = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

/** Product API. Versioned, so a breaking change ships as /api/v2 alongside it. */
export const API_V1_SERVER = `${SERVER_ORIGIN}/api/v1`;
export const API_V1 = `${BROWSER_ORIGIN}/api/v1`;

/** Operational endpoints sit outside the versioned surface. */
export const OPS_SERVER = SERVER_ORIGIN;

export const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? 'ws://localhost:8000';

export type ApiError = {
  code: string;
  message: string;
  details?: unknown;
  request_id?: string;
};

/**
 * Pull the message out of the API's error envelope.
 *
 * Every failure returns `{error: {code, message, ...}}`, so the UI can show what
 * actually went wrong instead of a generic string.
 */
export async function readError(res: Response, fallback: string): Promise<string> {
  try {
    const body = await res.json();
    return body?.error?.message ?? fallback;
  } catch {
    return fallback;
  }
}
