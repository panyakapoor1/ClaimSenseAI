'use client';

import { useEffect, useState } from 'react';
import { Loader2, CheckCircle2, Bot, AlertCircle } from 'lucide-react';

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

  useEffect(() => {
    // Connect to WebSocket
    const ws = new WebSocket(`ws://localhost:8000/ws/tasks/${jobId}`);

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.type === 'progress') {
          setProgress(data.progress);
          setLogs(prev => [...prev, { message: data.message, progress: data.progress }]);
        } else if (data.type === 'complete') {
          setProgress(100);
          setStatus('completed');
          setLogs(prev => [...prev, { message: 'Audit complete!', progress: 100 }]);
        }
      } catch (err) {
        console.error('Error parsing WS message', err);
      }
    };

    ws.onerror = (err) => {
      console.error('WebSocket error:', err);
      setStatus('failed');
    };

    ws.onclose = () => {
      console.log('WebSocket connection closed');
    };

    return () => {
      ws.close();
    };
  }, [jobId]);

  return (
    <div className="glass-panel p-8 max-w-2xl mx-auto animate-in slide-in-from-bottom-4 duration-500">
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
        <div className="w-16 h-16 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center">
          <Bot className="w-8 h-8 text-indigo-400" />
        </div>
      </div>

      {/* Progress Bar */}
      <div className="mb-8">
        <div className="flex justify-between text-sm mb-2">
          <span className="text-slate-300 font-medium">Overall Progress</span>
          <span className="text-teal-400 font-bold">{progress}%</span>
        </div>
        <div className="h-3 w-full bg-slate-800 rounded-full overflow-hidden">
          <div 
            className="h-full bg-gradient-to-r from-teal-500 to-indigo-500 transition-all duration-500 ease-out"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Terminal / Logs View */}
      <div className="bg-slate-900 border border-slate-700 rounded-lg p-4 font-mono text-sm max-h-64 overflow-y-auto space-y-2">
        {logs.length === 0 ? (
          <div className="text-slate-500 flex items-center">
            <span className="w-2 h-2 rounded-full bg-teal-500 animate-pulse mr-2" />
            Initializing ClaimSense Auditor...
          </div>
        ) : (
          logs.map((log, index) => (
            <div key={index} className="flex text-slate-300 animate-in fade-in slide-in-from-left-2">
              <span className="text-teal-500 mr-3">[{log.progress}%]</span>
              <span>{log.message}</span>
            </div>
          ))
        )}
        {status === 'running' && logs.length > 0 && (
          <div className="text-slate-500 flex items-center mt-2">
            <span className="w-2 h-2 rounded-full bg-teal-500 animate-pulse mr-2" />
            Processing...
          </div>
        )}
      </div>

      {status === 'completed' && (
        <div className="mt-8 flex justify-end">
          <button 
            onClick={onComplete}
            className="btn-primary"
          >
            View Audit Results
          </button>
        </div>
      )}
      
      {status === 'failed' && (
        <div className="mt-8 flex justify-end">
          <button 
            onClick={() => window.location.reload()}
            className="btn-secondary"
          >
            Retry
          </button>
        </div>
      )}
    </div>
  );
}
