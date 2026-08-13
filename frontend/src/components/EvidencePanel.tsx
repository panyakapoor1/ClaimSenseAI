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
 * hidden. An analyst needs to know which figures are traceable and which are
 * the model's reading alone.
 */
export default function EvidencePanel({ evidence }: { evidence: Evidence }) {
  const { documents, facts } = evidence;

  if (documents.length === 0 && facts.length === 0) return null;

  const located = facts.filter((f) => f.located).length;
  const ocrPages = documents.reduce((sum, d) => sum + d.ocr_page_count, 0);

  return (
    <section className="panel p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <p className="eyebrow">Evidence</p>
        <span className="font-mono text-xs tabular-nums text-ink-500">
          {located} of {facts.length} values traced to a page
        </span>
      </div>

      <div className="mt-6 space-y-2">
        {documents.map((doc) => (
          <div key={doc.id} className="well p-4">
            <div className="flex items-start justify-between gap-4">
              <div className="flex min-w-0 items-start gap-3">
                <FileText className="mt-0.5 h-4 w-4 shrink-0 text-ink-300" strokeWidth={1.6} />
                <div className="min-w-0">
                  <p className="truncate text-sm text-ink-900">{doc.filename}</p>
                  <p className="mt-1 font-mono text-xs tabular-nums text-ink-500">
                    {doc.kind.toLowerCase()} · {doc.page_count ?? 0}{' '}
                    {doc.page_count === 1 ? 'page' : 'pages'}
                  </p>
                </div>
              </div>

              {doc.ocr_page_count > 0 && (
                <span className="chip shrink-0 border-capped-line bg-capped-soft text-capped">
                  <ScanLine className="h-3.5 w-3.5" />
                  {doc.ocr_page_count} scanned
                </span>
              )}
            </div>

            {doc.parse_error && (
              <p className="mt-3 flex items-start gap-2 text-xs text-rejected">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                {doc.parse_error}
              </p>
            )}
          </div>
        ))}
      </div>

      {ocrPages > 0 && (
        <p className="mt-5 border-l-2 border-capped pl-4 text-xs leading-relaxed text-ink-700">
          {ocrPages} {ocrPages === 1 ? 'page was' : 'pages were'} read by OCR because
          there was no text layer. Recognised text can contain errors, so check figures
          against the source before acting on them.
        </p>
      )}

      {facts.length > 0 && (
        <div className="mt-6 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left">
                <th className="pb-3 pr-4 font-normal">
                  <span className="eyebrow">Value</span>
                </th>
                <th className="pb-3 pr-4 font-normal">
                  <span className="eyebrow">Source</span>
                </th>
                <th className="pb-3 text-right font-normal">
                  <span className="eyebrow">Match</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {facts.map((fact) => (
                <tr key={fact.id} className="border-b border-line last:border-b-0">
                  <td className="py-3 pr-4">
                    <span className="block max-w-xs truncate text-ink-900">
                      {fact.label}
                    </span>
                    {fact.value_number != null && (
                      <span className="font-mono text-xs tabular-nums text-ink-500">
                        {fact.value_number.toLocaleString()}
                      </span>
                    )}
                  </td>
                  <td className="py-3 pr-4">
                    {fact.located && fact.region ? (
                      <span className="inline-flex items-center gap-1.5 font-mono text-xs text-ink-900">
                        <MapPin className="h-3.5 w-3.5 text-ink-300" strokeWidth={1.8} />
                        Page {fact.region.page_number}
                      </span>
                    ) : (
                      <span className="text-xs text-ink-300">Not located</span>
                    )}
                  </td>
                  <td className="py-3 text-right">
                    {fact.match ? (
                      <span
                        title={MATCH_LABELS[fact.match]?.hint ?? fact.match}
                        className="chip border-line bg-mist text-ink-700"
                      >
                        {MATCH_LABELS[fact.match]?.label ?? fact.match}
                      </span>
                    ) : (
                      <span className="text-xs text-ink-300">None</span>
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
