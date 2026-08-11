'use client';

import Link from 'next/link';
import { motion, type Variants } from 'framer-motion';
import { ArrowRight, CheckCircle2, ShieldCheck, Zap } from 'lucide-react';
import { HeartPulse } from 'lucide-react';

// Annotated so the literal "spring" narrows to Framer's generator union rather
// than widening to string, which fails to satisfy Variants.
const fadeIn: Variants = {
  hidden: { opacity: 0, y: 20 },
  visible: { 
    opacity: 1, 
    y: 0,
    transition: { type: "spring", stiffness: 300, damping: 30 }
  }
};

const staggerContainer: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1
    }
  }
};

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[#000000] text-white selection:bg-teal-500/30 font-sans">
      {/* Navigation */}
      <nav className="flex items-center justify-between px-8 py-6 max-w-7xl mx-auto border-b border-white/10">
        <div className="flex items-center">
          <HeartPulse className="w-8 h-8 text-white mr-3" />
          <span className="font-bold text-2xl tracking-tight">
            ClaimSense<span className="text-teal-400">AI</span>
          </span>
        </div>
        <div className="flex items-center space-x-6">
          <Link href="/login" className="text-sm font-medium text-slate-300 hover:text-white transition-colors">
            Log in
          </Link>
          <Link href="/login" className="bg-white text-black px-5 py-2.5 rounded-none font-medium text-sm hover:bg-slate-200 transition-colors">
            Sign up
          </Link>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-8 pt-24 pb-32">
        <motion.div 
          variants={staggerContainer}
          initial="hidden"
          animate="visible"
          className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center"
        >
          {/* Hero Content */}
          <div className="space-y-8">
            <motion.h1 
              variants={fadeIn}
              className="text-6xl md:text-7xl font-bold tracking-tighter leading-[1.1]"
            >
              Medical audits,<br />
              powered by AI.
            </motion.h1>
            
            <motion.p 
              variants={fadeIn}
              className="text-xl text-slate-400 max-w-lg leading-relaxed"
            >
              Automatically parse, audit, and flag discrepancies in complex medical claims with unprecedented speed and accuracy.
            </motion.p>
            
            <motion.div variants={fadeIn} className="pt-4 flex flex-col sm:flex-row gap-4">
              <Link 
                href="/login"
                className="inline-flex items-center justify-center bg-teal-500 text-black px-8 py-4 font-semibold text-lg hover:bg-teal-400 transition-colors"
              >
                Start Demo
                <ArrowRight className="ml-2 w-5 h-5" />
              </Link>
            </motion.div>
          </div>

          {/* Hero Graphic / Features Grid */}
          <motion.div variants={fadeIn} className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            <div className="bg-[#0f0f0f] border border-white/10 p-8 flex flex-col items-start justify-between min-h-[240px] hover:border-white/30 transition-colors cursor-default">
              <Zap className="w-10 h-10 text-white mb-6" />
              <div>
                <h3 className="text-xl font-bold mb-2">Line-item extraction</h3>
                <p className="text-slate-400 text-sm">Parses a hospital bill PDF into categorised, structured charges.</p>
              </div>
            </div>

            <div className="bg-[#0f0f0f] border border-white/10 p-8 flex flex-col items-start justify-between min-h-[240px] hover:border-white/30 transition-colors cursor-default">
              <ShieldCheck className="w-10 h-10 text-white mb-6" />
              <div>
                <h3 className="text-xl font-bold mb-2">Policy matching</h3>
                <p className="text-slate-400 text-sm">Retrieves the governing clause for each charge and cites its section and page.</p>
              </div>
            </div>

            <div className="bg-[#0f0f0f] border border-white/10 p-8 flex flex-col items-start justify-between min-h-[240px] hover:border-white/30 transition-colors cursor-default sm:col-span-2">
              <CheckCircle2 className="w-10 h-10 text-teal-400 mb-6" />
              <div>
                <h3 className="text-xl font-bold mb-2">Automated appeals</h3>
                <p className="text-slate-400 text-sm">Drafts a formal appeal letter arguing each disputed charge against the clause used to reject it.</p>
              </div>
            </div>
          </motion.div>
        </motion.div>
      </main>
    </div>
  );
}
