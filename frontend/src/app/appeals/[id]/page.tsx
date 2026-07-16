import Link from 'next/link';
import { ArrowLeft, Download, FileText, CheckCircle2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

async function getAppeal(id: string) {
  try {
    const res = await fetch(`http://localhost:8000/appeal/${id}`, { cache: 'no-store' });
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

export default async function AppealDetailsPage({ params }: { params: { id: string } }) {
  const appeal = await getAppeal(params.id);

  if (!appeal) {
    return (
      <div className="glass-panel p-12 text-center flex flex-col items-center">
        <FileText className="w-16 h-16 text-slate-600 mb-4" />
        <h2 className="text-xl font-medium text-slate-300 mb-2">No Appeal Found</h2>
        <p className="text-slate-500 mb-6">
          An appeal letter has not been generated for this claim yet.
        </p>
        <Link href={`/claims/${params.id}`} className="btn-primary">
          Back to Claim Details
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-in fade-in duration-500 max-w-4xl mx-auto">
      <header className="mb-8">
        <Link href={`/claims/${params.id}`} className="inline-flex items-center text-slate-400 hover:text-teal-400 transition-colors mb-4 text-sm font-medium">
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
              Generated successfully by ClaimSense AI on {new Date(appeal.created_at).toLocaleDateString()}
            </p>
          </div>
          
          <button className="btn-secondary flex items-center bg-slate-800">
            <Download className="w-4 h-4 mr-2" />
            Download PDF
          </button>
        </div>
      </header>

      <div className="glass-panel p-8 md:p-12 bg-white text-slate-900 border-none print:shadow-none prose prose-slate max-w-none">
        {/* Render markdown using react-markdown. 
            Note: We set the background to white to mimic a real document. */}
        <ReactMarkdown>{appeal.appeal_text}</ReactMarkdown>
      </div>
    </div>
  );
}
