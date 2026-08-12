'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { LayoutDashboard, FileUp, ListChecks, FileText, HeartPulse, LogOut, Loader2, User } from 'lucide-react';
import clsx from 'clsx';
import { motion } from 'framer-motion';

import { API_V1 } from '@/lib/api';
import { CAPABILITIES, ROLE_LABELS, type Session } from '@/lib/roles';

const ROLE_ACCENT: Record<string, string> = {
  ADMIN: 'bg-indigo-500/20 text-indigo-300',
  SENIOR_ANALYST: 'bg-violet-500/20 text-violet-300',
  ANALYST: 'bg-teal-500/20 text-teal-300',
  AUDITOR: 'bg-slate-500/20 text-slate-300',
};

export default function Sidebar({ session }: { session: Session }) {
  const pathname = usePathname();
  const router = useRouter();
  const [signingOut, setSigningOut] = useState(false);

  const { user, capabilities } = session;

  // Navigation reflects what this role can actually do. This is presentation
  // only — the server rejects the call regardless of what is rendered here.
  const navItems = [
    { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard, capability: CAPABILITIES.readClaims },
    { name: 'Upload Claim', href: '/upload', icon: FileUp, capability: CAPABILITIES.createClaims },
    { name: 'Audit Results', href: '/claims', icon: ListChecks, capability: CAPABILITIES.readClaims },
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

  return (
    <motion.aside
      initial={{ x: -300, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      transition={{ type: 'spring', stiffness: 100, damping: 20 }}
      className="w-64 h-screen border-r border-white/10 bg-[#000000] flex flex-col fixed left-0 top-0 z-50"
    >
      <div className="h-20 flex items-center px-6 border-b border-white/10 shrink-0">
        <HeartPulse className="w-7 h-7 text-teal-400 mr-3" />
        <span className="font-bold text-2xl tracking-tight text-slate-100">
          ClaimSense<span className="text-teal-400">AI</span>
        </span>
      </div>

      <nav className="flex-1 overflow-y-auto py-8 px-4 space-y-2">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);

          return (
            <Link
              key={item.name}
              href={item.href}
              className={clsx(
                'relative flex items-center px-4 py-3 transition-colors group overflow-hidden',
                isActive ? 'text-teal-400' : 'text-slate-400 hover:text-slate-200',
              )}
            >
              {isActive && (
                <motion.div
                  layoutId="sidebar-active"
                  className="absolute inset-0 bg-[#0f0f0f] border border-white/10"
                  initial={false}
                  transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                />
              )}
              <Icon
                className={clsx(
                  'w-5 h-5 mr-3 transition-colors relative z-10',
                  isActive ? 'text-teal-400' : 'text-slate-500 group-hover:text-slate-300',
                )}
              />
              <span className="font-medium relative z-10">{item.name}</span>
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-white/10 p-4 shrink-0 space-y-2 bg-[#050505]">
        <div className="flex items-center px-4 py-3 mb-2 border border-white/5 bg-black">
          <div
            className={clsx(
              'w-8 h-8 flex items-center justify-center mr-3 shrink-0',
              ROLE_ACCENT[user.role] ?? ROLE_ACCENT.AUDITOR,
            )}
          >
            <User className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-medium text-white truncate">{user.full_name}</p>
            <p className="text-xs text-slate-500">{ROLE_LABELS[user.role]}</p>
          </div>
        </div>

        <button
          onClick={handleLogout}
          disabled={signingOut}
          className="flex items-center w-full px-4 py-2.5 text-sm text-rose-400 hover:text-rose-300 hover:bg-rose-500/10 transition-colors disabled:opacity-50"
        >
          {signingOut ? (
            <Loader2 className="w-5 h-5 mr-3 animate-spin" />
          ) : (
            <LogOut className="w-5 h-5 mr-3 text-rose-500" />
          )}
          <span className="font-medium">{signingOut ? 'Signing out…' : 'Sign out'}</span>
        </button>
      </div>
    </motion.aside>
  );
}
