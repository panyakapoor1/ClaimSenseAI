'use client';

import { Moon, Sun } from 'lucide-react';
import clsx from 'clsx';

import { setTheme, useResolvedTheme } from '@/lib/useTheme';

/**
 * Light/dark switch.
 *
 * Holds no state of its own. It reads the resolved theme and writes an
 * override. With nothing stored the page follows the operating system.
 */
export default function ThemeToggle({ invert = false }: { invert?: boolean }) {
  const theme = useResolvedTheme();
  const next = theme === 'dark' ? 'light' : 'dark';

  return (
    <button
      onClick={() => setTheme(next)}
      aria-label={`Switch to ${next} theme`}
      title={`Switch to ${next} theme`}
      className={clsx(
        'no-print inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-[2px] transition-colors',
        invert
          ? 'text-rail-dim hover:bg-rail-raised hover:text-rail-text'
          : 'text-ink-500 hover:bg-mist hover:text-ink-900',
      )}
    >
      {theme === 'dark' ? (
        <Sun className="h-4 w-4" strokeWidth={1.6} />
      ) : (
        <Moon className="h-4 w-4" strokeWidth={1.6} />
      )}
    </button>
  );
}
