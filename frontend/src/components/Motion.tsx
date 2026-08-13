'use client';

import { useEffect, useRef, useState } from 'react';
import {
  motion,
  useInView,
  useMotionValue,
  useSpring,
  useReducedMotion,
  type Variants,
} from 'framer-motion';
import clsx from 'clsx';

/**
 * The house motion, in one place.
 *
 * Everything settles with a short drop and a hair of scale, the "stamp". It is
 * used instead of the usual slide-up so that the whole interface shares one
 * gesture, and so nothing travels far enough to be distracting on a page an
 * analyst reads all day.
 */
export const stamp: Variants = {
  hidden: { opacity: 0, y: 8, scale: 0.99 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { duration: 0.5, ease: [0.16, 1, 0.3, 1] },
  },
};

export const stagger: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.07, delayChildren: 0.04 } },
};

/** A block that stamps itself onto the page when it scrolls into view. */
export function Reveal({
  children,
  className,
  delay = 0,
  once = true,
}: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
  once?: boolean;
}) {
  return (
    <motion.div
      className={className}
      initial="hidden"
      whileInView="visible"
      viewport={{ once, margin: '-12% 0px -12% 0px' }}
      variants={{
        hidden: { opacity: 0, y: 8, scale: 0.99 },
        visible: {
          opacity: 1,
          y: 0,
          scale: 1,
          transition: { duration: 0.5, delay, ease: [0.16, 1, 0.3, 1] },
        },
      }}
    >
      {children}
    </motion.div>
  );
}

/** A container whose direct <Reveal>-less children stagger in. */
export function Stagger({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <motion.div
      className={className}
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, margin: '-10% 0px' }}
      variants={stagger}
    >
      {children}
    </motion.div>
  );
}

export function StaggerItem({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <motion.div className={className} variants={stamp}>
      {children}
    </motion.div>
  );
}

/** A hairline that draws itself left-to-right when it enters view. */
export function DrawRule({ className }: { className?: string }) {
  return (
    <motion.div
      className={clsx('h-px bg-line origin-left', className)}
      initial={{ scaleX: 0 }}
      whileInView={{ scaleX: 1 }}
      viewport={{ once: true }}
      transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
    />
  );
}

/**
 * A figure that counts up once, when it is first seen.
 *
 * Reduced-motion users get the final value immediately rather than a stripped
 * animation that still moves.
 */
export function Counter({
  to,
  decimals = 0,
  suffix = '',
  prefix = '',
  className,
}: {
  to: number;
  decimals?: number;
  suffix?: string;
  prefix?: string;
  className?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: '-15% 0px' });
  const reduce = useReducedMotion();
  const value = useMotionValue(0);
  const spring = useSpring(value, { stiffness: 62, damping: 20, mass: 0.9 });
  const [shown, setShown] = useState(0);

  useEffect(() => {
    if (inView) value.set(to);
  }, [inView, to, value]);

  useEffect(() => spring.on('change', (v) => setShown(v)), [spring]);

  const display = reduce || !inView ? (inView ? to : 0) : shown;

  return (
    <span ref={ref} className={clsx('tabular-nums', className)}>
      {prefix}
      {display.toFixed(decimals)}
      {suffix}
    </span>
  );
}

/** Text that reveals word by word. Reserved for the single hero headline. */
export function WordReveal({
  text,
  className,
  delay = 0,
}: {
  text: string;
  className?: string;
  delay?: number;
}) {
  const words = text.split(' ');

  return (
    <span className={className}>
      {words.map((word, i) => (
        // The gap lives on the clipping wrapper as a margin: a trailing space
        // inside an inline-block collapses, which would run the words together.
        <span
          key={i}
          className="inline-block overflow-hidden align-bottom"
          style={{ marginRight: i < words.length - 1 ? '0.26em' : undefined }}
        >
          <motion.span
            className="inline-block"
            initial={{ y: '105%' }}
            animate={{ y: 0 }}
            transition={{
              duration: 0.72,
              delay: delay + i * 0.055,
              ease: [0.16, 1, 0.3, 1],
            }}
          >
            {word}
          </motion.span>
        </span>
      ))}
    </span>
  );
}
