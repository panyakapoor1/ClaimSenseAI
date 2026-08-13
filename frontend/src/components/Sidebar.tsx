'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { LayoutDashboard, FileUp, ListChecks, FileText, LogOut, Loader2 } from 'lucide-react';
import clsx from 'clsx';
import { motion } from 'framer-motion';

import Wordmark from '@/components/Wordmark';
import ThemeToggle from '@/components/ThemeToggle';
import { API_V1 } from '@/lib/api';
import { CAPABILITIES, ROLE_LABELS, type Session } from '@/lib/roles';

/**
 * The dark half of the shell.
 *
 * The rail is the system; the workspace to its right is the documents. Keeping
 * them in opposite tones means an analyst always knows whether they are looking
 * at the application or at a claim.
 *
 * Roles are labelled in mono rather than colour-coded: in this interface colour
 * means adjudication status and nothing else, so a role badge does not get to
 * borrow it.
 */
export default function Sidebar({ session }: { session: Session }) {
  const pathname = usePathname();
  const router = useRouter();
  const [signingOut, setSigningOut] = useState(false);

  const { user, capabilities } = session;

  // Navigation reflects what this role can actually do. This is presentation
  // only. The server rejects the call regardless of what is rendered here.
  const navItems = [
    { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard, capability: CAPABILITIES.readClaims },
    { name: 'Upload claim', href: '/upload', icon: FileUp, capability: CAPABILITIES.createClaims },
    { name: 'Audit results', href: '/claims', icon: ListChecks, capability: CAPABILITIES.readClaims },
    { name: 'Appeals', href: '/appeals', icon: FileText, capability: CAPABILITIES.readClaims },
  ].filter((item) => capabilities.includes(item.capability));

  const handleLogout = async () => {
    setSigningOut(true);
    try {
      // credentials: 'include' so the browser sends the httpOnly cookie the
      // server needs in order to clear it.
      await fetch(`${API_V1}/auth/logout`, { method: 'POST', credentials: 'include' });
    } catch (err) {
      console.error('Logout request failed:', err);
    } finally {
      router.push('/login');
      router.refresh();
    }
  };

  const initials = user.full_name
    .split(' ')
    .map((part) => part[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();

  return (
    <aside className="no-print fixed left-0 top-0 z-50 flex h-screen w-64 flex-col bg-rail">
      <div className="flex h-[4.5rem] shrink-0 items-center border-b border-rail-line px-5">
        <Link href="/dashboard" className="transition-opacity hover:opacity-80">
          <Wordmark size="sm" invert />
        </Link>
      </div>

      <nav className="scroll-dark flex-1 overflow-y-auto px-3 py-6">
        <p className="eyebrow eyebrow-invert px-2 pb-3">Workspace</p>

        <div className="space-y-0.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive =
              pathname === item.href || pathname.startsWith(`${item.href}/`);

            return (
              <Link
                key={item.name}
                href={item.href}
                aria-current={isActive ? 'page' : undefined}
                className={clsx(
                  'group relative flex items-center gap-3 rounded-[2px] px-3 py-2.5 text-sm transition-colors',
                  isActive ? 'text-white' : 'text-rail-text hover:text-white',
                )}
              >
                {isActive && (
                  <motion.span
                    layoutId="rail-active"
                    className="absolute inset-0 rounded-[2px] bg-rail-raised"
                    initial={false}
                    transition={{ type: 'spring', stiffness: 380, damping: 32 }}
                  />
                )}
                {/* The marker echoes the stamp in the logo. */}
                {isActive && (
                  <motion.span
                    layoutId="rail-marker"
                    className="absolute left-0 top-1/2 h-4 w-[2px] -translate-y-1/2 bg-white"
                    initial={false}
                    transition={{ type: 'spring', stiffness: 380, damping: 32 }}
                  />
                )}
                <Icon
                  className={clsx(
                    'relative z-10 h-[1.125rem] w-[1.125rem] shrink-0 transition-colors',
                    isActive ? 'text-white' : 'text-rail-dim group-hover:text-rail-text',
                  )}
                  strokeWidth={1.6}
                />
                <span className="relative z-10 font-medium">{item.name}</span>
              </Link>
            );
          })}
        </div>
      </nav>

      <div className="shrink-0 border-t border-rail-line p-3">
        <div className="flex items-center gap-3 rounded-[2px] px-2 py-2.5">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[2px] bg-rail-raised font-mono text-[0.6875rem] text-rail-text">
            {initials}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-white">{user.full_name}</p>
            <p className="eyebrow eyebrow-invert mt-1 truncate">
              {ROLE_LABELS[user.role]}
            </p>
          </div>
          <ThemeToggle invert />
        </div>

        <button
          onClick={handleLogout}
          disabled={signingOut}
          className="mt-1 flex w-full items-center gap-3 rounded-[2px] px-3 py-2.5 text-sm text-rail-dim transition-colors hover:bg-rail-raised hover:text-rail-text disabled:opacity-50"
        >
          {signingOut ? (
            <Loader2 className="h-[1.125rem] w-[1.125rem] animate-spin" />
          ) : (
            <LogOut className="h-[1.125rem] w-[1.125rem]" strokeWidth={1.6} />
          )}
          <span className="font-medium">{signingOut ? 'Signing out…' : 'Sign out'}</span>
        </button>
      </div>
    </aside>
  );
}
