'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { LayoutDashboard, FileUp, ListChecks, FileText, HeartPulse, LogOut, User } from 'lucide-react';
import clsx from 'clsx';
import { motion } from 'framer-motion';

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [role, setRole] = useState<string | null>(null);

  useEffect(() => {
    // Read the auth token from local storage
    const token = localStorage.getItem('auth_token');
    if (token) {
      if (token.includes('admin')) {
        setRole('admin');
      } else if (token.includes('auditor')) {
        setRole('auditor');
      }
    } else {
      // Not logged in, redirect to login
      router.push('/login');
    }
  }, [router]);

  const handleLogout = () => {
    localStorage.removeItem('auth_token');
    router.push('/login');
  };

  const navItems = [
    { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
    { name: 'Upload Claim', href: '/upload', icon: FileUp },
    { name: 'Audit Results', href: '/claims', icon: ListChecks },
    { name: 'Appeals', href: '/appeals', icon: FileText },
  ];

  return (
    <motion.aside 
      initial={{ x: -300, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      transition={{ type: "spring", stiffness: 100, damping: 20 }}
      className="w-64 h-screen border-r border-white/10 bg-[#000000] flex flex-col fixed left-0 top-0 z-50"
    >
      <div className="h-20 flex items-center px-6 border-b border-white/10 relative overflow-hidden shrink-0">
        <HeartPulse className="w-7 h-7 text-teal-400 mr-3 relative z-10" />
        <span className="font-bold text-2xl tracking-tight text-slate-100 relative z-10">
          ClaimSense<span className="text-teal-400">AI</span>
        </span>
      </div>

      <nav className="flex-1 overflow-y-auto py-8 px-4 space-y-2 relative">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href || (item.href !== '/' && pathname.startsWith(item.href));
          
          return (
            <Link
              key={item.name}
              href={item.href}
              className={clsx(
                'relative flex items-center px-4 py-3 rounded-none transition-colors group overflow-hidden',
                isActive ? 'text-teal-400' : 'text-slate-400 hover:text-slate-200'
              )}
            >
              {isActive && (
                <motion.div
                  layoutId="sidebar-active"
                  className="absolute inset-0 bg-[#0f0f0f] border border-white/10 rounded-none"
                  initial={false}
                  transition={{ type: "spring", stiffness: 300, damping: 30 }}
                />
              )}
              
              <Icon 
                className={clsx(
                  'w-5 h-5 mr-3 transition-colors relative z-10',
                  isActive ? 'text-teal-400' : 'text-slate-500 group-hover:text-slate-300'
                )} 
              />
              <span className="font-medium relative z-10">{item.name}</span>
              
              {isActive && (
                <motion.div 
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  className="absolute right-4 w-1.5 h-1.5 rounded-full bg-teal-400 shadow-[0_0_12px_rgba(45,212,191,1)] z-10" 
                />
              )}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-white/10 p-4 shrink-0 space-y-2 bg-[#050505]">
        {/* User Profile Area */}
        <div className="flex items-center px-4 py-3 mb-2 border border-white/5 bg-black">
          <div className={clsx(
            "w-8 h-8 rounded-full flex items-center justify-center mr-3",
            role === 'admin' ? "bg-indigo-500/20" : "bg-teal-500/20"
          )}>
            <User className={clsx(
              "w-4 h-4",
              role === 'admin' ? "text-indigo-400" : "text-teal-400"
            )} />
          </div>
          <div>
            <p className="text-sm font-medium text-white capitalize">{role ? `${role} Account` : 'Loading...'}</p>
            <p className="text-xs text-slate-500">demo environment</p>
          </div>
        </div>

        <button
          onClick={handleLogout}
          className="flex items-center w-full px-4 py-2.5 text-sm text-rose-400 hover:text-rose-300 hover:bg-rose-500/10 rounded-none transition-colors"
        >
          <LogOut className="w-5 h-5 mr-3 text-rose-500" />
          <span className="font-medium">Log out</span>
        </button>
      </div>
    </motion.aside>
  );
}
