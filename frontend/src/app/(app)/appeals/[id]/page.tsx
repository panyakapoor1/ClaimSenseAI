import Link from 'next/link';
import { ArrowLeft, FileText, CheckCircle2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
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
      throw new Error('Failed to fetch appeal');
    }
    return await res.json();
  } catch (err) {
    console.error(err);
    return null;
  }
}

export default async function AppealDetailsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const appeal = await getAppeal(id);

  if (!appeal) {
    return (
      <div className="glass-panel p-12 text-center flex flex-col items-center">
        <FileText className="w-16 h-16 text-slate-600 mb-4" />
        <h2 className="text-xl font-medium text-slate-300 mb-2">No Appeal Found</h2>
        <p className="text-slate-500 mb-6">
          An appeal letter has not been generated for this claim yet.
        </p>
        <Link href={`/claims/${id}`} className="btn-primary">
          Back to Claim Details
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-in fade-in duration-500 max-w-4xl mx-auto">
      <header className="mb-8">
        <Link href={`/claims/${id}`} className="inline-flex items-center text-slate-400 hover:text-teal-400 transition-colors mb-4 text-sm font-medium">
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Claim Details
        </Link>
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-white mb-2 flex items-center">
              Generated Appeal Letter
            </h1>
            <p className="text-slate-400 flex items-center">
              <CheckCircle2 className="w-4 h-4 mr-2 text-emerald-400" />
              Drafted on {new Date(appeal.created_at).toLocaleDateString()}
            </p>
          </div>
        </div>
      </header>

      <div className="glass-panel p-8 md:p-12 bg-white text-slate-900 border-none prose max-w-none">
        {/* Render markdown using react-markdown. 
            Note: We set the background to white to mimic a real document. */}
        <ReactMarkdown>{appeal.content}</ReactMarkdown>
      </div>
    </div>
  );
}
