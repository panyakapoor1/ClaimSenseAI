'use client';

import { useState } from 'react';
import { Sparkles, X } from 'lucide-react';
import { useRouter } from 'next/navigation';
import LiveTaskTracker from './LiveTaskTracker';
import { API_V1, readError } from '@/lib/api';

export default function GenerateAppealButton({ claimId }: { claimId: string }) {
  const [isGenerating, setIsGenerating] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const router = useRouter();

  const handleGenerate = async () => {
    setIsGenerating(true);
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
      setIsGenerating(false);
      alert('Error generating appeal');
    }
  };

  const handleComplete = () => {
    router.push(`/appeals/${claimId}`);
  };

  return (
    <>
      <button 
        onClick={handleGenerate}
        className="bg-gradient-to-r from-rose-500 to-indigo-600 text-white font-medium rounded-lg hover:from-rose-400 hover:to-indigo-500 shadow-lg shadow-rose-500/20 transition-all active:scale-95 px-5 py-2.5 flex items-center"
      >
        <Sparkles className="w-5 h-5 mr-2" />
        Generate AI Appeal Letter
      </button>

      {jobId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-2xl relative">
            <button 
              onClick={() => setJobId(null)}
              className="absolute -top-12 right-0 text-slate-400 hover:text-white"
            >
              <X className="w-8 h-8" />
            </button>
            <LiveTaskTracker jobId={jobId} onComplete={handleComplete} />
          </div>
        </div>
      )}
    </>
  );
}
