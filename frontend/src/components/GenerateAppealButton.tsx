'use client';

import { useState } from 'react';
import { X, Loader2, AlertTriangle } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';

import LiveTaskTracker from './LiveTaskTracker';
import { API_V1, readError } from '@/lib/api';

export default function GenerateAppealButton({ claimId }: { claimId: string }) {
  const [isGenerating, setIsGenerating] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  const handleGenerate = async () => {
    setIsGenerating(true);
    setError(null);
    try {
      const res = await fetch(`${API_V1}/claims/${claimId}/appeal`, {
        method: 'POST',
        credentials: 'include',
      });
      if (!res.ok) throw new Error(await readError(res, 'Could not start appeal generation.'));
      const data = await res.json();
      setJobId(data.job_id);
    } catch (err) {
      console.error(err);
      // Reported in place rather than through alert(), which cannot be styled
      // and reads as the browser talking rather than the application.
      setError(err instanceof Error ? err.message : 'Could not start appeal generation.');
      setIsGenerating(false);
    }
  };

  return (
    <>
      <div className="flex flex-col items-end gap-2">
        <button onClick={handleGenerate} disabled={isGenerating} className="btn">
          {isGenerating && !jobId ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Starting…
            </>
          ) : (
            'Draft an appeal'
          )}
        </button>

        {error && (
          <p className="flex items-start gap-1.5 text-xs text-rejected">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            {error}
          </p>
        )}
      </div>

      <AnimatePresence>
        {jobId && (
          <motion.div
            className="fixed inset-0 z-50 flex items-center justify-center bg-ink-900/40 p-4 backdrop-blur-[2px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
          >
            <motion.div
              className="relative w-full max-w-2xl"
              initial={{ opacity: 0, y: 10, scale: 0.99 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 10, scale: 0.99 }}
              transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
            >
              <button
                onClick={() => {
                  setJobId(null);
                  setIsGenerating(false);
                }}
                aria-label="Close"
                className="absolute -top-10 right-0 text-white/70 transition-colors hover:text-white"
              >
                <X className="h-5 w-5" />
              </button>

              <LiveTaskTracker
                jobId={jobId}
                onComplete={() => router.push(`/appeals/${claimId}`)}
              />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
