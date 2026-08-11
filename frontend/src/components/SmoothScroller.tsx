"use client";

// Imported from `lenis/react` rather than the deprecated
// `@studio-freight/react-lenis` wrapper, which ships its own pinned @types/react
// and so conflicts with React 19 at the type level.
import { ReactLenis } from 'lenis/react';
import { ReactNode } from 'react';

export default function SmoothScroller({ children }: { children: ReactNode }) {
  return (
    <ReactLenis root options={{ lerp: 0.08, duration: 1.5, smoothWheel: true }}>
      {children}
    </ReactLenis>
  );
}
