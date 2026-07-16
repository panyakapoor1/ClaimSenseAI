'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, FileUp, ListChecks, FileText, Settings, HeartPulse } from 'lucide-react';
import clsx from 'clsx';

const navItems = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Upload Claim', href: '/upload', icon: FileUp },
  { name: 'Audit Results', href: '/claims', icon: ListChecks },
  { name: 'Appeals', href: '/appeals', icon: FileText },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 h-screen border-r border-slate-800 bg-slate-900/50 backdrop-blur-xl flex flex-col fixed left-0 top-0">
      <div className="h-16 flex items-center px-6 border-b border-slate-800/50">
        <HeartPulse className="w-6 h-6 text-teal-400 mr-3" />
        <span className="font-bold text-xl tracking-tight text-slate-100">
          ClaimSense<span className="text-teal-400">AI</span>
        </span>
      </div>

      <nav className="flex-1 py-6 px-3 space-y-1">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href || (item.href !== '/' && pathname.startsWith(item.href));
          
          return (
            <Link
              key={item.name}
              href={item.href}
              className={clsx(
                'flex items-center px-3 py-2.5 rounded-lg transition-all duration-200 group',
                isActive 
                  ? 'bg-gradient-to-r from-teal-500/10 to-indigo-500/10 text-teal-400 font-medium' 
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              )}
            >
              <Icon 
                className={clsx(
                  'w-5 h-5 mr-3 transition-colors',
                  isActive ? 'text-teal-400' : 'text-slate-500 group-hover:text-slate-300'
                )} 
              />
              {item.name}
              {isActive && (
                <div className="ml-auto w-1.5 h-1.5 rounded-full bg-teal-400 shadow-[0_0_8px_rgba(45,212,191,0.8)]" />
              )}
            </Link>
          );
        })}
      </nav>

      <div className="p-4 border-t border-slate-800/50">
        <button className="flex items-center w-full px-3 py-2.5 text-sm text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 rounded-lg transition-colors">
          <Settings className="w-5 h-5 mr-3 text-slate-500" />
          Settings
        </button>
      </div>
    </aside>
  );
}
