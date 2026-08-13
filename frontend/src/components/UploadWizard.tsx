'use client';

import { useState, useCallback } from 'react';
import { UploadCloud, Check, AlertTriangle, Loader2, ArrowRight } from 'lucide-react';
import clsx from 'clsx';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';

import LiveTaskTracker from './LiveTaskTracker';
import { API_V1, readError } from '@/lib/api';

interface FileDropzoneProps {
  step: string;
  label: string;
  hint: string;
  onFileSelect: (file: File) => void;
  onReject: (message: string) => void;
  selectedFile: File | null;
  accept?: string;
}

function formatSize(bytes: number) {
  return bytes < 1024 * 1024
    ? `${(bytes / 1024).toFixed(0)} KB`
    : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function FileDropzone({
  step,
  label,
  hint,
  onFileSelect,
  onReject,
  selectedFile,
  accept = 'application/pdf',
}: FileDropzoneProps) {
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

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);

      const file = e.dataTransfer.files?.[0];
      if (!file) return;

      // Reported inline rather than through alert(), which interrupts the drag
      // and gives the browser's voice to our error.
      if (file.type !== accept) {
        onReject(`${file.name} is not a PDF.`);
        return;
      }
      onFileSelect(file);
    },
    [accept, onFileSelect, onReject],
  );

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onFileSelect(file);
  };

  return (
    <div
      className={clsx(
        'relative flex h-56 cursor-pointer flex-col justify-between border border-dashed p-5 transition-colors',
        isDragging && 'border-ink-900 bg-mist',
        !isDragging && selectedFile && 'border-verified-line bg-verified-soft',
        !isDragging && !selectedFile && 'border-line-strong hover:border-ink-300 hover:bg-mist',
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
        aria-label={label}
        className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
      />

      <div className="flex items-start justify-between">
        <span className="font-mono text-xs tabular-nums text-ink-300">{step}</span>
        {selectedFile ? (
          <Check className="h-4 w-4 text-verified" />
        ) : (
          <UploadCloud className="h-4 w-4 text-ink-300" strokeWidth={1.6} />
        )}
      </div>

      <AnimatePresence mode="wait">
        {selectedFile ? (
          <motion.div
            key="selected"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
          >
            <p className="eyebrow">{label}</p>
            <p className="mt-2 truncate text-sm text-ink-900">{selectedFile.name}</p>
            <p className="mt-1 font-mono text-xs tabular-nums text-ink-500">
              {formatSize(selectedFile.size)} · click to replace
            </p>
          </motion.div>
        ) : (
          <motion.div
            key="empty"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
          >
            <p className="text-base font-medium text-ink-900">{label}</p>
            <p className="mt-1.5 text-sm leading-relaxed text-ink-500">{hint}</p>
            <p className="mt-2 font-mono text-xs text-ink-300">PDF · up to 10 MB</p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function UploadWizard() {
  const [billFile, setBillFile] = useState<File | null>(null);
  const [policyFile, setPolicyFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [loadingDemo, setLoadingDemo] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const router = useRouter();

  const handleStartAudit = async () => {
    if (!billFile || !policyFile) {
      setError('Select both a bill and a policy document.');
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
    } catch (err) {
      console.error(err);
      setError(err instanceof Error ? err.message : 'An error occurred during upload.');
      setIsUploading(false);
    }
  };

  const loadDemoDocuments = async () => {
    setLoadingDemo(true);
    setError(null);
    try {
      const [billRes, policyRes] = await Promise.all([
        fetch('/demo-hospital-bill-2026.pdf'),
        fetch('/demo-aetna-policy-document.pdf'),
      ]);
      if (!billRes.ok || !policyRes.ok) throw new Error('Demo documents are missing.');

      const [billBlob, policyBlob] = await Promise.all([
        billRes.blob(),
        policyRes.blob(),
      ]);

      setBillFile(
        new File([billBlob], 'demo-hospital-bill-2026.pdf', { type: 'application/pdf' }),
      );
      setPolicyFile(
        new File([policyBlob], 'demo-aetna-policy-document.pdf', {
          type: 'application/pdf',
        }),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load the demo documents.');
    } finally {
      setLoadingDemo(false);
    }
  };

  const ready = Boolean(billFile && policyFile);

  return (
    <AnimatePresence mode="wait">
      {jobId ? (
        <motion.div
          key="tracker"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        >
          <LiveTaskTracker jobId={jobId} onComplete={() => router.push('/claims')} />
        </motion.div>
      ) : (
        <motion.div
          key="upload"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        >
          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="overflow-hidden"
              >
                <div className="mb-6 flex items-start gap-2.5 border border-rejected-line bg-rejected-soft p-4">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-rejected" />
                  <p className="text-sm text-rejected">{error}</p>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <div className="grid gap-4 md:grid-cols-2">
            <FileDropzone
              step="01"
              label="Hospital bill"
              hint="The itemised bill to adjudicate. Scanned copies are read by OCR."
              onFileSelect={setBillFile}
              onReject={setError}
              selectedFile={billFile}
            />
            <FileDropzone
              step="02"
              label="Insurance policy"
              hint="The governing policy. Its clauses are what every line is decided against."
              onFileSelect={setPolicyFile}
              onReject={setError}
              selectedFile={policyFile}
            />
          </div>

          <div className="mt-6 flex flex-col items-start justify-between gap-4 border-t border-line pt-6 sm:flex-row sm:items-center">
            <button
              onClick={loadDemoDocuments}
              disabled={loadingDemo || isUploading}
              className="inline-flex items-center gap-2 text-sm text-ink-500 transition-colors hover:text-ink-900 disabled:opacity-50"
            >
              {loadingDemo && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              Use the demo bill and policy
            </button>

            <button
              onClick={handleStartAudit}
              disabled={!ready || isUploading}
              className="btn w-full sm:w-auto"
            >
              {isUploading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Uploading…
                </>
              ) : (
                <>
                  Start the audit
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
