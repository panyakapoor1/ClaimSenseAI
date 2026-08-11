'use client';

import { useEffect, useState, useRef } from 'react';
import { Loader2, CheckCircle2, Bot, AlertCircle } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { WS_URL } from '@/lib/api';

interface LiveTaskTrackerProps {
  jobId: string;
  onComplete: () => void;
}

interface LogEntry {
  message: string;
  progress: number;
}

export default function LiveTaskTracker({ jobId, onComplete }: LiveTaskTrackerProps) {
  const [progress, setProgress] = useState(0);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [status, setStatus] = useState<'running' | 'completed' | 'failed'>('running');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Connect to WebSocket
    const ws = new WebSocket(`${WS_URL}/ws/tasks/${jobId}`);

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        // The server sends a handshake frame before any task events.
        if (data.type === 'connected') return;
        if (data.type !== 'progress') return;

        // The backend publishes `progress_pct`.
        const pct = data.progress_pct ?? data.progress ?? 0;

        if (data.status === 'error') {
          setStatus('failed');
          setErrorMessage(data.message ?? 'The task failed.');
          setLogs(prev => [...prev, { message: data.message ?? 'Task failed.', progress: pct }]);
          return;
        }

        if (data.status === 'completed') {
          setProgress(100);
          setStatus('completed');
          setLogs(prev => [...prev, { message: data.message ?? 'Complete!', progress: 100 }]);
          return;
        }

        setProgress(pct);
        setLogs(prev => [...prev, { message: data.message, progress: pct }]);
      } catch (err) {
        console.error('Error parsing WS message', err);
      }
    };

    ws.onerror = (err) => {
      console.error('WebSocket error:', err);
      setStatus(prev => (prev === 'completed' ? prev : 'failed'));
    };

    ws.onclose = () => {
      console.log('WebSocket connection closed');
    };

    return () => {
      ws.close();
    };
  }, [jobId]);

  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs]);

  return (
    <div className="glass-panel p-8 max-w-2xl mx-auto shadow-[0_8px_32px_rgba(45,212,191,0.1)]">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center">
            {status === 'running' && <Loader2 className="w-6 h-6 mr-3 text-teal-400 animate-spin" />}
            {status === 'completed' && <CheckCircle2 className="w-6 h-6 mr-3 text-emerald-400" />}
            {status === 'failed' && <AlertCircle className="w-6 h-6 mr-3 text-rose-400" />}
            AI Agent Audit in Progress
          </h2>
          <p className="text-slate-400 mt-2 text-sm">
            Job ID: <span className="font-mono text-slate-300">{jobId}</span>
          </p>
        </div>
        <motion.div 
          animate={status === 'running' ? { rotate: [0, 5, -5, 0] } : {}}
          transition={{ repeat: Infinity, duration: 2, ease: "easeInOut" }}
          className="w-16 h-16 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center shadow-[0_0_15px_rgba(99,102,241,0.2)]"
        >
          <Bot className="w-8 h-8 text-indigo-400" />
        </motion.div>
      </div>

      {/* Progress Bar */}
      <div className="mb-8">
        <div className="flex justify-between text-sm mb-2">
          <span className="text-slate-300 font-medium">Overall Progress</span>
          <span className="text-teal-400 font-bold">{progress}%</span>
        </div>
        <div className="h-3 w-full bg-slate-900/50 rounded-full overflow-hidden border border-white/5">
          <motion.div 
            initial={{ width: 0 }}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.5, ease: "easeOut" }}
            className="h-full bg-gradient-to-r from-teal-500 to-indigo-500 relative"
          >
            {/* Shimmer effect inside progress bar */}
            <div className="absolute top-0 bottom-0 left-0 right-0 bg-gradient-to-r from-transparent via-white/20 to-transparent w-[200%] animate-[shimmer_2s_infinite]" style={{ backgroundSize: '50% 100%' }} />
          </motion.div>
        </div>
      </div>

      {/* Terminal / Logs View */}
      <div className="bg-slate-950/80 border border-white/5 rounded-xl p-5 font-mono text-sm h-64 overflow-y-auto space-y-3 shadow-inner relative">
        <AnimatePresence initial={false}>
          {logs.length === 0 ? (
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="text-slate-500 flex items-center"
            >
              <span className="w-2 h-2 rounded-full bg-teal-500 animate-pulse mr-3" />
              Initializing ClaimSense Auditor...
            </motion.div>
          ) : (
            logs.map((log, index) => (
              <motion.div 
                key={index} 
                initial={{ opacity: 0, x: -10, y: 10 }}
                animate={{ opacity: 1, x: 0, y: 0 }}
                transition={{ type: "spring", stiffness: 200, damping: 20 }}
                className="flex text-slate-300"
              >
                <span className="text-teal-500 mr-3 shrink-0">[{log.progress}%]</span>
                <span className="leading-relaxed">{log.message}</span>
              </motion.div>
            ))
          )}
        </AnimatePresence>
        
        {status === 'running' && logs.length > 0 && (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-slate-500 flex items-center mt-4 pb-2"
          >
            <span className="w-2 h-2 rounded-full bg-teal-500 animate-pulse mr-3" />
            Processing...
          </motion.div>
        )}
        <div ref={logsEndRef} />
      </div>

      <AnimatePresence>
        {status === 'completed' && (
          <motion.div 
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-8 flex justify-end"
          >
            <button 
              onClick={onComplete}
              className="btn-primary text-lg px-8 py-3 shadow-[0_0_20px_rgba(20,184,166,0.3)]"
            >
              View Audit Results
            </button>
          </motion.div>
        )}
      </AnimatePresence>
      
      {status === 'failed' && (
        <motion.div 
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-8 flex items-center justify-between gap-4"
        >
          <p className="text-rose-300 text-sm">{errorMessage ?? 'Connection to the task stream failed.'}</p>
          <button
            onClick={() => window.location.reload()}
            className="btn-secondary shrink-0"
          >
            Retry
          </button>
        </motion.div>
      )}
    </div>
  );
}
