'use client';

import { useRef, useState, useEffect } from 'react';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import { motion, AnimatePresence, useScroll, useSpring } from 'framer-motion';
import {
  ArrowRight,
  ArrowUpRight,
  ScanLine,
  ShieldCheck,
  MapPin,
  GitBranch,
  ListChecks,
  AlertTriangle,
} from 'lucide-react';

import Wordmark from '@/components/Wordmark';
import ThemeToggle from '@/components/ThemeToggle';
import {
  Reveal,
  Stagger,
  StaggerItem,
  DrawRule,
  Counter,
  WordReveal,
} from '@/components/Motion';

// WebGL cannot render on the server, and the stack is decorative. The page is
// complete without it, so it loads after the rest rather than blocking it.
const ClaimScene = dynamic(() => import('@/components/three/ClaimScene'), {
  ssr: false,
});

/* -------------------------------------------------------------------------- */

const SCALE = [
  { value: 23, label: 'tables' },
  { value: 25, label: 'endpoints' },
  { value: 147, label: 'backend tests' },
  { value: 5, label: 'migrations' },
];

const PIPELINE = [
  {
    step: '01',
    title: 'Ingest',
    body: 'Uploads are validated by magic bytes rather than filename, then stored as objects. The claim opens in a declared state machine.',
  },
  {
    step: '02',
    title: 'Parse',
    body: 'Text-layer extraction with an OCR fallback, so a scanned or photographed bill still parses. Pages that needed OCR are labelled. Recognised text can be wrong, and the reader should know.',
  },
  {
    step: '03',
    title: 'Locate',
    body: 'Every extracted value is found in the parsed word geometry and stored with a page and bounding box. The model is never asked for coordinates, because it would invent them.',
  },
  {
    step: '04',
    title: 'Retrieve',
    body: 'Dense embeddings for paraphrase, PostgreSQL full-text for exact references like clause 4.1, fused by reciprocal rank, then reranked by a cross-encoder.',
  },
  {
    step: '05',
    title: 'Adjudicate',
    body: 'Each line becomes approved, capped, rejected or needs-review. The cited clause number resolves back to a real passage id, so a fabricated citation resolves to nothing instead of looking plausible.',
  },
  {
    step: '06',
    title: 'Score',
    body: 'A deterministic rules engine: duplicate lines, room-rent breaches, service dates outside the stay, excluded items, evidence gaps. The score is never shown without the contributions that produced it.',
  },
  {
    step: '07',
    title: 'Review',
    body: 'A person agrees, overrides, escalates or opens an investigation. An override records what it overrode; the model’s verdict is preserved on the decision, not erased by it.',
  },
];

const CAPABILITIES = [
  {
    icon: ListChecks,
    title: 'Hybrid retrieval, reranked',
    body: 'Dense vectors catch the paraphrase, full-text catches the clause number. Reciprocal-rank fusion combines them; a cross-encoder reorders the survivors.',
  },
  {
    icon: ShieldCheck,
    title: 'Citations that resolve',
    body: 'The model cites a clause by number from the retrieved set. That number is resolved back to a real passage, so an invented citation resolves to nothing rather than reading as fact.',
  },
  {
    icon: MapPin,
    title: 'Evidence located on the page',
    body: 'Values carry a page and a bounding box from the parsed geometry. How a value matched is reported (exact phrase, numeric form, partial token) instead of a confidence percentage nobody calibrated.',
  },
  {
    icon: AlertTriangle,
    title: 'Risk, decomposed',
    body: 'A deterministic rules engine with stated weights, versioned as rules-v1. A number an analyst cannot interrogate is a number they either accept or ignore, and both are bad.',
  },
  {
    icon: GitBranch,
    title: 'A human stays in charge',
    body: 'Approve, reject, override, escalate, request evidence, confirm fraud. Every privileged action lands in an append-only audit table enforced by a database trigger.',
  },
  {
    icon: ScanLine,
    title: 'Event-driven and idempotent',
    body: 'Nothing polls. If extraction is still running when an audit is requested, the audit stands down and is enqueued on completion. Re-running a stage replaces its output rather than duplicating it.',
  },
];

const RETRIEVAL = [
  { config: 'dense-only (baseline)', recall: 0.952, p1: 0.786, mrr: 0.861, ms: 46 },
  { config: 'hybrid', recall: 0.976, p1: 0.81, mrr: 0.879, ms: 53 },
  { config: 'hybrid + rerank', recall: 1.0, p1: 0.905, mrr: 0.952, ms: 552, best: true },
];

