'use client';

import { useState, useCallback } from 'react';
import { UploadCloud, FileType, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';
import clsx from 'clsx';
import { useRouter } from 'next/navigation';
import LiveTaskTracker from './LiveTaskTracker';
import { motion, AnimatePresence } from 'framer-motion';
import { Sparkles } from 'lucide-react';
import { API_V1, readError } from '@/lib/api';

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
    <motion.div 
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      className={clsx(
        "relative border-2 border-dashed p-8 flex flex-col items-center justify-center text-center transition-all cursor-pointer h-56",
        isDragging ? "border-teal-400 bg-[#111111]" : "border-white/20 hover:border-white/40 hover:bg-[#111111]",
        selectedFile ? "border-emerald-500 bg-[#0f0f0f]" : ""
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
      
      <AnimatePresence mode="wait">
        {selectedFile ? (
          <motion.div 
            key="selected"
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.8 }}
            className="flex flex-col items-center space-y-3"
          >
            <div className="w-16 h-16 bg-[#111111] flex items-center justify-center border border-emerald-500/30">
              <CheckCircle2 className="w-8 h-8 text-emerald-400" />
            </div>
            <div>
              <p className="text-emerald-400 font-medium">File Selected</p>
              <p className="text-slate-300 text-sm mt-1 max-w-[200px] truncate">{selectedFile.name}</p>
              <p className="text-slate-500 text-xs">
                {selectedFile.size < 1024 * 1024 
                  ? `${(selectedFile.size / 1024).toFixed(1)} KB` 
                  : `${(selectedFile.size / 1024 / 1024).toFixed(2)} MB`}
              </p>
            </div>
          </motion.div>
        ) : (
          <motion.div 
            key="unselected"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="flex flex-col items-center space-y-3"
          >
            <div className="w-16 h-16 bg-[#111111] border border-white/10 flex items-center justify-center group-hover:scale-105 transition-transform">
              <UploadCloud className="w-8 h-8 text-white" />
            </div>
            <div>
              <p className="text-slate-200 font-medium">{label}</p>
              <p className="text-slate-400 text-sm mt-1">Drag & drop or click to browse</p>
              <p className="text-slate-500 text-xs mt-1">PDF up to 10MB</p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
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
      // 1. Ingest the policy.
      const policyFormData = new FormData();
      policyFormData.append('file', policyFile);

      const policyRes = await fetch(`${API_V1}/policies`, {
        method: 'POST',
        credentials: 'include',
        body: policyFormData,
      });
      if (!policyRes.ok) throw new Error(await readError(policyRes, 'Could not upload the policy.'));
      const policyData = await policyRes.json();

      // 2. Open a claim from the bill.
      const billFormData = new FormData();
      billFormData.append('file', billFile);

      const billRes = await fetch(`${API_V1}/claims`, {
        method: 'POST',
        credentials: 'include',
        body: billFormData,
      });
      if (!billRes.ok) throw new Error(await readError(billRes, 'Could not upload the bill.'));
      const billData = await billRes.json();

      // 3. Adjudicate the claim against that policy.
      const auditRes = await fetch(`${API_V1}/claims/${billData.claim_id}/audit`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ policy_id: policyData.policy_id }),
      });
      if (!auditRes.ok) throw new Error(await readError(auditRes, 'Could not start the audit.'));
      const auditData = await auditRes.json();

      setJobId(auditData.job_id);

    } catch (err: any) {
      console.error(err);
      setError(err.message || 'An error occurred during upload.');
      setIsUploading(false);
    }
  };

  return (
    <AnimatePresence mode="wait">
      {jobId ? (
        <motion.div
          key="tracker"
          initial={{ opacity: 0, x: 50 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -50 }}
          transition={{ type: "spring", stiffness: 100 }}
        >
          <LiveTaskTracker 
            jobId={jobId} 
            onComplete={() => {
              router.push('/claims');
            }} 
          />
        </motion.div>
      ) : (
        <motion.div 
          key="upload"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -20 }}
          transition={{ type: "spring", stiffness: 100 }}
          className="glass-panel p-8 max-w-4xl mx-auto border-t-[3px] border-t-teal-500"
        >
          <div className="mb-8">
            <h2 className="text-3xl font-bold text-white tracking-tight">Upload Documents</h2>
            <p className="text-slate-400 mt-2 text-lg">
              Upload the medical bill and corresponding insurance policy to start the AI audit.
            </p>
          </div>

          <AnimatePresence>
            {error && (
              <motion.div 
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="mb-6 p-4 bg-[#111111] border border-rose-500 flex items-start overflow-hidden"
              >
                <AlertCircle className="w-5 h-5 text-rose-400 mr-3 shrink-0 mt-0.5" />
                <p className="text-rose-200">{error}</p>
              </motion.div>
            )}
          </AnimatePresence>

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

          <div className="flex flex-col sm:flex-row justify-between items-center pt-6 border-t border-white/10">
            <button
              onClick={async () => {
                const billRes = await fetch('/demo-hospital-bill-2026.pdf');
                const billBlob = await billRes.blob();
                setBillFile(new File([billBlob], "demo-hospital-bill-2026.pdf", { type: "application/pdf" }));

                const policyRes = await fetch('/demo-aetna-policy-document.pdf');
                const policyBlob = await policyRes.blob();
                setPolicyFile(new File([policyBlob], "demo-aetna-policy-document.pdf", { type: "application/pdf" }));
              }}
              className="flex items-center text-sm font-medium text-slate-400 hover:text-white transition-colors mb-4 sm:mb-0"
            >
              <Sparkles className="w-4 h-4 mr-2 text-teal-400" />
              Use Demo Documents
            </button>

            <motion.button 
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={handleStartAudit}
              disabled={!billFile || !policyFile || isUploading}
              className={clsx(
                "btn-primary flex items-center px-8 py-3 w-full sm:w-auto",
                (!billFile || !policyFile || isUploading) && "opacity-50 cursor-not-allowed grayscale"
              )}
            >
              {isUploading ? (
                <>
                  <Loader2 className="w-5 h-5 mr-3 animate-spin" />
                  Processing...
                </>
              ) : (
                <>
                  Start AI Audit
                  <FileType className="w-5 h-5 ml-3" />
                </>
              )}
            </motion.button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
