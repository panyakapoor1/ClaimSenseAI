import { FileText, MapPin, ScanLine, AlertTriangle } from 'lucide-react';

type Region = {
  page_number: number;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
};

type Fact = {
  id: string;
  kind: string;
  label: string;
  value_text: string | null;
  value_number: number | null;
  located: boolean;
  match: string | null;
  region: Region | null;
};

/**
 * How a value was tied to the page.
 *
 * Shown instead of a confidence percentage. The pipeline has no calibrated
 * probability for an extracted value, and a number would imply one.
 */
const MATCH_LABELS: Record<string, { label: string; hint: string }> = {
  EXACT_PHRASE: { label: 'Exact', hint: 'Every word matched, in order' },
  NUMERIC_FORM: { label: 'Amount', hint: 'Matched a printed form of this figure' },
  PARTIAL_TOKEN: { label: 'Partial', hint: 'Only the most distinctive word matched' },
};

type DocumentPage = {
  page_number: number;
  from_ocr: boolean;
  char_count: number;
};

type SourceDocument = {
  id: string;
  kind: string;
  status: string;
  filename: string;
  page_count: number | null;
  parse_error: string | null;
  ocr_page_count: number;
  pages: DocumentPage[];
};

export type Evidence = {
  documents: SourceDocument[];
  facts: Fact[];
};

/**
 * Where the numbers on this claim came from.
 *
 * Facts that could not be located on a page are shown as such rather than
 * hidden — an analyst needs to know which figures are traceable and which are
 * the model's reading alone.
 */
export default function EvidencePanel({ evidence }: { evidence: Evidence }) {
  const { documents, facts } = evidence;

  if (documents.length === 0 && facts.length === 0) return null;

  const located = facts.filter((f) => f.located).length;
  const ocrPages = documents.reduce((sum, d) => sum + d.ocr_page_count, 0);

  return (
    <section className="glass-panel p-6">
      <div className="flex items-baseline justify-between mb-5 gap-4 flex-wrap">
        <h2 className="text-xl font-semibold text-white">Evidence</h2>
        <span className="text-xs text-slate-500 tabular-nums">
          {located} of {facts.length} values traced to a page
        </span>
      </div>

      <div className="space-y-3 mb-6">
        {documents.map((doc) => (
          <div key={doc.id} className="border border-white/10 bg-black/40 p-4">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3 min-w-0">
                <FileText className="w-4 h-4 text-slate-500 shrink-0 mt-0.5" />
                <div className="min-w-0">
                  <p className="text-sm text-slate-200 truncate">{doc.filename}</p>
                  <p className="text-xs text-slate-500 mt-0.5 tabular-nums">
                    {doc.kind.toLowerCase()} · {doc.page_count ?? 0}{' '}
                    {doc.page_count === 1 ? 'page' : 'pages'}
                  </p>
                </div>
              </div>

              {doc.ocr_page_count > 0 && (
                <span className="shrink-0 flex items-center gap-1.5 text-xs text-amber-300 border border-amber-500/25 bg-amber-500/10 px-2 py-1">
                  <ScanLine className="w-3.5 h-3.5" />
                  {doc.ocr_page_count} scanned
                </span>
              )}
            </div>

            {doc.parse_error && (
              <p className="mt-3 text-xs text-rose-300 flex items-start gap-2">
                <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                {doc.parse_error}
              </p>
            )}
          </div>
        ))}
      </div>

      {ocrPages > 0 && (
        <p className="text-xs text-amber-200/80 border-l-2 border-amber-500/40 pl-3 mb-6">
          {ocrPages} {ocrPages === 1 ? 'page was' : 'pages were'} read by OCR because
          there was no text layer. Recognised text can contain errors — check figures
          against the source before acting on them.
        </p>
      )}

      {facts.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wider text-slate-500">
                <th className="pb-2 pr-4 font-medium">Value</th>
                <th className="pb-2 pr-4 font-medium">Source</th>
                <th className="pb-2 font-medium text-right">Match</th>
              </tr>
            </thead>
            <tbody>
              {facts.map((fact) => (
                <tr key={fact.id} className="border-t border-white/5">
                  <td className="py-2.5 pr-4 text-slate-200">
                    <span className="block truncate max-w-xs">{fact.label}</span>
                    {fact.value_number != null && (
                      <span className="text-xs text-slate-500 tabular-nums">
                        {fact.value_number.toLocaleString()}
                      </span>
                    )}
                  </td>
                  <td className="py-2.5 pr-4">
                    {fact.located && fact.region ? (
                      <span className="inline-flex items-center gap-1.5 text-xs text-teal-300">
                        <MapPin className="w-3.5 h-3.5" />
                        Page {fact.region.page_number}
                      </span>
                    ) : (
                      <span className="text-xs text-slate-500">Not located</span>
                    )}
                  </td>
                  <td className="py-2.5 text-right">
                    {fact.match ? (
                      <span
                        title={MATCH_LABELS[fact.match]?.hint ?? fact.match}
                        className="text-xs text-slate-400 border border-white/10 px-1.5 py-0.5"
                      >
                        {MATCH_LABELS[fact.match]?.label ?? fact.match}
                      </span>
                    ) : (
                      <span className="text-xs text-slate-600">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
