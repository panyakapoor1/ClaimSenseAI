'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { HeartPulse, ArrowRight, Loader2, User } from 'lucide-react';
import Link from 'next/link';

export default function LoginPage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState<string | null>(null);

  const handleLogin = (role: string) => {
    setIsLoading(role);
    // Simulate network request for auth
    setTimeout(() => {
      // In a real app, we would set a token/cookie here
      localStorage.setItem('auth_token', `demo_token_${role}`);
      router.push('/dashboard');
    }, 1500);
  };

  return (
    <div className="min-h-screen bg-[#000000] flex flex-col justify-center items-center p-6 text-white selection:bg-teal-500/30 font-sans relative overflow-hidden">
      
      {/* Background ambient light */}
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
        transition={{ type: "spring", stiffness: 300, damping: 30 }}
        className="w-full max-w-md relative z-10"
      >
        <div className="text-center mb-10">
          <h1 className="text-4xl font-bold tracking-tight mb-3">Welcome back.</h1>
          <p className="text-slate-400">Select a demo account to continue.</p>
        </div>

        <div className="bg-[#0f0f0f] border border-white/10 p-8">
          <div className="space-y-4">
            
            {/* Auditor Demo Account */}
            <button
              onClick={() => handleLogin('auditor')}
              disabled={isLoading !== null}
              className="w-full group relative flex items-center justify-between p-4 border border-white/10 hover:border-teal-500/50 bg-black hover:bg-[#050505] transition-all disabled:opacity-50 disabled:cursor-not-allowed text-left"
            >
              <div className="flex items-center">
                <div className="w-10 h-10 rounded-full bg-teal-500/20 flex items-center justify-center mr-4">
                  <User className="w-5 h-5 text-teal-400" />
                </div>
                <div>
                  <h3 className="font-medium text-white group-hover:text-teal-400 transition-colors">Medical Auditor</h3>
                  <p className="text-xs text-slate-500">auditor@demo.claimsense.ai</p>
                </div>
              </div>
              {isLoading === 'auditor' ? (
                <Loader2 className="w-5 h-5 text-teal-500 animate-spin" />
              ) : (
                <ArrowRight className="w-5 h-5 text-slate-600 group-hover:text-teal-500 group-hover:translate-x-1 transition-all" />
              )}
            </button>

            {/* Admin Demo Account */}
            <button
              onClick={() => handleLogin('admin')}
              disabled={isLoading !== null}
              className="w-full group relative flex items-center justify-between p-4 border border-white/10 hover:border-indigo-500/50 bg-black hover:bg-[#050505] transition-all disabled:opacity-50 disabled:cursor-not-allowed text-left"
            >
              <div className="flex items-center">
                <div className="w-10 h-10 rounded-full bg-indigo-500/20 flex items-center justify-center mr-4">
                  <User className="w-5 h-5 text-indigo-400" />
                </div>
                <div>
                  <h3 className="font-medium text-white group-hover:text-indigo-400 transition-colors">System Admin</h3>
                  <p className="text-xs text-slate-500">admin@demo.claimsense.ai</p>
                </div>
              </div>
              {isLoading === 'admin' ? (
                <Loader2 className="w-5 h-5 text-indigo-500 animate-spin" />
              ) : (
                <ArrowRight className="w-5 h-5 text-slate-600 group-hover:text-indigo-500 group-hover:translate-x-1 transition-all" />
              )}
            </button>

          </div>

          <div className="mt-8 pt-6 border-t border-white/10">
            <div className="text-center">
              <p className="text-xs text-slate-500">
                Demo environment. These accounts are unauthenticated placeholders — they select a
                display role and do not restrict access. Do not upload real patient data.
              </p>
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
