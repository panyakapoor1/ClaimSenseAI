'use client';

import { Printer } from 'lucide-react';

/** Prints the letter. The print stylesheet drops the shell around it. */
export default function PrintButton() {
  return (
    <button onClick={() => window.print()} className="btn-ghost no-print">
      <Printer className="h-4 w-4" strokeWidth={1.6} />
      Print
    </button>
  );
}
