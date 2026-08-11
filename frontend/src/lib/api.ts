// Server Components run inside the frontend container, where `localhost` is the
// frontend itself — they must reach the API over the compose network.
export const API_URL_SERVER = process.env.API_URL_INTERNAL ?? 'http://fastapi:8000';

// Client Components run in the browser, which reaches the API on the host port.
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
export const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? 'ws://localhost:8000';
