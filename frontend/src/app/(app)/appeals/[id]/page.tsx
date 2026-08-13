import Link from 'next/link';
import { ArrowLeft, FileText } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import PrintButton from '@/components/PrintButton';
import CopyLetterButton from '@/components/CopyLetterButton';
import { API_V1_SERVER } from '@/lib/api';
import { authHeaders } from '@/lib/session';

export const dynamic = 'force-dynamic';

async function getAppeal(id: string) {
  try {
    const res = await fetch(`${API_V1_SERVER}/claims/${id}/appeal`, {
      headers: await authHeaders(),
      cache: 'no-store',
    });
    if (!res.ok) {
      if (res.status === 404) return null;
      throw new Error(`API responded ${res.status}`);
    }
    return await res.json();
  } catch (err) {
    console.error('Could not load appeal:', err);
    return null;
  }
}

export default async function AppealDetailsPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const appeal = await getAppeal(id);

  if (!appeal) {
    return (
      <div className="stamp-in flex flex-col items-center border border-dashed border-line-strong px-6 py-20 text-center">
        <FileText className="h-8 w-8 text-ink-300" strokeWidth={1.4} />
        <h2 className="mt-5 text-lg font-semibold text-ink-900">No appeal yet</h2>
        <p className="mt-2 max-w-md text-sm leading-relaxed text-ink-700">
          An appeal letter has not been drafted for this claim. Open the claim and
          draft one from its disputed lines.
        </p>
        <Link href={`/claims/${id}`} className="btn mt-7">
          Back to the claim
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl">
      <header className="stamp-in no-print">
        <Link
          href={`/claims/${id}`}
          className="group inline-flex items-center gap-2 text-sm text-ink-500 transition-colors hover:text-ink-900"
        >
          <ArrowLeft className="h-4 w-4 transition-transform group-hover:-translate-x-0.5" />
          Back to the claim
        </Link>

        <div className="mt-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="eyebrow">Appeal letter</p>
            <h1 className="display mt-3 text-3xl text-ink-900">Draft correspondence</h1>
            <p className="mt-3 font-mono text-sm tabular-nums text-ink-500">
              Drafted {new Date(appeal.created_at).toLocaleDateString()}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <CopyLetterButton targetId="appeal-letter" />
            <PrintButton />
          </div>
        </div>

        <div className="rule mt-8" />
      </header>

      {/* Set as a document rather than as interface: the letter is the artefact
          an analyst sends, so it should already look like one on screen. */}
      <article className="print-sheet stamp-in mt-10 border border-line bg-white px-8 py-12 shadow-[0_1px_3px_rgb(21_22_26/0.04)] sm:px-14 sm:py-16">
        <div className="letter" id="appeal-letter">
          <ReactMarkdown>{appeal.content}</ReactMarkdown>
        </div>
      </article>

      <p className="no-print mt-6 text-xs leading-relaxed text-ink-500">
        A draft. Every disputed charge is argued against the clause used to reject
        it. Check both before this goes anywhere.
      </p>
    </div>
  );
}
