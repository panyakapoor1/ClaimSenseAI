'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { ArrowLeft, ArrowRight, Loader2, AlertTriangle } from 'lucide-react';
import Link from 'next/link';

import Wordmark from '@/components/Wordmark';
import ThemeToggle from '@/components/ThemeToggle';
import { API_V1, readError } from '@/lib/api';

/**
 * The seeded demo accounts, one per role.
 *
 * These are real accounts with real hashed passwords behind real authentication.
 * The credentials are shown because they are deliberately public demo logins.
 * Hiding them would imply a secrecy the environment does not have.
 */
const DEMO_ACCOUNTS = [
  {
    email: 'analyst@demo.claimsense.ai',
    label: 'Analyst',
    blurb: 'Uploads claims, runs audits, escalates and investigates',
  },
  {
    email: 'senior@demo.claimsense.ai',
    label: 'Senior Analyst',
    blurb: 'Everything an analyst can do, plus approve, reject and override',
  },
  {
    email: 'admin@demo.claimsense.ai',
    label: 'Administrator',
    blurb: 'Manages the platform, and deliberately cannot adjudicate a claim',
  },
  {
    email: 'auditor@demo.claimsense.ai',
    label: 'Auditor',
    blurb: 'Read-only oversight across the organisation',
  },
];

const DEMO_PASSWORD = 'claimsense-demo';

export default function LoginPage() {
  const router = useRouter();
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const signIn = async (email: string) => {
    setPending(email);
    setError(null);

    try {
      const res = await fetch(`${API_V1}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        // Lets the browser store the httpOnly session cookie the API sets.
        credentials: 'include',
        body: JSON.stringify({ email, password: DEMO_PASSWORD }),
      });

      if (!res.ok) {
        throw new Error(await readError(res, 'Could not sign in.'));
      }

      router.push('/dashboard');
      // Server Components cache the anonymous render otherwise, so the
      // dashboard would load without the session that was just established.
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not sign in.');
      setPending(null);
    }
  };

  return (
    <div className="grid min-h-screen lg:grid-cols-[0.85fr_1fr]">
      {/* The rail, carried over from the workspace shell. */}
      <aside className="relative hidden flex-col justify-between bg-rail p-12 lg:flex">
        <Link href="/" className="transition-opacity hover:opacity-80">
          <Wordmark invert />
        </Link>

        <div>
          <motion.p
            className="display max-w-sm text-3xl leading-[1.15] text-white"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
          >
            Four roles, enforced by the server.
          </motion.p>
          <motion.p
            className="mt-5 max-w-sm leading-relaxed text-rail-text"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.12, duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
          >
            Administering the platform and deciding a patient’s claim are
            different jobs. Conflating them is how an audit trail stops meaning
            anything. Sign in as an auditor and the decision controls are not
            merely hidden, they are refused.
          </motion.p>
        </div>

        <p className="eyebrow eyebrow-invert">Demo environment</p>
      </aside>

      {/* The account chooser. */}
      <main className="flex flex-col justify-center bg-paper px-6 py-12 sm:px-12 lg:px-16">
        <div className="mx-auto w-full max-w-md">
          <div className="flex items-center justify-between gap-3">
            <Link
              href="/"
              className="inline-flex items-center gap-2 text-sm text-ink-500 transition-colors hover:text-ink-900 lg:hidden"
            >
              <ArrowLeft className="h-4 w-4" />
              Back
            </Link>
            <div className="ml-auto">
              <ThemeToggle />
            </div>
          </div>

          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          >
            <p className="eyebrow mt-8 lg:mt-0">Sign in</p>
            <h1 className="display mt-4 text-3xl text-ink-900">
              Choose a demo account
            </h1>
            <p className="mt-3 leading-relaxed text-ink-700">
              Each one lands in the same workspace with different permissions.
            </p>
          </motion.div>

          {error && (
            <motion.div
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              className="mt-6 flex items-start gap-2.5 border border-rejected-line bg-rejected-soft p-3"
            >
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-rejected" />
              <p className="text-sm text-rejected">{error}</p>
            </motion.div>
          )}

          <div className="mt-8 border-t border-line">
            {DEMO_ACCOUNTS.map((account, i) => (
              <motion.button
                key={account.email}
                onClick={() => signIn(account.email)}
                disabled={pending !== null}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{
                  delay: 0.1 + i * 0.06,
                  duration: 0.5,
                  ease: [0.16, 1, 0.3, 1],
                }}
                className="group flex w-full items-center justify-between gap-4 border-b border-line py-4 text-left transition-colors hover:bg-mist disabled:cursor-not-allowed disabled:opacity-40"
              >
                <span className="min-w-0 pl-1">
                  <span className="block font-medium text-ink-900">
                    {account.label}
                  </span>
                  <span className="mt-1 block text-sm text-ink-500">
                    {account.blurb}
                  </span>
                  <span className="mt-1.5 block font-mono text-xs text-ink-300">
                    {account.email}
                  </span>
                </span>

                {pending === account.email ? (
                  <Loader2 className="h-4 w-4 shrink-0 animate-spin text-ink-500" />
                ) : (
                  <ArrowRight className="h-4 w-4 shrink-0 text-ink-300 transition-all group-hover:translate-x-1 group-hover:text-ink-900" />
                )}
              </motion.button>
            ))}
          </div>

          <p className="mt-8 text-xs leading-relaxed text-ink-500">
            The shared password is{' '}
            <code className="font-mono text-ink-700">{DEMO_PASSWORD}</code>. These
            are real accounts behind real authentication, and every role is
            enforced server-side. Do not upload real patient data.
          </p>
        </div>
      </main>
    </div>
  );
}
