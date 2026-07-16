'use client';

import { useState, useCallback } from 'react';
import { UploadCloud, FileType, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';
import clsx from 'clsx';
import { useRouter } from 'next/navigation';
import LiveTaskTracker from './LiveTaskTracker';

interface FileDropzoneProps {
  label: string;
  onFileSelect: (file: File) => void;
  selectedFile: File | null;
  accept?: string;
}

function FileDropzone({ label, onFileSelect, selectedFile, accept = 'application/pdf' }: FileDropzoneProps) {
  const [isDragging, setIsDragging] = useState(false);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setIsDragging(true);
    } else if (e.type === 'dragleave') {
      setIsDragging(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      if (file.type === accept) {
        onFileSelect(file);
      } else {
        alert('Please upload a PDF file.');
      }
    }
  }, [accept, onFileSelect]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      onFileSelect(e.target.files[0]);
    }
  };

  return (
    <div 
      className={clsx(
        "relative border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center text-center transition-all",
        isDragging ? "border-teal-400 bg-teal-500/10" : "border-slate-700 hover:border-slate-500 hover:bg-slate-800/30",
        selectedFile ? "border-emerald-500/50 bg-emerald-500/5" : ""
      )}
      onDragEnter={handleDrag}
      onDragLeave={handleDrag}
      onDragOver={handleDrag}
      onDrop={handleDrop}
    >
      <input 
        type="file" 
        accept={accept} 
        onChange={handleChange}
        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer" 
      />
      
      {selectedFile ? (
        <div className="flex flex-col items-center space-y-3">
          <div className="w-12 h-12 rounded-full bg-emerald-500/20 flex items-center justify-center">
            <CheckCircle2 className="w-6 h-6 text-emerald-400" />
          </div>
          <div>
            <p className="text-emerald-400 font-medium">File Selected</p>
            <p className="text-slate-300 text-sm mt-1">{selectedFile.name}</p>
            <p className="text-slate-500 text-xs">{(selectedFile.size / 1024 / 1024).toFixed(2)} MB</p>
          </div>
        </div>
      ) : (
        <div className="flex flex-col items-center space-y-3">
          <div className="w-12 h-12 rounded-full bg-slate-800 flex items-center justify-center">
            <UploadCloud className="w-6 h-6 text-slate-400" />
          </div>
          <div>
            <p className="text-slate-200 font-medium">{label}</p>
            <p className="text-slate-400 text-sm mt-1">Drag & drop or click to browse</p>
            <p className="text-slate-500 text-xs mt-1">PDF up to 10MB</p>
          </div>
        </div>
      )}
    </div>
  );
}

export default function UploadWizard() {
  const [billFile, setBillFile] = useState<File | null>(null);
  const [policyFile, setPolicyFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const router = useRouter();

  const handleStartAudit = async () => {
    if (!billFile || !policyFile) {
      setError("Please select both a bill and a policy document.");
      return;
    }
    
    setError(null);
    setIsUploading(true);

    try {
      // 1. Upload Policy
      const policyFormData = new FormData();
      policyFormData.append('file', policyFile);
      
      const policyRes = await fetch('http://localhost:8000/upload-policy/', {
        method: 'POST',
        body: policyFormData,
      });
      
      if (!policyRes.ok) throw new Error('Failed to upload policy');
      const policyData = await policyRes.json();
      
      // 2. Upload Bill
      const billFormData = new FormData();
      billFormData.append('file', billFile);
      
      const billRes = await fetch('http://localhost:8000/upload-bill/', {
        method: 'POST',
        body: billFormData,
      });
      
      if (!billRes.ok) throw new Error('Failed to upload bill');
      const billData = await billRes.json();

      // 3. Start Audit Task
      const auditRes = await fetch('http://localhost:8000/process-claim/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          bill_id: billData.bill_id,
          policy_id: policyData.policy_id
        })
      });
      
      if (!auditRes.ok) throw new Error('Failed to start audit process');
      const auditData = await auditRes.json();
      
      setJobId(auditData.job_id);

    } catch (err: any) {
      console.error(err);
      setError(err.message || 'An error occurred during upload.');
      setIsUploading(false);
    }
  };

  if (jobId) {
    return (
      <LiveTaskTracker 
        jobId={jobId} 
        onComplete={() => {
          // In a real app we might route to the claim details page based on the result.
          // For now, we'll route to the generic claims page.
          router.push('/claims');
        }} 
      />
    );
  }

  return (
    <div className="glass-panel p-8 max-w-4xl mx-auto animate-in slide-in-from-bottom-4 duration-500">
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-white">Upload Documents</h2>
        <p className="text-slate-400 mt-2">
          Upload the medical bill and corresponding insurance policy to start the AI audit.
        </p>
      </div>

      {error && (
        <div className="mb-6 p-4 rounded-lg bg-rose-500/10 border border-rose-500/20 flex items-start">
          <AlertCircle className="w-5 h-5 text-rose-400 mr-3 shrink-0 mt-0.5" />
          <p className="text-rose-200">{error}</p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <FileDropzone 
          label="Upload Medical Bill" 
          onFileSelect={setBillFile} 
          selectedFile={billFile} 
        />
        <FileDropzone 
          label="Upload Insurance Policy" 
          onFileSelect={setPolicyFile} 
          selectedFile={policyFile} 
        />
      </div>

      <div className="flex justify-end pt-6 border-t border-slate-700/50">
        <button 
          onClick={handleStartAudit}
          disabled={!billFile || !policyFile || isUploading}
          className={clsx(
            "btn-primary flex items-center text-lg px-6 py-3",
            (!billFile || !policyFile || isUploading) && "opacity-50 cursor-not-allowed"
          )}
        >
          {isUploading ? (
            <>
              <Loader2 className="w-5 h-5 mr-3 animate-spin" />
              Uploading & Starting Audit...
            </>
          ) : (
            <>
              Start AI Audit
              <FileType className="w-5 h-5 ml-3" />
            </>
          )}
        </button>
      </div>
    </div>
  );
}