const STACK = [
  {
    group: 'Backend',
    items: ['FastAPI', 'SQLAlchemy 2 · async', 'arq workers', 'Alembic'],
  },
  {
    group: 'Data',
    items: ['PostgreSQL 16', 'pgvector', 'Redis', 'MinIO'],
  },
  {
    group: 'Models',
    items: ['Groq · llama-3.3-70b', 'all-MiniLM-L6-v2', 'ms-marco cross-encoder'],
  },
  {
    group: 'Documents',
    items: ['pdfplumber', 'Tesseract OCR', 'word-geometry search'],
  },
  {
    group: 'Frontend',
    items: ['Next.js 16', 'Tailwind 4', 'Framer Motion', 'React Three Fiber'],
  },
  {
    group: 'Security',
    items: ['httpOnly sessions', 'bcrypt', 'four server-side roles', 'append-only audit'],
  },
];

const LIMITS = [
  {
    title: 'The rules-engine weights are chosen, not learned',
    body: 'A duplicate line is worth +26 because that is a stated policy, versioned and shown as such. No model was trained on claims data; there is none.',
  },
  {
    title: 'Retrieval numbers are small-sample',
    body: 'n=42 over a 24-clause policy, with questions and policy by the same author. That is characterisation, not a benchmark.',
  },
  {
    title: 'Finding confidence is the model’s own opinion',
    body: 'AuditFinding.confidence is a self-assessment and is not calibrated. It is labelled that way in the interface.',
  },
  {
    title: 'Contradiction detection is not implemented',
    body: 'The table exists and is empty. Finding a real contradiction needs cross-document comparison, and an empty table is better than invented rows.',
  },
];

/* -------------------------------------------------------------------------- */

function Preloader({ onDone }: { onDone: () => void }) {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const start = performance.now();
    const DURATION = 1100;
    let frame = 0;

    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / DURATION);
      // Eased so it decelerates into place instead of running out flat.
      setProgress(Math.round((1 - Math.pow(1 - t, 3)) * 100));
      if (t < 1) {
        frame = requestAnimationFrame(tick);
      } else {
        setTimeout(onDone, 180);
      }
    };

    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [onDone]);

  return (
    <motion.div
      className="fixed inset-0 z-[100] flex flex-col items-center justify-center bg-paper"
      exit={{ opacity: 0 }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
    >
      <Wordmark />
      <p className="eyebrow mt-5">Claims-integrity workstation</p>
      <div className="mt-7 h-px w-48 overflow-hidden bg-line">
        <div
          className="h-full bg-ink-900 origin-left transition-transform duration-100 ease-out"
          style={{ transform: `scaleX(${progress / 100})` }}
        />
      </div>
      <p className="mt-3 font-mono text-[0.6875rem] tabular-nums text-ink-300">
        {String(progress).padStart(3, '0')}
      </p>
    </motion.div>
  );
}

/* -------------------------------------------------------------------------- */

