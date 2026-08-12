'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { HeartPulse, ArrowRight, Loader2, AlertTriangle } from 'lucide-react';
import Link from 'next/link';

import { API_V1, readError } from '@/lib/api';

/**
 * The seeded demo accounts, one per role.
 *
 * These are real accounts with real hashed passwords behind real authentication.
 * The credentials are shown because they are deliberately public demo logins —
 * hiding them would imply a secrecy the environment does not have.
 */
const DEMO_ACCOUNTS = [
  {
    email: 'analyst@demo.claimsense.ai',
    label: 'Analyst',
    blurb: 'Uploads claims and runs audits',
    accent: 'hover:border-teal-500/50 group-hover:text-teal-400',
  },
  {
    email: 'senior@demo.claimsense.ai',
    label: 'Senior Analyst',
    blurb: 'Also approves and escalates',
    accent: 'hover:border-violet-500/50 group-hover:text-violet-400',
  },
  {
    email: 'admin@demo.claimsense.ai',
    label: 'Administrator',
    blurb: 'Manages the platform',
    accent: 'hover:border-indigo-500/50 group-hover:text-indigo-400',
  },
  {
    email: 'auditor@demo.claimsense.ai',
    label: 'Auditor',
    blurb: 'Read-only oversight',
    accent: 'hover:border-slate-400/50 group-hover:text-slate-200',
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
    <div className="min-h-screen bg-black flex flex-col justify-center items-center p-6 text-white font-sans relative overflow-hidden">
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-teal-500/10 blur-[120px] rounded-full pointer-events-none" />

      <Link href="/" className="absolute top-8 left-8 flex items-center hover:opacity-80 transition-opacity z-10">
        <HeartPulse className="w-8 h-8 text-white mr-3" />
        <span className="font-bold text-2xl tracking-tight">
          ClaimSense<span className="text-teal-400">AI</span>
        </span>
      </Link>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ type: 'spring', stiffness: 300, damping: 30 }}
        className="w-full max-w-md relative z-10"
      >
        <div className="text-center mb-10">
          <h1 className="text-4xl font-bold tracking-tight mb-3">Sign in</h1>
          <p className="text-slate-400">Choose a demo account to see its permissions.</p>
        </div>

        <div className="bg-[#0f0f0f] border border-white/10 p-8">
          {error && (
            <div className="mb-5 border border-rose-500/30 bg-rose-500/10 p-3 flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <p className="text-rose-200 text-sm">{error}</p>
            </div>
          )}

          <div className="space-y-3">
            {DEMO_ACCOUNTS.map((account) => (
              <button
                key={account.email}
                onClick={() => signIn(account.email)}
                disabled={pending !== null}
                className={`w-full group flex items-center justify-between p-4 border border-white/10 bg-black transition-all disabled:opacity-40 disabled:cursor-not-allowed text-left ${account.accent}`}
              >
                <div className="min-w-0">
                  <h3 className="font-medium text-white transition-colors">{account.label}</h3>
                  <p className="text-xs text-slate-500 mt-0.5">{account.blurb}</p>
                </div>
                {pending === account.email ? (
                  <Loader2 className="w-5 h-5 text-slate-400 animate-spin shrink-0" />
                ) : (
                  <ArrowRight className="w-5 h-5 text-slate-600 group-hover:translate-x-1 transition-transform shrink-0" />
                )}
              </button>
            ))}
          </div>

          <div className="mt-8 pt-6 border-t border-white/10">
            <p className="text-xs text-slate-500 leading-relaxed">
              Demo environment. These are real accounts with real passwords — the shared
              password is <code className="text-slate-400">{DEMO_PASSWORD}</code> and every
              role is enforced by the server. Do not upload real patient data.
            </p>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
