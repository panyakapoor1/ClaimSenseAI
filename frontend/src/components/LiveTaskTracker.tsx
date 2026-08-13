'use client';

import { useEffect, useState, useRef } from 'react';
import { Loader2, Check, AlertTriangle } from 'lucide-react';
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

/**
 * The pipeline, while it runs.
 *
 * Progress arrives over a WebSocket rather than being polled. The backend
 * publishes each stage as it completes, so the log below is the worker's own
 * account of what it did, not a simulated one.
 */
export default function LiveTaskTracker({ jobId, onComplete }: LiveTaskTrackerProps) {
  const [progress, setProgress] = useState(0);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [status, setStatus] = useState<'running' | 'completed' | 'failed'>('running');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
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
          setLogs((prev) => [...prev, { message: data.message ?? 'Task failed.', progress: pct }]);
          return;
        }

        if (data.status === 'completed') {
          setProgress(100);
          setStatus('completed');
          setLogs((prev) => [...prev, { message: data.message ?? 'Complete.', progress: 100 }]);
          return;
        }

        setProgress(pct);
        setLogs((prev) => [...prev, { message: data.message, progress: pct }]);
      } catch (err) {
        console.error('Error parsing WS message', err);
      }
    };

    ws.onerror = (err) => {
      console.error('WebSocket error:', err);
      setStatus((prev) => (prev === 'completed' ? prev : 'failed'));
    };

    ws.onclose = () => {
      console.log('WebSocket connection closed');
    };

    return () => {
      ws.close();
    };
  }, [jobId]);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [logs]);

  return (
    <div className="panel mx-auto max-w-2xl">
      <div className="flex items-start justify-between gap-4 p-6">
        <div className="min-w-0">
          <p className="eyebrow">
            {status === 'running' && 'Auditing'}
            {status === 'completed' && 'Audit complete'}
            {status === 'failed' && 'Audit failed'}
          </p>
          <h2 className="display mt-3 text-2xl text-ink-900">
            {status === 'running' && 'Reading the bill against the policy'}
            {status === 'completed' && 'Every line adjudicated'}
            {status === 'failed' && 'The run stopped'}
          </h2>
          <p className="mt-2 font-mono text-xs text-ink-300">job {jobId}</p>
        </div>

        <span className="shrink-0">
          {status === 'running' && (
            <Loader2 className="h-5 w-5 animate-spin text-ink-500" />
          )}
          {status === 'completed' && <Check className="h-5 w-5 text-verified" />}
          {status === 'failed' && <AlertTriangle className="h-5 w-5 text-rejected" />}
        </span>
      </div>

      <div className="px-6">
        <div className="flex items-baseline justify-between">
          <span className="eyebrow">Progress</span>
          <span className="font-mono text-sm tabular-nums text-ink-900">
            {String(progress).padStart(3, '0')}%
          </span>
        </div>

        <div className="mt-3 h-1 w-full overflow-hidden bg-mist">
          <motion.div
            className={`relative h-full overflow-hidden ${
              status === 'failed' ? 'bg-rejected' : 'bg-ink-900'
            } ${status === 'running' ? 'sweep' : ''}`}
            initial={{ width: 0 }}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          />
        </div>
      </div>

      {/* The worker's log, set on the rail tone so it reads as machine output
          rather than as part of the document surface. */}
      <div className="scroll-dark m-6 h-64 overflow-y-auto bg-rail p-5 font-mono text-xs leading-relaxed">
        <AnimatePresence initial={false}>
          {logs.length === 0 ? (
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex items-center gap-2.5 text-rail-dim"
            >
              <Pulse />
              Connecting to the task stream…
            </motion.p>
          ) : (
            logs.map((log, index) => (
              <motion.p
                key={index}
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                className="flex gap-3 py-0.5"
              >
                <span className="shrink-0 tabular-nums text-rail-dim">
                  {String(log.progress).padStart(3, '0')}
                </span>
                <span className="text-rail-text">{log.message}</span>
              </motion.p>
            ))
          )}
        </AnimatePresence>

        {status === 'running' && logs.length > 0 && (
          <p className="mt-3 flex items-center gap-2.5 text-rail-dim">
            <Pulse />
            Working…
          </p>
        )}

        <div ref={logsEndRef} />
      </div>

      <AnimatePresence>
        {status === 'completed' && (
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex justify-end border-t border-line p-6"
          >
            <button onClick={onComplete} className="btn">
              View audit results
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {status === 'failed' && (
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-wrap items-center justify-between gap-4 border-t border-line p-6"
        >
          <p className="text-sm text-rejected">
            {errorMessage ?? 'Connection to the task stream failed.'}
          </p>
          <button onClick={() => window.location.reload()} className="btn-ghost shrink-0">
            Retry
          </button>
        </motion.div>
      )}
    </div>
  );
}

function Pulse() {
  return (
    <span className="relative flex h-1.5 w-1.5 shrink-0">
      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-rail-dim opacity-70" />
      <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-rail-text" />
    </span>
  );
}