export default function LandingPage() {
  const [loading, setLoading] = useState(true);
  const pipelineRef = useRef<HTMLDivElement>(null);

  // Drives the vertical connector through the pipeline as the section scrolls.
  const { scrollYProgress } = useScroll({
    target: pipelineRef,
    offset: ['start 65%', 'end 75%'],
  });
  const trace = useSpring(scrollYProgress, { stiffness: 90, damping: 26, mass: 0.4 });

  return (
    <div className="min-h-screen bg-paper">
      <AnimatePresence>
        {loading && <Preloader onDone={() => setLoading(false)} />}
      </AnimatePresence>

      {/* ---------------------------------------------------------------- nav */}
      <header className="sticky top-0 z-50 border-b border-line bg-paper/90 backdrop-blur-sm">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Wordmark size="sm" />

          <nav className="hidden items-center gap-1 md:flex">
            {[
              ['Pipeline', '#pipeline'],
              ['Capabilities', '#capabilities'],
              ['Results', '#results'],
              ['Stack', '#stack'],
            ].map(([label, href]) => (
              <a
                key={href}
                href={href}
                className="px-3 py-2 text-sm text-ink-700 transition-colors hover:text-ink-900"
              >
                {label}
              </a>
            ))}
          </nav>

          <div className="flex items-center gap-2">
            <ThemeToggle />
            <Link href="/login" className="btn text-sm">
              Open the demo
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </header>

      {/* -------------------------------------------------------------- hero */}
      <section className="relative overflow-hidden border-b border-line">
        <div className="mx-auto grid max-w-6xl items-center gap-10 px-6 py-16 md:grid-cols-[1.05fr_1fr] md:py-24">
          <div>
            <motion.p
              className="eyebrow"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.15, duration: 0.6 }}
            >
              Health insurance · line-by-line adjudication
            </motion.p>

            <h1 className="display mt-5 text-[2.75rem] leading-[1.03] text-ink-900 md:text-6xl">
              <WordReveal text="Every rupee decided," delay={0.25} />
              <br />
              <WordReveal text="traced to a clause." delay={0.45} />
            </h1>

            <motion.p
              className="mt-6 max-w-lg text-lg leading-relaxed text-ink-700"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.7, duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
            >
              ClaimSense reads a hospital bill, adjudicates every line against the
              governing policy, scores the claim for risk, and shows its work:
              which clause, which page, which words.
            </motion.p>

            <motion.div
              className="mt-9 flex flex-wrap items-center gap-3"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.82, duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
            >
              <Link href="/login" className="btn">
                Open the demo
                <ArrowRight className="h-4 w-4" />
              </Link>
              <a href="#pipeline" className="btn-ghost">
                See how it works
              </a>
            </motion.div>

            <motion.p
              className="mt-8 max-w-md text-sm leading-relaxed text-ink-500"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 1, duration: 0.6 }}
            >
              Every number the interface shows is computed. There is no seeded
              analysis, no placeholder metric, and no confidence score that isn’t
              measuring something. Where the system doesn’t know, it says so.
            </motion.p>
          </div>

          {/* The stack of pages, being read. */}
          <motion.div
            className="relative h-[340px] md:h-[520px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.5, duration: 1.2 }}
          >
            <ClaimScene />
            <div className="pointer-events-none absolute bottom-0 left-0 right-0 flex justify-between border-t border-line pt-3">
              <span className="eyebrow">Bill · policy · verdict</span>
              <span className="eyebrow">Live scan</span>
            </div>
          </motion.div>
        </div>
      </section>

      {/* -------------------------------------------------------- scale strip */}
      <section className="border-b border-line bg-mist/50">
        <Stagger className="mx-auto grid max-w-6xl grid-cols-2 gap-px px-6 md:grid-cols-4">
          {SCALE.map((stat) => (
            <StaggerItem key={stat.label} className="py-8 md:py-10">
              <p className="display text-4xl text-ink-900 md:text-5xl">
                <Counter to={stat.value} />
              </p>
              <p className="eyebrow mt-2">{stat.label}</p>
            </StaggerItem>
          ))}
        </Stagger>
      </section>

      {/* ----------------------------------------------------------- problem */}
      <section className="border-b border-line">
        <div className="mx-auto max-w-6xl px-6 py-20 md:py-28">
          <Reveal>
            <p className="eyebrow">The problem</p>
            <DrawRule className="mt-4" />
          </Reveal>

          <div className="mt-10 grid gap-10 md:grid-cols-[1fr_1.1fr]">
            <Reveal>
              <h2 className="display text-3xl text-ink-900 md:text-[2.5rem]">
                Thirty line items.
                <br />
                Fifty pages of policy.
              </h2>
            </Reveal>

            <Reveal delay={0.1} className="space-y-5 text-lg leading-relaxed text-ink-700">
              <p>
                An Indian health-insurance claim arrives as a hospital bill and a
                policy document. Deciding what is payable means, for every line,
                finding the clause that governs it and applying it.
              </p>
              <p>
                That is slow, and it is where disputes come from: a room-rent cap
                applied to the wrong tariff, an excluded consumable paid by
                mistake, the same MRI billed twice.
              </p>
              <p className="text-ink-900">
                ClaimSense does that adjudication line by line, and every verdict
                it reaches can be opened up and checked against the page it came
                from.
              </p>
            </Reveal>
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------------- pipeline */}
      <section id="pipeline" className="border-b border-line bg-mist/40 scroll-mt-20">
        <div className="mx-auto max-w-6xl px-6 py-20 md:py-28">
          <Reveal>
            <p className="eyebrow">The pipeline</p>
            <DrawRule className="mt-4" />
            <h2 className="display mt-8 max-w-2xl text-3xl text-ink-900 md:text-[2.5rem]">
              Seven stages, each one idempotent.
            </h2>
            <p className="mt-5 max-w-xl text-lg leading-relaxed text-ink-700">
              Stages are event-driven. Nothing polls, every transition is declared
              in a state machine, and re-running any stage replaces its output
              rather than duplicating it.
            </p>
          </Reveal>

          <div ref={pipelineRef} className="relative mt-16 pl-8 md:pl-0">
            {/* The trace, drawn by scroll position. */}
            <div className="absolute left-[3px] top-2 bottom-2 w-px bg-line md:left-[calc(6rem+3px)]">
              <motion.div
                className="h-full w-full origin-top bg-ink-900"
                style={{ scaleY: trace }}
              />
            </div>

            <div className="space-y-12 md:space-y-14">
              {PIPELINE.map((stage) => (
                <Reveal key={stage.step}>
                  <div className="relative md:grid md:grid-cols-[6rem_1fr] md:gap-10">
                    <div className="md:text-right md:pr-0">
                      <span className="font-mono text-xs tabular-nums text-ink-500">
                        {stage.step}
                      </span>
                    </div>

                    {/* The node sits on the trace. */}
                    <span className="absolute -left-8 top-1.5 h-[7px] w-[7px] bg-ink-900 md:left-[calc(6rem+3px)] md:-translate-x-1/2" />

                    <div className="mt-1 md:mt-0 md:pl-8">
                      <h3 className="text-xl font-semibold text-ink-900">
                        {stage.title}
                      </h3>
                      <p className="mt-2 max-w-2xl leading-relaxed text-ink-700">
                        {stage.body}
                      </p>
                    </div>
                  </div>
                </Reveal>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------ capabilities */}
      <section id="capabilities" className="border-b border-line scroll-mt-20">
        <div className="mx-auto max-w-6xl px-6 py-20 md:py-28">
          <Reveal>
            <p className="eyebrow">What it does</p>
            <DrawRule className="mt-4" />
          </Reveal>

          <Stagger className="mt-12 grid gap-px bg-line sm:grid-cols-2 lg:grid-cols-3">
            {CAPABILITIES.map(({ icon: Icon, title, body }) => (
              <StaggerItem key={title} className="group bg-paper">
                <div className="h-full p-7 transition-colors hover:bg-surface">
                  <Icon
                    className="h-6 w-6 text-ink-900 transition-transform duration-500 group-hover:-translate-y-0.5"
                    strokeWidth={1.5}
                  />
                  <h3 className="mt-6 text-lg font-semibold leading-snug text-ink-900">
                    {title}
                  </h3>
                  <p className="mt-3 text-sm leading-relaxed text-ink-700">{body}</p>
                </div>
              </StaggerItem>
            ))}
          </Stagger>
        </div>
      </section>

      {/* ----------------------------------------------------------- results */}
      <section id="results" className="border-b border-line bg-rail scroll-mt-20">
        <div className="mx-auto max-w-6xl px-6 py-20 md:py-28">
          <Reveal>
            <p className="eyebrow eyebrow-invert">Measured results</p>
            <div className="mt-4 h-px bg-rail-line" />
            <h2 className="display mt-8 max-w-2xl text-3xl text-white md:text-[2.5rem]">
              Retrieval, measured rather than asserted.
            </h2>
            <p className="mt-5 max-w-xl leading-relaxed text-rail-text">
              42 labelled questions against a 24-clause policy, top_k=5. Reranking
              costs an order of magnitude in latency and buys the last 5% of
              recall, a trade worth stating rather than hiding.
            </p>
          </Reveal>

          <div className="mt-14 space-y-8">
            {RETRIEVAL.map((row, i) => (
              <Reveal key={row.config} delay={i * 0.08}>
                <div className="grid gap-4 border-t border-rail-line pt-6 md:grid-cols-[1fr_2fr]">
                  <div>
                    <p
                      className={
                        row.best
                          ? 'font-mono text-sm text-white'
                          : 'font-mono text-sm text-rail-text'
                      }
                    >
                      {row.config}
                    </p>
                    <p className="mt-1 font-mono text-xs tabular-nums text-rail-dim">
                      median {row.ms} ms
                    </p>
                  </div>

                  <div className="grid grid-cols-3 gap-6">
                    {[
                      ['recall@5', row.recall],
                      ['P@1', row.p1],
                      ['MRR', row.mrr],
                    ].map(([label, value], j) => (
                      <div key={label as string}>
                        <div className="flex items-baseline justify-between gap-2">
                          <span className="eyebrow eyebrow-invert">{label}</span>
                          <span
                            className={`font-mono text-sm tabular-nums ${
                              row.best ? 'text-white' : 'text-rail-text'
                            }`}
                          >
                            <Counter to={value as number} decimals={3} />
                          </span>
                        </div>
                        <div className="mt-2 h-1.5 w-full overflow-hidden bg-rail-raised">
                          <motion.div
                            className={`h-full origin-left ${
                              row.best ? 'bg-white' : 'bg-rail-dim'
                            }`}
                            initial={{ scaleX: 0 }}
                            whileInView={{ scaleX: value as number }}
                            viewport={{ once: true, margin: '-10% 0px' }}
                            transition={{
                              duration: 0.9,
                              delay: 0.1 + j * 0.08,
                              ease: [0.16, 1, 0.3, 1],
                            }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </Reveal>
            ))}
          </div>

          <Reveal delay={0.1}>
            <p className="mt-10 max-w-2xl text-sm leading-relaxed text-rail-dim">
              Reproduce with{' '}
              <code className="font-mono text-rail-text">
                python evaluation/run_retrieval_eval.py
              </code>
              . n=42 on a small, self-authored corpus is characterisation, not a
              benchmark. The method and its limits are written down in
              docs/EVALUATION.md.
            </p>
          </Reveal>
        </div>
      </section>

      {/* ------------------------------------------------------------- stack */}
      <section id="stack" className="border-b border-line scroll-mt-20">
        <div className="mx-auto max-w-6xl px-6 py-20 md:py-28">
          <Reveal>
            <p className="eyebrow">Built with</p>
            <DrawRule className="mt-4" />
            <h2 className="display mt-8 max-w-2xl text-3xl text-ink-900 md:text-[2.5rem]">
              Routes do HTTP. Services hold the logic.
            </h2>
            <p className="mt-5 max-w-xl text-lg leading-relaxed text-ink-700">
              Services import no web framework, and the worker imports the same
              services, so the seed script and the API run identical code.
            </p>
          </Reveal>

          <Stagger className="mt-12 grid gap-x-10 gap-y-10 sm:grid-cols-2 lg:grid-cols-3">
            {STACK.map((column) => (
              <StaggerItem key={column.group}>
                <p className="eyebrow">{column.group}</p>
                <div className="mt-3 h-px bg-line" />
                <ul className="mt-4 space-y-2">
                  {column.items.map((item) => (
                    <li key={item} className="font-mono text-sm text-ink-700">
                      {item}
                    </li>
                  ))}
                </ul>
              </StaggerItem>
            ))}
          </Stagger>
        </div>
      </section>

      {/* ------------------------------------------------------------ limits */}
      <section className="border-b border-line bg-mist/40">
        <div className="mx-auto max-w-6xl px-6 py-20 md:py-28">
          <Reveal>
            <p className="eyebrow">What it does not do</p>
            <DrawRule className="mt-4" />
            <h2 className="display mt-8 max-w-2xl text-3xl text-ink-900 md:text-[2.5rem]">
              Stated plainly.
            </h2>
            <p className="mt-5 max-w-xl text-lg leading-relaxed text-ink-700">
              A system that hides its limits is harder to trust than one that names
              them.
            </p>
          </Reveal>

          <Stagger className="mt-12 grid gap-x-12 gap-y-8 md:grid-cols-2">
            {LIMITS.map((limit) => (
              <StaggerItem key={limit.title}>
                <div className="border-l-2 border-line-strong pl-5">
                  <h3 className="font-semibold text-ink-900">{limit.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-ink-700">
                    {limit.body}
                  </p>
                </div>
              </StaggerItem>
            ))}
          </Stagger>
        </div>
      </section>

      {/* --------------------------------------------------------------- cta */}
      <section className="border-b border-line">
        <div className="mx-auto max-w-6xl px-6 py-24 text-center md:py-32">
          <Reveal>
            <h2 className="display mx-auto max-w-2xl text-4xl text-ink-900 md:text-5xl">
              Run it on a bill and read the reasoning.
            </h2>
            <p className="mx-auto mt-6 max-w-lg text-lg leading-relaxed text-ink-700">
              Four demo accounts, one per role. The permissions are enforced by the
              server, so an auditor really cannot decide a claim.
            </p>
            <div className="mt-10 flex flex-wrap justify-center gap-3">
              <Link href="/login" className="btn">
                Open the demo
                <ArrowRight className="h-4 w-4" />
              </Link>
              <a
                href="https://github.com/panyakapoor1/ClaimSenseAI"
                target="_blank"
                rel="noreferrer"
                className="btn-ghost"
              >
                Read the source
                <ArrowUpRight className="h-4 w-4" />
              </a>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ------------------------------------------------------------ footer */}
      <footer className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-6 px-6 py-10 sm:flex-row sm:items-center">
        <Wordmark size="sm" />
        <p className="max-w-md text-xs leading-relaxed text-ink-500">
          Demo environment. The accounts are real and the credentials are public
          because it is a demo. Do not upload real patient data.
        </p>
      </footer>
    </div>
  );
}
