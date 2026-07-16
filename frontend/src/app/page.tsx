import Link from "next/link";
import { ArrowRight, Activity, FileCheck2, FileUp, Sparkles } from "lucide-react";

export default function Home() {
  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <header className="mb-10">
        <h1 className="text-4xl font-bold tracking-tight text-white mb-2">
          Dashboard
        </h1>
        <p className="text-slate-400 text-lg">
          Welcome to ClaimSense AI. Your intelligent medical claim auditor.
        </p>
      </header>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="glass-panel p-6 flex flex-col relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
            <Activity className="w-24 h-24 text-teal-400" />
          </div>
          <div className="flex items-center space-x-4 mb-4">
            <div className="w-12 h-12 rounded-full bg-teal-500/20 flex items-center justify-center">
              <Activity className="w-6 h-6 text-teal-400" />
            </div>
            <h2 className="text-xl font-semibold text-white">Active Audits</h2>
          </div>
          <p className="text-4xl font-bold text-white mt-auto">0</p>
          <p className="text-teal-400 text-sm font-medium mt-2">Currently processing</p>
        </div>

        <div className="glass-panel p-6 flex flex-col relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
            <FileCheck2 className="w-24 h-24 text-indigo-400" />
          </div>
          <div className="flex items-center space-x-4 mb-4">
            <div className="w-12 h-12 rounded-full bg-indigo-500/20 flex items-center justify-center">
              <FileCheck2 className="w-6 h-6 text-indigo-400" />
            </div>
            <h2 className="text-xl font-semibold text-white">Processed Claims</h2>
          </div>
          <p className="text-4xl font-bold text-white mt-auto">0</p>
          <p className="text-indigo-400 text-sm font-medium mt-2">Historically audited</p>
        </div>

        <div className="glass-panel p-6 flex flex-col relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
            <Sparkles className="w-24 h-24 text-rose-400" />
          </div>
          <div className="flex items-center space-x-4 mb-4">
            <div className="w-12 h-12 rounded-full bg-rose-500/20 flex items-center justify-center">
              <Sparkles className="w-6 h-6 text-rose-400" />
            </div>
            <h2 className="text-xl font-semibold text-white">Appeals Generated</h2>
          </div>
          <p className="text-4xl font-bold text-white mt-auto">0</p>
          <p className="text-rose-400 text-sm font-medium mt-2">Successful drafts</p>
        </div>
      </div>

      {/* Quick Actions */}
      <h2 className="text-2xl font-bold text-white mt-12 mb-6">Quick Actions</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Link href="/upload" className="block">
          <div className="glass-panel p-6 border-teal-500/30 hover:border-teal-400/60 hover:bg-slate-800/80 transition-all cursor-pointer group h-full">
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 rounded-full bg-gradient-to-br from-teal-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-teal-500/20 group-hover:scale-110 transition-transform">
                <FileUp className="w-6 h-6 text-white" />
              </div>
              <ArrowRight className="w-6 h-6 text-slate-500 group-hover:text-teal-400 transition-colors group-hover:translate-x-1" />
            </div>
            <h3 className="text-xl font-semibold text-white mb-2">Upload & Audit Claim</h3>
            <p className="text-slate-400">
              Upload a new medical bill and an insurance policy to automatically parse, audit, and flag discrepancies using AI.
            </p>
          </div>
        </Link>
        
        <Link href="/claims" className="block">
          <div className="glass-panel p-6 border-indigo-500/30 hover:border-indigo-400/60 hover:bg-slate-800/80 transition-all cursor-pointer group h-full">
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 rounded-full bg-slate-800 border border-indigo-500/50 flex items-center justify-center group-hover:scale-110 transition-transform">
                <ListChecks className="w-6 h-6 text-indigo-400" />
              </div>
              <ArrowRight className="w-6 h-6 text-slate-500 group-hover:text-indigo-400 transition-colors group-hover:translate-x-1" />
            </div>
            <h3 className="text-xl font-semibold text-white mb-2">View Audit Results</h3>
            <p className="text-slate-400">
              Review completed claim audits, inspect the reasoning of the AI Claim Auditor, and generate appeal letters for denied items.
            </p>
          </div>
        </Link>
      </div>
    </div>
  );
}
