import clsx from 'clsx';

/**
 * The mark: a page with three lines and a stamped verdict in the margin.
 *
 * It is the same object the hero renders in three dimensions and the same shape
 * the status chips take, so the logo, the scene and the interface are all
 * describing one thing.
 */
function Mark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden="true">
      <rect width="24" height="24" rx="2" className="fill-current" />
      <g className="text-paper">
        <rect x="5" y="7" width="9" height="1.6" rx="0.4" fill="currentColor" />
        <rect x="5" y="11.2" width="11" height="1.6" rx="0.4" fill="currentColor" />
        <rect x="5" y="15.4" width="6" height="1.6" rx="0.4" fill="currentColor" />
        {/* The verdict, stamped in the margin. */}
        <rect x="15.6" y="15" width="3.4" height="3.4" rx="0.5" fill="currentColor" />
      </g>
    </svg>
  );
}

export default function Wordmark({
  size = 'md',
  invert = false,
  className,
}: {
  size?: 'sm' | 'md';
  invert?: boolean;
  className?: string;
}) {
  const sm = size === 'sm';

  return (
    <span className={clsx('inline-flex items-center gap-2.5', className)}>
      <Mark
        className={clsx(
          sm ? 'h-7 w-7' : 'h-9 w-9',
          invert ? 'text-white' : 'text-ink-900',
        )}
      />
      <span
        className={clsx(
          'font-semibold tracking-[-0.02em]',
          sm ? 'text-lg' : 'text-2xl',
          invert ? 'text-white' : 'text-ink-900',
        )}
      >
        ClaimSense
      </span>
      <span
        className={clsx(
          'font-mono uppercase tracking-[0.16em]',
          sm ? 'text-[0.5625rem]' : 'text-[0.625rem]',
          invert ? 'text-rail-dim' : 'text-ink-300',
        )}
      >
        AI
      </span>
    </span>
  );
}
