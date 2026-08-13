'use client';

import { useState } from 'react';
import { Check, Copy } from 'lucide-react';

/**
 * Copies the letter as plain text, ready to paste into an email or a document.
 *
 * Reads `innerText` off the rendered letter rather than the raw markdown, so
 * what lands on the clipboard is what the analyst read on screen, with no stray
 * asterisks or heading hashes to clean up at the other end.
 */
export default function CopyLetterButton({ targetId }: { targetId: string }) {
  const [copied, setCopied] = useState(false);
  const [failed, setFailed] = useState(false);

  const copy = async () => {
    const text = document.getElementById(targetId)?.innerText;
    if (!text) return;

    try {
      await navigator.clipboard.writeText(text.trim());
      setCopied(true);
      setFailed(false);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard access needs a secure context; over plain http on a LAN
      // address it is refused, and silently doing nothing would look broken.
      setFailed(true);
      setTimeout(() => setFailed(false), 4000);
    }
  };

  return (
    <button onClick={copy} className="btn-ghost no-print">
      {copied ? (
        <Check className="h-4 w-4 text-verified" strokeWidth={1.8} />
      ) : (
        <Copy className="h-4 w-4" strokeWidth={1.6} />
      )}
      {copied ? 'Copied' : failed ? 'Press Ctrl+C' : 'Copy text'}
    </button>
  );
}
