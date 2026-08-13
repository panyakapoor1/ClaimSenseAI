/**
 * The masthead every workspace page opens with.
 *
 * Deliberately a server component: it animates with the CSS stamp rather than
 * Framer, so a page of server-rendered claim data does not need a client bundle
 * just to introduce itself.
 */
export default function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow: string;
  title: string;
  description?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <header className="stamp-in">
      <p className="eyebrow">{eyebrow}</p>

      <div className="mt-4 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <h1 className="display text-3xl text-ink-900 md:text-[2.5rem]">{title}</h1>
          {description && (
            <p className="mt-3 max-w-2xl leading-relaxed text-ink-700">{description}</p>
          )}
        </div>
        {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
      </div>

      <div className="rule mt-8" />
    </header>
  );
}
