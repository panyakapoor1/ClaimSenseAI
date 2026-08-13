'use client';

import { useSyncExternalStore } from 'react';

export const THEME_KEY = 'claimsense-theme';

export type ResolvedTheme = 'light' | 'dark';

/**
 * The theme is external state. It lives on the document element and in
 * localStorage, and the system preference can change underneath us. Subscribing
 * to it is what useSyncExternalStore is for; holding a copy in useState and
 * syncing it from an effect would mean rendering the wrong theme first and
 * correcting it a frame later.
 */
function subscribe(onChange: () => void) {
  const media = window.matchMedia('(prefers-color-scheme: dark)');
  // The toggle writes data-theme on <html> rather than dispatching an event.
  const observer = new MutationObserver(onChange);

  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-theme'],
  });
  media.addEventListener('change', onChange);
  // Keeps two tabs of the app in agreement.
  window.addEventListener('storage', onChange);

  return () => {
    observer.disconnect();
    media.removeEventListener('change', onChange);
    window.removeEventListener('storage', onChange);
  };
}

function getSnapshot(): ResolvedTheme {
  const explicit = document.documentElement.dataset.theme;
  if (explicit === 'dark' || explicit === 'light') return explicit;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

// The server cannot know the reader's preference. It renders light and the
// client corrects on hydration; the inline script in the root layout is what
// stops that correction from being visible.
function getServerSnapshot(): ResolvedTheme {
  return 'light';
}

export function useResolvedTheme(): ResolvedTheme {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}

/** Records an explicit choice, overriding the system preference. */
export function setTheme(next: ResolvedTheme) {
  document.documentElement.dataset.theme = next;
  try {
    localStorage.setItem(THEME_KEY, next);
  } catch {
    // Private browsing can refuse storage; the theme still applies for this
    // page, it just will not be remembered.
  }
}
